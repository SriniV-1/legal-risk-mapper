#!/usr/bin/env bash
# Run this after SSH-ing into your EC2 instance.
# Assumes you've already written .env in the repo directory.
# Usage: bash deploy/start-app.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"

cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example to .env and fill in values."
  exit 1
fi

echo "Building Docker image..."
docker build -t legal-risk-mapper .

echo "Stopping previous container (if any)..."
docker rm -f lrm-backend 2>/dev/null || true

echo "Starting container..."
docker run -d \
  --name lrm-backend \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  legal-risk-mapper

echo ""
echo "Container started. Check status:"
echo "  docker logs -f lrm-backend"
echo "  curl http://localhost:8000/health"
