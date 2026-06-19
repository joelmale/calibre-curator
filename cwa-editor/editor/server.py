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
    
    fmt = fmt.upper()
    if fmt not in ("EPUB", "AZW3", "KEPUB"):
        return jsonify({"error": f"Editing format {fmt} is not supported. Please convert to EPUB or AZW3 first."}), 400
    
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

    # Call calibre-debug --explode-book
    try:
        proc = subprocess.run(
            ["/app/calibre/calibre-debug", "--explode-book", src_path, book_dir],
            capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            return jsonify({"error": "calibre-debug error", "detail": proc.stderr or proc.stdout}), 500
    except Exception as e:
        return jsonify({"error": "subprocess error", "detail": str(e)}), 500
    
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
        
    elif request.method == 'DELETE':
        if not os.path.exists(file_path):
            return jsonify({"error": "file not found"}), 404
            
        if os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            os.remove(file_path)
            
        meta_path = os.path.join(session_dir, "session.json")
        with open(meta_path, "r+") as f:
            meta = json.load(f)
            meta["dirty"] = True
            f.seek(0)
            f.truncate()
            json.dump(meta, f)
            
        return jsonify({"ok": True})
        
@app.route('/api/v1/sessions/<session_id>/rename', methods=['POST'])
def rename_file(session_id):
    session_dir = os.path.join(SCRATCH_DIR, session_id)
    book_dir = os.path.join(session_dir, "book")
    if not os.path.exists(book_dir):
        return jsonify({"error": "session not found"}), 404
        
    body = request.get_json() or {}
    old_name = body.get('old_name')
    new_name = body.get('new_name')
    
    if not old_name or not new_name or '..' in old_name or '..' in new_name:
        return jsonify({"error": "invalid names"}), 400
        
    old_path = os.path.join(book_dir, old_name)
    new_path = os.path.join(book_dir, new_name)
    
    if not os.path.exists(old_path):
        return jsonify({"error": "file not found"}), 404
        
    os.makedirs(os.path.dirname(new_path), exist_ok=True)
    os.rename(old_path, new_path)
    
    meta_path = os.path.join(session_dir, "session.json")
    with open(meta_path, "r+") as f:
        meta = json.load(f)
        meta["dirty"] = True
        f.seek(0)
        f.truncate()
        json.dump(meta, f)
        
    return jsonify({"ok": True})

@app.route('/api/v1/sessions/<session_id>/preview/<path:name>', methods=['GET'])
def preview_file(session_id, name):
    session_dir = os.path.join(SCRATCH_DIR, session_id)
    book_dir = os.path.join(session_dir, "book")
    if not os.path.exists(book_dir):
        return "Session not found", 404
        
@app.route('/api/v1/recover', methods=['GET'])
def recover_db():
    try:
        proc = subprocess.run(
            [CALIBREDB_BIN, "--with-library", CALIBRE_LIB, "restore_database", "--really-do-it"],
            capture_output=True, text=True, timeout=300
        )
        if proc.returncode == 0:
            return jsonify({"ok": True, "log": proc.stdout})
        else:
            return jsonify({"error": proc.stderr}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if '..' in name:
        return "Invalid name", 400
        
    file_path = os.path.join(book_dir, name)
    if not os.path.exists(file_path):
        return "File not found", 404
        
    # send_file guesses mime types based on extension, which is usually correct
    return send_file(file_path)

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
    
    try:
        proc = subprocess.run(
            ["/app/calibre/calibre-debug", "--implode-book", book_dir, out_file],
            capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            return jsonify({"error": "calibre-debug implode error", "detail": proc.stderr or proc.stdout}), 500
    except Exception as e:
        return jsonify({"error": "subprocess error", "detail": str(e)}), 500
        
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
    # Auto-recovery of database if corrupted
    print("Checking database health...")
    try:
        conn = _calibre_conn()
        conn.execute("SELECT count(*) FROM books")
        conn.close()
        print("Database is healthy.")
    except sqlite3.DatabaseError:
        print("Database is corrupted. Starting recovery process...")
        try:
            subprocess.run([CALIBREDB_BIN, "--with-library", CALIBRE_LIB, "restore_database", "--really-do-it"], check=True)
            print("Database recovered successfully.")
        except Exception as e:
            print(f"Failed to recover database: {e}")

    app.run(host='0.0.0.0', port=8091, debug=True)
