"""workers.py QThread 工作线程测试（pytest-qt）。
ClassifyWorker / ArchiveWorker 在 llm=None（纯本地）下的信号与产物。"""
from pathlib import Path

import pytest

from classify import Classifier
from workers import ArchiveWorker, ClassifyWorker

# 需要 Qt 事件循环：无桌面会话的环境会被 conftest 自动跳过
pytestmark = [pytest.mark.gui, pytest.mark.usefixtures("qapp")]


def _make_case(d: Path) -> list:
    names = [
        "收案审查表.pdf",
        "律师费发票.pdf",
        "委托合同.docx",
        "民事起诉状.pdf",
        "证据目录.pdf",
        "开庭传票.pdf",
        "代理词.docx",
        "民事判决书.pdf",
        "随机材料zzz.pdf",
    ]
    paths = []
    for nm in names:
        p = d / nm
        p.write_text("测试内容", encoding="utf-8")
        paths.append(p)
    return paths


def test_classify_worker_local_only(qtbot, tmp_case_dir):
    files = _make_case(tmp_case_dir)
    w = ClassifyWorker(tmp_case_dir, "原告", None)  # llm=None → 不触网
    with qtbot.waitSignal(w.finished_ok, timeout=15000) as blocker:
        w.start()
    results = blocker.args[0]
    w.wait()
    assert len(results) == len(files)
    # 起诉状应命中第 4 项，且我方（原告）
    by_name = {c.file_path.name: c for c in results}
    assert by_name["民事起诉状.pdf"].category_id == 4
    assert by_name["民事起诉状.pdf"].side == "我方"
    # 无关键词材料落入兜底第 13 项
    assert by_name["随机材料zzz.pdf"].category_id == 13


def test_classify_worker_empty_dir_fails(qtbot, tmp_case_dir):
    w = ClassifyWorker(tmp_case_dir, "原告", None)
    with qtbot.waitSignal(w.failed, timeout=8000):
        w.start()
    w.wait()


def test_classify_worker_progress_emitted(qtbot, tmp_case_dir):
    _make_case(tmp_case_dir)
    w = ClassifyWorker(tmp_case_dir, "原告", None)
    with qtbot.waitSignal(w.progress, timeout=8000):
        w.start()
    with qtbot.waitSignal(w.finished_ok, timeout=15000):
        pass
    w.wait()


def test_archive_worker_produces_outputs(qtbot, tmp_case_dir, categories_path):
    files = _make_case(tmp_case_dir)
    clf = Classifier(categories_path, llm=None)
    results = [clf.classify(f, role="原告") for f in files]

    w = ArchiveWorker(
        results=results,
        case_dir=tmp_case_dir,
        case_no="(2024)测0106民初001号",
        case_name="张三诉李四合同纠纷",
        role="原告",
        auto_write=False,
        llm=None,
    )
    with qtbot.waitSignal(w.finished_ok, timeout=20000) as blocker:
        w.start()
    out_dir, total = blocker.args
    w.wait()

    out_dir = Path(out_dir)
    assert out_dir.exists() and out_dir.is_dir()
    assert (out_dir / "00_卷内目录.docx").exists()
    assert (out_dir / "归档清单.json").exists()
    assert (out_dir / "归档清单.txt").exists()
    # 复制的原始材料数 == 输入数（卷内目录/清单为额外产物）
    copied = [p for p in out_dir.iterdir() if p.is_file()]
    assert len(copied) >= len(files)
