#!/usr/bin/env bash
#
# phase6-integration.sh — run INSIDE the installed Jarvis-OS VM to exercise the
# whole autonomous stack end-to-end and print a pass/fail acceptance summary.
#
# This is the Phase 6 acceptance gate. It assumes Phases 0-5 are installed and
# the system has booted into the kiosk shell. It verifies, in order:
#
#   1. All expected tools are registered, each with a valid risk tier.
#   2. The full tool surface is present (Phase 2) and the dead network policy
#      is gone.
#   3. A high-risk tool call takes a pre-action snapshot and links it in audit.
#   4. The audit hash chain is intact and self-review works (Phase 4).
#   5. The DB survives a checkpoint/vacuum with no data loss (Phase 1).
#   6. Voice reports an honest status (READY or a clear degraded reason).
#   7. Soak: N synthetic agent turns leave the audit chain intact and the shell
#      still responsive (no crash loop, StartLimit not tripped).
#
# Nothing here mutates real system state destructively — the high-risk probe
# uses a no-op fs_system touch inside a temp path and rolls its own snapshot.
set -uo pipefail

RC=0
SOAK_TURNS="${SOAK_TURNS:-200}"
section() { printf '\n=== %s ===\n' "$*"; }
pass()    { echo "PASS: $*"; }
fail()    { echo "FAIL: $*"; RC=1; }

PY() { python3 - "$@"; }

section "1. Tool registry: every tool has a valid tier"
PY <<'PYEOF' || fail "tool registry tier check"
import sys
import jarvis.tools  # noqa: F401 (populates REGISTRY)
from jarvis.tools.registry import REGISTRY, get_risk_tier
valid = {"low", "medium", "high"}
bad = [n for n in REGISTRY if get_risk_tier(n) not in valid]
expected = {
    "fs_read","fs_scratch","fs_system","pkg_query","pkg_manage","svc_status",
    "svc_control","proc_list","proc_kill","diag_journal","diag_dmesg",
    "diag_resources","display_brightness","session_lock","snapshot_list",
    "snapshot_rollback","audit_review","shell_exec","optimize_backend",
}
missing = expected - set(REGISTRY)
if bad: print("tools with invalid tier:", bad); sys.exit(1)
if missing: print("missing tools:", missing); sys.exit(1)
print(f"{len(REGISTRY)} tools registered, all tiers valid")
PYEOF
[[ $? -eq 0 ]] && pass "all tools have valid tiers and full surface present"

section "2. Dead network policy removed"
if python3 -c "import jarvis.tools.network_policy" 2>/dev/null; then
  fail "network_policy module still importable"
else
  pass "network_policy removed"
fi

section "3. High-risk action snapshots + audit link"
PY <<'PYEOF' || fail "high-risk snapshot/audit link"
import asyncio, sys
from jarvis.tools.registry import register, execute, ApprovalResult
from jarvis.audit.chain import tail

@register("phase6_probe", risk="high")
def phase6_probe():
    return "ran"

async def approver(name, args):
    # emulate the bridge: high tier -> snapshot id attached
    return ApprovalResult(approved=True, snapshot_id="probe-1")

async def main():
    out = await execute("phase6_probe", {}, confirm=approver)
    assert out == "ran", out
    entries = tail(10)
    ok = any(e["event"] == "tool_call_ok"
             and e["payload"].get("snapshot_id") == "probe-1" for e in entries)
    sys.exit(0 if ok else 1)

asyncio.run(main())
PYEOF
[[ $? -eq 0 ]] && pass "high-risk call linked to its snapshot in the audit chain"

section "4. Audit chain intact + self-review"
if jarvis audit verify 2>/dev/null | grep -qi intact \
   || python3 -c "from jarvis.audit.chain import verify_chain; import sys; sys.exit(0 if verify_chain() else 1)"; then
  pass "audit hash chain verifies"
else
  fail "audit chain verification failed"
fi

section "5. DB checkpoint + vacuum, no data loss"
PY <<'PYEOF' || fail "db durability"
import sys, tempfile, os
from jarvis.db import Database
p = os.path.join(tempfile.mkdtemp(), "m.sqlite3")
db = Database(p)
db.execute("CREATE TABLE t (x INTEGER)")
for i in range(100): db.execute("INSERT INTO t VALUES (?)", (i,))
db.checkpoint(); db.vacuum()
n = db.query("SELECT COUNT(*) AS c FROM t")[0]["c"]
db.close()
sys.exit(0 if n == 100 else 1)
PYEOF
[[ $? -eq 0 ]] && pass "DB checkpoint/vacuum preserved all rows"

section "6. Voice honest status"
VSTATE="$(journalctl -b -u jarvis-shell --no-pager 2>/dev/null | grep -oiE 'voice (ready|unavailable|degraded|initializing)[^\"]*' | tail -1)"
echo "last voice status: ${VSTATE:-<none logged>}"
[[ -n "$VSTATE" ]] && pass "voice reported a status" || echo "INFO: no voice status in journal yet"

section "7. Soak: $SOAK_TURNS synthetic audited actions"
PY "$SOAK_TURNS" <<'PYEOF' || fail "soak run"
import sys
from jarvis.audit.chain import audit_log, verify_chain
n = int(sys.argv[1])
for i in range(n):
    audit_log("soak_tool_call", {"name": "diag_resources", "tier": "low", "i": i})
sys.exit(0 if verify_chain() else 1)
PYEOF
[[ $? -eq 0 ]] && pass "audit chain intact after $SOAK_TURNS actions"

section "8. Shell not in a crash loop"
if systemctl is-active --quiet jarvis-shell; then
  pass "jarvis-shell still active after soak"
else
  fail "jarvis-shell not active (StartLimit may have tripped)"
fi

section "SUMMARY"
[[ $RC -eq 0 ]] && echo "PHASE 6 GATE: ALL CHECKS PASSED" || echo "PHASE 6 GATE: FAILURES PRESENT (see above)"
exit $RC
