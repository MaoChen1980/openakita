# -*- mode: python ; coding: utf-8 -*-
"""
OpenAkita PyInstaller spec 文件

用法:
  核心包: pyinstaller build/openakita.spec  (默认排除重型依赖)
  完整包: OPENAKITA_BUILD_MODE=full pyinstaller build/openakita.spec

环境变量:
  OPENAKITA_BUILD_MODE: "core" (默认) 或 "full"
"""

import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(SPECPATH).parent
SRC_DIR = PROJECT_ROOT / "src"

# 构建模式
BUILD_MODE = os.environ.get("OPENAKITA_BUILD_MODE", "core")

# ============== Hidden Imports ==============
# PyInstaller 静态分析可能遗漏的动态导入

hidden_imports_core = [
    # -- openakita 内部模块 --
    "openakita",
    "openakita.main",
    "openakita.config",
    "openakita.runtime_env",
    "openakita.core.agent",
    "openakita.core.llm",
    "openakita.core.tools",
    "openakita.memory",
    "openakita.memory.manager",
    "openakita.memory.vector_store",
    "openakita.memory.daily_consolidator",
    "openakita.memory.consolidator",
    "openakita.channels",
    "openakita.channels.gateway",
    "openakita.channels.base",
    "openakita.channels.types",
    "openakita.channels.adapters",
    "openakita.channels.adapters.telegram",
    "openakita.channels.adapters.feishu",
    "openakita.channels.adapters.dingtalk",
    "openakita.channels.adapters.onebot",
    "openakita.channels.adapters.qq_official",
    "openakita.channels.adapters.wework_bot",
    "openakita.channels.media",
    "openakita.channels.media.handler",
    "openakita.channels.media.audio_utils",
    "openakita.channels.media.storage",
    "openakita.skills",
    "openakita.skills.loader",
    "openakita.evolution",
    "openakita.evolution.installer",
    "openakita.setup_center",
    "openakita.setup_center.bridge",
    "openakita.orchestration",
    "openakita.orchestration.bus",
    "openakita.tracing",
    "openakita.logging",
    "openakita.tools",
    "openakita.tools.shell",
    # -- 第三方核心依赖 --
    "uvicorn",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "fastapi",
    "pydantic",
    "pydantic_settings",
    "anthropic",
    "openai",
    "httpx",
    "aiofiles",
    "aiosqlite",
    "yaml",
    "dotenv",
    "tenacity",
    "typer",
    "rich",
    "git",
    "mcp",
    "nest_asyncio",
]

hidden_imports_full = [
    # -- 重型可选依赖 (仅完整包包含) --
    "sentence_transformers",
    "chromadb",
    "torch",
    "playwright",
    "zmq",
    "whisper",
]

hidden_imports = hidden_imports_core
if BUILD_MODE == "full":
    hidden_imports += hidden_imports_full

# ============== Excludes ==============
# 核心包排除的重型依赖

excludes_core = [
    "sentence_transformers",
    "chromadb",
    "torch",
    "torchvision",
    "torchaudio",
    "playwright",
    "zmq",
    "pyzmq",
    "whisper",
    "browser_use",
    "langchain",
    "langchain_openai",
    # 其他不需要的大型包
    "matplotlib",
    "scipy",
    "numpy.testing",
    "pandas",
    "PIL",
    "tkinter",
    "unittest",
    "test",
    "tests",
]

excludes = excludes_core if BUILD_MODE == "core" else []

# ============== Data Files ==============
# 需要打包的非 Python 文件

datas = []

# rich._unicode_data: 文件名含连字符(unicode17-0-0.py)，PyInstaller 无法通过
# hidden_imports 处理，必须作为 data 文件复制
import rich._unicode_data as _rud
_rud_dir = str(Path(_rud.__file__).parent)
datas.append((_rud_dir, "rich/_unicode_data"))

# 服务商列表（唯一数据源，前后端共享）
# 必须打包到 openakita/llm/registries/ 目录下，Python 通过 Path(__file__).parent 读取
providers_json = SRC_DIR / "openakita" / "llm" / "registries" / "providers.json"
if providers_json.exists():
    datas.append((str(providers_json), "openakita/llm/registries"))

# pyproject.toml（版本号来源，打包后 __init__.py 通过相对路径读取）
# PyInstaller 打包后 openakita 模块在 _internal/ 下，pyproject.toml 放在其上三层
# 即 _internal/openakita/__init__.py 的 parent.parent.parent 指向 _internal/../../
# 实际在打包模式下靠这个路径找不到，所以改用直接写入版本文件的方式
_pyproject_path = PROJECT_ROOT / "pyproject.toml"
if _pyproject_path.exists():
    import tomllib
    with open(_pyproject_path, "rb") as _f:
        _pyproject_version = tomllib.load(_f)["project"]["version"]
    # 写一个简单的版本文件到打包目录
    _version_file = SRC_DIR / "openakita" / "_bundled_version.txt"
    _version_file.write_text(_pyproject_version, encoding="utf-8")
    datas.append((str(_version_file), "openakita"))

# 内置 Python 解释器 + pip（打包模式下安装可选模块无需主机预装 Python）
# 将系统 python.exe 和 pip 模块打入 _internal/，Rust 端通过 find_pip_python 发现
import shutil
_sys_python_exe = Path(sys.executable)
if _sys_python_exe.exists():
    datas.append((str(_sys_python_exe), "."))  # python.exe -> _internal/

# pip 及其依赖（pip install 需要的最小集合）
import pip
_pip_dir = str(Path(pip.__file__).parent)
datas.append((_pip_dir, "pip"))

# pip 的 vendor 依赖（pip._vendor 包含 requests, urllib3 等）
# 已包含在 pip 目录下，无需额外处理

# 内置系统技能
skills_dir = PROJECT_ROOT / "skills" / "system"
if skills_dir.exists():
    datas.append((str(skills_dir), "openakita/builtin_skills/system"))

# ============== Analysis ==============

a = Analysis(
    [str(SRC_DIR / "openakita" / "__main__.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="openakita-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="openakita-server",
)
