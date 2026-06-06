"""pytest 共享 fixtures 与路径设置。"""
import subprocess
import sys
from pathlib import Path

# 让测试能 import 项目根目录的模块
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest


def _detect_qt_gui() -> bool:
    """用子进程探测能否安全创建 QApplication/QWidget。
    某些无桌面会话的沙箱 / CI 环境下，Qt 平台插件初始化会触发原生 fast-fail
    崩溃（0xC0000409），无法用 try/except 捕获，会直接杀死整个 pytest 进程。
    因此用一次性子进程探测：探测进程崩溃即判定 GUI 不可用，对应测试自动跳过。
    在真实桌面（用户机器）上探测成功，GUI/worker 测试将正常运行。"""
    probe = (
        "import sys\n"
        "from PyQt5 import QtWidgets\n"
        "app = QtWidgets.QApplication(sys.argv)\n"
        "w = QtWidgets.QWidget()\n"
        "print('QT_OK')\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, timeout=30,
        )
        return proc.returncode == 0 and "QT_OK" in (proc.stdout or "")
    except Exception:
        return False


GUI_AVAILABLE = _detect_qt_gui()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "gui: 需要可用的 Qt GUI 环境（无桌面会话时自动跳过）"
    )


def pytest_collection_modifyitems(config, items):
    if GUI_AVAILABLE:
        return
    skip_gui = pytest.mark.skip(reason="当前环境无法初始化 Qt GUI（无桌面会话），跳过 GUI/worker 测试")
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
