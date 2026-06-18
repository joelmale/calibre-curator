FROM ghcr.io/crocodilestick/calibre-web-automated:v4.0.6

# NOTE: requests is already provided by CWA's bundled cps dependencies.
# The old /lsiopy/bin/pip line was removed — it targeted the linuxserver venv
# which does not exist in this image. Verify at build time that `import requests`
# succeeds inside the CWA Python env if you see ImportError.

# Copy bridge module and compiled frontend assets
COPY cps/ai_bridge.py /app/calibre-web-automated/cps/ai_bridge.py
COPY cps/templates/ai_dashboard.html /app/calibre-web-automated/cps/templates/ai_dashboard.html
COPY cps/templates/ai_scrub.html /app/calibre-web-automated/cps/templates/ai_scrub.html
COPY cps/templates/_ai_nav.html /app/calibre-web-automated/cps/templates/_ai_nav.html
COPY cps/templates/ai_enrichment.html /app/calibre-web-automated/cps/templates/ai_enrichment.html
COPY cps/templates/ai_providers.html /app/calibre-web-automated/cps/templates/ai_providers.html
COPY cps/static/ai/ /app/calibre-web-automated/cps/static/ai/

# Patch main.py: +2 lines (import + register blueprint)
COPY patch_main.py /tmp/patch_main.py
RUN python3 /tmp/patch_main.py /app/calibre-web-automated/cps/main.py && rm /tmp/patch_main.py

# Patch layout.html: +1 nav entry
COPY patch_layout.py /tmp/patch_layout.py
RUN python3 /tmp/patch_layout.py /app/calibre-web-automated/cps/templates/layout.html && rm /tmp/patch_layout.py
