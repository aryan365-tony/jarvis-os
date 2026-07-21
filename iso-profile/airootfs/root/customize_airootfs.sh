#!/usr/bin/env bash
set -euo pipefail

# Create jarvisuser and set permissions.
# The `seat` group is required so cage/libseat can talk to seatd without a
# graphical login manager; without it the compositor fails and the screen
# stays black.
useradd -m -U -G wheel,video,audio,input,seat -s /bin/bash jarvisuser || true
usermod -aG seat jarvisuser || true
chown -R jarvisuser:jarvisuser /home/jarvisuser

# Enable necessary services
# llama-server is intentionally left disabled by default so the system can boot
# and be debugged without a preloaded GGUF model. Start/enable it after
# downloading a model post-boot.
systemctl enable jarvis-shell.service
systemctl enable seatd.service
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
