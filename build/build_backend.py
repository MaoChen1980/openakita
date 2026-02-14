#!/usr/bin/env python3
"""
OpenAkita Python 后端打包脚本

用法:
  python build/build_backend.py --mode core    # 核心包 (~100-150MB)
  python build/build_backend.py --mode full    # 完整包 (~600-800MB)
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = PROJECT_ROOT / "build" / "openakita.spec"
DIST_DIR = PROJECT_ROOT / "dist"
OUTPUT_DIR = DIST_DIR / "openakita-server"


def run_cmd(cmd: list[str], env: dict | None = None, **kwargs) -> subprocess.CompletedProcess:
    """执行命令并打印输出"""
    print(f"  $ {' '.join(cmd)}")
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, env=merged_env, **kwargs)
    if result.returncode != 0:
        print(f"  ❌ 命令失败 (exit {result.returncode})")
        sys.exit(1)
    return result


def check_pyinstaller():
    """检查 PyInstaller 是否已安装"""
    try:
        import PyInstaller  # noqa: F401
        print(f"  ✓ PyInstaller {PyInstaller.__version__} 已安装")
    except ImportError:
        print("  ⚠ PyInstaller 未安装，正在安装...")
        run_cmd([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean_dist():
    """清理之前的构建输出"""
    if OUTPUT_DIR.exists():
        print(f"  🗑 清理旧的构建输出: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

    build_tmp = PROJECT_ROOT / "build" / "openakita-server"
    if build_tmp.exists():
        shutil.rmtree(build_tmp)


def build_backend(mode: str):
    """执行 PyInstaller 打包"""
    print(f"\n{'='*60}")
    print(f"  OpenAkita 后端打包 - 模式: {mode.upper()}")
    print(f"{'='*60}\n")

    print("[1/4] 检查依赖...")
    check_pyinstaller()

    print("\n[2/4] 清理旧构建...")
    clean_dist()

    print("\n[3/4] 执行 PyInstaller 打包...")
    env = {"OPENAKITA_BUILD_MODE": mode}
    run_cmd(
        [
            sys.executable, "-m", "PyInstaller",
            str(SPEC_FILE),
            "--distpath", str(DIST_DIR),
            "--workpath", str(PROJECT_ROOT / "build" / "pyinstaller_work"),
            "--noconfirm",
        ],
        env=env,
    )

    print("\n[4/4] 验证构建结果...")
    if sys.platform == "win32":
        exe_path = OUTPUT_DIR / "openakita-server.exe"
    else:
        exe_path = OUTPUT_DIR / "openakita-server"

    if not exe_path.exists():
        print(f"  ❌ 可执行文件不存在: {exe_path}")
        sys.exit(1)

    # 测试可执行文件
    try:
        result = subprocess.run(
            [str(exe_path), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"  ✓ 可执行文件验证通过: {exe_path}")
        else:
            print(f"  ⚠ 可执行文件运行返回非零退出码: {result.returncode}")
            print(f"    stderr: {result.stderr[:500]}")
    except subprocess.TimeoutExpired:
        print("  ⚠ 可执行文件运行超时 (可能正常，继续)")
    except Exception as e:
        print(f"  ⚠ 验证时发生异常: {e}")

    # 统计大小
    total_size = sum(f.stat().st_size for f in OUTPUT_DIR.rglob("*") if f.is_file())
    size_mb = total_size / (1024 * 1024)
    print(f"\n  📦 构建完成!")
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"  总大小: {size_mb:.1f} MB")
    print(f"  模式: {mode.upper()}")


def main():
    parser = argparse.ArgumentParser(description="OpenAkita 后端打包脚本")
    parser.add_argument(
        "--mode",
        choices=["core", "full"],
        default="core",
        help="打包模式: core=核心包(排除重型依赖), full=完整包(包含全部依赖)",
    )
    args = parser.parse_args()
    build_backend(args.mode)


if __name__ == "__main__":
    main()
