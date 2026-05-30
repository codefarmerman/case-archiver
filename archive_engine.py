"""
archive_engine.py — 归档核心引擎
供 gui.py 和 archive.py 共用的扫描、排序、复制、补写逻辑。
"""
from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from auto_write import auto_write_document
from build_cover import build_cover
from classify import Classification
from llm_client import LLMClient
from logger import get_logger

log = get_logger()

SUPPORTED_EXT = {".pdf", ".docx", ".doc", ".txt", ".jpg", ".jpeg", ".png", ".xlsx", ".ofd"}
SIDE_ORDER = {"我方": 0, "对方": 1, "待确认": 2, "": 3}
_UNSAFE_CHARS = set('\\/:*?"<>|')


def scan_files(case_dir: Path) -> List[Path]:
    return [
        p for p in sorted(case_dir.rglob("*"))
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXT
    ]


def sort_category4(results: List[Classification]) -> List[Classification]:
    return sorted(
        results,
        key=lambda c: (c.sort_weight, SIDE_ORDER.get(c.side, 3), c.file_path.name),
    )


def sort_all_results(results: List[Classification]) -> List[Classification]:
    by_cat: dict[int, list[Classification]] = defaultdict(list)
    for c in results:
        by_cat[c.category_id].append(c)

    sorted_results: List[Classification] = []
    for cat_id in range(1, 14):
        items = by_cat.get(cat_id, [])
        if cat_id == 4:
            items = sort_category4(items)
        sorted_results.extend(items)
    return sorted_results


def make_output_dir(case_dir: Path, case_no: str) -> Path:
    safe_no = "".join(ch for ch in case_no if ch not in _UNSAFE_CHARS)
    output_root = case_dir.parent / f"归档_{safe_no}_{datetime.now():%Y%m%d}"
    if output_root.exists():
        output_root = case_dir.parent / f"归档_{safe_no}_{datetime.now():%Y%m%d_%H%M%S}"
    output_root.mkdir(parents=True, exist_ok=True)
    return output_root


def copy_files(
    sorted_results: List[Classification],
    output_root: Path,
    on_progress: Optional[Callable[[str], None]] = None,
) -> List[dict]:
    """复制并重命名。idx 按类别单调递增，保证同类文件名唯一、永不互相覆盖。
    复制结束后校验"成功数 == 预期数"，有丢失则醒目告警（律师文件不容丢失）。
    """
    classified_files: List[dict] = []
    counters: dict[int, int] = {}
    failed = 0

    for c in sorted_results:
        counters[c.category_id] = counters.get(c.category_id, 0) + 1
        idx = counters[c.category_id]
        side_prefix = f"{c.side}-" if c.side and c.side != "待确认" else ""
        new_name = f"{c.category_id:02d}-{idx}_{side_prefix}{c.file_path.name}"
        target = output_root / new_name
        # 防御：理论上 idx 递增保证唯一，仍做一次存在性兜底
        if target.exists():
            stem, suffix = target.stem, target.suffix
            n = 1
            while target.exists():
                target = output_root / f"{stem}_dup{n}{suffix}"
                n += 1
            log.warning("目标已存在，改名避免覆盖：%s", target.name)
        try:
            shutil.copy2(c.file_path, target)
            classified_files.append({
                "category_id": c.category_id,
                "category_name": c.category_name,
                "filename": c.file_path.name,
                "new_name": target.name,
                "original_path": str(c.file_path),
                "side": c.side,
                "confidence": round(c.confidence, 2),
                "method": c.method,
                "note": c.note,
                "page_start": "",
            })
            if on_progress:
                on_progress(f"已复制：{target.name}")
        except Exception as e:
            failed += 1
            log.exception("复制失败 %s", c.file_path)
            if on_progress:
                on_progress(f"⚠ 复制失败 {c.file_path.name}: {e}")

    # 数量校验：成功数应等于输入数
    expected = len(sorted_results)
    succeeded = len(classified_files)
    if succeeded != expected:
        msg = f"⚠ 复制数量不符：预期 {expected} 份，成功 {succeeded} 份，失败 {failed} 份，请检查日志！"
        log.error(msg)
        if on_progress:
            on_progress(msg)

    return classified_files


def auto_write_missing(
    config_path: Path,
    by_cat: dict,
    sorted_results: List[Classification],
    output_root: Path,
    role: str,
    case_no: str,
    case_name: str,
    llm: Optional[LLMClient],
    on_progress: Optional[Callable[[str], None]] = None,
) -> List[dict]:
    import yaml

    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    auto_cats = [c for c in cfg["categories"] if c.get("auto_write_if_missing", False)]
    missing = [c for c in auto_cats if c["id"] not in by_cat]
    new_files: List[dict] = []

    for cat in missing:
        cat_id = cat["id"]
        prompt = cat.get("auto_write_prompt", "")
        if not prompt:
            continue

        if cat_id == 8:
            ref_files = [c.file_path for c in by_cat.get(4, [])]
        elif cat_id == 11:
            ref_files = [c.file_path for c in sorted_results]
        else:
            ref_files = []

        output_name = {8: "代理词.docx", 11: "办案小结.docx"}.get(cat_id, f"第{cat_id}项.docx")
        output_file = output_root / f"{cat_id:02d}-1_{output_name}"

        if on_progress:
            on_progress(f"正在自动补写第 {cat_id} 项 ...")

        result_path = auto_write_document(
            category_id=cat_id,
            prompt_template=prompt,
            role=role,
            case_no=case_no,
            case_name=case_name,
            reference_files=ref_files,
            output_path=output_file,
            llm=llm,
        )
        if result_path:
            new_files.append({
                "category_id": cat_id,
                "filename": output_name,
                "side": "",
                "page_start": "",
            })
            if on_progress:
                on_progress(f"已生成 {output_name}")
        else:
            if on_progress:
                on_progress(f"第 {cat_id} 项补写未生成（详见日志）")

    return new_files


def generate_cover(
    output_root: Path,
    case_no: str,
    case_name: str,
    classified_files: List[dict],
) -> Path:
    cover_path = output_root / "00_卷内目录.docx"
    build_cover(cover_path, case_no, case_name, classified_files)
    return cover_path


def write_manifest(
    output_root: Path,
    case_no: str,
    case_name: str,
    role: str,
    classified_files: List[dict],
    archived_at: str,
) -> Path:
    """写归档审计清单（JSON + 可读 TXT）：记录每份文件的归类依据，供事后追溯。
    archived_at 由调用方传入（避免在引擎内取系统时间，便于测试与确定性）。"""
    import json

    manifest = {
        "case_no": case_no,
        "case_name": case_name,
        "role": role,
        "archived_at": archived_at,
        "total": len(classified_files),
        "files": classified_files,
    }
    json_path = output_root / "归档清单.json"
    json_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 人类可读版
    lines = [
        f"案号：{case_no}",
        f"案由/当事人：{case_name}",
        f"我方诉讼地位：{role}",
        f"归档时间：{archived_at}",
        f"文件总数：{len(classified_files)}",
        "=" * 60,
    ]
    for f in classified_files:
        side = f.get("side", "")
        side_tag = f"[{side}] " if side and side != "待确认" else ""
        lines.append(
            f"第{f.get('category_id'):>2}项 {f.get('category_name', '')}　"
            f"{side_tag}{f.get('new_name', f.get('filename', ''))}"
        )
        lines.append(
            f"    依据：{f.get('method', '')} "
            f"置信度={f.get('confidence', '')} "
            f"原始={f.get('original_path', '')}"
        )
        if f.get("note"):
            lines.append(f"    说明：{f.get('note')}")
    txt_path = output_root / "归档清单.txt"
    txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return json_path
