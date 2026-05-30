"""LLM 缓存测试。"""

import pytest


@pytest.fixture
def cache(tmp_path, monkeypatch):
    """每个测试用独立临时缓存文件，避免污染用户目录。"""
    import llm_cache
    monkeypatch.setattr(llm_cache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm_cache, "CACHE_FILE", tmp_path / "llm_cache.json")
    monkeypatch.setattr(llm_cache, "_cache", None)
    return llm_cache


def test_make_key_stable(cache):
    k1 = cache.make_key("classify", "model", "a.pdf", "内容", "目录")
    k2 = cache.make_key("classify", "model", "a.pdf", "内容", "目录")
    assert k1 == k2


def test_make_key_differs(cache):
    k1 = cache.make_key("classify", "model", "a.pdf", "内容A", "目录")
    k2 = cache.make_key("classify", "model", "a.pdf", "内容B", "目录")
    assert k1 != k2


def test_set_get_roundtrip(cache):
    cache.set("k1", [4, 0.9, "起诉状"])
    assert cache.get("k1") == [4, 0.9, "起诉状"]


def test_get_miss(cache):
    assert cache.get("nonexistent") is None


def test_persists_to_file(cache):
    cache.set("k1", [4, 0.9, "x"])
    assert cache.CACHE_FILE.exists()
    # 重新加载（模拟新进程）
    cache._cache = None
    assert cache.get("k1") == [4, 0.9, "x"]


def test_clear(cache):
    cache.set("k1", [1, 0.5, "x"])
    cache.clear()
    assert cache.get("k1") is None


def test_eviction_cap(cache, monkeypatch):
    monkeypatch.setattr(cache, "MAX_ENTRIES", 3)
    for i in range(5):
        cache.set(f"k{i}", i)
    st = cache.stats()
    assert st["entries"] <= 3
    # 最新的应保留
    assert cache.get("k4") == 4


def test_corrupt_cache_resets(cache):
    cache.CACHE_FILE.write_text("{ not valid json", encoding="utf-8")
    cache._cache = None
    # 不应抛异常，返回 None
    assert cache.get("anything") is None
