"""归档清单审计文件测试。"""
import json

from archive_engine import write_manifest


def _files():
    return [
        {
            "category_id": 4, "category_name": "诉讼文书",
            "filename": "起诉状.pdf", "new_name": "04-1_我方-起诉状.pdf",
            "original_path": "/case/起诉状.pdf", "side": "我方",
            "confidence": 0.95, "method": "filename", "note": "命中关键词: 起诉状",
            "page_start": "",
        },
        {
            "category_id": 2, "category_name": "收费凭证",
            "filename": "发票.pdf", "new_name": "02-1_发票.pdf",
            "original_path": "/case/发票.pdf", "side": "",
            "confidence": 0.95, "method": "filename", "note": "",
            "page_start": "",
        },
    ]


def test_writes_json_and_txt(tmp_path):
    write_manifest(tmp_path, "(2026)001", "张三诉李四", "原告", _files(), "2026-05-30 12:00:00")
    assert (tmp_path / "归档清单.json").exists()
    assert (tmp_path / "归档清单.txt").exists()


def test_json_content(tmp_path):
    write_manifest(tmp_path, "(2026)001", "张三诉李四", "原告", _files(), "2026-05-30 12:00:00")
    data = json.loads((tmp_path / "归档清单.json").read_text(encoding="utf-8"))
    assert data["case_no"] == "(2026)001"
    assert data["role"] == "原告"
    assert data["total"] == 2
    assert data["files"][0]["method"] == "filename"
    assert data["files"][0]["confidence"] == 0.95


def test_txt_traceability(tmp_path):
    write_manifest(tmp_path, "(2026)001", "张三诉李四", "原告", _files(), "2026-05-30 12:00:00")
    txt = (tmp_path / "归档清单.txt").read_text(encoding="utf-8")
    # 应能追溯：原始路径、依据、置信度
    assert "起诉状.pdf" in txt
    assert "原始=" in txt
    assert "命中关键词" in txt
    assert "[我方]" in txt
