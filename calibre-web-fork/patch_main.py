#!/usr/bin/env python3
"""Idempotent two-line patch for Calibre-Web's cps/main.py.

Adds the ai_bridge Blueprint import and registration alongside the existing
web blueprint, so the fork diff on main.py stays at exactly two lines.
"""
import sys

IMPORT_ANCHOR = "from .web import web"
REGISTER_ANCHOR = "app.register_blueprint(web)"
IMPORT_LINE = "from .ai_bridge import ai_bridge"
REGISTER_LINE = "app.register_blueprint(ai_bridge)"

path = sys.argv[1]
with open(path) as f:
    src = f.read()

if IMPORT_LINE in src:
    print(f"Already patched: {path}")
    sys.exit(0)

if IMPORT_ANCHOR not in src:
    sys.exit(
        f"ERROR: anchor '{IMPORT_ANCHOR}' not found in {path}. "
        "Upstream main.py may have changed — update IMPORT_ANCHOR."
    )
if REGISTER_ANCHOR not in src:
    sys.exit(
        f"ERROR: anchor '{REGISTER_ANCHOR}' not found in {path}. "
        "Upstream main.py may have changed — update REGISTER_ANCHOR."
    )

src = src.replace(IMPORT_ANCHOR, f"{IMPORT_ANCHOR}\n{IMPORT_LINE}", 1)
src = src.replace(REGISTER_ANCHOR, f"{REGISTER_ANCHOR}\n{REGISTER_LINE}", 1)

with open(path, "w") as f:
    f.write(src)

print(f"Patched {path} successfully.")
