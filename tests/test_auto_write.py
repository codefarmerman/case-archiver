"""自动补写输出清洗测试。"""
from auto_write import MAX_WRITE_TOKENS, MIN_CONTENT_CHARS, _clean_llm_output


def test_strip_code_fence():
    assert "```" not in _clean_llm_output("```\n正文内容\n```")


def test_strip_markdown_headers():
    out = _clean_llm_output("# 代理词\n## 一、事实\n正文")
    assert "#" not in out
    assert "代理词" in out


def test_strip_bold():
    out = _clean_llm_output("**重点**内容")
    assert "*" not in out
    assert "重点内容" in out


def test_strip_list_markers():
    out = _clean_llm_output("- 第一点\n- 第二点")
    assert not out.startswith("-")
    assert "第一点" in out


def test_strip_ai_preamble():
    out = _clean_llm_output("好的，以下是代理词：\n尊敬的审判长")
    assert out.startswith("尊敬的审判长")
    assert "好的" not in out


def test_strip_trailing_pleasantry():
    out = _clean_llm_output("正文内容\n希望对您有帮助")
    assert "希望对您有帮助" not in out


def test_empty_input():
    assert _clean_llm_output("") == ""
    assert _clean_llm_output(None) == ""


def test_preserves_normal_text():
    text = "尊敬的审判长：\n本案中，原告主张..."
    out = _clean_llm_output(text)
    assert "尊敬的审判长" in out
    assert "原告主张" in out


def test_constants_sane():
    assert MIN_CONTENT_CHARS > 0
    assert MAX_WRITE_TOKENS >= 4000
