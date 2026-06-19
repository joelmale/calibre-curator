import json
import socket
import sys
import threading
import traceback
import os

try:
    from calibre.ebooks.oeb.polish.container import get_container
except ImportError:
    print("Must be run via calibre-debug!")
    sys.exit(1)

def handle_client(conn):
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\n" in chunk:
                break
        
        if not data:
            return

        req = json.loads(data.decode('utf-8'))
        action = req.get('action')
        args = req.get('args', {})

        result = None
        error = None

        try:
            if action == 'get_container':
                src = args['src']
                work_dir = args['work_dir']
                
                # calibre's get_container opens an ebook file (e.g. .epub)
                # and container.commit(work_dir) unpacks it into work_dir
                container = get_container(src, tweak_mode=True)
                container.commit(work_dir)
                result = "ok"
            elif action == 'commit_container':
                work_dir = args['work_dir']
                out_path = args['out_path']
                
                # Opening an exploded directory:
                # get_container actually supports opening a directory (it checks if path is a dir)
                container = get_container(work_dir, tweak_mode=True)
                container.commit(out_path)
                result = "ok"
            else:
                error = f"Unknown action: {action}"
        except Exception as e:
            error = traceback.format_exc()

        resp = json.dumps({"result": result, "error": error}) + "\n"
        conn.sendall(resp.encode('utf-8'))
    except Exception as e:
        print(f"Worker client error: {e}")
    finally:
        conn.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('127.0.0.1', 8092))
    server.listen(5)
    print("Calibre Polish worker listening on 127.0.0.1:8092", flush=True)

    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn,))
        t.daemon = True
        t.start()

if __name__ == '__main__':
    main()
