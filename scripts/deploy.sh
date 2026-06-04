#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SERVER="root@192.168.50.5" # Your docker server
REMOTE_DIR="/root/spiir-alternative"

cd "$ROOT_DIR"

if [[ "${SKIP_CHECKS:-0}" != "1" ]]; then
    ./scripts/check.sh
fi

echo "Deploying spiir-alternative to $SERVER..."

# Ensure the remote directory exists
ssh $SERVER "mkdir -p $REMOTE_DIR"

# Rsync the runnable codebase to the server, excluding local docs, caches, secrets, and generated data.
rsync -avz \
    --exclude 'node_modules' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '.agent/' \
    --exclude '.codex/' \
    --exclude 'data/' \
    --exclude 'dist/' \
    --exclude '.env' \
    --exclude '*.pem' \
    --exclude '.git' \
    --exclude 'spiir-scrape/' \
    ./ $SERVER:$REMOTE_DIR/

# Trigger a rebuild and restart on the remote server
ssh $SERVER "cd $REMOTE_DIR && docker compose build && docker compose up -d"

echo "Deployment complete!"
