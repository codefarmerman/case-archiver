"""gui.py 冒烟测试（pytest-qt）。
只验证 UI 逻辑（构建、校验、表格填充、并发守卫、关闭守卫），不触发真实分类/网络。"""
from pathlib import Path

import pytest

from classify import Classification

# 需要 Qt GUI：无桌面会话的环境会被 conftest 自动跳过
pytestmark = pytest.mark.gui


@pytest.fixture
def main_window(qtbot, monkeypatch):
    import gui

    # 避免弹出 API Key 对话框 / 读真实凭据 / 写真实配置文件
    monkeypatch.setattr(gui, "load_api_key", lambda: "sk-test-key-xxxx")
    monkeypatch.setattr(gui, "get_setting", lambda name, default=None: default)
    monkeypatch.setattr(gui, "set_setting", lambda *a, **k: None)

    win = gui.MainWindow()
    qtbot.addWidget(win)
    yield win
    # teardown：pytest-qt 会在结束时关闭窗口触发 closeEvent。
    # 若某测试残留了"运行中"的假 worker，closeEvent 会弹模态 QMessageBox，
    # 在 offscreen（CI）下会触发访问冲突崩溃。这里先清空，确保安全关闭。
    win._classify_worker = None
    win._archive_worker = None


def test_window_builds_and_categories_loaded(main_window):
    assert len(main_window.category_choices) == 13
    assert main_window.table.columnCount() == 5
    assert main_window.table.rowCount() == 0  # 初始空


def test_validate_inputs(main_window):
    main_window.case_dir = None
    assert main_window._validate_inputs() == "请先选择案件文件夹"

    # 给一个存在的目录但不填案号
    main_window.case_dir = Path(__file__).resolve().parent
    main_window.input_case_no.setText("")
    assert main_window._validate_inputs() == "请填写案号"

    main_window.input_case_no.setText("(2024)测001号")
    main_window.input_case_name.setText("")
    assert main_window._validate_inputs() == "请填写案由 / 当事人"

    main_window.input_case_name.setText("张三诉李四")
    assert main_window._validate_inputs() is None


def _sample_results():
    return [
        Classification(Path("民事起诉状.pdf"), 4, "诉讼文书", "诉讼文书", 0.95, "filename", side="我方"),
        Classification(Path("随机zzz.pdf"), 13, "其他", "其他", 0.3, "fallback"),
    ]


def test_populate_table(main_window):
    results = _sample_results()
    main_window.results = results
    main_window._populate_table(results)
    assert main_window.table.rowCount() == 2
    # 第 0 行文件名列
    assert main_window.table.item(0, 1).text() == "民事起诉状.pdf"
    # 归类下拉存在
    assert main_window.table.cellWidget(0, 2) is not None


def test_category_change_marks_manual(main_window):
    results = _sample_results()
    main_window.results = results
    main_window._populate_table(results)

    combo = main_window.table.cellWidget(1, 2)  # 第二行（兜底第13项）
    # 找到“01”项（第1项）的索引并切换
    target_index = next(i for i in range(combo.count()) if combo.itemData(i) == 1)
    combo.setCurrentIndex(target_index)

    assert main_window.results[1].category_id == 1
    assert main_window.results[1].method == "人工"
    assert main_window.results[1].confidence >= 0.99


def test_concurrency_guard_blocks_second_classify(main_window, monkeypatch):
    """上一次分类未结束时，再次 on_classify 应直接返回，不替换 worker。"""

    class _FakeRunning:
        def isRunning(self):
            return True

    fake = _FakeRunning()
    main_window._classify_worker = fake
    main_window.case_dir = Path(__file__).resolve().parent
    main_window.input_case_no.setText("X")
    main_window.input_case_name.setText("Y")

    main_window.on_classify()
    # worker 未被新对象替换
    assert main_window._classify_worker is fake
    # 清理：避免 teardown 关窗时 closeEvent 因"运行中"弹模态在 offscreen 崩溃
    main_window._classify_worker = None


def test_close_event_blocked_when_running(main_window, monkeypatch):
    import gui

    warned = {"called": False}
    monkeypatch.setattr(
        gui.QtWidgets.QMessageBox, "warning",
        lambda *a, **k: warned.__setitem__("called", True),
    )

    class _FakeRunning:
        def isRunning(self):
            return True

    main_window._archive_worker = _FakeRunning()

    class _Ev:
        def __init__(self):
            self.accepted = True

        def ignore(self):
            self.accepted = False

        def accept(self):
            self.accepted = True

    ev = _Ev()
    main_window.closeEvent(ev)
    assert ev.accepted is False
    assert warned["called"] is True
    # 清理：避免 teardown 关窗时 closeEvent 因"运行中"弹模态在 offscreen 崩溃
    main_window._archive_worker = None
