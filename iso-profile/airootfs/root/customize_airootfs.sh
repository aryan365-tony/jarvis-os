#!/usr/bin/env bash
set -e

# Create jarvisuser and set permissions.
# The `seat` group is required so cage/libseat can talk to seatd without a
# graphical login manager; without it the compositor fails and the screen
# stays black.
useradd -m -U -G wheel,video,audio,input,seat -s /bin/bash jarvisuser || true
usermod -aG seat jarvisuser || true
chown -R jarvisuser:jarvisuser /home/jarvisuser

# Enable necessary services
systemctl enable llama-server.service
systemctl enable jarvis-shell.service
systemctl enable seatd.service

# Boot straight into the graphical (kiosk) target. Without this the shell units,
# which are WantedBy=graphical.target, would never start on the default target.
systemctl set-default graphical.target

# Setup plymouth theme
plymouth-set-default-theme jarvis
mkinitcpio -P

# Keep tty2 as a debug/recovery console. If the kiosk stack fails, users can
# still switch to tty2 and inspect logs instead of being stuck on black.
systemctl mask getty@tty1.service getty@tty3.service getty@tty4.service \
              getty@tty5.service getty@tty6.service
systemctl mask serial-getty@ttyS0.service

# Check for dm violations
for dm in lightdm gdm sddm greetd; do
  if pacman -Qq "$dm" &>/dev/null; then
    echo "FATAL: $dm present, violates zero-login design" >&2
    exit 1
  fi
done
