#!/usr/bin/env bash
# Build frontend assets then (re)build and start the full stack.
# Usage: ./build.sh [docker compose args]
set -euo pipefail

echo "==> Building frontend..."
(cd ai-frontend && npm ci && npm run build && npm run copy-to-static)

echo "==> Starting stack..."
docker compose up --build "$@"
