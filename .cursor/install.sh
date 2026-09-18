#!/usr/bin/env bash
# Idempotent setup for the ZMK / Zephyr firmware toolchain used by this repo.
# Installs system build deps, west, the Zephyr SDK (arm-zephyr-eabi), python
# deps, initializes an isolated west workspace and performs an initial build.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${ZMK_WORKSPACE:-$HOME/zmk-workspace}"
ZEPHYR_SDK_VERSION="0.16.3"
ZEPHYR_SDK_DIR="$HOME/zephyr-sdk-${ZEPHYR_SDK_VERSION}"

export PATH="$HOME/.local/bin:$PATH"
export ZEPHYR_SDK_INSTALL_DIR="$ZEPHYR_SDK_DIR"
export ZEPHYR_TOOLCHAIN_VARIANT="zephyr"

echo "==> Installing system packages"
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  git curl wget \
  ninja-build gperf ccache dfu-util device-tree-compiler \
  python3-dev python3-venv python3-pip python3-setuptools python3-wheel \
  xz-utils file make gcc gcc-multilib g++-multilib libsdl2-dev libmagic1 \
  protobuf-compiler

echo "==> Installing west"
pip3 install --break-system-packages --user --upgrade west

echo "==> Installing Zephyr SDK ${ZEPHYR_SDK_VERSION} (arm-zephyr-eabi)"
if [ ! -d "$ZEPHYR_SDK_DIR" ]; then
  tmp_tar="$(mktemp -d)/zephyr-sdk-min.tar.xz"
  wget -q "https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-x86_64_minimal.tar.xz" -O "$tmp_tar"
  tar xf "$tmp_tar" -C "$HOME"
  rm -f "$tmp_tar"
fi
# (Re-)register the toolchain and CMake package; safe to run repeatedly.
"$ZEPHYR_SDK_DIR/setup.sh" -t arm-zephyr-eabi -h -c

echo "==> Initializing west workspace at ${WORKSPACE}"
# The repo root ships zephyr/module.yml, so the west workspace must live
# outside the repo (matching ZMK's CI) to avoid clobbering it. The repo is
# passed to the build as an extra Zephyr module (it provides the board root).
mkdir -p "$WORKSPACE/config"
cp -R "$REPO_ROOT/config/." "$WORKSPACE/config/"
cd "$WORKSPACE"
if [ ! -d "$WORKSPACE/.west" ]; then
  west init -l "$WORKSPACE/config"
fi
west update --fetch-opt=--filter=tree:0

echo "==> Installing Zephyr python requirements"
pip3 install --break-system-packages --user -r "$WORKSPACE/zephyr/scripts/requirements-base.txt"
pip3 install --break-system-packages --user protobuf grpcio-tools

west zephyr-export

echo "==> Performing initial firmware build"
"$REPO_ROOT/.cursor/build.sh"

echo "==> Setup complete"
