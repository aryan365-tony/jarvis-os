"""Single shared SQLite database with WAL and a migration runner.

Design note
-----------
The old code opened a brand-new connection on every ``audit_log`` / memory read
and re-parsed the TOML config at import time in three modules. That is both slow
and racy. Here we centralise a single connection (WAL mode, thread-safe with a
lock) and a tiny forward-only migration runner that also guarantees the audit
table exists before the first write.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent / "memory" / "migrations"

# Audit table lives here (not in the SQL migrations) because the audit chain is
# a security primitive that must exist even if content migrations are skipped.
_AUDIT_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    event TEXT NOT NULL,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    row_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY,
    applied_at REAL NOT NULL
);
"""


class Database:
    def __init__(self, path: str) -> None:
        self._path = path
        self._lock = threading.RLock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False + explicit lock lets tool threads log safely.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_AUDIT_DDL)
            self._conn.commit()

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def migrate(self) -> list[str]:
        """Apply any *.sql migrations not yet recorded. Returns applied names."""
        import time

        applied: list[str] = []
        if not _MIGRATIONS_DIR.is_dir():
            return applied
        with self._lock:
            done = {
                r[0]
                for r in self._conn.execute("SELECT name FROM schema_migrations")
            }
            for sql_file in sorted(_MIGRATIONS_DIR.glob("*.sql")):
                if sql_file.name in done:
                    continue
                self._conn.executescript(sql_file.read_text())
                self._conn.execute(
                    "INSERT INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                    (sql_file.name, time.time()),
                )
                applied.append(sql_file.name)
            self._conn.commit()
        return applied

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params))

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# Lazy process-wide singleton, built from config on first use so that modules
# which still import at top level keep working during the transition.
_db: Database | None = None


def get_db() -> Database:
    global _db
    if _db is None:
        from .config import get_config

        _db = Database(get_config().memory.db_path)
        _db.migrate()
    return _db


def set_db(db: Database) -> None:
    """Allow the runtime/tests to inject a pre-built database."""
    global _db
    _db = db
