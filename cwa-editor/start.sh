#!/usr/bin/env bash
set -e

# Run calibre-debug worker in the background
echo "Starting Calibre-debug Polish worker on 127.0.0.1:8092..."
/app/calibre/calibre-debug /app/cwa-editor/editor/worker.py &

# Start Flask API
echo "Starting Flask API server..."
export FLASK_APP=/app/cwa-editor/editor/server.py
export FLASK_RUN_HOST=0.0.0.0
export FLASK_RUN_PORT=8091
export FLASK_DEBUG=1
exec python3 -m flask run
