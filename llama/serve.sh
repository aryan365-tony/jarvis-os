#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="/usr/local/lib/jarvis/llama"
MODEL_PATH="$BASE_DIR/models/gemma-4-E4B-it-Q4_K_M.gguf"

GPU_BACKEND="$RUNTIME_DIR/gpu/server-gpu"
CPU_BACKEND="$RUNTIME_DIR/cpu/server-cpu"

if [[ ! -x "$GPU_BACKEND" ]]; then
    GPU_BACKEND="$BASE_DIR/gpu/server-gpu"
fi

if [[ ! -x "$CPU_BACKEND" ]]; then
    CPU_BACKEND="$BASE_DIR/cpu/server-cpu"
fi

if [[ ! -f "$MODEL_PATH" ]]; then
    echo "$(date -Is) INFO: model not found at $MODEL_PATH"
    echo "$(date -Is) INFO: llama-server is optional; skipping backend start"
    exit 0
fi

if [[ -x "$GPU_BACKEND" ]]; then
    echo "$(date -Is) Using optimized GPU backend"
    exec "$GPU_BACKEND" -m "$MODEL_PATH" -ngl 999 -c 8192 --flash-attn --host 127.0.0.1 --port 8080 --threads "$(nproc)"
fi

if [[ -x "$CPU_BACKEND" ]]; then
    echo "$(date -Is) Using generic CPU backend"
    exec "$CPU_BACKEND" -m "$MODEL_PATH" -ngl 0 -c 8192 --host 127.0.0.1 --port 8080 --threads "$(nproc)"
fi

echo "$(date -Is) INFO: no executable llama backend found; skipping start"
exit 0
