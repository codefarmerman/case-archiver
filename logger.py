"""
logger.py — 统一日志系统
- 文件日志：logs/archive.log（rotating，5MB × 3）
- 控制台日志：INFO 及以上
- GUI 日志：QtLogHandler 通过 pyqtSignal 转发
"""
from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).parent / "logs"
_LOGGER_NAME = "case_archiver"
_initialized = False
_init_lock = threading.Lock()


def _app_root() -> Path:
    """支持 pyinstaller 打包后的运行目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_logger() -> logging.Logger:
    """获取统一 logger，首次调用时初始化。"""
    global _initialized
    logger = logging.getLogger(_LOGGER_NAME)
    if _initialized:
        return logger

    # 双重检查加锁：并发首次调用（线程池工作线程）只初始化一次，避免重复添加 handler
    with _init_lock:
        if _initialized:
            return logger
        return _init_logger(logger)


def _init_logger(logger: logging.Logger) -> logging.Logger:
    global _initialized
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    log_dir = _app_root() / "logs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "archive.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"[logger] 无法创建文件日志: {e}\n")

    # Windows 控制台默认 cp936，中文会乱码；尝试切到 utf-8
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console)

    _initialized = True
    return logger


class QtLogHandler(logging.Handler):
    """把日志转发到 PyQt5 信号，供 GUI 日志面板订阅。"""

    def __init__(self, signal_emit):
        super().__init__(level=logging.INFO)
        self._emit = signal_emit
        self.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emit(self.format(record))
        except Exception:
            pass


def attach_qt_handler(signal_emit) -> QtLogHandler:
    """给 GUI 挂一个 Qt 日志 handler，返回 handler 便于需要时移除。"""
    handler = QtLogHandler(signal_emit)
    get_logger().addHandler(handler)
    return handler
