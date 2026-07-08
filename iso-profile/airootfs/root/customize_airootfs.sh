#!/usr/bin/env bash
set -e

# Enable necessary services
systemctl enable llama-server.service
systemctl enable jarvis-shell.service
systemctl enable seatd.service

# Setup plymouth theme
plymouth-set-default-theme jarvis
mkinitcpio -P

# Mask other VTs
systemctl mask getty@tty2.service getty@tty3.service getty@tty4.service \
              getty@tty5.service getty@tty6.service
systemctl mask serial-getty@ttyS0.service

# Check for dm violations
for dm in lightdm gdm sddm greetd; do
  if pacman -Qq "$dm" &>/dev/null; then
    echo "FATAL: $dm present, violates zero-login design" >&2
    exit 1
  fi
done
