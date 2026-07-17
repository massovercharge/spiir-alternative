#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SERVER="root@192.168.50.5" # Your docker server
REMOTE_DIR="/root/peng"

cd "$ROOT_DIR"

if [[ "${SKIP_CHECKS:-0}" != "1" ]]; then
    ./scripts/check.sh
fi

echo "Deploying spiir-alternative to $SERVER..."

# Ensure the remote directory exists
ssh $SERVER "mkdir -p $REMOTE_DIR"

# Rsync the runnable codebase to the server, excluding local docs, caches, secrets, and generated data.
rsync -avz --delete \
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
echo "Executing remote deployment steps..."
ssh $SERVER << EOF
  set -e
  echo "Navigating to remote directory..."
  cd $REMOTE_DIR

  echo "Rebuilding and starting the new container stack..."
  docker compose up --build -d --remove-orphans

  echo "Cleaning up dangling images to prevent disk-bloat..."
  docker image prune -f

  echo "Deployment successful!"
EOF
