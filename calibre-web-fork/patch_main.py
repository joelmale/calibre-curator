#!/usr/bin/env python3
"""Idempotent two-line patch for Calibre-Web's cps/main.py.

Adds the ai_bridge Blueprint import and registration alongside the existing
web blueprint, preserving whatever indentation the anchor lines use so the
patch works regardless of whether the imports are at module level or inside
a block (the linuxserver image has changed this between versions).
"""
import sys

IMPORT_ANCHOR = "from .web import web"
REGISTER_ANCHOR = "app.register_blueprint(web)"
IMPORT_LINE = "from .ai_bridge import ai_bridge"
REGISTER_LINE = "app.register_blueprint(ai_bridge)"


def insert_after(src: str, anchor: str, new_line: str) -> str:
    """Insert new_line after the line whose stripped content matches anchor.

    The inserted line inherits the leading whitespace of the anchor line so it
    stays valid regardless of indentation depth.
    """
    lines = src.splitlines(keepends=True)
    result = []
    inserted = False
    for line in lines:
        result.append(line)
        if not inserted and line.strip() == anchor.strip():
            indent = line[: len(line) - len(line.lstrip())]
            eol = "\r\n" if line.endswith("\r\n") else "\n"
            result.append(indent + new_line.strip() + eol)
            inserted = True
    if not inserted:
        sys.exit(f"ERROR: anchor '{anchor}' not found in {path}. "
                 "Upstream main.py may have changed — update the anchor.")
    return "".join(result)


path = sys.argv[1]
with open(path) as f:
    src = f.read()

if IMPORT_LINE in src:
    print(f"Already patched: {path}")
    sys.exit(0)

src = insert_after(src, IMPORT_ANCHOR, IMPORT_LINE)
src = insert_after(src, REGISTER_ANCHOR, REGISTER_LINE)

with open(path, "w") as f:
    f.write(src)

print(f"Patched {path} successfully.")
