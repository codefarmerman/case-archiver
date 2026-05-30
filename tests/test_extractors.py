"""多格式提取器测试（xlsx/ofd 无需外部依赖；doc/图片 仅验证优雅降级）。"""
import zipfile

from extractors import extract_sample


def test_txt(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("起诉状内容", encoding="utf-8")
    assert "起诉状" in extract_sample(p)


def test_xlsx(tmp_path):
    import openpyxl
    p = tmp_path / "费用.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "明细"
    ws.append(["项目", "金额"])
    ws.append(["律师费", 5000])
    wb.save(str(p))
    out = extract_sample(p)
    assert "律师费" in out
    assert "明细" in out


def test_ofd(tmp_path):
    """构造一个最小 OFD（zip + Content.xml with TextCode）。"""
    p = tmp_path / "电子公文.ofd"
    content_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Page xmlns="http://www.ofdspec.org/2016">'
        '<Content><TextObject><TextCode>判决如下</TextCode></TextObject></Content>'
        '</Page>'
    )
    with zipfile.ZipFile(str(p), "w") as zf:
        zf.writestr("Doc_0/Pages/Page_0/Content.xml", content_xml)
    out = extract_sample(p)
    assert "判决如下" in out


def test_unsupported_returns_empty(tmp_path):
    p = tmp_path / "x.zip"
    p.write_bytes(b"PK\x03\x04nonsense")
    assert extract_sample(p) == ""


def test_doc_graceful_without_word(tmp_path):
    # 无 Word/pywin32 时不应抛异常，返回空串
    p = tmp_path / "old.doc"
    p.write_bytes(b"\xd0\xcf\x11\xe0fake-doc")
    assert extract_sample(p) == ""


def test_image_graceful_without_ocr(tmp_path):
    # 无 pytesseract 时不应抛异常
    p = tmp_path / "scan.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    result = extract_sample(p)
    assert isinstance(result, str)


def test_corrupt_file_no_crash(tmp_path):
    p = tmp_path / "bad.xlsx"
    p.write_bytes(b"not a real xlsx")
    assert extract_sample(p) == ""
