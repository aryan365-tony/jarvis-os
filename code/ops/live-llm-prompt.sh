#!/usr/bin/env bash
#
# live-llm-prompt.sh - TUI Setup for Live ISO
#

set -euo pipefail

if [[ ! -d /run/archiso ]]; then
    exit 0
fi

if [[ -f /tmp/.jarvis_live_prompt_done ]]; then
    exit 0
fi
touch /tmp/.jarvis_live_prompt_done

LLM_CONFIG_DIR="/home/jarvisuser/dev/jarvis-os/config"
CONFIG_FILE="$LLM_CONFIG_DIR/jarvis.toml"
LLM_MODE="local"
LLM_BASE_URL="http://127.0.0.1:8080/v1"
LLM_API_KEY_ENV=""

# Main Menu
CHOICE=$(dialog --clear --backtitle "Jarvis-OS Out-Of-Box Experience" \
    --title "LLM Configuration" \
    --menu "Choose your AI backend mode for this live session:" 15 50 2 \
    "Local" "Run on this device (Offline)" \
    "Remote" "Connect to an external API server" \
    2>&1 >/dev/tty) || true

clear

if [[ "$CHOICE" == "Remote" ]]; then
    LLM_MODE="remote"
    
    # URL Prompt
    while true; do
        URL=$(dialog --clear --backtitle "Jarvis-OS Out-Of-Box Experience" \
            --title "Remote LLM Server" \
            --inputbox "Enter the base URL of your remote API server\n(e.g., http://192.168.1.100:8080/v1):" 10 60 \
            2>&1 >/dev/tty) || true
            
        if [[ -z "$URL" ]]; then
            # Cancel pressed or empty
            dialog --yesno "URL cannot be empty. Cancel remote setup and use Local?" 8 50 2>&1 >/dev/tty
            if [ $? -eq 0 ]; then
                LLM_MODE="local"
                break
            fi
        elif [[ "$URL" == http* ]]; then
            LLM_BASE_URL="$URL"
            break
        else
            dialog --msgbox "Please enter a valid URL starting with http:// or https://" 8 50 2>&1 >/dev/tty
        fi
    done
    
    # Authentication
    if [[ "$LLM_MODE" == "remote" ]]; then
        dialog --yesno "Does this remote server require a Bearer token for authentication?" 8 60 2>&1 >/dev/tty
        if [ $? -eq 0 ]; then
            ENV_VAR=$(dialog --clear --backtitle "Jarvis-OS Out-Of-Box Experience" \
                --title "Authentication Token" \
                --inputbox "Enter the ENVIRONMENT VARIABLE name that will hold the token (e.g. JARVIS_LLM_TOKEN):" 10 60 \
                2>&1 >/dev/tty) || true
            if [[ -n "$ENV_VAR" ]]; then
                LLM_API_KEY_ENV="$ENV_VAR"
                # This only records the NAME of an env var to read the token
                # from at request time (llm_client.py does
                # os.environ.get(LLM_API_KEY_ENV)); it does not collect or
                # store the token itself. If that env var isn't actually
                # exported anywhere jarvis-shell.service inherits from (e.g.
                # via a systemd drop-in), every remote request silently goes
                # out with NO Authorization header instead of failing loudly.
                # Warn now so "dummy" (typed as if it were the token) doesn't
                # look like a successful auth setup.
                if [[ -z "${!ENV_VAR:-}" ]]; then
                    dialog --msgbox "Note: the environment variable '$ENV_VAR' is not currently set in this session. Jarvis will read the token from it at request time, but you must export it (e.g. in a systemd drop-in for jarvis-shell.service) before the token will actually be sent. Requests will otherwise go out unauthenticated." 10 60 2>&1 >/dev/tty
                fi
            fi
        fi
    fi
fi

dialog --clear --backtitle "Jarvis-OS Out-Of-Box Experience" --infobox "Configuration saved! Starting Jarvis..." 5 50 2>&1 >/dev/tty
sleep 1
clear

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LLM_MODE
export LLM_BASE_URL
export LLM_API_KEY_ENV
export IN_CHROOT=0

# Invoke via `bash` explicitly rather than direct exec. mkarchiso's squashfs
# packaging (and zip/git checkouts in general) can silently drop the +x bit
# on files that aren't declared in iso-profile/profiledef.sh's
# file_permissions map. A direct exec then fails with "Permission Denied"
# and, because this script runs under `set -euo pipefail`, aborts BEFORE
# jarvis.toml is ever written -- silently leaving the system on whatever
# mode was last on disk (default: local) instead of the mode the user chose.
# Calling through `bash` sidesteps the exec-bit requirement entirely.
bash "$SCRIPT_DIR/lib/llm-mode-apply.sh"