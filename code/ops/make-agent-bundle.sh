#!/usr/bin/env bash
set -euo pipefail

# Find the repository root dynamically
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

OUTPUT_ZIP="jarvis-os-src.zip"

echo "Creating AI Agent source bundle: $OUTPUT_ZIP"

# We zip only the `code/` directory and top-level gitignore, preserving structure,
# while excluding local python environments and python cache.
# We also include graphify-out/GRAPH_REPORT.md if it exists, as it's useful for agents.

# We don't include build-assets/ as those are binaries/models.

zip -q -r "$OUTPUT_ZIP" \
    code/ \
    .gitignore \
    graphify-out/GRAPH_REPORT.md \
    -x "*/__pycache__/*" \
    -x "*.pyc" \
    -x "*.egg-info/*" \
    -x "*/.venv/*" \
    -x "code/iso-profile/airootfs/home/*" \
    -x "code/iso-profile/airootfs/usr/*"

echo "Bundle created successfully."
ls -lh "$OUTPUT_ZIP"
