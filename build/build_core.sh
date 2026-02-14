#!/usr/bin/env bash
# OpenAkita 核心包构建脚本 (Linux/macOS)
# 输出: 仅包含核心依赖的安装包 (~180MB)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SETUP_CENTER_DIR="$PROJECT_ROOT/apps/setup-center"
RESOURCE_DIR="$SETUP_CENTER_DIR/src-tauri/resources"

echo "============================================"
echo "  OpenAkita 核心包构建"
echo "============================================"

# Step 1: 打包 Python 后端 (核心模式)
echo ""
echo "[1/3] 打包 Python 后端 (core mode)..."
python3 "$SCRIPT_DIR/build_backend.py" --mode core

# Step 2: 复制打包结果到 Tauri resources
echo ""
echo "[2/3] 复制后端到 Tauri resources..."
DIST_SERVER_DIR="$PROJECT_ROOT/dist/openakita-server"
TARGET_DIR="$RESOURCE_DIR/openakita-server"

rm -rf "$TARGET_DIR"
mkdir -p "$RESOURCE_DIR"
cp -r "$DIST_SERVER_DIR" "$TARGET_DIR"
echo "  已复制到: $TARGET_DIR"

# Step 3: 构建 Tauri 应用
echo ""
echo "[3/3] 构建 Tauri 应用..."
cd "$SETUP_CENTER_DIR"
npm run tauri build

echo ""
echo "============================================"
echo "  核心包构建完成!"
echo "  安装包位于: $SETUP_CENTER_DIR/src-tauri/target/release/bundle/"
echo "============================================"
