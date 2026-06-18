#!/usr/bin/env python3
"""Idempotent two-line patch for Calibre-Web's cps/main.py.

Uses Python's AST to locate the exact line numbers of 'from .web import web'
and 'app.register_blueprint(web)', then inserts the ai_bridge equivalents
with matching indentation.  This is immune to indentation depth, inline
comments, surrounding try/except blocks, and other textual variations.
"""
import ast
import sys

AI_IMPORT = "from .ai_bridge import ai_bridge"
AI_REGISTER = "app.register_blueprint(ai_bridge)"

path = sys.argv[1]
with open(path) as f:
    src = f.read()

if AI_IMPORT in src:
    print(f"Already patched: {path}")
    sys.exit(0)

try:
    tree = ast.parse(src)
except SyntaxError as exc:
    sys.exit(f"ERROR: {path} has a syntax error before patching: {exc}")

# ── locate web import ────────────────────────────────────────────────────────
# Matches: from .web import web  (level=1, module="web", name="web")
import_linenos: list[int] = []
for node in ast.walk(tree):
    if (
        isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module == "web"
        and any(a.name == "web" for a in node.names)
    ):
        import_linenos.append(node.lineno)

# ── locate register_blueprint(web) call ─────────────────────────────────────
register_linenos: list[int] = []
for node in ast.walk(tree):
    if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
        continue
    call = node.value
    if (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "register_blueprint"
        and len(call.args) == 1
        and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "web"
    ):
        register_linenos.append(node.lineno)

if not import_linenos:
    sys.exit(
        f"ERROR: 'from .web import web' not found in {path}.\n"
        "Upstream main.py may have changed — inspect the file and update this patcher."
    )
if not register_linenos:
    sys.exit(
        f"ERROR: 'app.register_blueprint(web)' not found in {path}.\n"
        "Upstream main.py may have changed — inspect the file and update this patcher."
    )

import_lineno = sorted(import_linenos)[0]
register_lineno = sorted(register_linenos)[0]

print(f"Found web import  at line {import_lineno}")
print(f"Found web register at line {register_lineno}")

# ── build patched source ─────────────────────────────────────────────────────
lines = src.splitlines(keepends=True)


def _indent(lineno: int) -> str:
    line = lines[lineno - 1]
    return line[: len(line) - len(line.lstrip())]


def _eol(lineno: int) -> str:
    return "\r\n" if lines[lineno - 1].endswith("\r\n") else "\n"


result = list(lines)

# Insert register line first (higher index) so it doesn't shift import index.
result.insert(register_lineno, _indent(register_lineno) + AI_REGISTER + _eol(register_lineno))
result.insert(import_lineno,   _indent(import_lineno)   + AI_IMPORT   + _eol(import_lineno))

patched = "".join(result)

# ── self-verify before writing ───────────────────────────────────────────────
try:
    ast.parse(patched)
except SyntaxError as exc:
    sys.exit(
        f"ERROR: patched {path} has a syntax error — this is a bug in the patcher.\n"
        f"Details: {exc}"
    )

with open(path, "w") as f:
    f.write(patched)

print(f"Patched {path} successfully.")
