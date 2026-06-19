#!/usr/bin/env python3
import sys

AI_EDITOR_BTN = """\
                                    {% if current_user.role_admin() and entry.data|length > 0 %}
                                        <a href="{{ url_for('ai_bridge.editor_page', book_id=entry.id, format=entry.data[0].format|lower) }}"
                                           class="btn btn-warning action-icon-btn" role="button" title="Edit Content ({{ entry.data[0].format }})" aria-label="Edit Content">
                                            <span class="glyphicon glyphicon-console"></span>
                                        </a>
                                    {% endif %}\
"""

ANCHOR = "{% if current_user.role_edit() and current_user.role_delete_books() %}"

path = sys.argv[1]
with open(path) as f:
    src = f.read()

if "ai_bridge.editor_page" in src:
    print(f"Already patched: {path}")
    sys.exit(0)

if ANCHOR in src:
    src = src.replace(ANCHOR, AI_EDITOR_BTN + "\n" + ANCHOR)
    with open(path, "w") as f:
        f.write(src)
    print(f"Patched {path}")
    sys.exit(0)
    
sys.exit("ERROR: No anchor found in detail.html")
