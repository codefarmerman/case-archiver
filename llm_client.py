"""
llm_client.py — DeepSeek API 封装（OpenAI 兼容）
三类任务：
1. classify_content  文件名未命中时，让 LLM 判断归入第几项
2. detect_side       第 4 项我方/对方不明时，让 LLM 读 PDF 前两页判断
3. write_document    缺件自动补写正文
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Optional, Tuple

import llm_cache
from logger import get_logger

log = get_logger()

DEFAULT_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MAX_RETRIES = 2
REQUEST_TIMEOUT = 60.0       # 单次请求超时（秒），防止卡死并发线程
RETRY_BASE_DELAY = 1.5       # 指数退避基数

# DeepSeek deepseek-chat 估算价格（元/百万 token，2025 标准时段，缓存未命中）
# 仅用于粗略成本提示，非精确账单。官方价随时段/版本浮动。
PRICE_INPUT_PER_M = 2.0
PRICE_OUTPUT_PER_M = 8.0


class LLMClient:
    """封装 DeepSeek 客户端。无 API Key 或 SDK 未装时所有方法返回 None。"""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._client = None
        self._ready = False
        self._init_error: Optional[str] = None
        # 用量累计（线程安全）
        import threading
        self._usage_lock = threading.Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.api_calls = 0          # 实际发出的请求数（不含缓存命中）
        self._init()

    def _add_usage(self, usage) -> None:
        if not usage:
            return
        with self._usage_lock:
            self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
            self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
            self.api_calls += 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def estimated_cost_cny(self) -> float:
        """粗略估算本会话花费（人民币元）。"""
        return (
            self.prompt_tokens / 1_000_000 * PRICE_INPUT_PER_M
            + self.completion_tokens / 1_000_000 * PRICE_OUTPUT_PER_M
        )

    def usage_summary(self) -> str:
        if self.api_calls == 0:
            return "本次未发生 API 调用（全部命中缓存或纯本地）"
        return (
            f"本次 API 调用 {self.api_calls} 次，"
            f"输入 {self.prompt_tokens} + 输出 {self.completion_tokens} = {self.total_tokens} tokens，"
            f"约 ¥{self.estimated_cost_cny():.4f}"
        )

    def _init(self) -> None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            self._init_error = "未设置 DEEPSEEK_API_KEY 环境变量"
            log.warning("LLM 客户端未初始化：%s", self._init_error)
            return
        try:
            from openai import OpenAI
        except ImportError:
            self._init_error = "openai SDK 未安装，请运行 pip install openai"
            log.warning("LLM 客户端未初始化：%s", self._init_error)
            return
        try:
            self._client = OpenAI(
                api_key=api_key,
                base_url=DEEPSEEK_BASE_URL,
                timeout=REQUEST_TIMEOUT,
                max_retries=0,   # 自行管理重试与退避
            )
            self._ready = True
            log.info("LLM 客户端已就绪（DeepSeek，模型 %s，超时 %.0fs）", self.model, REQUEST_TIMEOUT)
        except Exception as e:
            self._init_error = f"初始化 DeepSeek 客户端失败：{e}"
            log.error(self._init_error)

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def _call(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> Optional[str]:
        if not self._ready:
            return None
        last_err: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                kwargs = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = self._client.chat.completions.create(**kwargs)
                self._add_usage(getattr(resp, "usage", None))
                if resp.choices and resp.choices[0].message.content:
                    finish = getattr(resp.choices[0], "finish_reason", None)
                    if finish == "length":
                        log.warning(
                            "LLM 输出因达到 max_tokens(%d) 被截断，内容可能不完整", max_tokens
                        )
                    return resp.choices[0].message.content
                log.error("LLM 返回内容为空")
                return None
            except Exception as e:
                last_err = e
                log.warning("LLM 调用失败 (第%d次): %s", attempt + 1, e)
                if attempt < MAX_RETRIES:
                    # 指数退避：1.5s, 3s, 6s ...
                    time.sleep(RETRY_BASE_DELAY * (2 ** attempt))
        log.error("LLM 调用最终失败: %s", last_err)
        return None

    def classify_content(
        self,
        file_name: str,
        sample_text: str,
        categories_brief: str,
    ) -> Optional[Tuple[int, float, str]]:
        """让 LLM 判断文件应归入哪一项。返回 (category_id, confidence, reason)。"""
        if not self._ready or not sample_text.strip():
            return None

        # 缓存：相同模型 + 文件名 + 内容 + 目录定义 → 直接复用，省钱提速
        cache_key = llm_cache.make_key("classify", self.model, file_name, sample_text, categories_brief)
        cached = llm_cache.get(cache_key)
        if cached is not None:
            try:
                return int(cached[0]), float(cached[1]), str(cached[2])
            except (TypeError, ValueError, IndexError):
                pass  # 缓存格式异常则忽略，重新调用

        system = "你是一个中国律所的案件材料分类助手，只输出 JSON，不要解释。"
        user = (
            f"律师案件材料 13 项目录：\n{categories_brief}\n\n"
            f"文件名：{file_name}\n"
            f"文件内容前若干字：\n\"\"\"\n{sample_text}\n\"\"\"\n\n"
            "请判断该文件应归入哪一项（1-13），并给出 0~1 之间的置信度。"
            "只返回 JSON：{\"category_id\": <int>, \"confidence\": <float>, \"reason\": \"<简短理由>\"}"
        )
        raw = self._call(system, user, max_tokens=300, json_mode=True)
        if not raw:
            return None
        data = _safe_json(raw)
        if not data:
            log.warning("LLM 分类返回无法解析：%s", raw[:200])
            return None
        try:
            cat_id = int(data.get("category_id", 13))
            conf = float(data.get("confidence", 0.5))
            reason = str(data.get("reason", ""))[:120]
            cat_id = max(1, min(13, cat_id))
            conf = max(0.0, min(1.0, conf))
            llm_cache.set(cache_key, [cat_id, conf, reason])
            return cat_id, conf, reason
        except (TypeError, ValueError):
            log.warning("LLM 分类返回字段异常：%s", data)
            return None

    def detect_side(
        self,
        file_name: str,
        sample_text: str,
        role: str,
    ) -> Optional[Tuple[str, float]]:
        """判断诉讼文书是我方还是对方提交。返回 (我方|对方, confidence)。"""
        if not self._ready or not sample_text.strip():
            return None

        cache_key = llm_cache.make_key("side", self.model, file_name, sample_text, role)
        cached = llm_cache.get(cache_key)
        if cached is not None:
            try:
                side_c = str(cached[0])
                if side_c in ("我方", "对方"):
                    return side_c, float(cached[1])
            except (TypeError, ValueError, IndexError):
                pass

        system = "你是一个中国律师助手，擅长识别诉讼文书的提交方。只输出 JSON。"
        user = (
            f"我方诉讼地位是：{role}\n"
            f"文件名：{file_name}\n"
            f"文书内容前两页（摘要）：\n\"\"\"\n{sample_text}\n\"\"\"\n\n"
            "请判断这份文书是我方还是对方提交（例如起诉状通常是原告方提交，答辩状通常是被告方提交）。"
            "只返回 JSON：{\"side\": \"我方\" 或 \"对方\", \"confidence\": <0~1>, \"reason\": \"<简短>\"}"
        )
        raw = self._call(system, user, max_tokens=200, json_mode=True)
        if not raw:
            return None
        data = _safe_json(raw)
        if not data:
            log.warning("LLM 角色判断返回无法解析：%s", raw[:200])
            return None
        side = str(data.get("side", "")).strip()
        if side not in ("我方", "对方"):
            log.warning("LLM 角色判断返回非法 side：%s", side)
            return None
        try:
            conf = float(data.get("confidence", 0.6))
        except (TypeError, ValueError):
            conf = 0.6
        conf = max(0.0, min(1.0, conf))
        llm_cache.set(cache_key, [side, conf])
        return side, conf

    def write_document(self, system: str, prompt: str, max_tokens: int = 4000) -> Optional[str]:
        """用于补写代理词/办案小结。"""
        return self._call(system, prompt, max_tokens=max_tokens)


def _safe_json(text: str) -> Optional[dict]:
    """从 LLM 输出中抓第一个 JSON 对象。"""
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*?\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# 文本提取已拆分到 extractors.py（支持 pdf/docx/txt/xlsx/ofd/doc/图片）。
# 此处重新导出以保持 classify.py、auto_write.py 的旧导入路径不变。
from extractors import extract_sample  # noqa: E402,F401


def categories_brief_text(categories: list) -> str:
    """把 yaml 中的分类转成给 LLM 的简要描述。"""
    lines = []
    for cat in categories:
        kws = "、".join((cat.get("keywords") or [])[:6])
        line = f"{cat['id']}. {cat['name']}"
        if kws:
            line += f"（典型：{kws}）"
        lines.append(line)
    return "\n".join(lines)
