# Phase 0 test gate — reproducible procedure

This maps each Phase 0 gate item to an exact command. Because the build needs a
privileged Arch container and snapper needs an installed btrfs system, the flow
is: build ISO → install to a btrfs disk in QEMU → boot the installed system →
run the verifier.

## 1. Build the ISO (host)

```bash
ops/test/build-iso.sh           # model baked in by default; ISO -> dist/
```

Gate: `mkarchiso` build succeeds and an ISO appears in `dist/`.

## 2. Install onto a btrfs disk (QEMU, UEFI)

```bash
ops/test/qemu-install-boot.sh iso
```

Inside the live VM:

```bash
sudo jarvis-install --yes /dev/vda
```

Then power the VM off. This creates the `@ / @home / @snapshots / @var_log`
layout, snapper configs, and a systemd-boot entry.

## 3. Boot the installed system and verify (QEMU)

```bash
ops/test/qemu-install-boot.sh disk
```

Inside the installed VM:

```bash
sudo /home/jarvisuser/dev/jarvis-os/ops/test/phase0-verify.sh
```

`phase0-verify.sh` checks every gate item and prints PASS/FAIL:

| Gate item | Check |
|-----------|-------|
| ISO boots to a working `jarvisuser` session | VM reaches the Wayland shell on tty1 |
| `sudo -l -U jarvisuser` shows only the scoped list | section 1 |
| `jarvis-shell` + `llama-server` active, no `ProtectSystem` denials | sections 2–4 |
| `snapper list` works; create + rollback one snapshot | section 5 (`snapper-selftest.sh`) |

## Notes

- `llama-server` may be inactive until a model start is triggered; this is by
  design (offline-first). The baked GGUF lives under
  `/home/jarvisuser/dev/jarvis-os/llama/models/`.
- The full subvolume-level `snapper rollback` (with reboot) is exercised by the
  Phase 3 destructive drill; Phase 0 verifies create + reversible rollback.
