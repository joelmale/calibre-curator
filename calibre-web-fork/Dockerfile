FROM lscr.io/linuxserver/calibre-web:latest

# requests is needed by ai_bridge.py for the internal proxy.
# Must install into the lsiopy venv that calibre-web runs in, not system Python.
RUN /lsiopy/bin/pip install --no-cache-dir requests

# Copy bridge module and compiled frontend assets
COPY cps/ai_bridge.py /app/calibre-web/cps/ai_bridge.py
COPY cps/templates/ai_dashboard.html /app/calibre-web/cps/templates/ai_dashboard.html
COPY cps/templates/ai_scrub.html /app/calibre-web/cps/templates/ai_scrub.html
COPY cps/templates/_ai_nav.html /app/calibre-web/cps/templates/_ai_nav.html
COPY cps/templates/ai_enrichment.html /app/calibre-web/cps/templates/ai_enrichment.html
COPY cps/templates/ai_duplicates.html /app/calibre-web/cps/templates/ai_duplicates.html
COPY cps/static/ai/ /app/calibre-web/cps/static/ai/

# Patch main.py: +2 lines (import + register blueprint)
COPY patch_main.py /tmp/patch_main.py
RUN python /tmp/patch_main.py /app/calibre-web/cps/main.py && rm /tmp/patch_main.py

# Patch layout.html: +1 nav entry
COPY patch_layout.py /tmp/patch_layout.py
RUN python /tmp/patch_layout.py /app/calibre-web/cps/templates/layout.html && rm /tmp/patch_layout.py
