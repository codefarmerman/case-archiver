"""
archive.py — 案件自动归档主入口 v2.0
用法:
  python archive.py <案件文件夹> --case-no XX --case-name XX --role 原告 [--dry-run] [--auto-write]
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from archive_engine import (
    auto_write_missing,
    copy_files,
    generate_cover,
    make_output_dir,
    scan_files,
    sort_all_results,
    write_manifest,
)
from auto_write import check_api_key
from classify import Classification, Classifier
from config_store import apply_api_key_to_env
from llm_client import LLMClient
from logger import get_logger

log = get_logger()

CONFIG_PATH = Path(__file__).parent / "categories.yaml"


def main():
    apply_api_key_to_env()
    ap = argparse.ArgumentParser(description="律师案件自动归档程序 v2.0")
    ap.add_argument("case_dir", type=Path, help="案件原始材料文件夹路径")
    ap.add_argument("--case-no", required=True, help="案号")
    ap.add_argument("--case-name", required=True, help="案由/当事人")
    ap.add_argument("--role", required=True, help="我方诉讼地位: 原告/被告/第三人/申请人/被申请人")
    ap.add_argument("--dry-run", action="store_true", help="仅输出分类报告，不实际操作")
    ap.add_argument("--auto-write", action="store_true", help="缺件时自动补写代理词和办案小结")
    args = ap.parse_args()

    if not args.case_dir.exists():
        print(f"[错误] 路径不存在: {args.case_dir}")
        sys.exit(1)

    # ===== 第1步：扫描 =====
    print(f"\n{'='*60}")
    print("  案件归档程序 v2.0")
    print(f"  案号: {args.case_no}")
    print(f"  案由: {args.case_name}")
    print(f"  我方: {args.role}")
    print(f"{'='*60}\n")

    print(f"[1/5] 扫描 {args.case_dir} ...")
    files = scan_files(args.case_dir)
    if not files:
        print("  未发现任何支持格式的文件，请检查路径。")
        sys.exit(1)
    print(f"  共发现 {len(files)} 份材料\n")

    # ===== 第2步：分类 =====
    print("[2/5] 分类中 ...")
    llm = LLMClient() if (args.auto_write or check_api_key()) else None
    clf = Classifier(CONFIG_PATH, llm=llm)
    results: list[Classification] = []
    needs_review: list[Classification] = []

    for f in files:
        c = clf.classify(f, role=args.role)
        results.append(c)
        if c.confidence < 0.7:
            needs_review.append(c)
        side_tag = f"[{c.side}]" if c.side else ""
        print(f"  [{c.category_id:>2}] {c.short_name:<12} {side_tag:<6} ← {f.name}  ({c.method}, conf={c.confidence})")

    # 统计各项命中情况
    by_cat = defaultdict(list)
    for c in results:
        by_cat[c.category_id].append(c)

    print("\n  分类结果汇总:")
    for cat_id in range(1, 14):
        items = by_cat.get(cat_id, [])
        cat_name = clf._get_cat(cat_id).get("short_name", "")
        if items:
            print(f"    第{cat_id:>2}项 {cat_name:<10} : {len(items)} 份")
        else:
            print(f"    第{cat_id:>2}项 {cat_name:<10} : （空）")

    if needs_review:
        print(f"\n  ⚠ {len(needs_review)} 份材料置信度偏低，请人工确认：")
        for c in needs_review:
            print(f"    - {c.file_path.name} → 暂归第{c.category_id}项({c.short_name})")

    # ===== 第3步：检查缺件 =====
    print("\n[3/5] 检查缺件 ...")
    auto_write_cats = clf.get_auto_write_categories()
    missing_items = []
    for cat in auto_write_cats:
        if cat["id"] not in by_cat:
            missing_items.append(cat)
            print(f"  ⚠ 第{cat['id']}项 {cat.get('short_name', '')} 缺失")

    if not missing_items:
        print("  所有可补写项均已存在")

    if args.dry_run:
        print(f"\n{'='*60}")
        print("  [dry-run] 不执行实际归档。")
        print("  确认分类无误后，去掉 --dry-run 重新运行。")
        if missing_items and not args.auto_write:
            print("  如需自动补写缺件，加 --auto-write 参数。")
        print(f"{'='*60}")
        return

    # ===== 第4步：归档 =====
    output_root = make_output_dir(args.case_dir, args.case_no)
    print(f"\n[4/5] 复制文件到 {output_root} ...")

    sorted_results = sort_all_results(results)
    classified_files = copy_files(sorted_results, output_root, lambda msg: print(f"  {msg}"))

    # 自动补写缺件
    if args.auto_write and missing_items:
        print("\n  正在补写缺失文书 ...")
        new_files = auto_write_missing(
            config_path=CONFIG_PATH,
            by_cat=by_cat,
            sorted_results=sorted_results,
            output_root=output_root,
            role=args.role,
            case_no=args.case_no,
            case_name=args.case_name,
            llm=llm,
            on_progress=lambda msg: print(f"  {msg}"),
        )
        classified_files.extend(new_files)

    # ===== 第5步：生成卷内目录 =====
    print("\n[5/5] 生成卷内目录 ...")
    cover_path = generate_cover(output_root, args.case_no, args.case_name, classified_files)

    write_manifest(
        output_root, args.case_no, args.case_name, args.role,
        classified_files, f"{datetime.now():%Y-%m-%d %H:%M:%S}",
    )

    # 最终报告
    print(f"\n{'='*60}")
    print("  ✓ 归档完成!")
    print(f"  输出目录: {output_root}")
    print(f"  卷内目录: {cover_path}")
    print("  归档清单: 归档清单.json / 归档清单.txt")
    total = len([f for f in output_root.iterdir() if f.is_file()])
    print(f"  文件总数: {total} 份")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
