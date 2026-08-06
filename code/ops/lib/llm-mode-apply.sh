#!/usr/bin/env bash
#
# llm-mode-apply.sh - Shared script to apply LLM configuration (Local vs Remote).
#
# Expects the following environment variables:
#   LLM_MODE         : "local" or "remote"
#   LLM_BASE_URL     : e.g. "http://127.0.0.1:8080/v1"
#   LLM_API_KEY_ENV  : e.g. "JARVIS_LLM_TOKEN" or empty string
#   IN_CHROOT        : "1" if running inside the archiso build chroot, "0" or empty otherwise.

set -euo pipefail

LLM_CONFIG_DIR="/home/jarvisuser/dev/jarvis-os/config"
CONFIG_FILE="$LLM_CONFIG_DIR/jarvis.toml"
IN_CHROOT="${IN_CHROOT:-0}"

if [[ -z "${LLM_MODE:-}" || -z "${LLM_BASE_URL:-}" ]]; then
    echo "ERROR: LLM_MODE and LLM_BASE_URL must be set." >&2
    exit 1
fi

if [[ "${LLM_MODE}" == "local" ]]; then
    AUTO_START="true"
else
    AUTO_START="false"
fi

mkdir -p "$LLM_CONFIG_DIR"

# This script runs in two contexts: as root (systemd OOBE prompt at boot,
# IN_CHROOT=0, no human watching a tty) and as jarvisuser (agent-triggered
# svc_control.py, which DOES have a NOPASSWD sudoers grant). `sudo` has no
# NOPASSWD rule for root, so `sudo systemctl ...` run as root blocks forever
# on a password prompt nobody can answer -- the boot hangs with no error and
# no timeout. Skip sudo when already root; use -n elsewhere so a missing/
# denied credential fails fast instead of hanging (the existing `|| true`
# fallbacks can then actually run).
if [[ "${EUID}" -eq 0 ]]; then
    SUDO=()
else
    SUDO=(sudo -n)
fi

if [[ -f "$CONFIG_FILE" ]]; then
    python3 - <<EOF
import tomllib
import sys
import os

path = "$CONFIG_FILE"
data = {}
try:
    with open(path, "rb") as f:
        data = tomllib.load(f)
except Exception:
    pass

if "llm" not in data:
    data["llm"] = {}
if "boot" not in data:
    data["boot"] = {}
if "tools" not in data:
    data["tools"] = {}
if "enabled_domains" not in data["tools"]:
    data["tools"]["enabled_domains"] = {
        "home_assistant": False,
        "browser": False,
        "desktop_control": False,
        "calendar": False
    }

data["llm"]["mode"] = "$LLM_MODE"
data["llm"]["base_url"] = "$LLM_BASE_URL"
if "$LLM_API_KEY_ENV":
    data["llm"]["api_key_env"] = "$LLM_API_KEY_ENV"
elif "api_key_env" in data["llm"]:
    del data["llm"]["api_key_env"]

data["boot"]["model_auto_start"] = ($AUTO_START == "true")

lines = []
for k, v in data.items():
    if k == "tools":
        lines.append("[tools]")
        for sub_k, sub_v in v.items():
            if sub_k == "enabled_domains":
                continue # handled below
            if isinstance(sub_v, str):
                lines.append(f'{sub_k} = "{sub_v}"')
            elif isinstance(sub_v, bool):
                lines.append(f'{sub_k} = {"true" if sub_v else "false"}')
            else:
                lines.append(f"{sub_k} = {sub_v}")
        if "enabled_domains" in v:
            lines.append("")
            lines.append("[tools.enabled_domains]")
            for dom_k, dom_v in v["enabled_domains"].items():
                lines.append(f'{dom_k} = {"true" if dom_v else "false"}')
    else:
        lines.append(f"[{k}]")
        for sub_k, sub_v in v.items():
            if isinstance(sub_v, str):
                lines.append(f'{sub_k} = "{sub_v}"')
            elif isinstance(sub_v, bool):
                lines.append(f'{sub_k} = {"true" if sub_v else "false"}')
            else:
                lines.append(f"{sub_k} = {sub_v}")
    lines.append("")

with open(path, "w") as f:
    f.write("\n".join(lines))
EOF
else
    # Create canonical TOML from scratch
    cat > "$CONFIG_FILE" <<TOML
[llm]
mode = "${LLM_MODE}"
base_url = "${LLM_BASE_URL}"
api_key_env = "${LLM_API_KEY_ENV:-}"

[boot]
model_auto_start = ${AUTO_START}

[tools.enabled_domains]
home_assistant = false
browser = false
desktop_control = false
calendar = false
TOML
fi

# Ensure ownership if running outside chroot and jarvisuser exists
if id -u jarvisuser >/dev/null 2>&1; then
    chown -R jarvisuser:jarvisuser "$LLM_CONFIG_DIR"
fi

# Apply system changes based on mode
if [[ "${LLM_MODE}" == "local" ]]; then
    if [[ "${IN_CHROOT}" != "1" ]]; then
        # On a live system: ensure model and backend are present
        echo "Ensuring local model and backend are present..."
        # Download model if missing
        if [[ -x /home/jarvisuser/dev/jarvis-os/llama/download-model.sh ]]; then
            /home/jarvisuser/dev/jarvis-os/llama/download-model.sh
        fi
        # Build backend if missing
        if [[ -x /home/jarvisuser/dev/jarvis-os/llama/scripts/build_backend.sh ]]; then
            /home/jarvisuser/dev/jarvis-os/llama/scripts/build_backend.sh
        fi
        echo "Starting local llama-server..."
        "${SUDO[@]}" systemctl start --no-block llama-server.service || true
        echo "Enabling local llama-server for next boot..."
        "${SUDO[@]}" systemctl enable llama-server.service || true
    else
        # In chroot: only enable, don't start or download
        echo "Enabling local llama-server for next boot..."
        systemctl enable llama-server.service || true
    fi
else
    if [[ "${IN_CHROOT}" != "1" ]]; then
        echo "Stopping local llama-server (if running)..."
        "${SUDO[@]}" systemctl stop --no-block llama-server.service || true
        "${SUDO[@]}" systemctl disable llama-server.service || true
    else
        systemctl disable llama-server.service || true
    fi
fi

# Restart jarvis-shell if active
if [[ "${IN_CHROOT}" != "1" ]]; then
    if systemctl is-active --quiet jarvis-shell.service; then
        echo "Restarting jarvis-shell service to apply changes..."
        "${SUDO[@]}" systemctl restart --no-block jarvis-shell || echo "Could not restart jarvis-shell."
    fi
fi