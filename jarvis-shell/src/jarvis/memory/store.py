import sqlite3
from ..config import load_config

cfg = load_config()

def _conn():
    return sqlite3.connect(cfg.memory.db_path)

def load_core_memory():
    try:
        with _conn() as c:
            rows = c.execute("SELECT key, value FROM core_memory ORDER BY updated_at").fetchall()
            return {k: v for k, v in rows}
    except sqlite3.OperationalError:
        return {}
