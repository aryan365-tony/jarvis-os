#!/usr/bin/env bash
#
# snapper-selftest.sh - run INSIDE the installed Jarvis-OS VM to prove the
# Phase 0 snapshot infrastructure works: configs exist, a snapshot can be
# created, and a change can be rolled back.
#
# This performs a *live, reversible* create+rollback using a pre/post snapshot
# pair and `snapper undochange` (no reboot needed), which satisfies the Phase 0
# gate "manually create + rollback one test snapshot". The full subvolume-level
# `snapper rollback` (which needs a reboot) is exercised by the Phase 3
# destructive drill via ops/rollback.sh.
set -euo pipefail

fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "PASS: $*"; }

CANARY="/root/.snapper-selftest-canary"

echo "=== snapper configs ==="
snapper list-configs
snapper list-configs | grep -qw root || fail "no 'root' snapper config"
snapper list-configs | grep -qw home || fail "no 'home' snapper config"
ok "root + home snapper configs present"

echo "=== create pre snapshot ==="
PRE="$(snapper -c root create -t pre -p -d 'phase0 selftest pre')"
[[ -n "$PRE" ]] || fail "could not create pre snapshot"
ok "pre snapshot #$PRE"

echo "test-content-$(date +%s)" > "$CANARY"

echo "=== create post snapshot ==="
POST="$(snapper -c root create -t post --pre-number "$PRE" -p -d 'phase0 selftest post')"
[[ -n "$POST" ]] || fail "could not create post snapshot"
ok "post snapshot #$POST"

echo "=== snapper list ==="
snapper -c root list

echo "=== status pre..post (should show the canary added) ==="
snapper -c root status "${PRE}..${POST}" | tee /tmp/snapper-status.txt
grep -q "$CANARY" /tmp/snapper-status.txt || fail "canary not detected in snapshot diff"
ok "snapshot captured the change"

echo "=== rollback the change (undochange pre..post) ==="
snapper -c root undochange "${PRE}..${POST}"
[[ ! -e "$CANARY" ]] || fail "rollback did not remove the canary"
ok "rollback restored pre-change state"

echo "=== cleanup selftest snapshots ==="
snapper -c root delete "$PRE" "$POST" || true

echo "ALL SNAPPER SELFTEST CHECKS PASSED"
