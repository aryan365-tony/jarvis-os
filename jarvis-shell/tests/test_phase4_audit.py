"""Phase 4: audit chain completeness, self-review tool, tamper detection."""

import pytest

from jarvis import db as db_mod
from jarvis.audit import chain
from jarvis.tools import audit_review as ar_mod


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path, monkeypatch):
    """Point the audit chain at a throwaway DB per test."""
    fresh = db_mod.Database(str(tmp_path / "m.sqlite3"))
    monkeypatch.setattr(chain, "get_db", lambda: fresh)
    monkeypatch.setattr(ar_mod, "verify_chain_detailed", chain.verify_chain_detailed)
    monkeypatch.setattr(ar_mod, "_tail", chain.tail)
    yield fresh
    fresh.close()


def test_every_write_extends_intact_chain():
    for i in range(10):
        chain.audit_log("tool_call_ok", {"name": f"t{i}", "tier": "low"})
    ok, broken = chain.verify_chain_detailed()
    assert ok and broken is None


def test_tamper_is_detected(_fresh_db):
    chain.audit_log("tool_call_ok", {"name": "a", "tier": "high"})
    chain.audit_log("tool_call_ok", {"name": "b", "tier": "high"})
    # Mutate a stored payload out from under the hash chain.
    with _fresh_db.lock:
        _fresh_db.conn.execute("UPDATE audit_log SET payload='{\"name\":\"HACKED\"}' WHERE id=1")
        _fresh_db.conn.commit()
    ok, broken = chain.verify_chain_detailed()
    assert not ok
    assert broken == 1


def test_audit_review_reports_intact_and_filters():
    chain.audit_log("high_risk_action", {"tool": "pkg_manage", "snapshot_id": "5"})
    chain.audit_log("tool_call_ok", {"name": "fs_read", "tier": "low"})
    out = ar_mod.audit_review(limit=10)
    assert "INTACT" in out
    filtered = ar_mod.audit_review(limit=10, event_filter="high_risk")
    assert "high_risk_action" in filtered
    assert "fs_read" not in filtered


def test_audit_review_reports_break(_fresh_db):
    chain.audit_log("tool_call_ok", {"name": "a"})
    chain.audit_log("tool_call_ok", {"name": "b"})
    with _fresh_db.lock:
        _fresh_db.conn.execute("UPDATE audit_log SET event='TAMPERED' WHERE id=2")
        _fresh_db.conn.commit()
    out = ar_mod.audit_review()
    assert "BROKEN" in out
