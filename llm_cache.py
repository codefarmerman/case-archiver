"""
llm_cache.py — LLM 分类结果本地缓存
按输入哈希缓存 classify_content / detect_side 的结果，避免对同一文件重复付费调用。
线程安全（并发分类会从多线程访问）。仅缓存确定性的分类/角色判断，不缓存文书生成。
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Optional

from logger import get_logger

log = get_logger()

CACHE_VERSION = 1
CACHE_DIR = Path.home() / ".case-archiver"
CACHE_FILE = CACHE_DIR / "llm_cache.json"
MAX_ENTRIES = 5000          # 超出后按插入顺序淘汰最旧的

_lock = threading.Lock()
_cache: Optional[dict] = None   # 惰性加载


def make_key(*parts: object) -> str:
    """由任意输入片段生成稳定的缓存键（含版本号，便于整体失效）。"""
    h = hashlib.sha256()
    h.update(str(CACHE_VERSION).encode("utf-8"))
    for p in parts:
        h.update(b"\x1f")  # 分隔符，避免拼接歧义
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            _cache = data if isinstance(data, dict) else {}
        except Exception as e:
            log.warning("LLM 缓存损坏，已重置：%s", e)
            _cache = {}
    else:
        _cache = {}
    return _cache


def get(key: str):
    """命中返回缓存值（已反序列化），未命中返回 None。"""
    with _lock:
        return _load().get(key)


def set(key: str, value) -> None:
    """写入缓存并持久化。超出容量时淘汰最旧条目。"""
    with _lock:
        cache = _load()
        cache[key] = value
        if len(cache) > MAX_ENTRIES:
            # dict 保持插入顺序，删最早的一批
            for old_key in list(cache.keys())[: len(cache) - MAX_ENTRIES]:
                cache.pop(old_key, None)
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            # 原子写入：临时文件 + rename，避免中途崩溃损坏缓存
            tmp = CACHE_FILE.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, CACHE_FILE)
            # 缓存含案件文档分类元数据，限制为仅属主可读写
            try:
                os.chmod(CACHE_FILE, 0o600)
            except Exception:
                pass
        except Exception as e:
            log.warning("LLM 缓存写入失败：%s", e)


def clear() -> None:
    """清空缓存（供测试或用户手动清理）。"""
    global _cache
    with _lock:
        _cache = {}
        try:
            if CACHE_FILE.exists():
                CACHE_FILE.unlink()
        except Exception as e:
            log.warning("清空 LLM 缓存失败：%s", e)


def stats() -> dict:
    with _lock:
        return {"entries": len(_load()), "file": str(CACHE_FILE)}
