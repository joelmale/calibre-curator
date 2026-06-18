#!/usr/bin/env bash
# Build frontend assets then (re)build and start the full stack.
# Usage: ./build.sh [docker compose args]
#
# Iterating on the sidecar only? Skip the slow calibre-web rebuild with:
#   scripts/deploy-sidecar.sh
set -euo pipefail

echo "==> Building frontend..."
(cd ai-frontend && npm ci && npm run build && npm run copy-to-static)

echo "==> Starting stack..."
docker compose up --build "$@"
