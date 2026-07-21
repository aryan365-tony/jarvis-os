#!/usr/bin/env bash
set -euo pipefail

echo "Setting up Jarvis-OS build environment..."

# Keep the kiosk/session entrypoints executable so systemd can launch them even
# if a checkout loses mode bits.
chmod +x compositor/cage-jarvis.session llama/serve.sh ops/healthcheck.sh \
    llama/scripts/build_backend.sh llama/scripts/detect_gpu.py \
    llama/download-model.sh

# 1. Build the CPU server backend (model download is now post-boot and optional)
if [ ! -f llama/cpu/server-cpu ]; then
    echo "Compiling CPU fallback server from source..."
    TMP_DIR=$(mktemp -d)
    cd "$TMP_DIR"
    git clone https://github.com/ggerganov/llama.cpp.git .
    # # # # # git checkout 5556cd369a4c86e093952ba9529cc5cb121b65e9
    cmake -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release -j"$(nproc)"
    cd - > /dev/null
    mkdir -p llama/cpu
    cp "$TMP_DIR/build/bin/llama-server" llama/cpu/server-cpu
    rm -rf "$TMP_DIR"
else
    echo "CPU server already compiled."
fi

# 2. Vendor files into iso-profile
echo "Vendoring files to the ISO staging directory (airootfs)..."
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/cpu
mkdir -p iso-profile/airootfs/usr/local/lib/jarvis/llama/cpu
mkdir -p iso-profile/airootfs/usr/local/lib/jarvis/llama/gpu
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/models
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/scripts
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/jarvis-shell
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/compositor
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/ops
mkdir -p iso-profile/airootfs/etc/systemd/system

# Copy/link CPU server
rsync -a llama/cpu/server-cpu iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/cpu/
rsync -a llama/cpu/server-cpu iso-profile/airootfs/usr/local/lib/jarvis/llama/cpu/
if [ -f llama/gpu/server-gpu ]; then
    rsync -a llama/gpu/server-gpu iso-profile/airootfs/usr/local/lib/jarvis/llama/gpu/
fi

rsync -a jarvis-shell/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/jarvis-shell/ --exclude '.venv' --exclude '__pycache__'
rsync -a llama/scripts/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/scripts/
cp llama/serve.sh iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/
cp llama/download-model.sh iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/
rsync -a compositor/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/compositor/
rsync -a ops/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/ops/
cp systemd/*.service iso-profile/airootfs/etc/systemd/system/

chmod +x iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/serve.sh
chmod +x iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/download-model.sh
chmod +x iso-profile/airootfs/usr/local/lib/jarvis/llama/cpu/server-cpu
if [ -f iso-profile/airootfs/usr/local/lib/jarvis/llama/gpu/server-gpu ]; then
    chmod +x iso-profile/airootfs/usr/local/lib/jarvis/llama/gpu/server-gpu
fi

# Optional: include local GGUFs in the image only when explicitly requested.
# Default behavior keeps ISO small and shifts model fetch to post-boot.
if [[ "${INCLUDE_MODELS_IN_ISO:-0}" == "1" ]]; then
    if [ -n "$(ls llama/models/*.gguf 2>/dev/null)" ]; then
        echo "Including local GGUF model files in ISO staging (INCLUDE_MODELS_IN_ISO=1)..."
        rsync -a llama/models/*.gguf iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/models/
    else
        echo "WARNING: INCLUDE_MODELS_IN_ISO=1 set, but no GGUF files found in llama/models/"
    fi
else
    echo "Skipping GGUF inclusion (default). Models will be downloaded post-boot if needed."
fi

echo "Setup complete! You can now build the ISO by running:"
echo "cd iso-profile && sudo mkarchiso -v -w ~/jarvis-work -o ~/jarvis-out ."
