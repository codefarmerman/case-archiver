"""pytest 共享 fixtures 与路径设置。"""
import sys
from pathlib import Path

# 让测试能 import 项目根目录的模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest


@pytest.fixture
def categories_path() -> Path:
    return ROOT / "categories.yaml"


@pytest.fixture
def tmp_case_dir(tmp_path: Path) -> Path:
    """临时案件文件夹。"""
    d = tmp_path / "case"
    d.mkdir()
    return d
