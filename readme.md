# Jarvis OS Build and Run Guide

This repository builds a bootable Arch-based live ISO with a Wayland shell and optional local llama backend.

Two supported workflows:

1. Full clean build in a container (recommended for reproducibility).
2. Direct build from your current local repo checkout.

## Prerequisites

Host requirements:

- Linux host with KVM support
- about 25 GB free disk
- 8 GB or more RAM

Install host packages (Ubuntu or Debian example):

```bash
sudo apt update
sudo apt install -y podman qemu-system-x86 ovmf
```

## Quick Start: Full Clean Build in Container

Run these commands on the host:

```bash
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

Inside the container:

```bash
pacman -Sy --noconfirm
pacman -S --noconfirm archiso base-devel git cmake rsync

cd /root/jarvis-os
chmod +x setup.sh
./setup.sh

cd iso-profile
mkarchiso -v -w /root/jarvis-work -o /root/jarvis-out .
exit
```

Back on the host, verify ISO output:

```bash
ls -lh ~/jarvis-output/*.iso
```

## Quick Start: Direct Build From Current Repo

If your host already has build tools and you want a faster loop:

```bash
cd ~/projects/jarvis-os

# Optional knobs
export BUILD_LOCAL_LLAMA_BACKEND=1
export INCLUDE_MODELS_IN_ISO=0
export SQUASHFS_ZSTD_LEVEL=15

./setup.sh
cd iso-profile
sudo mkarchiso -v -w ~/jarvis-work -o ~/jarvis-output .
```

Useful overrides:

```bash
# Skip local backend compilation entirely
BUILD_LOCAL_LLAMA_BACKEND=0 ./setup.sh

# Force backend rebuild even if an existing bundled one is usable
FORCE_REBUILD_LLAMA_BACKEND=1 ./setup.sh

# Fail if staged model cleanup cannot complete
STRICT_STAGING_CLEAN=1 ./setup.sh
```

## Boot the Latest ISO in QEMU

Run on host:

```bash
ISO=$(ls -t ~/jarvis-output/*.iso | head -1)

env -u LD_LIBRARY_PATH -u GTK_PATH -u GDK_PIXBUF_MODULE_FILE -u LOCPATH qemu-system-x86_64 \
  -enable-kvm \
  -m 8G -smp 4 -cpu host \
  -device virtio-vga-gl -display gtk,gl=on \
  -cdrom "$ISO" -boot d
```

If your environment is not Snap-based, remove the env -u prefix.

For hosts without GL support, use:

```bash
qemu-system-x86_64 -enable-kvm -m 8G -smp 4 -cpu host -vga virtio -display sdl -cdrom "$ISO" -boot d
```

VirtualBox note:

- Use Linux/Arch (64-bit)
- Set RAM to 8192 MB and CPU to 4
- Set Graphics Controller to VMSVGA
- Enable 3D acceleration

## First Boot Checks Inside VM

After UI appears, or from tty2 (Ctrl+Alt+F2):

```bash
systemctl status jarvis-shell
```

Expected: shell service is active even when no model is installed yet.

## Model and Backend Runtime Behavior

The runtime supports any GGUF model in:

```text
/home/jarvisuser/dev/jarvis-os/llama/models/
```

GO ONLINE behavior:

1. If one or more .gguf files already exist, one is auto-selected.
2. If no model exists, default model download is triggered.
3. llama-server is started after model availability checks pass.

Manual runtime commands inside VM:

```bash
# Download model helper
jarvis-model-download

# One-shot service: download then start backend
sudo systemctl start jarvis-model-download.service

# Start backend manually
sudo systemctl start llama-server.service

# Enable backend on future boots
sudo systemctl enable llama-server.service

# Health checks
systemctl status llama-server
curl http://127.0.0.1:8080/health
```

## ISO Size and Build Performance

Default behavior keeps ISOs smaller by not embedding models.

To embed models in ISO intentionally:

```bash
INCLUDE_MODELS_IN_ISO=1 ./setup.sh
```

When model embedding is disabled, setup.sh clears previously staged .gguf files to prevent accidental carryover between builds.

## Write ISO to USB

Only do this after VM validation:

```bash
lsblk
ISO=$(ls -t ~/jarvis-output/*.iso | head -1)
sudo dd if="$ISO" of=/dev/sdX bs=4M status=progress oflag=sync
```

Replace /dev/sdX with the correct USB target.

## Troubleshooting

Black screen or frozen UI:

```bash
journalctl -u jarvis-shell -b --no-pager
cat /home/jarvisuser/.local/share/jarvis/cage.log
ls -l /dev/dri/
```

If /dev/dri is empty, VM GPU passthrough config is missing. Use virtio-vga-gl in QEMU or VMSVGA + 3D in VirtualBox.

llama-server issues:

```bash
journalctl -u llama-server -b --no-pager
ls -lh /home/jarvisuser/dev/jarvis-os/llama/models/
jarvis-model-download
```

ISO ownership fix on host:

```bash
sudo chown "$USER:$USER" ~/jarvis-output/*.iso
```
