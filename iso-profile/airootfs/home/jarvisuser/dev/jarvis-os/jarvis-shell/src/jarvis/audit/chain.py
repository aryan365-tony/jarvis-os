import sqlite3, hashlib, json, time
from ..config import load_config

cfg = load_config()

def _conn():
    return sqlite3.connect(cfg.memory.db_path)

def init_audit_table():
    with _conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            event TEXT NOT NULL,
            payload TEXT NOT NULL,
            prev_hash TEXT NOT NULL,
            row_hash TEXT NOT NULL
        )""")

def audit_log(event: str, payload: dict) -> None:
    with _conn() as c:
        row = c.execute("SELECT row_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        prev_hash = row[0] if row else "0" * 64
        ts = time.time()
        payload_json = json.dumps(payload, sort_keys=True)
        row_hash = hashlib.sha256(f"{prev_hash}{ts}{event}{payload_json}".encode()).hexdigest()
        c.execute(
            "INSERT INTO audit_log (ts, event, payload, prev_hash, row_hash) VALUES (?,?,?,?,?)",
            (ts, event, payload_json, prev_hash, row_hash),
        )

def verify_chain() -> bool:
    prev_hash = "0" * 64
    with _conn() as c:
        for id_, ts, event, payload, stored_prev, stored_hash in c.execute(
            "SELECT id, ts, event, payload, prev_hash, row_hash FROM audit_log ORDER BY id"
        ):
            if stored_prev != prev_hash:
                return False
            expect = hashlib.sha256(f"{prev_hash}{ts}{event}{payload}".encode()).hexdigest()
            if expect != stored_hash:
                return False
            prev_hash = stored_hash
    return True
