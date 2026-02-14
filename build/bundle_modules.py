#!/usr/bin/env python3
"""
OpenAkita 可选模块预打包脚本 (完整包用)

将可选模块的 wheels 和模型文件预下载到 build/modules/ 目录，
供完整包安装器直接打包使用。

用法:
  python build/bundle_modules.py                    # 下载所有模块
  python build/bundle_modules.py --module vector-memory  # 仅下载向量记忆模块
  python build/bundle_modules.py --mirror https://pypi.tuna.tsinghua.edu.cn/simple  # 使用镜像源
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = PROJECT_ROOT / "build" / "modules"

# 模块定义: module_id -> {packages, model_commands}
MODULE_DEFS = {
    "vector-memory": {
        "description": "向量记忆增强 (语义搜索)",
        "packages": [
            "sentence-transformers>=2.2.0",
            "chromadb>=0.4.0",
        ],
        "model_script": """
import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("shibing624/text2vec-base-chinese")
print(f"模型已下载到: {model._model_card_text if hasattr(model, '_model_card_text') else 'cache'}")
""",
    },
    "browser": {
        "description": "浏览器自动化 (playwright)",
        "packages": [
            "playwright>=1.40.0",
        ],
        "post_install": [sys.executable, "-m", "playwright", "install", "chromium"],
    },
    "whisper": {
        "description": "语音识别 (OpenAI Whisper)",
        "packages": [
            "openai-whisper>=20231117",
            "static-ffmpeg>=2.7",
        ],
    },
    "orchestration": {
        "description": "多 Agent 协同 (ZeroMQ)",
        "packages": [
            "pyzmq>=25.0.0",
        ],
    },
}


def run_cmd(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """执行命令"""
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"  ⚠ 命令返回非零退出码: {result.returncode}")
    return result


def download_wheels(module_id: str, module_def: dict, mirror: str | None = None):
    """下载模块的 wheel 文件"""
    wheels_dir = MODULES_DIR / module_id / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)

    packages = module_def["packages"]
    cmd = [
        sys.executable, "-m", "pip", "download",
        "--dest", str(wheels_dir),
        "--only-binary=:all:",
        *packages,
    ]
    if mirror:
        cmd.extend(["-i", mirror])

    print(f"\n  📥 下载 {module_id} 的 wheel 包...")
    result = run_cmd(cmd)
    if result.returncode != 0:
        # 尝试不带 --only-binary 重新下载 (有些包没有预编译 wheel)
        print("  ⚠ 仅二进制下载失败，尝试包含源码包...")
        cmd2 = [
            sys.executable, "-m", "pip", "download",
            "--dest", str(wheels_dir),
            *packages,
        ]
        if mirror:
            cmd2.extend(["-i", mirror])
        run_cmd(cmd2)

    # 统计
    wheel_files = list(wheels_dir.glob("*.whl")) + list(wheels_dir.glob("*.tar.gz"))
    total_size = sum(f.stat().st_size for f in wheel_files)
    print(f"  ✓ {module_id}: {len(wheel_files)} 个包, {total_size / 1024 / 1024:.1f} MB")


def download_model(module_id: str, module_def: dict):
    """下载模块需要的模型文件"""
    model_script = module_def.get("model_script")
    if not model_script:
        return

    models_dir = MODULES_DIR / module_id / "models"
    models_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  🤖 下载 {module_id} 的模型文件...")
    # 设置模型缓存目录
    env = {
        **os.environ,
        "TRANSFORMERS_CACHE": str(models_dir),
        "HF_HOME": str(models_dir),
        "HF_ENDPOINT": os.environ.get("HF_ENDPOINT", "https://hf-mirror.com"),
    }
    result = subprocess.run(
        [sys.executable, "-c", model_script],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        total_size = sum(
            f.stat().st_size for f in models_dir.rglob("*") if f.is_file()
        )
        print(f"  ✓ 模型下载完成: {total_size / 1024 / 1024:.1f} MB")
    else:
        print(f"  ⚠ 模型下载失败: {result.stderr[:500]}")


def bundle_module(module_id: str, mirror: str | None = None):
    """打包单个模块"""
    module_def = MODULE_DEFS.get(module_id)
    if not module_def:
        print(f"  ❌ 未知模块: {module_id}")
        return False

    print(f"\n{'─'*50}")
    print(f"  📦 打包模块: {module_id} - {module_def['description']}")
    print(f"{'─'*50}")

    download_wheels(module_id, module_def, mirror)
    download_model(module_id, module_def)
    return True


def main():
    parser = argparse.ArgumentParser(description="OpenAkita 可选模块预打包脚本")
    parser.add_argument(
        "--module",
        choices=list(MODULE_DEFS.keys()),
        help="仅打包指定模块 (不指定则打包全部)",
    )
    parser.add_argument(
        "--mirror",
        help="PyPI 镜像源 URL (如 https://pypi.tuna.tsinghua.edu.cn/simple)",
    )
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  OpenAkita 可选模块预打包")
    print(f"{'='*60}")
    print(f"  输出目录: {MODULES_DIR}")
    if args.mirror:
        print(f"  镜像源: {args.mirror}")

    modules_to_bundle = [args.module] if args.module else list(MODULE_DEFS.keys())

    for module_id in modules_to_bundle:
        bundle_module(module_id, args.mirror)

    # 汇总
    print(f"\n{'='*60}")
    print("  打包汇总")
    print(f"{'='*60}")
    total = 0
    for module_id in modules_to_bundle:
        module_dir = MODULES_DIR / module_id
        if module_dir.exists():
            size = sum(f.stat().st_size for f in module_dir.rglob("*") if f.is_file())
            total += size
            print(f"  {module_id}: {size / 1024 / 1024:.1f} MB")
    print(f"  ────────────────────")
    print(f"  总计: {total / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
