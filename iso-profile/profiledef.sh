#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="jarvis-os"
iso_label="JARVIS_$(date +%Y%m)"
iso_publisher="jarvis-os project"
iso_application="Jarvis-OS Live/Installer"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="jarvis"
buildmodes=('iso')
bootmodes=('bios.syslinux.mbr' 'bios.syslinux.eltorito'
           'uefi-x64.systemd-boot.esp' 'uefi-x64.systemd-boot.eltorito')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' '15')
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/root/.automated_script.sh"]="0:0:755"
  ["/root/.gnupg"]="0:0:700"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
  ["/usr/local/bin/Installation_guide"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
  ["/usr/local/bin/jarvis-model-download"]="0:0:755"
  # The llama.cpp backend must be executable in the squashfs, otherwise
  # serve.sh's `[[ -x ... ]]` guard fails with "no executable llama backend
  # found" (exit 126) and llama-server.service crash-loops. mkarchiso strips
  # the exec bit during squashfs creation, so file_permissions is the only
  # authoritative way to guarantee the mode. (server-gpu is built on-device,
  # so it is not listed here.)
  ["/usr/local/lib/jarvis/llama/cpu/server-cpu"]="0:0:755"
  ["/home/jarvisuser/dev/jarvis-os/llama/cpu/server-cpu"]="1000:1000:755"
  ["/home/jarvisuser/dev/jarvis-os/llama/download-model.sh"]="1000:1000:755"
)
