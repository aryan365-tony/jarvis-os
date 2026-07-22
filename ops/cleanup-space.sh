#!/usr/bin/env bash
# cleanup-space.sh — Reclaim disk space in the Jarvis-OS build tree
# Usage: ./ops/cleanup-space.sh [options]
# Options:
#   --dry-run          Show what would be deleted without deleting
#   --aggressive       Also remove models and source staging (CAREFUL!)

set -euo pipefail

DRY_RUN=false
AGGRESSIVE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true; shift ;;
        --aggressive) AGGRESSIVE=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

total_freed=0

cleanup() {
    local path=$1
    local desc=$2
    if [ -e "$path" ]; then
        local size=$(du -sh "$path" 2>/dev/null | cut -f1)
        if [ "$DRY_RUN" = true ]; then
            echo "  [DRY-RUN] Would remove: $path ($size)"
        else
            echo "  Removing: $path ($size)"
            rm -rf "$path"
        fi
    fi
}

echo "=== Jarvis-OS Build Space Cleanup ==="
echo ""

# Always safe to clean
echo "1. Python cache (__pycache__):"
find . -type d -name __pycache__ -exec echo "  Removing: {}" \; -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -o -name "*.pyo" | xargs rm -f 2>/dev/null || true

echo ""
echo "2. Graphify cache (regenerable):"
cleanup "graphify-out/cache" "Graphify AST/semantic cache"

echo ""
echo "3. SQLite memory/audit DB maintenance (checkpoint + vacuum):"
# Phase 1: fold the WAL back into the main DB and compact it so the
# conversation/audit database does not grow unbounded over long unattended runs.
# Runs only on an installed system where the DB and the `jarvis` CLI exist.
DB_PATH="${JARVIS_DB_PATH:-/home/jarvisuser/.local/share/jarvis/memory.sqlite3}"
if [ -f "$DB_PATH" ]; then
    if [ "$DRY_RUN" = true ]; then
        echo "  [DRY-RUN] Would run: jarvis db vacuum ($DB_PATH)"
    elif command -v jarvis >/dev/null 2>&1; then
        echo "  Running: jarvis db vacuum"
        jarvis db vacuum || echo "  WARN: jarvis db vacuum failed (non-fatal)"
    elif command -v python3 >/dev/null 2>&1; then
        echo "  Running: sqlite checkpoint + VACUUM via python3"
        python3 - "$DB_PATH" <<'PY' || echo "  WARN: DB maintenance failed (non-fatal)"
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
c.execute("VACUUM")
c.commit(); c.close()
PY
    else
        echo "  Skipped: no 'jarvis' CLI or python3 available"
    fi
else
    echo "  Skipped: no memory DB at $DB_PATH (build host / not installed)"
fi

echo ""
echo "4. Snapper snapshot pruning (keep recent high-risk safety net):"
# Phase 3: pre-action snapshots accumulate over long autonomous runs and can
# fill @snapshots. Prune conservatively:
#   * keep the most recent KEEP_SNAPSHOTS snapshots unconditionally, AND
#   * never delete any snapshot referenced by the most recent AUDIT_WINDOW
#     high-risk audit entries (so a recent change is always rollback-able).
KEEP_SNAPSHOTS="${JARVIS_KEEP_SNAPSHOTS:-20}"
AUDIT_WINDOW="${JARVIS_AUDIT_WINDOW:-50}"
if command -v snapper >/dev/null 2>&1; then
    # snapshot ids still needed by recent high-risk audit entries.
    protected="$(jarvis audit tail "$AUDIT_WINDOW" 2>/dev/null \
        | grep -oE '"snapshot_id":[[:space:]]*"?[0-9]+' \
        | grep -oE '[0-9]+' | sort -u || true)"
    # candidate ids = all but the newest KEEP_SNAPSHOTS (column 1 = number).
    mapfile -t all_ids < <(sudo snapper -c root list --columns number 2>/dev/null \
        | grep -oE '^[[:space:]]*[0-9]+' | grep -oE '[0-9]+' || true)
    n=${#all_ids[@]}
    if (( n > KEEP_SNAPSHOTS )); then
        for id in "${all_ids[@]:0:$((n - KEEP_SNAPSHOTS))}"; do
            [[ "$id" == "0" ]] && continue   # snapper's current-state snapshot
            if grep -qx "$id" <<<"$protected"; then
                echo "  Keeping #$id (referenced by recent audit)"
                continue
            fi
            if [ "$DRY_RUN" = true ]; then
                echo "  [DRY-RUN] Would delete snapshot #$id"
            else
                echo "  Deleting snapshot #$id"
                sudo snapper -c root delete "$id" || echo "  WARN: delete #$id failed"
            fi
        done
    else
        echo "  Nothing to prune (<= $KEEP_SNAPSHOTS snapshots)"
    fi
else
    echo "  Skipped: snapper not installed (build host / not installed)"
fi

echo ""
echo "5. ISO build work directory:"
cleanup "jarvis-work" "mkarchiso work directory"

if [ "$AGGRESSIVE" = true ]; then
    echo ""
    echo "6. [AGGRESSIVE] Source-side llama models:"
    echo "   (These will be re-downloaded on next setup.sh if needed)"
    cleanup "llama/models/" "Source model files"
    
    echo ""
    echo "7. [AGGRESSIVE] ISO staging area (will be recreated on next setup.sh):"
    cleanup "iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/models" "Staged model files"
    cleanup "iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/cpu" "Staged CPU binary"
else
    echo ""
    echo "6. [SKIPPED - use --aggressive] Source-side llama models (9.4 GB)"
    echo "   Run with --aggressive to remove (will be re-downloaded on setup.sh)"
    echo "   Or manually: rm -rf llama/models/*.gguf iso-profile/airootfs/.../llama/models/"
fi

echo ""
echo "=== Space Summary ==="
if [ "$DRY_RUN" = false ]; then
    TOTAL=$(du -sh . | cut -f1)
    echo "Project size after cleanup: $TOTAL"
else
    echo "[DRY-RUN] No changes made. Run without --dry-run to apply."
fi
