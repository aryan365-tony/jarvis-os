#!/usr/bin/env bash
#
# build-iso.sh - reproducible Jarvis-OS ISO build inside an Arch container.
#
# Runs the same flow the README documents, but scripted end-to-end so the
# Phase 0 test gate ("mkarchiso build succeeds") is reproducible from a clean
# checkout on a non-Arch host (Ubuntu/Debian etc.).
#
# Requirements on the host: docker OR podman with privileged support.
# The container needs --privileged because mkarchiso uses loop devices and
# mounts to assemble the squashfs/ISO.
#
# Usage:
#   ops/test/build-iso.sh                 # build with model baked in (default)
#   INCLUDE_MODELS_IN_ISO=0 ops/test/build-iso.sh
#   ENGINE=podman ops/test/build-iso.sh   # force podman (uses sudo)
#
# Output ISO is written to ./dist/ in the repo root.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$REPO_ROOT"

ENGINE="${ENGINE:-docker}"
INCLUDE_MODELS_IN_ISO="${INCLUDE_MODELS_IN_ISO:-1}"
OUT_DIR="$REPO_ROOT/dist"
mkdir -p "$OUT_DIR"

# podman generally needs sudo for --privileged loop mounts; docker (with the
# user in the docker group) does not.
SUDO=""
if [[ "$ENGINE" == "podman" ]]; then
  SUDO="sudo"
fi
command -v "$ENGINE" >/dev/null 2>&1 || { echo "ERROR: $ENGINE not found" >&2; exit 1; }

echo ">>> Building Jarvis-OS ISO via $ENGINE (INCLUDE_MODELS_IN_ISO=$INCLUDE_MODELS_IN_ISO)"

$SUDO "$ENGINE" run --rm --privileged \
  -e INCLUDE_MODELS_IN_ISO="$INCLUDE_MODELS_IN_ISO" \
  -e BUILD_LOCAL_LLAMA_BACKEND="${BUILD_LOCAL_LLAMA_BACKEND:-0}" \
  -v "$REPO_ROOT":/build/jarvis-os \
  -v "$OUT_DIR":/build/out \
  -w /build/jarvis-os \
  archlinux:latest \
  bash -euo pipefail -c '
    pacman -Sy --noconfirm
    pacman -S --noconfirm archiso base-devel git cmake rsync
    chmod +x build.sh
    ./build.sh
    cd code/iso-profile
    mkarchiso -v -w /build/work -o /build/out .
  '

echo ">>> Build complete. ISO(s):"
ls -lh "$OUT_DIR"/*.iso
