"""归档引擎测试：排序、输出目录、复制防覆盖。"""
from pathlib import Path

from archive_engine import (
    copy_files,
    make_output_dir,
    sort_all_results,
    sort_category4,
)
from classify import Classification


def _mk(name: str, cat_id: int, side: str = "", weight: int = 0) -> Classification:
    return Classification(
        file_path=Path(name),
        category_id=cat_id,
        category_name="",
        short_name="",
        confidence=0.95,
        method="filename",
        side=side,
        sort_weight=weight,
    )


def test_sort_all_orders_by_category():
    items = [_mk("a", 4), _mk("b", 1), _mk("c", 13), _mk("d", 2)]
    out = sort_all_results(items)
    assert [c.category_id for c in out] == [1, 2, 4, 13]


def test_sort_category4_litigation_progression():
    # 诉讼推进顺序：起诉(1) → 答辩(2) → 上诉(4)
    items = [
        _mk("上诉状", 4, side="我方", weight=4),
        _mk("起诉状", 4, side="我方", weight=1),
        _mk("答辩状", 4, side="对方", weight=2),
    ]
    out = sort_category4(items)
    assert [c.sort_weight for c in out] == [1, 2, 4]


def test_sort_category4_my_side_first_same_weight():
    items = [
        _mk("对方文书", 4, side="对方", weight=1),
        _mk("我方文书", 4, side="我方", weight=1),
    ]
    out = sort_category4(items)
    assert out[0].side == "我方"
    assert out[1].side == "对方"


def test_make_output_dir_no_overwrite(tmp_path):
    case_dir = tmp_path / "案件"
    case_dir.mkdir()
    d1 = make_output_dir(case_dir, "(2024)案号001")
    assert d1.exists()
    # 第二次同案号同日 → 不应是同一目录（带时间戳）
    d2 = make_output_dir(case_dir, "(2024)案号001")
    assert d2.exists()
    assert d1 != d2


def test_make_output_dir_strips_unsafe_chars(tmp_path):
    case_dir = tmp_path / "案件"
    case_dir.mkdir()
    d = make_output_dir(case_dir, '(2024)民初/001:号*?')
    # 非法字符应被剔除
    assert "/" not in d.name
    assert ":" not in d.name
    assert "*" not in d.name


def test_copy_files_renames_with_category_prefix(tmp_path):
    case_dir = tmp_path / "案件"
    case_dir.mkdir()
    src = case_dir / "起诉状.pdf"
    src.write_text("content", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()

    c = _mk(str(src), 4, side="我方", weight=1)
    classified = copy_files([c], out)
    assert len(classified) == 1
    copied = list(out.iterdir())
    assert len(copied) == 1
    assert copied[0].name.startswith("04-1_我方-")


def test_copy_files_no_silent_overwrite(tmp_path):
    """两份同类同名文件不应互相覆盖（来自不同子目录）。"""
    case_dir = tmp_path / "案件"
    (case_dir / "证据").mkdir(parents=True)
    (case_dir / "附件").mkdir(parents=True)
    f1 = case_dir / "证据" / "照片.jpg"
    f2 = case_dir / "附件" / "照片.jpg"
    f1.write_text("AAA", encoding="utf-8")
    f2.write_text("BBB", encoding="utf-8")
    out = tmp_path / "out"
    out.mkdir()

    c1 = _mk(str(f1), 6)
    c2 = _mk(str(f2), 6)
    classified = copy_files([c1, c2], out)
    # 两份都应保留，不能丢
    copied = list(out.iterdir())
    assert len(copied) == 2, f"期望 2 份，实际 {len(copied)}：同名文件被覆盖"
    assert len(classified) == 2
