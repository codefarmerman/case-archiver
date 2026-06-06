"""config_store 测试：keyring 存储、明文迁移、通用设置。"""

import pytest


class FakeKeyring:
    """内存版 keyring，模拟 Windows 凭据管理器。"""

    def __init__(self):
        self._store = {}

    def get_keyring(self):
        class _B:
            __class__ = type("WinVaultKeyring", (), {})
        return _B()

    def get_password(self, service, user):
        return self._store.get((service, user))

    def set_password(self, service, user, pw):
        self._store[(service, user)] = pw

    def delete_password(self, service, user):
        self._store.pop((service, user), None)


@pytest.fixture
def cs(tmp_path, monkeypatch):
    import config_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    fake = FakeKeyring()
    # _keyring() 返回 fake；其类名含 WinVault 不会被判为 fail/null
    monkeypatch.setattr(config_store, "_keyring", lambda: fake)
    return config_store


def test_save_load_via_keyring(cs):
    cs.save_api_key("sk-test123")
    assert cs.load_api_key() == "sk-test123"
    # 不应落在 config.json 明文
    assert "sk-test123" not in (cs.CONFIG_FILE.read_text(encoding="utf-8") if cs.CONFIG_FILE.exists() else "")


def test_env_var_takes_priority(cs, monkeypatch):
    cs.save_api_key("sk-stored")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env")
    assert cs.load_api_key() == "sk-env"


def test_migration_plaintext_to_keyring(cs):
    # 模拟旧版：config.json 里有明文 key
    cs._write({"deepseek_api_key": "sk-legacy"})
    # 首次 load 应触发迁移
    assert cs.load_api_key() == "sk-legacy"
    # 迁移后 config.json 不再含明文
    data = cs._read()
    assert "deepseek_api_key" not in data
    # 且能从 keyring 再次读到
    assert cs.load_api_key() == "sk-legacy"


def test_clear_key(cs):
    cs.save_api_key("sk-x")
    cs.save_api_key("")
    assert cs.load_api_key() is None


def test_settings_roundtrip(cs):
    assert cs.get_setting("local_only", False) is False
    cs.set_setting("local_only", True)
    assert cs.get_setting("local_only") is True


def test_fallback_dpapi_when_no_keyring_on_windows(tmp_path, monkeypatch):
    """keyring 不可用且支持 DPAPI（Windows）时，落盘应为密文而非明文，但可正常读回。"""
    import secure_store
    if not secure_store.available():
        pytest.skip("非 Windows 平台无 DPAPI")
    import config_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(config_store, "_keyring", lambda: None)  # 无 keyring

    config_store.save_api_key("sk-plain")
    raw = config_store.CONFIG_FILE.read_text(encoding="utf-8")
    # 安全：明文不得落盘，应存为 DPAPI 密文字段
    assert "sk-plain" not in raw
    assert "deepseek_api_key_dpapi" in raw
    # 仍可正确读回
    assert config_store.load_api_key() == "sk-plain"


def test_fallback_plaintext_when_no_keyring_no_dpapi(tmp_path, monkeypatch):
    """keyring 与 DPAPI 均不可用（如非 Windows）时，才回退明文。"""
    import config_store
    import secure_store
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_store, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(config_store, "_keyring", lambda: None)  # 无 keyring
    monkeypatch.setattr(secure_store, "available", lambda: False)  # 无 DPAPI

    config_store.save_api_key("sk-plain")
    assert "sk-plain" in config_store.CONFIG_FILE.read_text(encoding="utf-8")
    assert config_store.load_api_key() == "sk-plain"


def test_key_storage_location(cs):
    loc = cs.key_storage_location()
    assert "凭据管理器" in loc
