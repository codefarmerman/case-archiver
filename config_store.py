"""
config_store.py — 本地配置持久化
- API Key：优先存入系统凭据管理器（keyring / Windows Credential Manager）；
  keyring 不可用时回退到明文 config.json 并告警。
- 普通设置（如纯本地模式）：存 config.json（非敏感）。
- 启动时自动迁移历史明文 key 到 keyring 并从 config.json 抹除。
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

KEY_FIELD = "deepseek_api_key"          # config.json 中的历史明文字段（迁移用）
LEGACY_KEY_FIELD = "anthropic_api_key"  # 更早期的字段
ENV_VAR = "DEEPSEEK_API_KEY"

# keyring 服务/用户标识
KEYRING_SERVICE = "case-archiver"
KEYRING_USER = "deepseek_api_key"


# ---------------- keyring 后端（优雅降级） ----------------

def _keyring():
    """返回可用的 keyring 模块，不可用时返回 None。"""
    try:
        import keyring
        # 验证有真实后端（非 fail/null 后端）
        backend = keyring.get_keyring().__class__.__name__
        if "fail" in backend.lower() or "null" in backend.lower():
            return None
        return keyring
    except Exception:
        return None


def _keyring_get() -> Optional[str]:
    kr = _keyring()
    if not kr:
        return None
    try:
        return kr.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception as e:
        log.warning("读取 keyring 失败：%s", e)
        return None


def _keyring_set(key: str) -> bool:
    kr = _keyring()
    if not kr:
        return False
    try:
        kr.set_password(KEYRING_SERVICE, KEYRING_USER, key)
        return True
    except Exception as e:
        log.warning("写入 keyring 失败：%s", e)
        return False


def _keyring_delete() -> None:
    kr = _keyring()
    if not kr:
        return
    try:
        kr.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        pass  # 不存在时忽略


# ---------------- config.json 读写 ----------------

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


def _migrate_plaintext_key() -> None:
    """把 config.json 中的历史明文 key 迁移到 keyring，并从文件抹除。"""
    data = _read()
    plain = (data.get(KEY_FIELD) or data.get(LEGACY_KEY_FIELD) or "").strip()
    if not plain:
        return
    if _keyring_set(plain):
        data.pop(KEY_FIELD, None)
        data.pop(LEGACY_KEY_FIELD, None)
        _write(data)
        log.info("已将明文 API Key 迁移到系统凭据管理器，并从 config.json 抹除")


# ---------------- API Key 公开接口 ----------------

def load_api_key() -> Optional[str]:
    """优先级：环境变量 > keyring > config.json 明文（兼容旧版）。"""
    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return env

    _migrate_plaintext_key()

    from_keyring = _keyring_get()
    if from_keyring and from_keyring.strip():
        return from_keyring.strip()

    # 回退：keyring 不可用时读明文
    data = _read()
    key = (data.get(KEY_FIELD) or data.get(LEGACY_KEY_FIELD) or "").strip()
    return key or None


def apply_api_key_to_env() -> Optional[str]:
    """启动时调用：把存储的 key 写到环境变量，供 SDK 读取。"""
    key = load_api_key()
    if key and not os.environ.get(ENV_VAR):
        os.environ[ENV_VAR] = key
        log.info("已加载 API Key（来源：%s）", _key_source())
    return key


def _key_source() -> str:
    if _keyring_get():
        return "系统凭据管理器"
    return str(CONFIG_FILE)


def save_api_key(key: str) -> None:
    """保存 API Key；优先写 keyring，失败则回退明文 config.json。"""
    key = (key or "").strip()
    if key:
        if _keyring_set(key):
            # 确保 config.json 中没有残留明文
            data = _read()
            data.pop(KEY_FIELD, None)
            data.pop(LEGACY_KEY_FIELD, None)
            _write(data)
            log.info("API Key 已保存到系统凭据管理器")
        else:
            data = _read()
            data[KEY_FIELD] = key
            _write(data)
            log.warning("系统凭据管理器不可用，API Key 以明文保存到 %s", CONFIG_FILE)
        os.environ[ENV_VAR] = key
    else:
        _keyring_delete()
        data = _read()
        data.pop(KEY_FIELD, None)
        data.pop(LEGACY_KEY_FIELD, None)
        _write(data)
        os.environ.pop(ENV_VAR, None)
        log.info("API Key 已移除")


def key_storage_location() -> str:
    """供 UI 展示当前 key 的存储位置。"""
    if _keyring():
        return "系统凭据管理器（加密）"
    return f"{CONFIG_FILE}（明文，keyring 不可用）"


def config_file_path() -> Path:
    return CONFIG_FILE


# ---------------- 通用设置（非敏感） ----------------

def get_setting(name: str, default=None):
    return _read().get(name, default)


def set_setting(name: str, value) -> None:
    data = _read()
    data[name] = value
    _write(data)
