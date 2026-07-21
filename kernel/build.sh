#!/usr/bin/env bash
set -euo pipefail
LINUX_DIR="${1:-$HOME/dev/linux}"
FRAG="$(dirname "$0")/jarvis.config"

cd "$LINUX_DIR"
git rev-parse --verify jarvis-os >/dev/null 2>&1 || git checkout -b jarvis-os
make defconfig
./scripts/kconfig/merge_config.sh .config "$FRAG"
# olddefconfig resolves any new deps merge_config introduced, non-interactively
make olddefconfig
make -j"$(nproc)" 2>&1 | tee "$(dirname "$0")/last-build.log"
echo "Build complete. Run 'make modules_install' and 'make install' manually,
against a scratch root, only from Phase 5."
