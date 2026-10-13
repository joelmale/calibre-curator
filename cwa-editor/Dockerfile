FROM ghcr.io/crocodilestick/calibre-web-automated:v4.0.6

# We use the system Python 3 to run the Flask API Server.
# The calibre-debug python will run the JSON-RPC worker.
RUN apt-get update && apt-get install -y python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/*

# Set up a venv for the flask server
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy editor requirements
COPY requirements.txt /app/cwa-editor/requirements.txt
RUN pip3 install --no-cache-dir -r /app/cwa-editor/requirements.txt

# Copy editor application code
COPY editor /app/cwa-editor/editor
COPY start.sh /app/cwa-editor/start.sh
RUN chmod +x /app/cwa-editor/start.sh

WORKDIR /app/cwa-editor

# The flask app will listen on 8091
EXPOSE 8091

# Replace the base image's healthcheck (which probes :8083, not served here).
# No -f: any HTTP response (even a 404) means Flask is up.
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD curl -s -o /dev/null http://localhost:8091/ || exit 1

# Override the base image's entrypoint to run our start script
ENTRYPOINT ["/app/cwa-editor/start.sh"]
