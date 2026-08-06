#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="${MODEL_DIR:-$BASE_DIR/models}"
MODEL_NAME="${MODEL_NAME:-gemma-4-E4B-it-Q4_K_M.gguf}"
MODEL_URL="${MODEL_URL:-https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf}"
MODEL_PATH="$MODEL_DIR/$MODEL_NAME"
TMP_PATH="$MODEL_PATH.part"
START_LLAMA=0

find_existing_model() {
  shopt -s nullglob
  local matches=("$MODEL_DIR"/*.gguf)
  shopt -u nullglob
  if [[ ${#matches[@]} -gt 0 ]]; then
    printf '%s' "${matches[0]}"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start-llama)
      START_LLAMA=1
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--start-llama]" >&2
      exit 2
      ;;
  esac
done

EXISTING_MODEL="$(find_existing_model)"
if [[ -n "$EXISTING_MODEL" ]]; then
  MODEL_PATH="$EXISTING_MODEL"
  echo "$(date -Is) model already present: $MODEL_PATH"
else
  mkdir -p "$MODEL_DIR"
  
  exec 9>"/var/tmp/jarvis-model-download.lock"
  if ! flock -n 9; then
    echo "$(date -Is) INFO: model download already in progress by another process, skipping"
    exit 0
  fi

  echo "$(date -Is) downloading model to $MODEL_PATH"

  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 4 --retry-delay 2 -o "$TMP_PATH" "$MODEL_URL"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "$TMP_PATH" "$MODEL_URL"
  else
    python3 - "$MODEL_URL" "$TMP_PATH" <<'PY'
import sys
import urllib.request

url, out = sys.argv[1], sys.argv[2]
with urllib.request.urlopen(url) as resp, open(out, "wb") as f:
    while True:
        chunk = resp.read(1024 * 1024)
        if not chunk:
            break
        f.write(chunk)
PY
  fi

  mv "$TMP_PATH" "$MODEL_PATH"
  chmod 0644 "$MODEL_PATH"
  if [[ ! -s "$MODEL_PATH" ]]; then
    echo "$(date -Is) ERROR: downloaded model is empty" >&2
    rm -f "$MODEL_PATH"
    exit 1
  fi

  if [[ "$(head -c 4 "$MODEL_PATH" 2>/dev/null || true)" != "GGUF" ]]; then
    echo "$(date -Is) ERROR: downloaded file does not look like a GGUF model" >&2
    rm -f "$MODEL_PATH"
    exit 1
  fi

  echo "$(date -Is) model download complete"
fi

if id -u jarvisuser >/dev/null 2>&1; then
  chown jarvisuser:jarvisuser "$MODEL_PATH" 2>/dev/null || true
fi

if [[ "$START_LLAMA" == "1" ]]; then
  if command -v systemctl >/dev/null 2>&1; then
    systemctl start llama-server.service
    echo "$(date -Is) started llama-server.service"
  else
    echo "$(date -Is) systemctl not found; cannot start llama-server.service" >&2
  fi
else
  echo "$(date -Is) model ready. Start backend manually with: sudo systemctl start llama-server.service"
fi
