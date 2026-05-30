"""分类核心逻辑测试（不依赖 LLM）。"""

import pytest

from classify import Classifier


@pytest.fixture
def clf(categories_path):
    return Classifier(categories_path, llm=None)


def test_filename_hit_qisushu(clf, tmp_case_dir):
    p = tmp_case_dir / "民事起诉状.pdf"
    p.write_text("x", encoding="utf-8")
    c = clf.classify(p, role="原告")
    assert c.category_id == 4
    assert c.method == "filename"
    assert c.confidence >= 0.9


def test_filename_hit_weituo_hetong(clf, tmp_case_dir):
    p = tmp_case_dir / "委托合同.pdf"
    p.write_text("x", encoding="utf-8")
    c = clf.classify(p)
    assert c.category_id == 3


def test_exclude_keyword(clf, tmp_case_dir):
    # 第2项收费凭证 exclude 含"合同"，"收费合同.pdf" 不应命中第2项
    p = tmp_case_dir / "收费合同.pdf"
    p.write_text("x", encoding="utf-8")
    c = clf.classify(p)
    assert c.category_id != 2


def test_fallback_to_13_without_llm(clf, tmp_case_dir):
    p = tmp_case_dir / "完全无关的随机名字xyz.pdf"
    p.write_text("x", encoding="utf-8")
    c = clf.classify(p)
    assert c.category_id == 13
    assert c.method == "fallback"
    assert c.confidence == 0.3


def test_side_detection_plaintiff_qisu(clf, tmp_case_dir):
    # 原告方的起诉状 → 我方
    p = tmp_case_dir / "起诉状.pdf"
    p.write_text("x", encoding="utf-8")
    c = clf.classify(p, role="原告")
    assert c.category_id == 4
    assert c.side == "我方"


def test_side_detection_plaintiff_dabian(clf, tmp_case_dir):
    # 原告视角，答辩状是对方提交 → 对方
    p = tmp_case_dir / "答辩状.pdf"
    p.write_text("x", encoding="utf-8")
    c = clf.classify(p, role="原告")
    assert c.category_id == 4
    assert c.side == "对方"


def test_side_by_role_in_filename(clf, tmp_case_dir):
    # 文件名直接含"被告"，原告视角 → 对方
    p = tmp_case_dir / "被告答辩状.pdf"
    p.write_text("x", encoding="utf-8")
    c = clf.classify(p, role="原告")
    assert c.side == "对方"


def test_sort_weight_assigned(clf, tmp_case_dir):
    p = tmp_case_dir / "上诉状.pdf"
    p.write_text("x", encoding="utf-8")
    c = clf.classify(p, role="原告")
    # 上诉 sort_weight 应为 4（见 categories.yaml）
    assert c.sort_weight == 4


def test_get_category_public_api(clf):
    # 验证公开 API（替代私有 _get_cat）
    cat = clf.get_category(4)
    assert cat["id"] == 4
    cat_unknown = clf.get_category(999)
    assert cat_unknown["name"] == "未知"


def test_category_choices(clf):
    choices = clf.category_choices()
    assert len(choices) == 13
    assert choices[0][0] == 1
