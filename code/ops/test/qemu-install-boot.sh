#!/usr/bin/env bash
#
# qemu-install-boot.sh - boot the Jarvis-OS ISO in QEMU/KVM (UEFI) with a
# persistent btrfs target disk attached, so `jarvis-install` can lay the system
# down and you can then boot the *installed* system to exercise snapper.
#
# This is a UEFI VM (OVMF), because the installer's bootloader path uses
# systemd-boot on an EFI System Partition.
#
# Phase 0 test-gate flow:
#   1) ops/test/qemu-install-boot.sh iso   -> boots the live ISO; inside the VM run:
#          sudo jarvis-install --yes /dev/vda
#      then power off the VM.
#   2) ops/test/qemu-install-boot.sh disk  -> boots the INSTALLED system from the
#      disk; log in and run ops/test/snapper-selftest.sh and `sudo -l -U jarvisuser`.
#
# Requirements: qemu-system-x86_64, /dev/kvm, OVMF firmware.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DISK_IMG="${DISK_IMG:-$REPO_ROOT/dist/jarvis-target.qcow2}"
DISK_SIZE="${DISK_SIZE:-30G}"
MEM="${MEM:-8G}"
SMP="${SMP:-4}"

# Locate OVMF firmware (Debian/Ubuntu path shown; adjust OVMF_CODE/OVMF_VARS if needed).
OVMF_CODE="${OVMF_CODE:-/usr/share/OVMF/OVMF_CODE_4M.fd}"
OVMF_VARS_SRC="${OVMF_VARS:-/usr/share/OVMF/OVMF_VARS_4M.fd}"
OVMF_VARS_RUN="$REPO_ROOT/dist/OVMF_VARS.local.fd"

find_iso() { ls -t "$REPO_ROOT"/dist/*.iso 2>/dev/null | head -1; }

ensure_firmware() {
  [[ -f "$OVMF_CODE" ]] || { echo "ERROR: OVMF_CODE not found at $OVMF_CODE (install 'ovmf')." >&2; exit 1; }
  [[ -f "$OVMF_VARS_RUN" ]] || cp "$OVMF_VARS_SRC" "$OVMF_VARS_RUN"
}

ensure_disk() {
  if [[ ! -f "$DISK_IMG" ]]; then
    echo ">>> Creating target disk $DISK_IMG ($DISK_SIZE)"
    qemu-img create -f qcow2 "$DISK_IMG" "$DISK_SIZE" >/dev/null
  fi
}

common_args=(
  -enable-kvm -m "$MEM" -smp "$SMP" -cpu host -machine q35
  -drive if=pflash,format=raw,unit=0,readonly=on,file="$OVMF_CODE"
  -drive if=pflash,format=raw,unit=1,file="$OVMF_VARS_RUN"
  -device virtio-vga-gl -display gtk,gl=on
  -drive file="$DISK_IMG",if=virtio,format=qcow2
)

mode="${1:-iso}"
ensure_firmware
ensure_disk

case "$mode" in
  iso)
    ISO="$(find_iso)"; [[ -n "$ISO" ]] || { echo "ERROR: no ISO in dist/; run build-iso.sh first." >&2; exit 1; }
    echo ">>> Booting live ISO $ISO with target disk $DISK_IMG attached as /dev/vda"
    echo ">>> Inside the VM run:  sudo jarvis-install --yes /dev/vda   then power off."
    exec qemu-system-x86_64 "${common_args[@]}" -cdrom "$ISO" -boot d
    ;;
  disk)
    echo ">>> Booting the INSTALLED system from $DISK_IMG"
    exec qemu-system-x86_64 "${common_args[@]}" -boot c
    ;;
  *)
    echo "Usage: $0 [iso|disk]" >&2; exit 2 ;;
esac
