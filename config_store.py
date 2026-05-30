"""
config_store.py — 本地配置（API Key 等）持久化
存储位置：%USERPROFILE%\\.case-archiver\\config.json
注意：明文存储，仅适用于个人单机使用，不要把该文件上传或分享。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from logger import get_logger

log = get_logger()

CONFIG_DIR = Path.home() / ".case-archiver"
CONFIG_FILE = CONFIG_DIR / "config.json"
KEY_FIELD = "deepseek_api_key"


def _read() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        log.warning("配置文件损坏，已忽略：%s", e)
        return {}


def _write(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except Exception:
        pass


def load_api_key() -> Optional[str]:
    """优先读环境变量；否则读本地配置文件。"""
    env = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if env:
        return env
    data = _read()
    key = data.get(KEY_FIELD, "").strip()
    if not key:
        # Backward compat: read legacy anthropic_api_key if present
        key = data.get("anthropic_api_key", "").strip()
    return key or None


def apply_api_key_to_env() -> Optional[str]:
    """启动时调用：把本地配置里的 key 写到环境变量，供 SDK 自动读取。"""
    key = load_api_key()
    if key and not os.environ.get("DEEPSEEK_API_KEY"):
        os.environ["DEEPSEEK_API_KEY"] = key
        log.info("已从本地配置加载 API Key（来源：%s）", CONFIG_FILE)
    return key


def save_api_key(key: str) -> None:
    """保存 API Key 到本地配置；同步写到当前进程的环境变量。"""
    key = (key or "").strip()
    data = _read()
    if key:
        data[KEY_FIELD] = key
        os.environ["DEEPSEEK_API_KEY"] = key
        log.info("API Key 已保存到 %s", CONFIG_FILE)
    else:
        data.pop(KEY_FIELD, None)
        os.environ.pop("DEEPSEEK_API_KEY", None)
        log.info("API Key 已从本地配置移除")
    _write(data)


def config_file_path() -> Path:
    return CONFIG_FILE
