#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

SERVER="${SERVER:-root@192.168.50.5}" # Your docker server
REMOTE_DIR="${REMOTE_DIR:-/root/peng}"

cd "$ROOT_DIR"

if [[ "${SKIP_CHECKS:-0}" != "1" ]]; then
    ./scripts/check.sh "$@"
fi

echo "Deploying spiir-alternative to $SERVER..."

# Ensure the remote directory exists
ssh -T $SERVER "mkdir -p $REMOTE_DIR"

# Rsync the runnable codebase to the server, excluding local docs, caches, secrets, and generated data.
rsync -avz --delete \
    --exclude 'node_modules' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '.agent/' \
    --exclude '.codex/' \
    --exclude 'data/' \
    --exclude 'private_data/' \
    --exclude 'dist/' \
    --exclude '.env' \
    --exclude '*.pem' \
    --exclude '.git' \
    --exclude 'spiir-scrape/' \
    ./ $SERVER:$REMOTE_DIR/

# Trigger a rebuild and restart on the remote server
echo "Executing remote deployment steps on $SERVER..."
ssh -T $SERVER "cd $REMOTE_DIR && mkdir -p data && chown -R 1000:1000 data && chmod -R u+rwX data && docker compose up --build -d --remove-orphans && docker image prune -f && echo 'Deployment successful!'"

