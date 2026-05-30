"""
workers.py — 后台 QThread 工作线程
ClassifyWorker：并发扫描 + 分类（线程池）
ArchiveWorker：复制 + 补写 + 生成卷内目录
从 gui.py 抽出，UI 无关，仅通过 pyqtSignal 与界面通信。
"""
from __future__ import annotations

import traceback
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from PyQt5 import QtCore

from archive_engine import (
    auto_write_missing,
    copy_files,
    generate_cover,
    make_output_dir,
    sort_all_results,
    write_manifest,
)
from classify import Classification, Classifier
from llm_client import LLMClient
from logger import get_logger
from paths import config_path, scan_files


class ClassifyWorker(QtCore.QThread):
    """扫描 + 分类（可能调用 LLM，避免阻塞 UI）。"""

    progress = QtCore.pyqtSignal(int, int, str)           # cur, total, filename
    finished_ok = QtCore.pyqtSignal(list)                 # list[Classification]
    failed = QtCore.pyqtSignal(str)

    # 并发线程数：LLM 调用是 IO 密集，4-5 路并发可显著提速
    MAX_WORKERS = 5

    def __init__(self, case_dir: Path, role: str, llm: Optional[LLMClient]):
        super().__init__()
        self.case_dir = case_dir
        self.role = role
        self.llm = llm

    def run(self):
        log = get_logger()
        try:
            files = scan_files(self.case_dir)
            if not files:
                self.failed.emit("未发现任何支持格式的文件")
                return
            clf = Classifier(config_path(), llm=self.llm)
            total = len(files)

            # Classifier.classify 仅读共享状态、返回新对象，线程安全；
            # 用线程池并发（每文件可能 LLM 往返 5-8 秒，并发提速 4-5 倍）。
            import threading
            from concurrent.futures import ThreadPoolExecutor, as_completed

            results: List[Optional[Classification]] = [None] * total
            done = 0
            lock = threading.Lock()

            def work(index: int, fp: Path):
                return index, clf.classify(fp, role=self.role)

            workers = min(self.MAX_WORKERS, total)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(work, i, f) for i, f in enumerate(files)]
                for fut in as_completed(futures):
                    name = ""
                    try:
                        idx, c = fut.result()
                        results[idx] = c
                        name = c.file_path.name
                        log.info("%s → 第%d项 %s conf=%.2f",
                                 c.file_path.name, c.category_id, c.short_name, c.confidence)
                    except Exception as e:
                        log.exception("分类失败: %s", e)
                    with lock:
                        done += 1
                        cur = done
                    self.progress.emit(cur, total, name)

            # 过滤掉失败的 None，保持原始顺序
            final = [c for c in results if c is not None]
            self.finished_ok.emit(final)
        except Exception as e:
            log.exception("扫描分类线程异常")
            self.failed.emit(f"{e}\n{traceback.format_exc()}")


class ArchiveWorker(QtCore.QThread):
    """归档执行：复制 + 补写 + 生成卷内目录。"""

    progress = QtCore.pyqtSignal(str)
    finished_ok = QtCore.pyqtSignal(Path, int)            # output_dir, file_count
    failed = QtCore.pyqtSignal(str)

    def __init__(
        self,
        results: List[Classification],
        case_dir: Path,
        case_no: str,
        case_name: str,
        role: str,
        auto_write: bool,
        llm: Optional[LLMClient],
    ):
        super().__init__()
        self.results = results
        self.case_dir = case_dir
        self.case_no = case_no
        self.case_name = case_name
        self.role = role
        self.auto_write = auto_write
        self.llm = llm

    def run(self):
        log = get_logger()
        try:
            output_root = make_output_dir(self.case_dir, self.case_no)
            self.progress.emit(f"输出目录：{output_root}")

            sorted_results = sort_all_results(self.results)
            classified_files = copy_files(sorted_results, output_root, self.progress.emit)

            if self.auto_write:
                by_cat = defaultdict(list)
                for c in self.results:
                    by_cat[c.category_id].append(c)

                new_files = auto_write_missing(
                    config_path=config_path(),
                    by_cat=by_cat,
                    sorted_results=sorted_results,
                    output_root=output_root,
                    role=self.role,
                    case_no=self.case_no,
                    case_name=self.case_name,
                    llm=self.llm,
                    on_progress=self.progress.emit,
                )
                classified_files.extend(new_files)

            self.progress.emit("生成卷内目录 …")
            generate_cover(output_root, self.case_no, self.case_name, classified_files)

            from datetime import datetime
            write_manifest(
                output_root, self.case_no, self.case_name, self.role,
                classified_files, f"{datetime.now():%Y-%m-%d %H:%M:%S}",
            )
            self.progress.emit("已生成归档清单（归档清单.json / .txt）")

            total = len([f for f in output_root.iterdir() if f.is_file()])
            self.finished_ok.emit(output_root, total)
        except Exception as e:
            log.exception("归档线程异常")
            self.failed.emit(f"{e}\n{traceback.format_exc()}")
