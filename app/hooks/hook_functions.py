#!/usr/bin/env python3
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

import logging
import re

class DictQuery(dict):
    '''
    Dictionary class to get JSON hierarchical data structures

    Parameters:
        dict (dict): Dictionary with hierachical structures

    Returns:
        val (dict): Dictionary where hierachical structured keys be seperated with slashes
    '''
    def get(self, path, default=None):
        keys = path.split("/")
        val = None

        for key in keys:
            if val:
                if isinstance(val, list):
                    val = [v.get(key, default) if v else None for v in val]
                else:
                    val = val.get(key, default)
            else:
                val = dict.get(self, key, default)

            if not val:
                break

        return val

def replace_all_placeholders(messagetext, payload_dict, eventtype):
    '''
        Function to replace placeholders with hierarchical data structures.

        Parameters:
            messagetext (str): original text with placeholders
            payload_dict (dict): Python dictionary with content to be inserted
            eventtype (str): event type to replace {event} placeholder

        Returns:
            messagetext (str): Text with replaced placeholders
    '''
    placeholders = ""
    placeholders = re.findall(r"{(.*?)}", messagetext)
    messagetext = messagetext.replace("{event}", str(eventtype))

    for placeholder_key in placeholders:
        if placeholder_key not in ("payload_text", "payload_table_html", "payload_table_md"):
            # replace all placeholders; default ist empty string to prevent orphan placeholders
            placeholder_value = DictQuery(payload_dict).get(placeholder_key, "")
            messagetext = messagetext.replace("{"+placeholder_key+"}", str(placeholder_value))
            logging.debug("replace placeholder: %s => %s", placeholder_key, placeholder_value)
    return messagetext

def flatten_json(payload_dict):
    '''
        Flatten a multi-hierarchy Python dictionary to a single-hierachy dict.

        Parameters:
            payload_dict (dict): The Python multi-hierarchy dictionary which is to be flatten to one hierarchy.

        Returns:
            out (dict): The flatten Python dict as a single-hierarchy Python dict. 
    '''
    out = {}
    def flatten(x, name=''):
        # If the Nested key-value
        # pair is of dict type
        if type(x) is dict:
            for a in x:
                flatten(x[a], name + a + '/')
        # If the Nested key-value
        # pair is of list type
        elif type(x) is list:
            i = 0
            for a in x:
                flatten(a, name + str(i) + '/')
                i += 1
        else:
            out[name[:-1]] = x
    flatten(payload_dict)
    return out

def flatten_json_text(payload_dict):
    '''
        Prepare output of a flatten dict to text.

        Parameters:
            payload_dict (dict): Multi-hierarchy dictionary which is to be output as text.

        Returns:
            ret (dict): Flatten (single hierachy) dict as text
    '''
    ret = ''
    data = flatten_json(payload_dict)
    for key, value in data.items():
        ret = ret+("{:40s} => {}\n".format("{"+str(key)+"}", str(value)))
    return ret

def flatten_json_table_html(payload_dict):
    '''
        Prepare output of a flatten Python dict to html table.

        Parameters:
            payload_dict (dict): Multi-hierarchy dictionary which is to be output as html table.

        Returns:
            ret (dict): Flatten (single hierachy) dict as html table
    '''
    data = flatten_json(payload_dict)
    ret = "<table class=blueTable><tr><td><b>key</b></td><td><b>value</b></td></tr>"
    for key, value in data.items():
        ret = ret+("<tr><td>{}</td><td>{}</td></tr>\n".format("{"+str(key)+"}", str(value)))
    ret = ret + "</table>"
    return ret

def flatten_json_table_md(payload_dict):
    '''
        Prepare output of a flatten Python dict to markdown table.

        Parameters:
            payload_dict (dict): Multi-hierarchy dictionary which is to be output as markdown table.

        Returns:
            ret (dict): Flatten (single hierachy) dict as markdown table
    '''
    data = flatten_json(payload_dict)
    ret = "| key | value |"
    ret = ret + "| :-- | :-- |"
    for key, value in data.items():
        ret = ret+("| {} | {} |\n".format("{"+str(key)+"}", str(value)))
    return ret
