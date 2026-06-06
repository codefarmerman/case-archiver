"""端到端集成测试：扫描 → 分类 → 排序 → 复制 → 卷内目录 → 归档清单。
全程 llm=None（纯本地、不触网），验证真实产物结构与内容正确性。"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from archive_engine import (
    copy_files,
    generate_cover,
    make_output_dir,
    scan_files,
    sort_all_results,
    write_manifest,
)
from classify import Classifier

ROOT = Path(__file__).resolve().parent.parent

# 代表性案件材料（文件名即可命中规则）
CASE_FILES = {
    "收案审查表.pdf": 1,
    "律师费发票.pdf": 2,
    "法律服务合同.docx": 3,
    "民事起诉状.pdf": 4,
    "证据目录.pdf": 6,
    "开庭传票.pdf": 7,
    "代理词.docx": 8,
    "民事判决书.pdf": 10,
    "完全无关的材料abc.pdf": 13,
}


@pytest.fixture
def populated_case(tmp_case_dir):
    for nm in CASE_FILES:
        (tmp_case_dir / nm).write_text(f"内容-{nm}", encoding="utf-8")
    return tmp_case_dir


def _run_full_flow(case_dir: Path, categories_path: Path, case_no: str, case_name: str, role: str):
    files = scan_files(case_dir)
    clf = Classifier(categories_path, llm=None)
    results = [clf.classify(f, role=role) for f in files]
    output_root = make_output_dir(case_dir, case_no)
    sorted_results = sort_all_results(results)
    classified = copy_files(sorted_results, output_root)
    generate_cover(output_root, case_no, case_name, classified)
    write_manifest(
        output_root, case_no, case_name, role, classified, "2025-01-01 00:00:00"
    )
    return output_root, results, classified


def test_e2e_full_archive(populated_case, categories_path):
    out, results, classified = _run_full_flow(
        populated_case, categories_path,
        "(2024)琼0106民初888号", "张三诉李四合同纠纷", "原告",
    )

    # 1) 输出目录存在
    assert out.exists() and out.is_dir()

    # 2) 每份原始材料都被分类
    assert len(results) == len(CASE_FILES)

    # 3) 分类结果与预期一致
    by_name = {c.file_path.name: c.category_id for c in results}
    for nm, expected_cat in CASE_FILES.items():
        assert by_name[nm] == expected_cat, f"{nm} 应归第 {expected_cat} 项，实际第 {by_name[nm]} 项"

    # 4) 复制零丢失
    assert len(classified) == len(CASE_FILES)

    # 5) 卷内目录与清单都生成
    assert (out / "00_卷内目录.docx").exists()
    assert (out / "归档清单.json").exists()
    assert (out / "归档清单.txt").exists()

    # 6) 重命名规则：NN- 前缀
    copied_names = [f["new_name"] for f in classified]
    assert any(n.startswith("04-") for n in copied_names)  # 起诉状第4项
    # 起诉状（原告=我方）应带“我方-”标注
    assert any(n.startswith("04-") and "我方-" in n for n in copied_names)


def test_e2e_manifest_content(populated_case, categories_path):
    out, results, classified = _run_full_flow(
        populated_case, categories_path,
        "(2024)测001号", "测试案件", "原告",
    )
    data = json.loads((out / "归档清单.json").read_text(encoding="utf-8"))
    assert data["total"] == len(CASE_FILES)
    assert data["case_no"] == "(2024)测001号"
    assert len(data["files"]) == len(CASE_FILES)
    # JSON 保留完整原始路径供审计
    assert all("original_path" in f for f in data["files"])
    assert any(str(populated_case) in f["original_path"] for f in data["files"])

    # M2：可读 txt 不暴露完整绝对路径
    txt = (out / "归档清单.txt").read_text(encoding="utf-8")
    assert str(populated_case) not in txt


def test_e2e_no_file_loss_on_duplicate_names(tmp_case_dir, categories_path):
    """同名但不同子目录的多份起诉状不得互相覆盖。"""
    sub1 = tmp_case_dir / "a"
    sub2 = tmp_case_dir / "b"
    sub1.mkdir()
    sub2.mkdir()
    (sub1 / "民事起诉状.pdf").write_text("v1", encoding="utf-8")
    (sub2 / "民事起诉状.pdf").write_text("v2", encoding="utf-8")

    out, results, classified = _run_full_flow(
        tmp_case_dir, categories_path, "(2024)测002号", "重名测试", "原告"
    )
    # 两份都应被复制，文件名唯一
    cat4 = [f for f in classified if f["category_id"] == 4]
    assert len(cat4) == 2
    names = {f["new_name"] for f in cat4}
    assert len(names) == 2, "同类重名文件未被唯一化，存在覆盖风险"


def test_e2e_cli_dry_run(populated_case):
    """通过子进程运行 archive.py --dry-run，覆盖 CLI 入口。"""
    proc = subprocess.run(
        [
            sys.executable, "archive.py", str(populated_case),
            "--case-no", "(2024)CLI测试001号",
            "--case-name", "命令行测试",
            "--role", "原告",
            "--dry-run",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert proc.returncode == 0, f"CLI 退出码非 0：{proc.stderr}"
    out = proc.stdout
    assert "分类结果汇总" in out
    assert "dry-run" in out
    # dry-run 不应产生归档目录
    archives = list(populated_case.parent.glob("归档_*"))
    assert not archives, "dry-run 不应实际归档"
