"""
classify.py — 文件分类核心模块 v2.1
两层识别：文件名规则 → LLM 内容采样兜底
第 4 项额外支持我方/对方角色判断（文件名无线索时调用 LLM 读前两页）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

from llm_client import LLMClient, categories_brief_text, extract_sample
from logger import get_logger

log = get_logger()


@dataclass
class Classification:
    file_path: Path
    category_id: int
    category_name: str
    short_name: str
    confidence: float
    method: str        # filename / llm / fallback
    side: str = ""     # 我方 / 对方（仅第 4 项）
    sort_weight: int = 0
    note: str = ""


class Classifier:
    def __init__(self, config_path: Path, llm: Optional[LLMClient] = None):
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.categories = self.cfg["categories"]
        self.clf_cfg = self.cfg.get("classifier", {})
        self._categories_brief = categories_brief_text(self.categories)
        self._cat_map = {c["id"]: c for c in self.categories}
        self.llm = llm

    def classify(self, file_path: Path, role: str = "") -> Classification:
        # 第一层：文件名规则
        result = self._by_filename(file_path)
        if result:
            if result.category_id == 4 and role:
                result = self._detect_side(result, role)
                result = self._assign_sort_weight(result)
            return result

        # 第二层：LLM 内容采样
        result = self._by_content(file_path)
        if result:
            if result.category_id == 4 and role:
                result = self._detect_side(result, role)
                result = self._assign_sort_weight(result)
            return result

        # 兜底：其他
        cat13 = self._get_cat(13)
        return Classification(
            file_path=file_path,
            category_id=13,
            category_name=cat13["name"],
            short_name=cat13.get("short_name", "其他"),
            confidence=0.3,
            method="fallback",
            note="未命中规则，需人工确认",
        )

    def _by_filename(self, file_path: Path) -> Optional[Classification]:
        filename = file_path.name
        for cat in self.categories:
            if cat["id"] == 13:
                continue
            excludes = cat.get("exclude", []) or []
            if any(ex in filename for ex in excludes):
                continue
            for kw in cat.get("keywords", []) or []:
                if kw in filename:
                    return Classification(
                        file_path=file_path,
                        category_id=cat["id"],
                        category_name=cat["name"],
                        short_name=cat.get("short_name", cat["name"][:10]),
                        confidence=0.95,
                        method="filename",
                        note=f"命中关键词: {kw}",
                    )
        return None

    def _detect_side(self, c: Classification, role: str) -> Classification:
        filename = c.file_path.name
        role_map = {
            "原告": ("被告",),
            "被告": ("原告",),
            "申请人": ("被申请人",),
            "被申请人": ("申请人",),
            "第三人": ("原告", "被告"),
        }
        opponent_roles = role_map.get(role, ())

        if role in filename:
            c.side = "我方"
            c.note += f" | 角色: 我方({role}) [文件名]"
            return c
        for opp in opponent_roles:
            if opp in filename:
                c.side = "对方"
                c.note += f" | 角色: 对方({opp}) [文件名]"
                return c

        # 文件名无线索：按文书类型粗判（规则来自 yaml）
        side_guess = self._side_by_doc_type(filename, role)
        if side_guess:
            c.side = side_guess
            c.note += f" | 角色: {side_guess} [文书类型]"
            return c

        # 粗判不出，调用 LLM 读 PDF 前两页
        if self.llm and self.llm.ready:
            sample = extract_sample(c.file_path, n_chars=1500, max_pages=2)
            if sample.strip():
                log.info("第 4 项角色判断 LLM 采样：%s", c.file_path.name)
                detection = self.llm.detect_side(c.file_path.name, sample, role)
                if detection:
                    side, conf = detection
                    c.side = side
                    c.confidence = min(c.confidence, conf)
                    c.note += f" | 角色: {side} [LLM conf={conf:.2f}]"
                    return c

        # 实在判不出来
        c.side = "待确认"
        c.confidence = min(c.confidence, 0.5)
        c.note += " | 角色: 待确认"
        return c

    def _side_by_doc_type(self, filename: str, role: str) -> str:
        """按文书类型粗判我方/对方，规则来自 categories.yaml 第4项 side_rules。
        无匹配规则时返回空串（交由 LLM 判断）。"""
        rules = self._get_cat(4).get("side_rules", []) or []
        for group in rules:
            if role not in (group.get("roles") or []):
                continue
            # 收集命中的(side, 关键词)，按关键词长度取最具体的一个，确保确定性
            hits = []
            for side in ("我方", "对方"):
                for kw in group.get(side, []) or []:
                    if kw in filename:
                        hits.append((len(kw), side))
            if hits:
                hits.sort(reverse=True)   # 最长关键词优先
                return hits[0][1]
        return ""

    def _assign_sort_weight(self, c: Classification) -> Classification:
        cat4 = self._get_cat(4)
        weights = cat4.get("sort_weights", {})
        filename = c.file_path.name
        for keyword, weight in weights.items():
            if keyword in filename:
                c.sort_weight = weight
                return c
        c.sort_weight = 99
        return c

    def _by_content(self, file_path: Path) -> Optional[Classification]:
        """LLM 内容采样分类。"""
        if not self.llm or not self.llm.ready:
            return None
        sample_chars = int(self.clf_cfg.get("sample_chars", 800))
        sample = extract_sample(file_path, n_chars=sample_chars, max_pages=2)
        if not sample.strip():
            return None
        log.info("LLM 内容分类采样：%s", file_path.name)
        detection = self.llm.classify_content(file_path.name, sample, self._categories_brief)
        if not detection:
            return None
        cat_id, conf, reason = detection
        threshold = float(self.clf_cfg.get("confidence_threshold", 0.7))
        if conf < threshold:
            log.info("LLM 置信度 %.2f 低于阈值 %.2f，放弃采用", conf, threshold)
            return None
        cat = self._get_cat(cat_id)
        return Classification(
            file_path=file_path,
            category_id=cat_id,
            category_name=cat.get("name", ""),
            short_name=cat.get("short_name", ""),
            confidence=conf,
            method="llm",
            note=f"LLM: {reason}",
        )

    def get_category(self, cat_id: int) -> dict:
        """公开 API：按 id 取分类配置，未知 id 返回占位 dict。"""
        return self._cat_map.get(cat_id, {"id": cat_id, "name": "未知", "short_name": "未知"})

    # 向后兼容别名（内部仍可用）
    _get_cat = get_category

    def get_auto_write_categories(self) -> List[dict]:
        return [c for c in self.categories if c.get("auto_write_if_missing", False)]

    def category_choices(self) -> List[tuple]:
        """返回 [(id, 显示名), ...] 供 GUI 下拉框使用。"""
        return [(c["id"], f"{c['id']:02d} {c.get('short_name', c['name'])}") for c in self.categories]
