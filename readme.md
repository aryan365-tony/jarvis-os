# Jarvis OS — Build & Test Guide

Build the `jarvis-os` live ISO inside a container, then boot it in a VM.
Beginner-friendly: copy each block top to bottom. Just 4 steps.

- Source stays on your host; the ISO is written straight to your host.
- Only required packages are installed (small, fast, low disk usage).

---

## Prerequisites (host, one time)

```bash
# Ubuntu/Debian host
sudo apt update
sudo apt install -y podman qemu-system-x86 ovmf
```

You need ~25 GB free disk and 8 GB+ RAM.

---

## Direct Start From Current Repo

If you are already in this repository and just want to rebuild quickly:

```bash
cd ~/projects/jarvis-os

# Optional speed/size knobs
export BUILD_LOCAL_LLAMA_BACKEND=0        # skip local llama.cpp rebuild
export INCLUDE_MODELS_IN_ISO=0            # keep ISO smaller, fetch model post-boot
export SQUASHFS_ZSTD_LEVEL=15             # smaller ISO (higher = slower build)

# Stage payload + build ISO
./setup.sh
cd iso-profile
sudo mkarchiso -v -w ~/jarvis-work -o ~/jarvis-output .

# Boot latest ISO
ISO=$(ls -t ~/jarvis-output/*.iso | head -1)
env -u LD_LIBRARY_PATH -u GTK_PATH -u GDK_PIXBUF_MODULE_FILE -u LOCPATH qemu-system-x86_64 \
  -enable-kvm -m 8G -smp 4 -cpu host \
  -device virtio-vga-gl -display gtk,gl=on \
  -cdrom "$ISO" -boot d
```

Useful overrides:

- Force local backend rebuild even if an existing usable one is already bundled:

```bash
FORCE_REBUILD_LLAMA_BACKEND=1 ./setup.sh
```

- Fail fast if staged model cleanup cannot run (for fully deterministic ISO contents):

```bash
STRICT_STAGING_CLEAN=1 ./setup.sh
```

---

## Step 1 — Start the build container (host)

Copy this whole block:

```bash
# Clean old build state, enter the repo, launch the Arch container
sudo podman rm -f jarvis-build 2>/dev/null || true
sudo podman system prune -a --volumes -f
rm -rf ~/jarvis-work ~/jarvis-output
mkdir -p ~/jarvis-output
cd ~/projects/jarvis-os

sudo podman run --rm -it --privileged --network host --name jarvis-build \
  -v "$(pwd)":/root/jarvis-os \
  -v ~/jarvis-output:/root/jarvis-out \
  archlinux:latest
```

You are now **inside the container** (prompt changes to `root@...`).

---

## Step 2 — Build everything (inside container)

Copy this whole block:

```bash
# Install only what the build needs
pacman -Sy --noconfirm
pacman -S --noconfirm archiso base-devel git cmake rsync

# Build backend + stage the ISO payload, then build the ISO
cd /root/jarvis-os
chmod +x setup.sh
./setup.sh
cd iso-profile
mkarchiso -v -w /root/jarvis-work -o /root/jarvis-out .

# Leave the container when done
exit
```

Your ISO is now on the host:

```bash
ls -lh ~/jarvis-output
```

Notes:

- `setup.sh` builds and bundles the local CPU backend by default.
- `setup.sh` now reuses an already usable bundled backend in `llama/cpu/` and avoids re-cloning/rebuilding unless forced.
- If you need a faster/offline-safe setup path, skip local backend compilation:

```bash
BUILD_LOCAL_LLAMA_BACKEND=0 ./setup.sh
```

---

## Step 3 — Boot it in a VM (host)

Copy this whole block (it auto-detects the ISO name):

```bash
ISO=$(ls -t ~/jarvis-output/*.iso | head -1)

env -u LD_LIBRARY_PATH -u GTK_PATH -u GDK_PIXBUF_MODULE_FILE -u LOCPATH qemu-system-x86_64 \
  -enable-kvm \
  -m 8G -smp 4 -cpu host \
  -device virtio-vga-gl -display gtk,gl=on \
  -cdrom "$ISO" -boot d
```

> If your environment is not Snap-based, you can drop the `env -u ...` prefix.

> The `virtio-vga-gl` GPU is required — the `cage` compositor needs a real
> graphics device or the screen stays black. No GL on your host? Swap the
> display line for: `-vga virtio -display sdl`.

**VirtualBox users:** Linux / Arch (64-bit) VM, 8192 MB RAM, 4 CPUs, attach the
ISO to the optical drive, and under **Display** set Graphics Controller =
`VMSVGA` with **3D acceleration ON** (otherwise: black screen).

---

## Step 4 — Verify inside the VM

After the UI appears, or from a console (`Ctrl+Alt+F2`):

```bash
systemctl status jarvis-shell
```

At this point the OS is healthy even if no model is present.

## Optional — Download model post-boot and start inference

Model download is now intentionally **post-boot** so ISO builds stay small and
boot/debug is not blocked by GGUF packaging.

The shell now supports **any GGUF file** in
`/home/jarvisuser/dev/jarvis-os/llama/models/`.
It auto-detects models by `*.gguf` (no fixed filename required).

Inside the running VM:

```bash
# Primary path: click GO ONLINE in the top HUD.
# Behavior:
# 1) if any *.gguf already exists, it uses that model
# 2) otherwise it downloads a default model, then starts llama-server

# Optional CLI path A: run helper directly
jarvis-model-download

# Optional CLI path B: one-shot service (downloads + starts llama-server)
sudo systemctl start jarvis-model-download.service

# Start backend manually if you used CLI path A
sudo systemctl start llama-server.service

# Optional: auto-start llama-server on future boots
sudo systemctl enable llama-server.service

# Verify backend
systemctl status llama-server
curl http://127.0.0.1:8080/health
```

---

## Write to USB (only after the VM works)

```bash
lsblk                                  # find your USB device name first
ISO=$(ls -t ~/jarvis-output/*.iso | head -1)
sudo dd if="$ISO" of=/dev/sdX bs=4M status=progress oflag=sync
```

Replace `sdX` with your real device. `dd` erases the target drive — double-check.

---

## Save disk space

After a successful build, reclaim space:

```bash
rm -rf ~/jarvis-work                   # temp build tree (safe to delete)
sudo podman system prune -a -f         # drop cached container images
```

**Smaller ISO (default behavior):** GGUF files are no longer embedded unless you
explicitly opt in:

```bash
INCLUDE_MODELS_IN_ISO=1 ./setup.sh
```

Without that env var, models are fetched after boot.
`setup.sh` also clears previously staged `*.gguf` files during default builds,
so models cannot be accidentally carried over into a later ISO.

If you do opt in, any `*.gguf` files placed in `llama/models/` are embedded.

---

## Troubleshooting

**Black screen / frozen boot** — open a console with `Ctrl+Alt+F2` (tty2):

```bash
journalctl -u jarvis-shell -b --no-pager
cat /home/jarvisuser/.local/share/jarvis/cage.log
ls -l /dev/dri/        # empty = no VM GPU; enable virtio-vga-gl / VMSVGA+3D
```

- Repeated `jarvis.main exited` in `cage.log` = compositor crash-loop (usually
  the GPU issue above). Software fallback is already enabled in the image.
- `QML failed to load` = missing `qt6-declarative` / `qt6-wayland`.

**ISO owned by root** (an ISO is a disk image — never needs `chmod +x`):

```bash
sudo chown "$USER:$USER" ~/jarvis-output/*.iso
```

**llama-server not healthy:**

```bash
journalctl -u llama-server -b --no-pager
ls -lh /home/jarvisuser/dev/jarvis-os/llama/models/
jarvis-model-download
```

If multiple `*.gguf` files are present, the runtime selects the first
lexicographically sorted filename.
