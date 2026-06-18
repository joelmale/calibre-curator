#!/usr/bin/env bash
# Rebuild and restart ONLY the ai-sidecar service.
#
# calibre-web is slow to rebuild (CWA base image is large) and rarely changes,
# so skip it while iterating on the sidecar.
# The sidecar is a plain python:3.12-slim image and needs no frontend build.
#
# Run this on the Docker host where the stack lives (the same place
# `docker compose` for this project runs).
#
# Usage:
#   scripts/deploy-sidecar.sh           # build + restart ai-sidecar only
#   scripts/deploy-sidecar.sh --pull    # git pull --ff-only first
#   scripts/deploy-sidecar.sh --logs    # follow sidecar logs after restart
#   scripts/deploy-sidecar.sh --pull --logs
set -euo pipefail
cd "$(dirname "$0")/.."

PULL=0
LOGS=0
for arg in "$@"; do
  case "$arg" in
    --pull) PULL=1 ;;
    --logs) LOGS=1 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [ "$PULL" -eq 1 ]; then
  echo "==> git pull --ff-only"
  git pull --ff-only
fi

echo "==> Building ai-sidecar image (calibre-web untouched)..."
docker compose build ai-sidecar

echo "==> Recreating ai-sidecar container..."
# --no-deps: never touch linked services (belt-and-suspenders; there is no
# depends_on between calibre-web and ai-sidecar today).
docker compose up -d --no-deps ai-sidecar

docker compose ps ai-sidecar

if [ "$LOGS" -eq 1 ]; then
  echo "==> Following ai-sidecar logs (Ctrl-C to stop)..."
  docker compose logs -f ai-sidecar
fi
