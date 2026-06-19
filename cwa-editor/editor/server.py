import json
import os
import shutil
import socket
import sqlite3
import subprocess
import time
import uuid
from flask import Flask, request, jsonify, send_file, Response

app = Flask(__name__)

# Config
CALIBRE_LIB = os.getenv("CALIBRE_LIBRARY_ROOT", "/calibre-library")
CALIBRE_DB = os.path.join(CALIBRE_LIB, "metadata.db")
CALIBREDB_BIN = shutil.which("calibredb") or "/app/calibre/calibredb"
SCRATCH_DIR = os.getenv("EDITOR_SCRATCH_DIR", "/state/editor_scratch")

os.makedirs(SCRATCH_DIR, exist_ok=True)

def call_worker(action: str, args: dict) -> dict:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', 8092))
        req = json.dumps({"action": action, "args": args}) + "\n"
        s.sendall(req.encode('utf-8'))
        
        data = b""
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
        s.close()
        return json.loads(data.decode('utf-8'))
    except Exception as e:
        return {"result": None, "error": str(e)}

def _calibre_conn():
    conn = sqlite3.connect(f"file:{CALIBRE_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def _get_book_path(book_id: int, fmt: str) -> str:
    fmt = fmt.upper()
    with _calibre_conn() as conn:
        book = conn.execute("SELECT path FROM books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            raise ValueError(f"Book {book_id} not found")
        rel_path = book["path"]
        
        data = conn.execute("SELECT name FROM data WHERE book = ? AND format = ?", (book_id, fmt)).fetchone()
        if not data:
            raise ValueError(f"Format {fmt} not found for book {book_id}")
        file_name = data["name"]
        
        full_path = os.path.join(CALIBRE_LIB, rel_path, f"{file_name}.{fmt.lower()}")
        if not os.path.exists(full_path):
            raise ValueError(f"File not found: {full_path}")
        
        return full_path

@app.route('/api/v1/sessions', methods=['POST'])
def create_session():
    body = request.get_json(silent=True) or {}
    book_id = body.get('book_id')
    fmt = body.get('format')
    
    if not book_id or not fmt:
        return jsonify({"error": "book_id and format required"}), 400
    
    try:
        book_id = int(book_id)
        src_path = _get_book_path(book_id, fmt)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    session_id = str(uuid.uuid4())
    session_dir = os.path.join(SCRATCH_DIR, session_id)
    book_dir = os.path.join(session_dir, "book")
    checkpoints_dir = os.path.join(session_dir, "checkpoints")
    
    os.makedirs(book_dir, exist_ok=True)
    os.makedirs(checkpoints_dir, exist_ok=True)

    resp = call_worker("get_container", {"src": src_path, "work_dir": book_dir})
    if resp.get("error"):
        return jsonify({"error": "worker error", "detail": resp["error"]}), 500
    
    meta = {
        "id": session_id,
        "book_id": book_id,
        "format": fmt,
        "src_path": src_path,
        "created_at": time.time(),
        "dirty": False
    }
    with open(os.path.join(session_dir, "session.json"), "w") as f:
        json.dump(meta, f)
        
    shutil.copytree(book_dir, os.path.join(checkpoints_dir, "Original"))

    return jsonify(meta)

@app.route('/api/v1/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    session_dir = os.path.join(SCRATCH_DIR, session_id)
    meta_path = os.path.join(session_dir, "session.json")
    if not os.path.exists(meta_path):
        return jsonify({"error": "session not found"}), 404
        
    with open(meta_path, "r") as f:
        meta = json.load(f)
    return jsonify(meta)

@app.route('/api/v1/sessions/<session_id>/files', methods=['GET'])
def get_files(session_id):
    session_dir = os.path.join(SCRATCH_DIR, session_id)
    book_dir = os.path.join(session_dir, "book")
    if not os.path.exists(book_dir):
        return jsonify({"error": "session not found"}), 404
        
    tree = []
    for root, dirs, files in os.walk(book_dir):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, book_dir)
            rel_path = rel_path.replace(os.sep, '/')
            tree.append({"name": rel_path})
            
    return jsonify({"files": tree})

@app.route('/api/v1/sessions/<session_id>/file', methods=['GET', 'PUT'])
def handle_file(session_id):
    session_dir = os.path.join(SCRATCH_DIR, session_id)
    book_dir = os.path.join(session_dir, "book")
    if not os.path.exists(book_dir):
        return jsonify({"error": "session not found"}), 404
        
    name = request.args.get('name')
    if not name or '..' in name:
        return jsonify({"error": "invalid name"}), 400
        
    file_path = os.path.join(book_dir, name)
    
    if request.method == 'GET':
        if not os.path.exists(file_path):
            return jsonify({"error": "file not found"}), 404
        return send_file(file_path)
        
    elif request.method == 'PUT':
        content = request.get_data()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(content)
            
        meta_path = os.path.join(session_dir, "session.json")
        with open(meta_path, "r+") as f:
            meta = json.load(f)
            meta["dirty"] = True
            f.seek(0)
            f.truncate()
            json.dump(meta, f)
            
        return jsonify({"ok": True})

@app.route('/api/v1/sessions/<session_id>/commit', methods=['POST'])
def commit_session(session_id):
    session_dir = os.path.join(SCRATCH_DIR, session_id)
    meta_path = os.path.join(session_dir, "session.json")
    book_dir = os.path.join(session_dir, "book")
    
    if not os.path.exists(meta_path):
        return jsonify({"error": "session not found"}), 404
        
    with open(meta_path, "r") as f:
        meta = json.load(f)
        
    book_id = meta["book_id"]
    fmt = meta["format"].upper()
    
    out_file = os.path.join(session_dir, f"compiled.{fmt.lower()}")
    
    resp = call_worker("commit_container", {"work_dir": book_dir, "out_path": out_file})
    if resp.get("error"):
        return jsonify({"error": "worker error", "detail": resp["error"]}), 500
        
    try:
        proc = subprocess.run(
            [CALIBREDB_BIN, "--with-library", CALIBRE_LIB, "add_format", "--replace", str(book_id), out_file],
            capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            return jsonify({"error": "calibredb error", "detail": proc.stderr or proc.stdout}), 500
    except Exception as e:
        return jsonify({"error": "subprocess error", "detail": str(e)}), 500
        
    meta["dirty"] = False
    with open(meta_path, "w") as f:
        json.dump(meta, f)
        
    return jsonify({"ok": True})

@app.route('/healthz', methods=['GET'])
def health():
    return "OK\n"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8091)
