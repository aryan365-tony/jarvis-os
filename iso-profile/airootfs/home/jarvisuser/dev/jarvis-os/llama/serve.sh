#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_DIR="/usr/local/lib/jarvis/llama"
LLAMA_HOST="${LLAMA_HOST:-127.0.0.1}"
LLAMA_PORT="${LLAMA_PORT:-8080}"
LLAMA_CTX_SIZE="${LLAMA_CTX_SIZE:-8192}"
CPU_COUNT="$(nproc)"
if (( CPU_COUNT > 2 )); then
    LLAMA_THREADS_DEFAULT=$((CPU_COUNT / 2))
else
    LLAMA_THREADS_DEFAULT=1
fi
LLAMA_THREADS="${LLAMA_THREADS:-$LLAMA_THREADS_DEFAULT}"
LLAMA_GPU_LAYERS="${LLAMA_GPU_LAYERS:-999}"
FLASH_ATTN_FLAG=()

if [[ "${LLAMA_FLASH_ATTN:-0}" == "1" ]]; then
    FLASH_ATTN_FLAG=(--flash-attn)
fi

shopt -s nullglob
MODELS=("$BASE_DIR"/models/*.gguf)
shopt -u nullglob
MODEL_PATH="${MODELS[0]:-}"

GPU_BACKEND="$RUNTIME_DIR/gpu/server-gpu"
CPU_BACKEND="$RUNTIME_DIR/cpu/server-cpu"
SYSTEM_BACKEND="$(command -v llama-server || true)"

if [[ ! -x "$GPU_BACKEND" ]]; then
    GPU_BACKEND="$BASE_DIR/gpu/server-gpu"
fi

if [[ ! -x "$CPU_BACKEND" ]]; then
    CPU_BACKEND="$BASE_DIR/cpu/server-cpu"
fi

backend_usable() {
    local backend="$1"
    [[ -n "$backend" && -x "$backend" ]] || return 1
    if command -v ldd >/dev/null 2>&1; then
        local backend_dir
        local ldd_out
        backend_dir="$(dirname "$backend")"
        if ! ldd_out="$(LD_LIBRARY_PATH="$backend_dir${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
            ldd "$backend" 2>/dev/null)"; then
            return 1
        fi
        if grep -q "not found" <<< "$ldd_out"; then
            return 1
        fi
    fi
    return 0
}

if [[ -z "$MODEL_PATH" ]]; then
    echo "$(date -Is) INFO: no GGUF models found in $BASE_DIR/models"
    echo "$(date -Is) INFO: llama-server is optional; skipping backend start"
    exit 0
fi

echo "$(date -Is) INFO: using model $MODEL_PATH"

if backend_usable "$GPU_BACKEND"; then
    echo "$(date -Is) Using optimized GPU backend"
    export LD_LIBRARY_PATH="$(dirname "$GPU_BACKEND")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    exec "$GPU_BACKEND" -m "$MODEL_PATH" -ngl "$LLAMA_GPU_LAYERS" -c "$LLAMA_CTX_SIZE" "${FLASH_ATTN_FLAG[@]}" --host "$LLAMA_HOST" --port "$LLAMA_PORT" --threads "$LLAMA_THREADS"
fi

if backend_usable "$CPU_BACKEND"; then
    echo "$(date -Is) Using generic CPU backend"
    export LD_LIBRARY_PATH="$(dirname "$CPU_BACKEND")${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    exec "$CPU_BACKEND" -m "$MODEL_PATH" -ngl 0 -c "$LLAMA_CTX_SIZE" --host "$LLAMA_HOST" --port "$LLAMA_PORT" --threads "$LLAMA_THREADS"
fi

if backend_usable "$SYSTEM_BACKEND"; then
    echo "$(date -Is) Using system llama-server backend"
    exec "$SYSTEM_BACKEND" -m "$MODEL_PATH" -ngl 0 -c "$LLAMA_CTX_SIZE" --host "$LLAMA_HOST" --port "$LLAMA_PORT" --threads "$LLAMA_THREADS"
fi

echo "$(date -Is) INFO: no usable llama backend found; skipping start"
exit 0
