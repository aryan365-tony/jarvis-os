#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(dirname "$0")"
MODEL_PATH="$BASE_DIR/models/gemma-4-E4B-it-Q4_K_M.gguf"

if [ -x "$BASE_DIR/gpu/server-gpu" ]; then
    echo "$(date -Is) Using optimized GPU backend"
    exec "$BASE_DIR/gpu/server-gpu" -m "$MODEL_PATH" -ngl 999 -c 8192 --flash-attn --host 127.0.0.1 --port 8080 --threads "$(nproc)"
else
    echo "$(date -Is) Using generic CPU backend"
    exec "$BASE_DIR/cpu/server-cpu" -m "$MODEL_PATH" -ngl 0 -c 8192 --host 127.0.0.1 --port 8080 --threads "$(nproc)"
fi
