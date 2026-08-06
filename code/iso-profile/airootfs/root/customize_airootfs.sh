#!/usr/bin/env bash
set -euo pipefail

# Create jarvisuser and set permissions.
# The `seat` group is required so cage/libseat can talk to seatd without a
# graphical login manager; without it the compositor fails and the screen
# stays black.
useradd -m -U -G wheel,video,audio,input,seat -s /bin/bash jarvisuser || true
usermod -aG seat jarvisuser || true
chown -R jarvisuser:jarvisuser /home/jarvisuser

# Agent runtime state dir must be writable by the sandboxed shell service
# (systemd ReadWritePaths=/var/lib/jarvis under ProtectSystem=strict).
install -d -o jarvisuser -g jarvisuser -m 0750 /var/lib/jarvis

# Phase 2: agent fs sandbox. Low-tier fs_scratch confines writes here; the shell
# service lists it in ReadWritePaths. Owned by jarvisuser (no root needed).
install -d -o jarvisuser -g jarvisuser -m 0755 /home/jarvisuser/scratch

# Install the jarvis console script (`jarvis audit|db ...`) system-wide without
# touching the pacman-managed deps (PyQt6/httpx/psutil come from packages).
# --break-system-packages is required because Arch marks its Python as
# externally-managed (PEP 668). Non-fatal: the shell also runs from source.
if ! pip install --no-deps --break-system-packages \
        /home/jarvisuser/dev/jarvis-os/jarvis-shell; then
  echo "WARN: could not install 'jarvis' CLI entrypoint; source still works" >&2
fi

# Phase 5: voice engines are OPTIONAL accelerators. Install best-effort; if the
# build host has no network or a wheel is unavailable, the shell degrades to
# text (see jarvis.voice). Never fail the build over voice. sounddevice is here
# (not in packages.x86_64) because python-sounddevice is AUR-only; the pip wheel
# binds to the system libportaudio provided by the 'portaudio' package.
if ! pip install --break-system-packages \
        sounddevice openwakeword faster-whisper piper-tts; then
  echo "WARN: voice engines not installed; shell will run text-only" >&2
fi

# Enable necessary services
# llama-server is intentionally left disabled by default so the system can boot
# and be debugged without a preloaded GGUF model. Start/enable it after
# downloading a model post-boot.
systemctl enable seatd.service
systemctl enable jarvis-shell.service
systemctl enable jarvis-live-prompt.service
# jarvis-shell owns /dev/tty1 (it Conflicts=getty@tty1). Enabling getty@tty1 here
# too made both units race for the same VT during graphical.target activation,
# which could tear down the VT right as cage grabbed it -> black screen. Put the
# recovery console on tty2 instead so tty1 belongs solely to the compositor.
systemctl enable getty@tty2.service

# Boot straight into the graphical (kiosk) target. Without this the shell units,
# which are WantedBy=graphical.target, would never start on the default target.
systemctl set-default graphical.target

# Setup plymouth theme (non-fatal for kiosk bring-up).
if ! plymouth-set-default-theme jarvis; then
  echo "WARN: could not set plymouth theme 'jarvis'; continuing" >&2
fi
if ! mkinitcpio -P; then
  echo "WARN: mkinitcpio failed during image customization; continuing" >&2
fi

# Keep tty2 as a recovery console. Mask only extra ttys to reduce clutter.
# jarvis-shell.service conflicts with getty@tty1 and owns tty1 when healthy.
systemctl mask getty@tty3.service getty@tty4.service \
              getty@tty5.service getty@tty6.service
systemctl mask serial-getty@ttyS0.service

# Check for dm violations
for dm in lightdm gdm sddm greetd; do
  if pacman -Qq "$dm" &>/dev/null; then
    echo "FATAL: $dm present, violates zero-login design" >&2
    exit 1
  fi
done
