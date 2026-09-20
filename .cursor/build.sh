#!/usr/bin/env bash
# Builds the firmware defined in build.yaml (board efogtech_trackball_0 with
# USB logging). Syncs config/ into the isolated west workspace, builds, and
# copies the resulting UF2 back into the repo root.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKSPACE="${ZMK_WORKSPACE:-$HOME/zmk-workspace}"
ZEPHYR_SDK_VERSION="0.16.3"

export PATH="$HOME/.local/bin:$PATH"
export ZEPHYR_SDK_INSTALL_DIR="$HOME/zephyr-sdk-${ZEPHYR_SDK_VERSION}"
export ZEPHYR_TOOLCHAIN_VARIANT="zephyr"

BOARD="efogtech_trackball_0"
SNIPPET="zmk-usb-logging"

# Keep the workspace's config in sync with the checked-out repo.
mkdir -p "$WORKSPACE/config"
rm -rf "$WORKSPACE/config"
mkdir -p "$WORKSPACE/config"
cp -R "$REPO_ROOT/config/." "$WORKSPACE/config/"

cd "$WORKSPACE"
west build -p -s zmk/app -d build -b "$BOARD" -S "$SNIPPET" -- \
  -DZMK_CONFIG="$WORKSPACE/config" \
  -DZMK_EXTRA_MODULES="$REPO_ROOT"

cp "$WORKSPACE/build/zephyr/zmk.uf2" "$REPO_ROOT/firmware.uf2"
echo "==> Firmware written to $REPO_ROOT/firmware.uf2"
ls -la "$REPO_ROOT/firmware.uf2"
