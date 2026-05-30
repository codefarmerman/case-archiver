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
    """可执行文件/脚本所在目录（用户可见、可放置外部配置）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def resource_path(name: str) -> Path:
    """定位随程序分发的资源文件（categories.yaml / style.qss）。
    PyInstaller --onefile 把 --add-data 的资源解压到 sys._MEIPASS；
    优先用 exe 同目录的外部副本（便于用户改配置），否则回退到 _MEIPASS。
    """
    external = app_root() / name
    if external.exists():
        return external
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / name
        if bundled.exists():
            return bundled
    return external  # 都没有时返回外部路径（调用方负责处理不存在）


def config_path() -> Path:
    return resource_path("categories.yaml")


def scan_files(case_dir: Path) -> List[Path]:
    return _engine_scan_files(case_dir)
