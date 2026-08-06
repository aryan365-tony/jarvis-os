"""Phase 1: DB durability (WAL/PRAGMA), checkpoint/vacuum, and 0600 perms."""

import os
import stat

from jarvis.db import Database


def test_wal_and_synchronous_pragmas(tmp_path):
    db = Database(str(tmp_path / "m.sqlite3"))
    mode = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
    sync = db.conn.execute("PRAGMA synchronous").fetchone()[0]
    assert mode.lower() == "wal"
    # synchronous=NORMAL is 1
    assert int(sync) == 1
    db.close()


def test_permissions_are_owner_only(tmp_path):
    path = tmp_path / "m.sqlite3"
    db = Database(str(path))
    db.execute("CREATE TABLE IF NOT EXISTS t (x INTEGER)")
    db.execute("INSERT INTO t (x) VALUES (1)")
    db._restrict_permissions()
    perm = stat.S_IMODE(os.stat(path).st_mode)
    assert perm == 0o600
    db.close()


def test_checkpoint_and_vacuum_do_not_lose_data(tmp_path):
    path = tmp_path / "m.sqlite3"
    db = Database(str(path))
    db.execute("CREATE TABLE t (x INTEGER)")
    for i in range(50):
        db.execute("INSERT INTO t (x) VALUES (?)", (i,))
    db.checkpoint()
    db.vacuum()
    rows = db.query("SELECT COUNT(*) AS c FROM t")
    assert rows[0]["c"] == 50
    db.close()


def test_reopen_after_close_recovers_cleanly(tmp_path):
    """Simulate a fresh open (as after a crash/reboot): WAL replays, no loss."""
    path = str(tmp_path / "m.sqlite3")
    db = Database(path)
    db.execute("CREATE TABLE t (x INTEGER)")
    db.execute("INSERT INTO t (x) VALUES (42)")
    db.close()

    db2 = Database(path)
    rows = db2.query("SELECT x FROM t")
    assert [r["x"] for r in rows] == [42]
    db2.close()
