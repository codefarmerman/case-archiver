"""LLMClient 用量/成本统计测试（不调真实 API）。"""
from llm_client import PRICE_INPUT_PER_M, PRICE_OUTPUT_PER_M, LLMClient


class _Usage:
    def __init__(self, p, c):
        self.prompt_tokens = p
        self.completion_tokens = c


def _client_without_api():
    # 不触发真实 _init（无 key 时 ready=False，但用量字段仍可累计）
    c = LLMClient.__new__(LLMClient)
    import threading
    c._usage_lock = threading.Lock()
    c.prompt_tokens = 0
    c.completion_tokens = 0
    c.api_calls = 0
    return c


def test_accumulates_usage():
    c = _client_without_api()
    c._add_usage(_Usage(100, 50))
    c._add_usage(_Usage(200, 80))
    assert c.prompt_tokens == 300
    assert c.completion_tokens == 130
    assert c.total_tokens == 430
    assert c.api_calls == 2


def test_cost_estimate():
    c = _client_without_api()
    c._add_usage(_Usage(1_000_000, 1_000_000))
    expected = PRICE_INPUT_PER_M + PRICE_OUTPUT_PER_M
    assert abs(c.estimated_cost_cny() - expected) < 1e-6


def test_usage_summary_no_calls():
    c = _client_without_api()
    assert "未发生 API 调用" in c.usage_summary()


def test_usage_summary_with_calls():
    c = _client_without_api()
    c._add_usage(_Usage(100, 50))
    s = c.usage_summary()
    assert "1 次" in s
    assert "¥" in s


def test_none_usage_ignored():
    c = _client_without_api()
    c._add_usage(None)
    assert c.api_calls == 0
