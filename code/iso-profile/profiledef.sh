#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="jarvis-os"
iso_label="JARVIS_$(date +%Y%m)"
iso_publisher="jarvis-os project"
iso_application="Jarvis-OS Live/Installer"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="jarvis"
buildmodes=('iso')
bootmodes=('bios.syslinux' 'uefi-x64.systemd-boot.esp')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'zstd' '-Xcompression-level' "${SQUASHFS_ZSTD_LEVEL:-15}")
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
file_permissions=(
  ["/etc/shadow"]="0:0:400"
  # Scoped agent sudoers drop-in must be root:root 0440 or sudo/visudo reject it
  # (a group/world-writable sudoers file is ignored). This is the agent's entire
  # privilege boundary; see the file header for the hard-boundary policy.
  ["/etc/sudoers.d/jarvis-agent"]="0:0:440"
  # Btrfs installer that lays down the @/@home/@snapshots/@var_log layout and the
  # snapper snapshot infrastructure required by Phase 3. Runs from the live ISO.
  ["/usr/local/bin/jarvis-install"]="0:0:755"
  # Phase 2: the ONLY root filesystem-mutation helper the agent can invoke via
  # sudo. Small, denylist-guarded, heavily commented; it is the fs privilege
  # boundary. Must be root-owned and executable.
  ["/usr/local/bin/jarvis-fsop"]="0:0:755"
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
  ["/home/jarvisuser/dev/jarvis-os/llama/download-model.sh"]="1000:1000:755"
)
