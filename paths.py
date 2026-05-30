"""
paths.py — 统一的路径与文件扫描工具
集中 app_root / config_path / scan_files，消除 gui.py 与 archive.py 的重复定义。
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List

from archive_engine import scan_files as _engine_scan_files


def app_root() -> Path:
    """支持 pyinstaller 打包后的运行目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def config_path() -> Path:
    return app_root() / "categories.yaml"


def scan_files(case_dir: Path) -> List[Path]:
    return _engine_scan_files(case_dir)
