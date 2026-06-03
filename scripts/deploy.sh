#!/bin/bash
set -e

SERVER="root@192.168.50.5" # Your docker server
REMOTE_DIR="/root/spiir-alternative"

echo "Deploying spiir-alternative to $SERVER..."

# Ensure the remote directory exists
ssh $SERVER "mkdir -p $REMOTE_DIR"

# Rsync the codebase to the server, excluding node_modules, python caches, and local data
rsync -avz --exclude 'node_modules' --exclude '.venv' --exclude '__pycache__' --exclude 'data/' --exclude '.git' ./ $SERVER:$REMOTE_DIR/

# Trigger a rebuild and restart on the remote server
ssh $SERVER "cd $REMOTE_DIR && docker compose build && docker compose up -d"

echo "Deployment complete!"
