"""LLM 辅助函数测试（纯函数，不调 API）。"""
from llm_client import _safe_json, categories_brief_text


def test_safe_json_plain():
    assert _safe_json('{"a": 1}') == {"a": 1}


def test_safe_json_with_preamble():
    # LLM 常在 JSON 前后加解释文字
    text = '好的，结果如下：\n{"category_id": 4, "confidence": 0.9}\n希望有帮助'
    out = _safe_json(text)
    assert out["category_id"] == 4


def test_safe_json_non_greedy():
    # 多个 JSON 对象时，应抓第一个完整的（非贪婪）
    text = '{"a": 1} 还有 {"b": 2}'
    out = _safe_json(text)
    assert out == {"a": 1}


def test_safe_json_code_fence():
    text = '```json\n{"side": "我方"}\n```'
    out = _safe_json(text)
    assert out["side"] == "我方"


def test_safe_json_invalid():
    assert _safe_json("这不是 JSON") is None
    assert _safe_json("") is None


def test_categories_brief_text(categories_path):
    import yaml
    cfg = yaml.safe_load(categories_path.read_text(encoding="utf-8"))
    brief = categories_brief_text(cfg["categories"])
    assert "1." in brief
    assert "起诉" in brief  # 第4项关键词应出现
