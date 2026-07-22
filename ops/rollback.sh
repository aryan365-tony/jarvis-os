#!/usr/bin/env bash
# =============================================================================
# ops/rollback.sh — restore the system to a snapper snapshot (Phase 3)
# =============================================================================
#
# The autonomy safety net: every high-risk agent action takes a pre-action
# snapshot (see tools/snapshot.py + ui_bridge.request_tool_approval). This
# script is the human/operator escape hatch to undo one of those changes.
#
# Usage:
#   ops/rollback.sh                 # interactive: list snapshots, pick one
#   ops/rollback.sh <snapshot_id>   # roll back to a specific snapshot
#   ops/rollback.sh --config home <id>
#
# It uses `snapper rollback`, which creates a new snapshot of the CURRENT state
# (so the rollback is itself reversible) and sets the target as the new default
# subvolume. A reboot is required to boot into the restored state.
# =============================================================================
set -euo pipefail

CONFIG="root"
SNAP_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) CONFIG="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) SNAP_ID="$1"; shift ;;
  esac
done

if ! command -v snapper >/dev/null 2>&1; then
  echo "error: snapper not installed (is this the installed btrfs system?)" >&2
  exit 1
fi

echo "== Snapshots for config '$CONFIG' =="
sudo snapper -c "$CONFIG" list --columns number,date,description || {
  echo "error: no snapper config '$CONFIG'" >&2; exit 1; }

if [[ -z "$SNAP_ID" ]]; then
  read -r -p "Enter snapshot id to roll back to (blank to cancel): " SNAP_ID
  [[ -z "$SNAP_ID" ]] && { echo "cancelled."; exit 0; }
fi

if ! [[ "$SNAP_ID" =~ ^[0-9]+$ ]]; then
  echo "error: snapshot id must be numeric" >&2; exit 2
fi

echo "Rolling '$CONFIG' back to snapshot $SNAP_ID ..."
sudo snapper -c "$CONFIG" rollback "$SNAP_ID"

echo
echo "Rollback staged. Reboot to boot into the restored state:"
echo "    sudo systemctl reboot"
