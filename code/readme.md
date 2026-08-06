# Jarvis OS Step-by-Step Build and Usage Guide

This guide is written for a new machine starting from an empty folder on the host. Follow the steps in order and you will end at a booted Jarvis OS ISO in QEMU.

## What You Will Do

1. Create a clean workspace on the host.
2. Install the minimum host tools.
3. Clone this repository.
4. Start a clean Arch build container.
5. Run the staging script.
6. Build the ISO with `mkarchiso`.
7. Boot the ISO in QEMU.
8. Verify the UI and backend behavior inside the VM.

## Host Requirements

You need:

- a Linux host
- KVM virtualization support
- about 25 GB free disk space
- at least 8 GB RAM

Ubuntu or Debian host setup:

```bash
sudo apt update
sudo apt install -y git podman qemu-system-x86 ovmf
```

Optional quick KVM check:

```bash
ls /dev/kvm
```

If `/dev/kvm` exists, hardware acceleration is available.

## Step 1: Create a Clean Working Folder

Run this on the host:

```bash
mkdir -p ~/jarvis-build-from-scratch
cd ~/jarvis-build-from-scratch
```

This folder can be completely empty before you start.

## Step 2: Clone the Repository

Run this on the host:

```bash
git clone https://github.com/aryan365-tony/jarvis-os.git
cd jarvis-os
```

At this point you should see files like `setup.sh`, `iso-profile/`, `jarvis-shell/`, and `llama/`.

## Step 3: Prepare Clean Output Paths

Run this on the host:

```bash
rm -rf ~/jarvis-work ~/jarvis-output
mkdir -p ~/jarvis-output
```

Purpose:

- `~/jarvis-work` is the temporary ISO build workspace
- `~/jarvis-output` is where the finished ISO will be written

## Step 4: Start the Arch Build Container

Run this on the host from inside the cloned repo:

```bash
sudo podman rm -f jarvis-build 2>/dev/null || true

sudo podman run --rm -it \
  --privileged \
  --network host \
  --name jarvis-build \
  -v "$(pwd)":/root/jarvis-os \
  -v ~/jarvis-output:/root/jarvis-out \
  archlinux:latest
```

After this, your shell prompt changes and you are inside the container.

## Step 5: Install Build Dependencies Inside the Container

Run this inside the container:

```bash
pacman -Sy --noconfirm
pacman -S --noconfirm archiso base-devel git cmake rsync
```

These are the only required packages for the default build flow.

## Step 6: Stage the Jarvis OS Payload

Run this inside the container:

```bash
cd /root/jarvis-os
chmod +x setup.sh
./setup.sh
```

What `setup.sh` does:

- stages the project into the Arch ISO filesystem tree
- keeps integrated llama backend build enabled by default
- reuses an already usable local backend when possible
- avoids embedding GGUF models by default, so the ISO stays smaller

## Step 7: Build the ISO

Run this inside the container:

```bash
cd /root/jarvis-os/iso-profile
mkarchiso -v -w /root/jarvis-work -o /root/jarvis-out .
```

When this finishes successfully, exit the container:

```bash
exit
```

## Step 8: Verify the ISO Was Created

Run this on the host:

```bash
ls -lh ~/jarvis-output/*.iso
```

You should see one newly created ISO file.

If the ISO is owned by root and you want normal user ownership:

```bash
sudo chown "$USER:$USER" ~/jarvis-output/*.iso
```

## Step 9: Boot the ISO in QEMU

Run this on the host:

```bash
ISO=$(ls -t ~/jarvis-output/*.iso | head -1)

env -u LD_LIBRARY_PATH -u GTK_PATH -u GDK_PIXBUF_MODULE_FILE -u LOCPATH qemu-system-x86_64 \
  -enable-kvm \
  -m 8G \
  -smp 4 \
  -cpu host \
  -device virtio-vga-gl \
  -display gtk,gl=on \
  -cdrom "$ISO" \
  -boot d
```

If your host is not running inside a Snap environment, you can usually remove the `env -u ...` prefix.

If OpenGL display fails on your host, use this fallback instead:

```bash
ISO=$(ls -t ~/jarvis-output/*.iso | head -1)

qemu-system-x86_64 \
  -enable-kvm \
  -m 8G \
  -smp 4 \
  -cpu host \
  -vga virtio \
  -display sdl \
  -cdrom "$ISO" \
  -boot d
```

## Step 10: Confirm the VM Reaches the Jarvis UI

Expected result:

- the system boots fully
- the Wayland UI appears
- the shell is usable even if no model has been downloaded yet

If you need a console inside the VM, use `Ctrl+Alt+F2`.

Check shell service health inside the VM:

```bash
systemctl status jarvis-shell
```

## Step 10a: Install Jarvis-OS to Disk (btrfs system)

The live ISO now ships an installer that lays down a **persistent btrfs system**
with the subvolume layout the snapshot safety net needs
(`@`, `@home`, `@snapshots`, `@var_log`) and configures `snapper` for `/` and
`/home`. Run it from the live environment (a console via `Ctrl+Alt+F2`):

```bash
lsblk                       # identify the target disk, e.g. /dev/vda
sudo jarvis-install /dev/vda
```

The installer partitions GPT (ESP + btrfs), clones the live rootfs, installs
systemd-boot, and enables `jarvis-shell`. Reboot into the installed system
(remove the ISO):

```bash
sudo systemctl reboot
```

To exercise install + first boot automatically in QEMU from the host, use:

```bash
ops/test/qemu-install-boot.sh
```

## Step 10b: Run the Acceptance Gates (inside the installed VM)

```bash
cd /home/jarvisuser/dev/jarvis-os
sudo ops/test/phase0-verify.sh          # hardening + scoped sudo + snapshots
sudo ops/test/snapper-selftest.sh       # snapshot create + rollback
SOAK_TURNS=200 ops/test/phase6-integration.sh   # full stack + soak
```

The acceptance checklist and how-to for every gate is in
`ops/test/PHASE6-ACCEPTANCE.md`.

## Step 10c: Autonomy — Tools, Snapshots, Audit, Voice

The agent now controls the whole system through a **risk-tiered** tool registry.
Every tool declares a tier at registration:

- **low** — read-only / sandboxed (runs instantly): `fs_read`, `fs_scratch`
  (writes confined to `~/scratch`), `pkg_query`, `svc_status`, `proc_list`,
  `diag_journal`/`diag_dmesg`/`diag_resources`, `display_brightness`,
  `session_lock`, `snapshot_list`, `audit_review`.
- **medium** — recoverable state changes (instant): `svc_control`, `proc_kill`.
- **high** — irreversible/system-altering: `pkg_manage` (install/remove/upgrade),
  `fs_system` (via the audited root helper `jarvis-fsop`), `snapshot_rollback`,
  `shell_exec`, `optimize_backend`. **Before any high-tier action runs, a
  pre-action `snapper` snapshot is taken automatically** and linked into the
  tamper-evident audit chain — so anything the agent does can be rolled back.

Privilege boundary: the agent's entire root surface is the five scoped commands
in `/etc/sudoers.d/jarvis-agent` (`pacman`, `systemctl`, `btrfs`, `snapper`,
`jarvis-fsop`). It is **never** granted `NOPASSWD: ALL`.

Headless CLI (works without the GUI):

```bash
jarvis audit verify        # walk the hash chain; report first broken entry
jarvis audit tail 20       # last 20 audited actions (tool, tier, snapshot id)
jarvis db checkpoint       # fold the WAL back into the DB
jarvis db vacuum           # compact the conversation/audit DB
```

Undo a change the agent made:

```bash
snapper -c root list                 # find the pre-action snapshot id
sudo ops/rollback.sh <snapshot_id>   # or run with no args to pick interactively
sudo systemctl reboot                # boot into the restored state
```

Housekeeping (checkpoints the DB and prunes old snapshots, keeping the recent
high-risk safety net referenced by the audit log):

```bash
ops/cleanup-space.sh                 # add --dry-run to preview
```

Voice: the shell is voice-first. When the optional engines
(openWakeWord + faster-whisper + piper) and a microphone are present, say the
wake word and the central **orb** cycles idle → listening → thinking → speaking;
you can **barge in** to interrupt speech. Voice and text drive the *same* agent,
so history is shared. Without engines/mic the shell runs text-only and clearly
says so — voice is an optional accelerator, never a gate. Toggle in
`jarvis-shell/config/jarvis.toml` under `[voice]`.

At-rest memory: the conversation/audit DB is always `0600` owner-only. Optional
SQLCipher encryption is available via `[memory] encrypt_at_rest = true` when the
`pysqlcipher3` driver is present; full-disk LUKS on `@home` is an installer
opt-in.

## Step 11: Use the Runtime After Boot

The UI can operate before any model is downloaded.

Model directory inside the VM:

```text
/home/jarvisuser/dev/jarvis-os/llama/models/
```

Runtime behavior when you press GO ONLINE:

1. If any `.gguf` model already exists, it is selected automatically.
2. If no model exists, the default model is downloaded.
3. `llama-server` is started after model validation succeeds.

Manual commands inside the VM:

```bash
# Download a model
jarvis-model-download

# Download model and start the backend service
sudo systemctl start jarvis-model-download.service

# Start backend manually
sudo systemctl start llama-server.service

# Make backend start automatically on future boots
sudo systemctl enable llama-server.service

# Verify backend health
systemctl status llama-server
curl http://127.0.0.1:8080/health
```

## Step 12: Optional Build Controls

Default behavior is the recommended path. Use overrides only when you need them.

Inside the repo, before running `./setup.sh`:

```bash
# Skip local llama backend compilation
BUILD_LOCAL_LLAMA_BACKEND=0 ./setup.sh

# Force local backend rebuild even if an existing one is usable
FORCE_REBUILD_LLAMA_BACKEND=1 ./setup.sh

# Embed local GGUF models into the ISO
INCLUDE_MODELS_IN_ISO=1 ./setup.sh

# Fail if staged cleanup cannot complete
STRICT_STAGING_CLEAN=1 ./setup.sh
```

## Step 13: Troubleshooting

### Black Screen or Frozen UI

Inside the VM console:

```bash
journalctl -u jarvis-shell -b --no-pager
cat /home/jarvisuser/.local/share/jarvis/cage.log
ls -l /dev/dri/
```

If `/dev/dri/` is empty, the VM does not have a usable virtual GPU. Use `virtio-vga-gl` in QEMU or enable `VMSVGA` plus 3D acceleration in VirtualBox.

### llama-server Does Not Start

Inside the VM:

```bash
journalctl -u llama-server -b --no-pager
ls -lh /home/jarvisuser/dev/jarvis-os/llama/models/
jarvis-model-download
```

### Build Artifacts Use Too Much Disk

On the host:

```bash
rm -rf ~/jarvis-work
sudo podman system prune -a -f
```

## Step 14: Optional USB Write After VM Validation

Only do this after the ISO works in QEMU.

On the host:

```bash
lsblk
ISO=$(ls -t ~/jarvis-output/*.iso | head -1)
sudo dd if="$ISO" of=/dev/sdX bs=4M status=progress oflag=sync
```

Replace `/dev/sdX` with the correct target device.

## One-Block Summary

If you already understand the process and just want the shortest working path:

```bash
mkdir -p ~/jarvis-build-from-scratch
cd ~/jarvis-build-from-scratch
sudo apt update
sudo apt install -y git podman qemu-system-x86 ovmf
git clone https://github.com/aryan365-tony/jarvis-os.git
cd jarvis-os
rm -rf ~/jarvis-work ~/jarvis-output
mkdir -p ~/jarvis-output
sudo podman rm -f jarvis-build 2>/dev/null || true
sudo podman run --rm -it --privileged --network host --name jarvis-build \
  -v "$(pwd)":/root/jarvis-os \
  -v ~/jarvis-output:/root/jarvis-out \
  archlinux:latest
```

Then inside the container:

```bash
pacman -Sy --noconfirm
pacman -S --noconfirm archiso base-devel git cmake rsync
cd /root/jarvis-os
chmod +x setup.sh
./setup.sh
cd /root/jarvis-os/iso-profile
mkarchiso -v -w /root/jarvis-work -o /root/jarvis-out .
exit
```

Then back on the host:

```bash
ISO=$(ls -t ~/jarvis-output/*.iso | head -1)
env -u LD_LIBRARY_PATH -u GTK_PATH -u GDK_PIXBUF_MODULE_FILE -u LOCPATH qemu-system-x86_64 \
  -enable-kvm -m 8G -smp 4 -cpu host \
  -device virtio-vga-gl -display gtk,gl=on \
  -cdrom "$ISO" -boot d
```
