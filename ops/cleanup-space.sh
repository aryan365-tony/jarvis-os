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
echo "3. ISO build work directory:"
cleanup "jarvis-work" "mkarchiso work directory"

if [ "$AGGRESSIVE" = true ]; then
    echo ""
    echo "4. [AGGRESSIVE] Source-side llama models:"
    echo "   (These will be re-downloaded on next setup.sh if needed)"
    cleanup "llama/models/" "Source model files"
    
    echo ""
    echo "5. [AGGRESSIVE] ISO staging area (will be recreated on next setup.sh):"
    cleanup "iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/models" "Staged model files"
    cleanup "iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/cpu" "Staged CPU binary"
else
    echo ""
    echo "4. [SKIPPED - use --aggressive] Source-side llama models (9.4 GB)"
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
