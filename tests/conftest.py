"""pytest 共享 fixtures 与路径设置。"""
import os
import sys
from pathlib import Path

# 让测试能 import 项目根目录的模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest


def _gui_tests_enabled() -> bool:
    """GUI / worker 冒烟测试是否启用。

    默认**关闭**。原因：在 offscreen / 无桌面会话（CI、容器、沙箱）下，PyQt5 控件的
    创建与 teardown 会触发原生层崩溃（0xC0000409 / access violation），且无法用
    try/except 捕获——一旦发生会直接杀死整个 pytest 进程，使全部测试报失败。
    这类崩溃是 Qt 在 headless 环境的固有脆弱性，而非产品缺陷。

    因此把这些测试设为**显式 opt-in**：在真实桌面上设 `RUN_GUI_TESTS=1` 即可运行，
    用于人工/本地验证；CI 不设该变量，自动跳过，保持稳定绿。
    """
    return os.environ.get("RUN_GUI_TESTS", "").strip().lower() in ("1", "true", "yes", "on")


GUI_AVAILABLE = _gui_tests_enabled()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "gui: 需要真实桌面的 Qt GUI 测试（默认跳过，设 RUN_GUI_TESTS=1 开启）"
    )


def pytest_collection_modifyitems(config, items):
    if GUI_AVAILABLE:
        return
    skip_gui = pytest.mark.skip(
        reason="GUI/worker 测试默认跳过（headless 下 Qt 易崩溃）；在桌面设 RUN_GUI_TESTS=1 运行"
    )
    for item in items:
        if "gui" in item.keywords:
            item.add_marker(skip_gui)


@pytest.fixture
def categories_path() -> Path:
    return ROOT / "categories.yaml"


@pytest.fixture
def tmp_case_dir(tmp_path: Path) -> Path:
    """临时案件文件夹。"""
    d = tmp_path / "case"
    d.mkdir()
    return d
