#!/usr/bin/env bash
set -euo pipefail

BACKEND="$1"
BASE_DIR="$(dirname "$(dirname "$(readlink -f "$0")")")"
LLAMA_CPP_REF="${LLAMA_CPP_REF:-5556cd369a4c86e093952ba9529cc5cb121b65e9}"

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
cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

git init -q "$TMP_DIR"
git -C "$TMP_DIR" remote add origin https://github.com/ggerganov/llama.cpp.git
git -C "$TMP_DIR" fetch --depth 1 origin "$LLAMA_CPP_REF"
git -C "$TMP_DIR" checkout --detach -q FETCH_HEAD

echo "Building..."
cmake -S "$TMP_DIR" -B "$TMP_DIR/build" -DCMAKE_BUILD_TYPE=Release $CMAKE_FLAGS
cmake --build "$TMP_DIR/build" --config Release -j"$(nproc)"

if command -v strip >/dev/null 2>&1; then
    strip --strip-unneeded "$TMP_DIR/build/bin/llama-server" 2>/dev/null || true
    find "$TMP_DIR/build/bin" -maxdepth 1 -type f \( -name 'libllama*.so*' -o -name 'libggml*.so*' -o -name 'libmtmd*.so*' \) -exec strip --strip-unneeded {} + 2>/dev/null || true
fi

echo "Installing to $BASE_DIR/gpu/server-gpu..."
mkdir -p "$BASE_DIR/gpu"
cp "$TMP_DIR/build/bin/llama-server" "$BASE_DIR/gpu/server-gpu"
find "$BASE_DIR/gpu" -maxdepth 1 -type f \( -name 'libllama*.so*' -o -name 'libggml*.so*' -o -name 'libmtmd*.so*' \) -delete
shopt -s nullglob
GPU_RUNTIME_LIBS=("$TMP_DIR"/build/bin/libllama*.so* "$TMP_DIR"/build/bin/libggml*.so* "$TMP_DIR"/build/bin/libmtmd*.so*)
if [[ ${#GPU_RUNTIME_LIBS[@]} -gt 0 ]]; then
    cp "${GPU_RUNTIME_LIBS[@]}" "$BASE_DIR/gpu/"
fi
shopt -u nullglob

echo "Optimization complete."
