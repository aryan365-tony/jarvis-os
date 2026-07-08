#!/usr/bin/env bash
set -e

echo "Setting up Jarvis-OS build environment..."

# 1. Download the model
mkdir -p llama/models
if [ ! -f llama/models/gemma-4-E4B-it-Q4_K_M.gguf ]; then
    echo "Downloading model from Hugging Face..."
    wget -O llama/models/gemma-4-E4B-it-Q4_K_M.gguf https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf
else
    echo "Model already downloaded."
fi

# 2. Build the CPU server
if [ ! -f llama/cpu/server-cpu ]; then
    echo "Compiling CPU fallback server from source..."
    TMP_DIR=$(mktemp -d)
    cd "$TMP_DIR"
    git clone https://github.com/ggerganov/llama.cpp.git .
    git checkout 5556cd369a4c86e093952ba9529cc5cb121b65e9
    cmake -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build --config Release -j"$(nproc)"
    cd - > /dev/null
    mkdir -p llama/cpu
    cp "$TMP_DIR/build/bin/llama-server" llama/cpu/server-cpu
    rm -rf "$TMP_DIR"
else
    echo "CPU server already compiled."
fi

# 3. Vendor files into iso-profile
echo "Vendoring files to the ISO staging directory (airootfs)..."
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/cpu
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/models
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/scripts
mkdir -p iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/jarvis-shell
mkdir -p iso-profile/airootfs/etc/systemd/system

rsync -a llama/cpu/server-cpu iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/cpu/
rsync -a llama/models/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/models/
rsync -a jarvis-shell/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/jarvis-shell/ --exclude '.venv' --exclude '__pycache__'
rsync -a llama/scripts/ iso-profile/airootfs/home/jarvisuser/dev/jarvis-os/llama/scripts/
cp systemd/*.service iso-profile/airootfs/etc/systemd/system/

echo "Setup complete! You can now build the ISO by running:"
echo "cd iso-profile && sudo mkarchiso -v -w ~/jarvis-work -o ~/jarvis-out ."
