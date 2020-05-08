#!/bin/bash

DOCKER_NAME="webhooks"
DOCKER_TAG="latest"

DDIR_BASE="/opt/repo/app"
LDIR_BASE="/Users/rnb/Desktop/webhooks"

DDIR_BACKUP="$DDIR_BASE/backup.jsons"
LDIR_BACKUP="$LDIR_BASE/backup.jsons"

DDIR_CLONE="$DDIR_BASE/backup.git"
LDIR_CLONE="$LDIR_BASE/backup.git"

DDIR_HOOKS="$DDIR_BASE/hooks"
LDIR_HOOKS="$LDIR_BASE/hooks"

mkdir -p "$LDIR_BACKUP"
mkdir -p "$LDIR_CLONE"
mkdir -p "$LDIR_HOOKS"

docker build --pull -f ./Dockerfile -t $DOCKER_NAME:$DOCKER_TAG .

echo "###################################################"
echo "##### "
echo "##### Directories"
echo "##### Base      : $LDIR_BASE"
echo "##### Backup    : $LDIR_BACKUP"
echo "##### Clone     : $LDIR_CLONE"
echo "##### Hooks     : $LDIR_HOOKS"
echo "#####"
echo "##### Starting Docker Container $DOCKER_NAME:$DOCKER_TAG as service..."
echo "#####"
echo "###################################################"

#docker run -d -p 5000:5000 -u 112233 -v "$LDIR_BACKUP":"$DDIR_BACKUP" -v "$LDIR_CLONE":"$DDIR_CLONE" -v "$LDIR_HOOKS":"$DDIR_HOOKS" $DOCKER_NAME:$DOCKER_TAG
docker run -d -p 5000:5000 -v "$LDIR_BACKUP":"$DDIR_BACKUP" -v "$LDIR_CLONE":"$DDIR_CLONE" -v "$LDIR_HOOKS":"$DDIR_HOOKS" $DOCKER_NAME:$DOCKER_TAG