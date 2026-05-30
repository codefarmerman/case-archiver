"""路径解析测试：版本一致性 + PyInstaller 资源定位。"""
import sys
from pathlib import Path

import paths
from _version import __version__


def test_version_format():
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_pyproject_version_matches():
    root = Path(__file__).resolve().parent.parent
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in text


def test_resource_path_external_preferred(tmp_path, monkeypatch):
    # 外部副本存在时优先返回外部路径
    monkeypatch.setattr(paths, "app_root", lambda: tmp_path)
    (tmp_path / "style.qss").write_text("x", encoding="utf-8")
    assert paths.resource_path("style.qss") == tmp_path / "style.qss"


def test_resource_path_falls_back_to_meipass(tmp_path, monkeypatch):
    # 外部不存在但 _MEIPASS 有 → 返回 bundled
    app_dir = tmp_path / "app"
    mei_dir = tmp_path / "mei"
    app_dir.mkdir()
    mei_dir.mkdir()
    (mei_dir / "categories.yaml").write_text("x", encoding="utf-8")
    monkeypatch.setattr(paths, "app_root", lambda: app_dir)
    # monkeypatch 在测试结束自动还原 _MEIPASS（包括删除原本不存在的属性）
    monkeypatch.setattr(sys, "_MEIPASS", str(mei_dir), raising=False)
    assert paths.resource_path("categories.yaml") == mei_dir / "categories.yaml"


def test_real_categories_yaml_found():
    # 开发态下真实 categories.yaml 应能定位
    assert paths.config_path().exists()
