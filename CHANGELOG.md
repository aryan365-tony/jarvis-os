# Changelog

All notable changes to Jarvis-OS are recorded here, one entry per implemented
phase of the implementation plan.

## Phase 6 — Integration, Soak & Acceptance

### Added
- `ops/test/phase6-integration.sh`: end-to-end acceptance gate run inside the
  installed VM — validates the full tool surface + tiers, that the dead network
  policy is gone, a high-risk call snapshots and links in the audit chain,
  chain integrity + self-review, DB checkpoint/vacuum with no data loss, honest
  voice status, and a configurable soak (`SOAK_TURNS`) that must leave the chain
  intact and the shell out of a crash loop.
- `ops/test/PHASE6-ACCEPTANCE.md`: the final acceptance checklist and how to run
  every gate (build → install/boot → phase0 → snapper → phase6).

## Phase 5 — Voice-First Interaction & Presence

### Added
- `voice/pipeline.py`: `VoicePipeline` — the engine-agnostic async state machine
  (IDLE → LISTENING → THINKING → SPEAKING) with **barge-in** (user can cut off
  speech any time) and token-streaming so TTS starts on the first token. Fully
  unit-testable with injected fake engines (no audio hardware needed).
- `voice/engines.py` + `voice/engines_impl.py`: guarded detection and concrete
  engines — openWakeWord (wake/VAD), faster-whisper (STT, sized from
  `detect_gpu.py`), piper (TTS) over sounddevice. All optional; missing engine or
  mic degrades to text.
- `voice/__init__.py`: `VoiceService` now builds and supervises the real pipeline
  when engines are present AND the agent is wired, else emits an honest
  UNAVAILABLE/DEGRADED status. Voice and text drive the **same** agent (unified
  history).
- `events.py`: `VOICE_ACTIVITY` topic + `VoiceActivity`/`VoicePhase` payloads.
- `ui_bridge.py`: `_voice_agent_turn` (routes spoken turns through the shared
  agent, mirroring transcript + streamed reply into the conversation view) and a
  `voiceActivity` Qt signal.
- QML `components/VoiceOrb.qml`: central voice-presence orb — idle breathing,
  level-reactive listening ring, thinking orbiter, speaking pulse — wired to
  `jarvis.voiceActivity`, with a live caption under it (`Main.qml`).
- ISO packages: pipewire/pipewire-pulse/wireplumber, python-sounddevice,
  python-numpy, python-psutil, brightnessctl; `[voice]` optional extra in
  `pyproject.toml` for the pip-installed engines.
- Tests: `tests/test_phase5_voice.py` — full-cycle phase transitions +
  barge-in cancellation (40 tests total pass).

## Phase 4 — Audit Chain Completeness & Self-Review

### Added
- `tools/audit_review.py`: `audit_review` (low, read-only) — lets the agent
  review its own recent actions (event, tier, linked snapshot) and confirm the
  SHA-256 hash chain is intact. It is the ONLY audit-facing tool; there is no
  tool to delete/edit/truncate entries, so the agent cannot erase its trail.
- Tests: `tests/test_phase4_audit.py` — chain stays intact across writes,
  tamper is detected at the exact entry, review reports intact/broken + filters
  (38 tests total pass).

### Notes
- Full tool-execution audit coverage (every call logs
  `tool_call_start/ok/error/denied` with `tier` + `snapshot_id`), boot-time
  chain verification (`runtime._verify_audit_on_boot`), and the
  `jarvis audit verify|tail` CLI were delivered in Phase 1; Phase 4 completes the
  loop by giving the agent read-only self-review.

## Phase 3 — Snapshot Safety Net & Collapsed Approval

### Added
- `tools/snapshot.py`: `create_pre_action_snapshot()` (called by the approval
  path, not the model), plus registered tools `snapshot_list` (low) and
  `snapshot_rollback` (high) over the scoped `sudo snapper` grant.
- `ui_bridge.request_tool_approval()`: the real approval logic replacing the
  auto-approve stub. Collapsed by tier — low/medium approve instantly; **high**
  takes a pre-action snapper snapshot first, writes a `high_risk_action` audit
  entry, and threads the `snapshot_id` back so the change is precisely
  undoable. If the snapshot cannot be taken, the high-risk action is **denied**
  (no irreversible action ever runs without its safety net).
- Tests: `tests/test_phase3_snapshots.py` (34 tests total pass).

### Changed
- `ops/rollback.sh`: rewritten from the old grub-reboot hack to `snapper
  rollback` (interactive list-and-pick or `rollback.sh <id>`; reboot to apply).
- `ops/cleanup-space.sh`: prunes old snapper snapshots but **keeps** the newest
  N and any snapshot still referenced by the most recent high-risk audit
  entries, so a recent change stays rollback-able.
- `tools/__init__.py`: registers the snapshot tools.

## Phase 2 — Full-System Tool Surface & Privilege Boundary

### Added
- `tools/fs_ops.py`: `fs_read` (low), `fs_scratch` (low, confined to the scratch
  dir, no root) and `fs_system` (high, routed through the root helper).
- `iso-profile/airootfs/usr/local/bin/jarvis-fsop`: the **single** root
  filesystem-mutation helper (verbs write/mkdir/rm/chmod/chown/copy/move/cat),
  with a realpath-canonicalised denylist protecting boot, sudoers, secrets, the
  audit store, and itself. This — not the Python — is the fs privilege boundary.
  Every invocation is logged to journald before acting.
- `tools/pkg_manage.py`: `pkg_query` (low) + `pkg_manage` (high) via scoped
  `sudo pacman`, package names charset-validated.
- `tools/svc_control.py`: `svc_status` (low) + `svc_control` (medium) via scoped
  `sudo systemctl`.
- `tools/proc_manage.py`: `proc_list` (low) + `proc_kill` (medium) via psutil;
  refuses pid ≤ 1 and the shell's own process.
- `tools/diagnostics.py`: `diag_journal` / `diag_dmesg` / `diag_resources` (all
  low, read-only, size-capped).
- `tools/display_control.py`: `display_brightness` / `session_lock` (low).
- `registry.ApprovalResult` (carries the pre-action `snapshot_id`) and
  `get_risk_tier()`.
- `psutil>=5.9` dependency (lock files regenerated).
- Tests: `tests/test_registry_tiers.py`, `tests/test_tools_phase2.py`
  (28 tests total pass).

### Changed
- `tools/registry.py`: risk tiers migrated to **low / medium / high** (legacy
  safe/reversible/irreversible mapped forward and rejected-if-unknown at
  registration, so a tier is mandatory). `high` tier now takes a pre-action
  snapshot via the approver and threads `snapshot_id` into the audit entry.
  Added a global `PER_TURN_TOOL_BUDGET` ceiling on top of per-tool limits.
- `shell_exec` and `optimize_backend` retiered to `high`.
- `config.PolicyConfig`: added `fs_scratch_dir`, raised `max_tool_calls_per_turn`
  to 12, removed the dead `network_allowlist_path`.
- `iso-profile/profiledef.sh`: `jarvis-fsop` installed 0:0:755.
- `customize_airootfs.sh`: creates `/home/jarvisuser/scratch` (jarvisuser-owned).
- `jarvis-shell.service`: added `/home/jarvisuser/scratch` to ReadWritePaths.

### Removed
- `tools/network_policy.py` and `config/network_allowlist.txt` — dead
  configuration; the image is offline by design (no egress path exists).

### Resolved (Phase 0 landmine)
- `NoNewPrivileges=yes` was **removed** from `jarvis-shell.service`. It
  categorically blocks the setuid `sudo` that every Phase 2 privileged tool
  needs, and per the plan the fix is to drop NNP on the shell — **not** to widen
  sudoers. The real boundary is the five-command scoped sudoers allow-list plus
  the denylist-guarded `jarvis-fsop`; the rest of the sandbox (ProtectSystem=
  strict, ProtectHome=read-only, PrivateTmp) stays on.

## Phase 1 — Runtime Reliability Upgrades

### Added
- `eventbus.py`: durable **audit_events** channel alongside the existing
  bounded, drop-oldest **ui_events** behavior. Durable topics
  (`events.DURABLE_TOPICS` = `AUDIT_EVENTS`) get unbounded subscriber queues and
  a non-dropping publish; `durable_published`/`durable_dropped` counters expose
  the zero-drop guarantee to the test gate.
- `events.py`: `AUDIT_EVENTS` topic, `DURABLE_TOPICS`, and the `AuditEvent`
  payload.
- `supervisor.py`: `SupervisedTask`/`Supervisor` — restart-with-exponential-backoff
  for background asyncio loops, with a restart **cap** that surfaces persistent
  crash loops to the audit log instead of looping forever.
- `cli.py`: headless `jarvis audit verify|tail` and `jarvis db checkpoint|vacuum`
  subcommands (no Qt import), dispatched from `main()`.
- `audit/chain.py`: `verify_chain_detailed()` (returns first broken entry id),
  `tail()`, and durable-channel mirroring via `set_audit_bus()`.
- Tests: `tests/test_eventbus_durable.py`, `tests/test_supervisor.py`,
  `tests/test_db_durability.py` (11 tests total pass).

### Changed
- `db.py`: explicit WAL + `synchronous=NORMAL` + `busy_timeout`; `checkpoint()`
  (WAL truncate) and `vacuum()`; DB + WAL/SHM sidecars chmod **0600**; optional
  SQLCipher-at-rest when `memory.encrypt_at_rest` is set and the driver is
  present (falls back to plaintext + LUKS/0600).
- `config.py`: `MemoryConfig.encrypt_at_rest` + `key_path`.
- `runtime.py`: marks the durable channel, attaches the audit bus, runs the
  supervised background loops, and verifies the audit chain on boot (warn, never
  block).
- `readiness.py` / `voice/__init__.py`: added `run()` entrypoints so the
  supervisor owns their task lifecycle.
- `systemd/jarvis-shell.service`: `StartLimitIntervalSec`/`StartLimitBurst` cap
  process-level crash loops.
- `ops/cleanup-space.sh`: automatic DB checkpoint + VACUUM on run.

### Flagged (not silently changed)
- At-rest encryption: a full-strength secret cannot be both zero-login-autonomous
  and interactively unlocked. Implemented layered defence (0600 owner-only +
  optional SQLCipher + installer LUKS-on-@home option); LUKS auto-unlock (TPM)
  is left as a documented opt-in because it is hardware-specific and not
  QEMU-testable.

## Phase 0 — Base OS Hardening & Boot Foundation

Architecture decision: Jarvis-OS is an **installed** btrfs system (not live-only),
so the Phase 3 snapshot safety net has a real filesystem to operate on. A new
installer clones the live payload onto a disk with the required subvolume layout.

### Added
- `iso-profile/airootfs/etc/sudoers.d/jarvis-agent`: scoped passwordless sudo for
  `jarvisuser`, limited to exactly `pacman, systemctl, btrfs, snapper,
  /usr/local/bin/jarvis-fsop`. Hard boundary — never widened to `NOPASSWD: ALL`.
- `iso-profile/airootfs/usr/local/bin/jarvis-install`: offline btrfs installer that
  lays down `@ / @home / @snapshots / @var_log`, clones the live rootfs, writes an
  installed-system mkinitcpio + systemd-boot path, and configures snapper for `/`
  and `/home`.
- Live-ISO packages for the install/snapshot foundation: `btrfs-progs`, `snapper`,
  `gptfdisk`, `dosfstools`, `arch-install-scripts`.
- Pre-created writable dirs (`~/.local/share/jarvis`, `~/.cache`, `~/.config`,
  `/var/lib/jarvis`) so the hardened service mount namespaces have valid bind
  targets at first boot.
- Reproducible test harness under `ops/test/`: `build-iso.sh`,
  `qemu-install-boot.sh`, `snapper-selftest.sh`, `phase0-verify.sh`, and
  `PHASE0-TESTS.md` mapping each gate item to a command.
- `jarvis-shell/uv.lock` and `jarvis-shell/requirements.lock.txt`: hash-pinned
  dependency locks.

### Changed
- `systemd/jarvis-shell.service` and `systemd/llama-server.service`: hardened with
  `ProtectSystem=strict`, `ProtectHome=read-only`, `NoNewPrivileges=yes`,
  `PrivateTmp=yes`, and a `ReadWritePaths` living-list covering the real write
  paths (DB, cage.log, Qt caches, `/var/lib/jarvis`, Wayland runtime dir).
- `setup.sh`: the GGUF model is now **baked into the ISO by default**
  (`INCLUDE_MODELS_IN_ISO=1` default); set `=0` to opt out and import from USB.
- `systemd/jarvis-model-download.service`: converted to a manual/offline-import
  helper only — `[Install]` section removed so it can never auto-start at boot.
- `iso-profile/profiledef.sh`: `file_permissions` for the sudoers drop-in (0440)
  and the installer (0755).
- `iso-profile/airootfs/root/customize_airootfs.sh`: create `/var/lib/jarvis`
  owned by `jarvisuser`.

### Flagged (not silently changed)
- `NoNewPrivileges=yes` on `jarvis-shell.service` blocks setuid `sudo`, which the
  Phase 2 tools require. Applied as the plan specifies; Phase 2 must resolve it
  (drop NNP on the shell or route privileged tool execution through a separate
  root helper unit) rather than widening the sudoers scope.
- The existing `tools/registry.py` risk tiers are `safe/reversible/irreversible`
  while the plan (Phases 2–3) uses `low/medium/high` + `registry.get_risk_tier()`;
  to be reconciled in Phase 2.
