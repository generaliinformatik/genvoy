#! /usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Generali AG, Rene Fuehrer <rene.fuehrer@generali.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

#import sys
import time
#import uuid
from sys import stderr, hexversion
import logging
from ipaddress import ip_address, ip_network

import hmac
#from hashlib import sha1

import json
from json import loads, dumps

from subprocess import Popen, PIPE
from tempfile import mkstemp

import os
from os import access, X_OK, remove, fdopen
from os.path import isfile, abspath, normpath, dirname, join, basename

import requests
from flask import Flask, request, abort

logging.basicConfig(stream=stderr, level=logging.INFO)

app = Flask(__name__)
@app.route('/', methods=['GET', 'POST'])


def index():
    """
    Main WSGI application entry.
    """
    app_path = os.path.dirname(os.path.abspath(__file__))
    path = normpath(abspath(dirname(__file__)))

    with open(join(path, 'config.json'), 'r') as cfg:
        config = loads(cfg.read())
        cfg.close()

    # Only POST is implemented
    if request.method != 'POST':
        abort(501)

    hooks = config.get('hooks_path', join(path, 'hooks'))
    logging.debug("webhook: hooks path: %s", hooks)
    # Allow Github IPs only
    logging.debug("webhook: check valid IPs")

    # get ip address of requester
    src_ip = ip_address(
        u'{}'.format(request.access_route[0])  # Fix stupid ipaddress issue
    )

    if config.get('github_ips_only', True):
        whitelist = requests.get('https://api.github.com/meta').json()['hooks']

        for valid_ip in whitelist:
            if src_ip in ip_network(valid_ip):
                break
        else:
            # pylint: disable=logging-format-interpolation
            logging.error('IP {} not allowed'.format(src_ip))
            abort(403)

    # Enforce secret
    logging.debug("webhook: check secret")
    secret = config.get('enforce_secret', '')
    if secret:
        # change type of secret
        secret = bytes(secret, 'utf-8')
        # Only SHA1 is supported
        header_signature = request.headers.get('X-Hub-Signature')
        if header_signature is None:
            logging.error("webhook: secret check failed, header mandantory")
            abort(403)

        sha_name, signature = header_signature.split('=')
        if sha_name != 'sha1':
            logging.error("webhook: secret check failed, sha1 mandantory")
            abort(501)

        # HMAC requires the key to be bytes, but data is string
        mac = hmac.new(secret, msg=request.data, digestmod='sha1')

        # Python prior to 2.7.7 does not have hmac.compare_digest
        if hexversion >= 0x020707F0:
            if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
                logging.warning("webhook: secret check failed, ip=%s", src_ip)
                abort(403)
        else:
            # What compare_digest provides is protection against timing
            # attacks; we can live without this protection for a web-based
            # application
            if str(mac.hexdigest()) != str(signature):
                logging.warning("webhook: secret check failed, ip=%s", src_ip)
                abort(403)

    # Implement ping
    event = request.headers.get('X-GitHub-Event', 'ping')
    logging.debug("webhook: event type = %s", event)
    if event == 'ping':
        return dumps({'msg': 'pong'})

    # Gather data
    try:
        payload = request.get_json()
    except Exception:
        logging.warning('Request parsing failed')
        abort(400)

    # Determining the branch is tricky, as it only appears for certain event
    # types an at different levels
    logging.debug("webhook: check branch")
    branch = None
    try:
        # backup evenry json
        backup_path = config.get('backup_path', "")
        logging.debug("webhook: backup path = %s", backup_path)
        if os.path.exists(backup_path):
            # pylint: disable=line-too-long
            backup_file = config.get('backup_path', path)+'/'+ \
                time.strftime("%Y%m%d-%H%M%S")+'-'+event+'.json'

            logging.debug("webhook: backup file = %s", backup_file)
            with open(backup_file, 'w') as this_payloadexport:
                json.dump(payload, this_payloadexport)
                this_payloadexport.close()

        else:
            logging.info("webhook: backup path not given or invalid, no backup created.")

        # Case 1: a ref_type indicates the type of ref.
        # This true for create and delete events.
        if 'ref_type' in payload:
            if payload['ref_type'] == 'branch':
                branch = payload['ref']

        # Case 2: a pull_request object is involved. This is pull_request and
        # pull_request_review_comment events.
        elif 'pull_request' in payload:
            # This is the TARGET branch for the pull-request, not the source
            # branch
            branch = payload['pull_request']['base']['ref']

        elif event in ['push']:
            # Push events provide a full Git ref in 'ref' and not a 'ref_type'.
            branch = payload['ref'].split('/', 2)[2]

    except KeyError:
        # If the payload structure isn't what we expect, we'll live without
        # the branch name
        pass

    # All current events have a repository, but some legacy events do not,
    # so let's be safe
    name = payload['repository']['name'] if 'repository' in payload else None

    meta = {
        'name': name,
        'branch': branch,
        'event': event
    }
    # pylint: disable=logging-format-interpolation
    logging.info('Metadata:\n{}'.format(dumps(meta)))

    # Skip push-delete
    if event == 'push' and payload['deleted']:
        # pylint: disable=logging-format-interpolation
        logging.info('Skipping push-delete event for {}'.format(dumps(meta)))
        return dumps({'status': 'skipped'})

    # Possible hooks
    scripts = []
    if branch and name:
        scripts.append(join(hooks, '{event}-{name}-{branch}'.format(**meta)))
        scripts.append(join(hooks, 'all-{name}-{branch}'.format(**meta)))
    if name:
        scripts.append(join(hooks, '{event}-{name}'.format(**meta)))
        scripts.append(join(hooks, 'all-{name}'.format(**meta)))
        #print("Script added: %s" % (join(hooks, '{event}-{name}'.format(**meta))))
    scripts.append(join(hooks, '{event}'.format(**meta)))
    scripts.append(join(hooks, 'all'))

    # Check permissions
    scripts = [s for s in scripts if isfile(s) and access(s, X_OK)]
    if not scripts:
        return dumps({'status': 'nop'})

    # Save payload to temporal file
    osfd, tmpfile = mkstemp()
    with fdopen(osfd, 'w') as this_payloadfile:
        this_payloadfile.write(dumps(payload))
        this_payloadfile.close()

    # Run scripts
    ran = {}
    for this_script in scripts:

        this_script = app_path+"/"+this_script
        logging.info("try to execute hook : %s", this_script)

        proc = Popen(
            [this_script, tmpfile, event],
            stdout=PIPE, stderr=PIPE
        )
        stdout, stderr = proc.communicate()

        ran[basename(this_script)] = {
            'returncode': proc.returncode,
            'stdout': stdout.decode('utf-8'),
            'stderr': stderr.decode('utf-8'),
        }

        # Log errors if a hook failed
        if proc.returncode != 0:
            # pylint: disable=logging-too-many-args
            logging.error('{} : {} \n{}', format(
                this_script, proc.returncode, stderr
            ))

    # Remove temporal file
    remove(tmpfile)

    info = config.get('return_scripts_info', False)
    if not info:
        return dumps({'status': 'done'})

    output = dumps(ran, sort_keys=True, indent=4)
    logging.info(output)
    return output


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
