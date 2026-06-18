#!/usr/bin/env python3
"""Idempotent nav entry patch for Calibre-Web's cps/templates/layout.html.

Inserts a single <li> entry for the AI dashboard before the Shelves link
(or before the next best anchor if Shelves isn't found).
"""
import re
import sys

AI_NAV_ENTRY = """\
            <li>
              <a href="{{ url_for('ai_bridge.dashboard') }}">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"
                     aria-hidden="true" style="vertical-align:-2px;margin-right:4px">
                  <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/>
                </svg>
                {{ _('AI Curated Library') }}
              </a>
            </li>"""

# Anchors tried in order; first match wins.
# Each entry is a substring that should appear inside or just before a <li>.
ANCHORS = [
    "url_for('shelf.shelf_list')",
    "url_for('shelf.create_shelf')",
    "url_for('web.books_list')",
]

path = sys.argv[1]
with open(path) as f:
    src = f.read()

if "ai_bridge.dashboard" in src:
    print(f"Already patched: {path}")
    sys.exit(0)

for anchor in ANCHORS:
    if anchor not in src:
        continue

    anchor_pos = src.find(anchor)
    # Walk back to the start of the <li> that contains this anchor
    li_pos = src.rfind("<li", 0, anchor_pos)
    if li_pos == -1:
        continue
    # Insert our entry on the line before this <li>
    line_start = src.rfind("\n", 0, li_pos) + 1
    src = src[:line_start] + AI_NAV_ENTRY + "\n" + src[line_start:]

    with open(path, "w") as f:
        f.write(src)
    print(f"Patched {path} (anchor: '{anchor}').")
    sys.exit(0)

sys.exit(
    f"ERROR: No layout.html anchor found in {path}.\n"
    f"Tried: {ANCHORS}\n"
    "Upstream template may have changed — inspect layout.html and update ANCHORS."
)
