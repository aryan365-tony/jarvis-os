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

import os
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
    def __init__(self, path: str, key: str | None = None) -> None:
        self._path = path
        self._key = key
        self._lock = threading.RLock()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = self._connect(path, key)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            # WAL keeps readers non-blocking and, crucially, survives a hard
            # power loss: an interrupted write leaves the main DB intact and the
            # WAL is replayed/rolled back cleanly on the next open (Phase 1
            # crash-durability requirement). synchronous=NORMAL is the correct
            # pairing with WAL — durable across app crashes, and across power
            # loss the DB stays consistent (at most the last uncommitted txn is
            # lost, never corrupted).
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            # A busy timeout avoids spurious "database is locked" under the
            # multi-thread tool executor.
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.executescript(_AUDIT_DDL)
            self._conn.commit()
        # The memory DB holds full conversation history and now runs with
        # reduced human oversight; lock it down to owner-only at rest (Phase 1).
        self._restrict_permissions()

    @staticmethod
    def _connect(path: str, key: str | None) -> sqlite3.Connection:
        """Open the DB, transparently using SQLCipher when a key is supplied.

        check_same_thread=False + an explicit RLock lets tool worker threads log
        to the audit table safely. When ``key`` is set and the pysqlcipher3
        driver is installed, the file is opened as an encrypted SQLCipher DB;
        otherwise we fall back to stdlib sqlite3 (plaintext file, still 0600 and
        typically on a LUKS-encrypted @home).
        """
        if key:
            try:
                from pysqlcipher3 import dbapi2 as sqlcipher  # type: ignore

                conn = sqlcipher.connect(path, check_same_thread=False)
                # PRAGMA key must be the very first statement on the connection.
                conn.execute(f"PRAGMA key = \"x'{key}'\"")
                return conn
            except ModuleNotFoundError:
                import logging

                logging.getLogger("jarvis.db").warning(
                    "encrypt_at_rest requested but pysqlcipher3 is not installed; "
                    "falling back to plaintext DB (rely on LUKS @home + 0600 perms)"
                )
        return sqlite3.connect(path, check_same_thread=False)

    def _restrict_permissions(self) -> None:
        """chmod the DB (and WAL/SHM sidecars) to 0600 — owner read/write only."""
        for suffix in ("", "-wal", "-shm"):
            p = self._path + suffix
            try:
                if os.path.exists(p):
                    os.chmod(p, 0o600)
            except OSError:  # best effort; never block startup on perms
                pass

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

    def execute(self, sql: str, params: tuple = (), commit: bool = True) -> sqlite3.Cursor:
        """Run one statement. BUG-013: every call previously committed
        (forcing a WAL fsync) even for high-frequency, non-critical writes
        like session_log inserts. ``commit=False`` lets a caller batch
        several writes under one fsync via :meth:`commit`; the default
        preserves prior behavior for every existing call site."""
        with self._lock:
            cur = self._conn.execute(sql, params)
            if commit:
                self._conn.commit()
            return cur

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params))

    def checkpoint(self) -> None:
        """Force a full WAL checkpoint and truncate the WAL file.

        Called by maintenance (``ops/cleanup-space.sh`` → ``jarvis db checkpoint``)
        so the WAL does not grow unbounded and every committed change is folded
        back into the main database file.
        """
        with self._lock:
            # Commit first: batched writers (BUG-013, e.g. session_log) may
            # have an open transaction on this connection. Checkpointing
            # before committing would checkpoint around it instead of
            # folding it in.
            self._conn.commit()
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self._conn.commit()

    def vacuum(self) -> None:
        """Compact the database, reclaiming space from deleted rows."""
        with self._lock:
            # VACUUM cannot run inside a transaction; commit any pending work.
            self._conn.commit()
            self._conn.execute("VACUUM")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            # Fold the WAL back before closing so a subsequent open is clean.
            try:
                self._conn.commit()
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._conn.commit()
            except sqlite3.Error:
                pass
            self._conn.close()


# Lazy process-wide singleton, built from config on first use so that modules
# which still import at top level keep working during the transition.
_db: Database | None = None
_db_init_lock = threading.Lock()


def get_db() -> Database:
    global _db
    if _db is None:
        # RISK-007: check-then-set was not thread-safe — two threads racing
        # here could each construct a Database and each run migrate(),
        # applying migrations twice. Guard construction with a lock; the
        # (cheap) None-check outside the lock avoids taking it on every call.
        with _db_init_lock:
            if _db is None:
                from .config import get_config

                cfg = get_config().memory
                key = _load_or_create_key(cfg.key_path) if cfg.encrypt_at_rest else None
                db = Database(cfg.db_path, key=key)
                db.migrate()
                _db = db
    return _db


def _load_or_create_key(key_path: str) -> str:
    """Return a hex key for SQLCipher, generating a 0600 keyfile if absent.

    NOTE: a key stored on the same disk protects against offline theft of the DB
    file alone, not against an attacker with full root on a running system. For
    strong at-rest protection, pair this with LUKS on @home (installer
    ``ENCRYPT_HOME=1``). Kept dependency-free (os.urandom) so it works offline.
    """
    p = Path(key_path)
    try:
        if p.exists():
            return p.read_text().strip()
        p.parent.mkdir(parents=True, exist_ok=True)
        key = os.urandom(32).hex()
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(key)
        return key
    except OSError:
        # If we cannot persist a stable key, fall back to no encryption rather
        # than locking the user out of their own history.
        import logging

        logging.getLogger("jarvis.db").error(
            "could not read/create memory key at %s; disabling encryption", key_path
        )
        return ""


def set_db(db: Database) -> None:
    """Allow the runtime/tests to inject a pre-built database."""
    global _db
    _db = db
