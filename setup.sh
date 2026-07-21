#!/usr/bin/env bash
set -euo pipefail

echo "Setting up Jarvis-OS build environment..."

RSYNC_ARGS=(
    -rlt
    --no-perms
    --no-owner
    --no-group
    --omit-dir-times
)

LLAMA_CPP_REF="${LLAMA_CPP_REF:-5556cd369a4c86e093952ba9529cc5cb121b65e9}"

bundled_cpu_backend_usable() {
    local backend="llama/cpu/server-cpu"
    [[ -x "$backend" ]] || return 1

    shopt -s nullglob
    local runtime_libs=(llama/cpu/libllama*.so* llama/cpu/libggml*.so* llama/cpu/libmtmd*.so*)
    shopt -u nullglob
    [[ ${#runtime_libs[@]} -gt 0 ]] || return 1

    if command -v ldd >/dev/null 2>&1; then
        local ldd_out
        if ! ldd_out="$(LD_LIBRARY_PATH="$(pwd)/llama/cpu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ldd "$backend" 2>/dev/null)"; then
            return 1
        fi
        if grep -q "not found" <<< "$ldd_out"; then
            return 1
        fi
    fi

    return 0
}

fetch_llama_cpp_source() {
    local target_dir="$1"
    git init -q "$target_dir"
    git -C "$target_dir" remote add origin https://github.com/ggerganov/llama.cpp.git
    git -C "$target_dir" fetch --depth 1 origin "$LLAMA_CPP_REF"
    git -C "$target_dir" checkout --detach -q FETCH_HEAD
}

# Keep the kiosk/session entrypoints executable so systemd can launch them even
# if a checkout loses mode bits.
chmod +x compositor/cage-jarvis.session llama/serve.sh ops/healthcheck.sh \
    llama/scripts/build_backend.sh llama/scripts/detect_gpu.py \
    llama/download-model.sh

# 1. Build local CPU backend from source by default.
# Set BUILD_LOCAL_LLAMA_BACKEND=0 to skip local backend compilation.
if [[ "${BUILD_LOCAL_LLAMA_BACKEND:-1}" == "1" ]]; then
    if [[ "${FORCE_REBUILD_LLAMA_BACKEND:-0}" != "1" ]] && bundled_cpu_backend_usable; then
        echo "Using existing bundled CPU backend from llama/cpu/."
    else
        echo "Compiling CPU fallback server from source (best effort)..."
        if ! (
            set -euo pipefail
            TMP_DIR=$(mktemp -d)
            cleanup() { rm -rf "$TMP_DIR"; }
            trap cleanup EXIT

            fetch_llama_cpp_source "$TMP_DIR"
            cmake -S "$TMP_DIR" -B "$TMP_DIR/build" -DCMAKE_BUILD_TYPE=Release
            cmake --build "$TMP_DIR/build" --config Release -j"$(nproc)"

            if command -v strip >/dev/null 2>&1; then
                strip --strip-unneeded "$TMP_DIR/build/bin/llama-server" 2>/dev/null || true
                find "$TMP_DIR/build/bin" -maxdepth 1 -type f \( -name 'libllama*.so*' -o -name 'libggml*.so*' -o -name 'libmtmd*.so*' \) -exec strip --strip-unneeded {} + 2>/dev/null || true
            fi

            mkdir -p llama/cpu
            rm -f llama/cpu/server-cpu
            find llama/cpu -maxdepth 1 -type f \( -name 'libllama*.so*' -o -name 'libggml*.so*' -o -name 'libmtmd*.so*' \) -delete
            cp "$TMP_DIR/build/bin/llama-server" llama/cpu/server-cpu
            shopt -s nullglob
            BUILT_RUNTIME_LIBS=("$TMP_DIR"/build/bin/libllama*.so* "$TMP_DIR"/build/bin/libggml*.so* "$TMP_DIR"/build/bin/libmtmd*.so*)
            if [[ ${#BUILT_RUNTIME_LIBS[@]} -gt 0 ]]; then
                cp "${BUILT_RUNTIME_LIBS[@]}" llama/cpu/
            fi
            shopt -u nullglob
        ); then
            echo "WARNING: local CPU backend build failed; continuing without a bundled backend binary."
        fi
    fi
else
    echo "Skipping local CPU backend build (BUILD_LOCAL_LLAMA_BACKEND is set to 0)."
    echo "Runtime will use any bundled backend binary if present."
fi

# 2. Vendor files into iso-profile
echo "Vendoring files to the ISO staging directory (airootfs)..."
mkdir -p \
    iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/{models,scripts} \
    iso-profile/airootfs/usr/local/lib/jarvis/llama/{cpu,gpu} \
    iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/{jarvis-shell,compositor,ops} \
    iso-profile/airootfs/etc/systemd/system

# Copy/link CPU server + runtime libs
rsync "${RSYNC_ARGS[@]}" llama/cpu/ iso-profile/airootfs/usr/local/lib/jarvis/llama/cpu/
HOME_CPU_DIR="iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/cpu"
if [[ -L "$HOME_CPU_DIR" ]]; then
    rm -f "$HOME_CPU_DIR"
elif [[ -d "$HOME_CPU_DIR" ]]; then
    if ! rm -rf "$HOME_CPU_DIR" 2>/dev/null; then
        echo "WARNING: could not replace $HOME_CPU_DIR with a symlink (permission issue)."
        echo "Keeping duplicated staged backend copy for this run."
        rsync "${RSYNC_ARGS[@]}" llama/cpu/ "$HOME_CPU_DIR/"
    fi
fi

if [[ ! -e "$HOME_CPU_DIR" ]]; then
    ln -s /usr/local/lib/jarvis/llama/cpu "$HOME_CPU_DIR"
fi

if [[ -d "$HOME_CPU_DIR" && ! -L "$HOME_CPU_DIR" ]]; then
    rsync "${RSYNC_ARGS[@]}" llama/cpu/ "$HOME_CPU_DIR/"
fi
if [ -f llama/gpu/server-gpu ]; then
    rsync "${RSYNC_ARGS[@]}" llama/gpu/server-gpu iso-profile/airootfs/usr/local/lib/jarvis/llama/gpu/
fi

rsync "${RSYNC_ARGS[@]}" jarvis-shell/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/jarvis-shell/ --exclude '.venv' --exclude '__pycache__'
rsync "${RSYNC_ARGS[@]}" llama/scripts/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/scripts/
cp llama/serve.sh iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/
cp llama/download-model.sh iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/
rsync "${RSYNC_ARGS[@]}" compositor/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/compositor/
rsync "${RSYNC_ARGS[@]}" ops/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/ops/
cp systemd/*.service iso-profile/airootfs/etc/systemd/system/

chmod +x iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/serve.sh
chmod +x iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/download-model.sh
if [ -f iso-profile/airootfs/usr/local/lib/jarvis/llama/cpu/server-cpu ]; then
    chmod +x iso-profile/airootfs/usr/local/lib/jarvis/llama/cpu/server-cpu
fi
if [ -f iso-profile/airootfs/usr/local/lib/jarvis/llama/gpu/server-gpu ]; then
    chmod +x iso-profile/airootfs/usr/local/lib/jarvis/llama/gpu/server-gpu
fi

# Optional: include local GGUFs in the image only when explicitly requested.
# Default behavior keeps ISO small and shifts model fetch to post-boot.
# Always clear staged GGUFs first so default builds cannot accidentally include
# leftovers from prior runs.
STAGED_MODEL_DIR="iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/models"
if ! find "$STAGED_MODEL_DIR" -maxdepth 1 -type f -name '*.gguf' -delete 2>/dev/null; then
    if [[ "${STRICT_STAGING_CLEAN:-0}" == "1" ]]; then
        echo "ERROR: could not clear staged GGUF files in $STAGED_MODEL_DIR (permission issue)."
        echo "Fix ownership with:"
        echo "  sudo chown -R \"$USER:$USER\" $STAGED_MODEL_DIR"
        exit 1
    fi
    echo "WARNING: could not clear staged GGUF files in $STAGED_MODEL_DIR (permission issue)."
    echo "If stale models are unexpectedly embedded, fix ownership with:"
    echo "  sudo chown -R \"$USER:$USER\" $STAGED_MODEL_DIR"
fi

shopt -s nullglob
LOCAL_GGUFS=(llama/models/*.gguf)
shopt -u nullglob

if [[ "${INCLUDE_MODELS_IN_ISO:-0}" == "1" ]]; then
    if [[ ${#LOCAL_GGUFS[@]} -gt 0 ]]; then
        echo "Including local GGUF model files in ISO staging (INCLUDE_MODELS_IN_ISO=1)..."
        rsync "${RSYNC_ARGS[@]}" "${LOCAL_GGUFS[@]}" iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/models/
    else
        echo "ERROR: INCLUDE_MODELS_IN_ISO=1 set, but no GGUF files found in llama/models/"
        exit 1
    fi
else
    if [[ ${#LOCAL_GGUFS[@]} -gt 0 ]]; then
        echo "Skipping GGUF inclusion by default (INCLUDE_MODELS_IN_ISO is not 1)."
        echo "Detected local model(s):"
        for f in "${LOCAL_GGUFS[@]}"; do
            echo "  - $f"
        done
        echo "To embed them in the ISO, run: INCLUDE_MODELS_IN_ISO=1 ./setup.sh"
    else
        echo "Skipping GGUF inclusion (default). Models will be downloaded post-boot if needed."
    fi
fi

echo "Setup complete! You can now build the ISO by running:"
echo "cd iso-profile && sudo mkarchiso -v -w ~/jarvis-work -o ~/jarvis-out ."
