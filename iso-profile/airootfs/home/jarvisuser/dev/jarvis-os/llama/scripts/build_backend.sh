#!/usr/bin/env bash
set -euo pipefail

BACKEND="$1"
BASE_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"

if [ "$BACKEND" == "cpu" ]; then
    echo "CPU backend is already the default."
    exit 0
fi

echo "Optimizing for $BACKEND..."

# Install smaller subset of dependencies depending on backend
if [ "$BACKEND" == "cuda" ]; then
    # Instead of installing the full 4.5GB cuda package, we install cuda-tools and compiler if available.
    # We will use pacman to install the required subsets.
    # Note: On Arch, `cuda` is massive, but necessary for nvcc unless using custom PKGBUILD. We'll use `cuda` for now as a fallback if smaller packages aren't found, but try `cuda-tools` or `gcc` first.
    sudo pacman -S --noconfirm --needed cmake base-devel git cuda
    CMAKE_FLAGS="-DGGML_CUDA=ON"
elif [ "$BACKEND" == "vulkan" ]; then
    sudo pacman -S --noconfirm --needed cmake base-devel git vulkan-headers vulkan-icd-loader shaderc
    CMAKE_FLAGS="-DGGML_VULKAN=ON"
else
    echo "Unknown backend."
    exit 1
fi

TMP_DIR=$(mktemp -d)
cd "$TMP_DIR"

echo "Cloning llama.cpp..."
git clone https://github.com/ggerganov/llama.cpp.git .
# Use a known stable commit for compatibility
git checkout 5556cd369a4c86e093952ba9529cc5cb121b65e9 || true

echo "Building..."
cmake -B build -DCMAKE_BUILD_TYPE=Release $CMAKE_FLAGS
cmake --build build --config Release -j"$(nproc)"

echo "Installing to $BASE_DIR/gpu/server-gpu..."
mkdir -p "$BASE_DIR/gpu"
cp build/bin/llama-server "$BASE_DIR/gpu/server-gpu"

echo "Cleaning up..."
cd /
rm -rf "$TMP_DIR"

echo "Optimization complete."
