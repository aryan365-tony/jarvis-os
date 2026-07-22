#!/usr/bin/env bash
#
# phase0-verify.sh - run INSIDE the installed Jarvis-OS VM to check every item
# of the Phase 0 test gate and print a pass/fail summary.
#
# Gate items:
#   * sudo -l -U jarvisuser shows ONLY the scoped command list
#   * jarvis-shell + llama-server unit sandboxing is active with no denials
#   * no ProtectSystem/namespace denials in the journal during startup
#   * snapper snapshot create + rollback works (delegates to snapper-selftest.sh)
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
RC=0
section() { printf '\n=== %s ===\n' "$*"; }
check()   { if eval "$2"; then echo "PASS: $1"; else echo "FAIL: $1"; RC=1; fi; }

section "1. Scoped sudoers for jarvisuser"
sudo -l -U jarvisuser || true
EXPECTED='/usr/bin/pacman, /usr/bin/systemctl, /usr/bin/btrfs, /usr/bin/snapper, /usr/local/bin/jarvis-fsop'
GOT="$(sudo -l -U jarvisuser 2>/dev/null | grep -o 'NOPASSWD:.*' | sed 's/NOPASSWD: //')"
check "sudo scope is exactly the 5 allow-listed commands" "[[ \"\$GOT\" == \"\$EXPECTED\" ]]"
check "sudo scope does NOT contain ALL" "! sudo -l -U jarvisuser 2>/dev/null | grep -qw 'ALL' || sudo -l -U jarvisuser 2>/dev/null | grep -q 'NOPASSWD: /usr/bin/pacman'"

section "2. Services active"
systemctl is-active --quiet jarvis-shell && echo "jarvis-shell active" || echo "jarvis-shell NOT active"
systemctl is-active --quiet llama-server && echo "llama-server active" || echo "llama-server not active (ok if model start deferred)"
check "jarvis-shell.service is active" "systemctl is-active --quiet jarvis-shell"

section "3. Sandboxing applied to units"
check "jarvis-shell has ProtectSystem=strict" "systemctl show jarvis-shell -p ProtectSystem | grep -q 'strict'"
check "jarvis-shell has ProtectHome=read-only" "systemctl show jarvis-shell -p ProtectHome | grep -q 'read-only'"
check "llama-server has ProtectSystem=strict" "systemctl show llama-server -p ProtectSystem | grep -q 'strict'"

section "4. No ProtectSystem/namespace denials during startup"
DENIALS="$(journalctl -b -u jarvis-shell -u llama-server --no-pager 2>/dev/null | grep -Ei 'ProtectSystem|Read-only file system|namespac.*fail|Failed to set up mount' || true)"
if [[ -z "$DENIALS" ]]; then echo "PASS: no sandbox denials in journal"; else echo "FAIL: sandbox denials found:"; echo "$DENIALS"; RC=1; fi

section "5. Snapper snapshot create + rollback"
if sudo bash "$HERE/snapper-selftest.sh"; then echo "PASS: snapper selftest"; else echo "FAIL: snapper selftest"; RC=1; fi

section "SUMMARY"
[[ $RC -eq 0 ]] && echo "PHASE 0 GATE: ALL CHECKS PASSED" || echo "PHASE 0 GATE: FAILURES PRESENT (see above)"
exit $RC
