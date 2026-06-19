import sys
sys.path.insert(0, '/Users/JoelN/Coding/calibre_curator/ai-sidecar')
from sidecar.config import get_config
from sidecar.db.session import get_db
from sidecar.embeddings import get_embedding_provider

try:
    config = get_config()
    with get_db() as conn:
        c = conn.execute("SELECT status, COUNT(*) FROM ai_books GROUP BY status")
        print("ai_books:", c.fetchall())
        
        c = conn.execute("SELECT COUNT(*) FROM book_chunks WHERE vector_id IS NULL")
        print("unembedded chunks:", c.fetchone()[0])
        
        c = conn.execute("SELECT COUNT(*) FROM book_chunks WHERE vector_id IS NOT NULL")
        print("embedded chunks:", c.fetchone()[0])
        
        c = conn.execute("SELECT chunk_uid, text FROM book_chunks WHERE vector_id IS NULL LIMIT 2")
        print("sample unembedded:", c.fetchall())
        
except Exception as e:
    import traceback
    traceback.print_exc()

