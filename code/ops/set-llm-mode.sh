#!/usr/bin/env bash
#
# set-llm-mode.sh - Switch Jarvis between local and remote LLM mode.
#

set -euo pipefail

LLM_CONFIG_DIR="/home/jarvisuser/dev/jarvis-os/config"
CONFIG_FILE="$LLM_CONFIG_DIR/jarvis.toml"
LLM_MODE="local"
LLM_BASE_URL="http://127.0.0.1:8080/v1"
LLM_API_KEY_ENV=""

echo "Jarvis LLM Configuration"
echo "------------------------"
read -r -p "Run the AI model locally (llama.cpp on this machine) or connect to a remote llama.cpp-compatible server? [local/remote] (default: local): " mode_ans
if [[ "${mode_ans,,}" == "remote" ]]; then
    LLM_MODE="remote"
    while true; do
        read -r -p "Enter the remote server base URL (e.g. http://192.168.1.100:8080/v1): " url_ans
        if [[ -n "$url_ans" && "$url_ans" == http* ]]; then
            LLM_BASE_URL="$url_ans"
            echo "Testing connection to $LLM_BASE_URL/models ..."
            if curl -s -f -m 3 "$LLM_BASE_URL/models" >/dev/null; then
                echo "Connection successful!"
                break
            else
                read -r -p "Warning: Could not connect to $LLM_BASE_URL/models. Continue anyway (server may not be up yet) or re-enter URL? [c/R]: " check_ans
                if [[ "${check_ans,,}" == "c" ]]; then
                    break
                fi
            fi
        else
            echo "Please enter a valid URL starting with http:// or https://"
        fi
    done
    
    read -r -p "Does this server require a Bearer token for authentication? [y/N]: " auth_ans
    if [[ "${auth_ans,,}" == "y" ]]; then
        read -r -p "Enter the name of the ENVIRONMENT VARIABLE that will hold the token (e.g. JARVIS_LLM_TOKEN): " env_ans
        if [[ -n "$env_ans" ]]; then
            LLM_API_KEY_ENV="$env_ans"
            echo "Configured to use environment variable $LLM_API_KEY_ENV for authentication."
        fi
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

export LLM_MODE
export LLM_BASE_URL
export LLM_API_KEY_ENV

# See live-llm-prompt.sh for why this is `bash script.sh` and not `./script.sh`.
bash "$SCRIPT_DIR/lib/llm-mode-apply.sh"
echo "Done."