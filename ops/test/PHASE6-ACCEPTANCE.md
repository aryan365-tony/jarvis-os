# Jarvis-OS — Phase 6 Acceptance & Soak Report

This document is the final acceptance checklist for the full tech upgrade
(Phases 0–6). Run the scripts below on the appropriate machine and record the
results. Local Python unit tests are already green on the dev host (see
"Local test status").

## How to run the gates

| Gate | Where | Command |
|------|-------|---------|
| Build the ISO | Build host (needs `mkarchiso`) | `sudo ops/test/build-iso.sh` |
| Install + first boot | QEMU (host has `qemu` + KVM) | `ops/test/qemu-install-boot.sh` |
| Phase 0 (hardening) | Inside the installed VM | `sudo ops/test/phase0-verify.sh` |
| Snapper safety net | Inside the installed VM | `sudo ops/test/snapper-selftest.sh` |
| Phase 6 (integration + soak) | Inside the installed VM | `SOAK_TURNS=200 ops/test/phase6-integration.sh` |

## Local test status (dev host, no privileged build)

Run from `jarvis-shell/`:

```
uv run --with pytest --with pytest-asyncio --with PyQt6 --with httpx --with psutil \
    python -m pytest -q
```

Expected: **all tests pass** covering
- Phase 1: durable event channel (zero drop under load), task supervisor
  backoff/cap, DB WAL/checkpoint/vacuum/0600.
- Phase 2: registry tier migration, per-tool + global budgets, high-tier
  snapshot threading, and each tool via mocked subprocess.
- Phase 3: pre-action snapshot + collapsed approval (high denied without a
  snapshot).
- Phase 4: hash-chain tamper detection at the exact entry, audit self-review.
- Phase 5: voice pipeline phase transitions + barge-in cancellation.

## Acceptance checklist

- [ ] ISO builds reproducibly (`build-iso.sh` exits 0).
- [ ] VM installs to btrfs (@/@home/@snapshots/@var_log) and boots to the kiosk
      shell with **no login prompt**.
- [ ] `phase0-verify.sh` — sudo scope is EXACTLY the five allow-listed commands;
      no `NOPASSWD: ALL`; unit sandboxing active; no namespace denials.
- [ ] `NoNewPrivileges` is NOT set on `jarvis-shell` (Phase 2 resolution) but
      ProtectSystem=strict / ProtectHome=read-only remain
      (`systemctl show jarvis-shell -p NoNewPrivileges,ProtectSystem`).
- [ ] Agent can install/remove a package; a **pre-action snapshot** appears in
      `snapper -c root list` and is linked in `jarvis audit tail`.
- [ ] `ops/rollback.sh <id>` restores the pre-action snapshot; reboot lands in
      the restored state.
- [ ] `jarvis audit verify` reports the chain INTACT; tampering with a row makes
      it report BROKEN at that entry.
- [ ] `audit_review` tool returns recent actions with tiers + snapshot ids.
- [ ] Voice: with engines installed, the orb cycles idle→listening→thinking→
      speaking and barge-in interrupts speech; without engines, the shell runs
      text-only and says so.
- [ ] `phase6-integration.sh` — **PHASE 6 GATE: ALL CHECKS PASSED**.
- [ ] Soak (`SOAK_TURNS=1000`) leaves the audit chain intact and the shell
      active (no crash loop / StartLimit trip).

## Notes / known limitations

- Voice engines (openWakeWord / faster-whisper / piper) are installed
  best-effort at image build time; a build host without network yields a
  text-only image (by design — voice is an optional accelerator).
- LUKS auto-unlock (TPM) for at-rest encryption is a documented installer
  opt-in, not exercised in QEMU.
