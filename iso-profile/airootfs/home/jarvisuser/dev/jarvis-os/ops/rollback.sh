#!/usr/bin/env bash
set -euo pipefail
echo "Reverting jarvis boot target to previous default..."
sudo systemctl set-default graphical.target   # or whatever the prior default was
sudo grub-reboot "$(grep -m1 'Advanced options' /boot/grub/grub.cfg | grep -oP "(?<=').*(?=')" | head -2 | tail -1)"
echo "Reboot now to return to the previous kernel/target for one boot."
