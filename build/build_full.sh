#!/usr/bin/env bash
# OpenAkita 完整包构建脚本 (Linux/macOS)
# 输出: 包含全部依赖和模型的安装包 (~1GB)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SETUP_CENTER_DIR="$PROJECT_ROOT/apps/setup-center"
RESOURCE_DIR="$SETUP_CENTER_DIR/src-tauri/resources"

echo "============================================"
echo "  OpenAkita 完整包构建"
echo "============================================"

# Step 1: 打包 Python 后端 (完整模式)
echo ""
echo "[1/4] 打包 Python 后端 (full mode)..."
python3 "$SCRIPT_DIR/build_backend.py" --mode full

# Step 2: 预打包可选模块
echo ""
echo "[2/4] 预打包可选模块..."
python3 "$SCRIPT_DIR/bundle_modules.py"

# Step 3: 复制到 Tauri resources
echo ""
echo "[3/4] 复制后端和模块到 Tauri resources..."
DIST_SERVER_DIR="$PROJECT_ROOT/dist/openakita-server"
MODULES_DIR="$SCRIPT_DIR/modules"
TARGET_SERVER_DIR="$RESOURCE_DIR/openakita-server"
TARGET_MODULES_DIR="$RESOURCE_DIR/modules"

rm -rf "$TARGET_SERVER_DIR" "$TARGET_MODULES_DIR"
mkdir -p "$RESOURCE_DIR"
cp -r "$DIST_SERVER_DIR" "$TARGET_SERVER_DIR"
if [ -d "$MODULES_DIR" ]; then
    cp -r "$MODULES_DIR" "$TARGET_MODULES_DIR"
fi
echo "  后端: $TARGET_SERVER_DIR"
echo "  模块: $TARGET_MODULES_DIR"

# Step 4: 构建 Tauri 应用（通过 TAURI_CONFIG 追加 modules 资源）
echo ""
echo "[4/4] 构建 Tauri 应用..."
cd "$SETUP_CENTER_DIR"
# 完整包需要额外包含 modules 资源目录
export TAURI_CONFIG='{"bundle":{"resources":["resources/openakita-server/","resources/modules/"]}}'
npx tauri build

echo ""
echo "============================================"
echo "  完整包构建完成!"
echo "  安装包位于: $SETUP_CENTER_DIR/src-tauri/target/release/bundle/"
echo "============================================"
