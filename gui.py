"""
gui.py — 律师案件自动归档程序（PyQt5 桌面版）
启动：python gui.py
打包：pyinstaller --onefile --windowed --name 案件归档 gui.py

UI 设计：GitHub Primer 风格 · 卡片化布局 · 品牌头栏 · 置信度徽章 · 拖拽支持
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def _fix_qt_plugin_path() -> None:
    """让 Qt 找到 PyQt5 自带的 platforms 插件。
    必要原因：当 Python 解释器在非标准位置（如 uv 缓存、嵌入式 Python）时，
    Qt 默认到解释器目录找插件会失败。本函数把环境变量指向 venv 里的实际目录。
    必须在 import PyQt5 之前执行。
    """
    try:
        import PyQt5  # noqa: F401  仅用于定位包路径
        pkg_dir = Path(PyQt5.__file__).resolve().parent
        plugin_dir = pkg_dir / "Qt5" / "plugins"
        if not plugin_dir.exists():
            plugin_dir = pkg_dir / "Qt" / "plugins"
        if plugin_dir.exists():
            os.environ["QT_PLUGIN_PATH"] = str(plugin_dir)
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(plugin_dir / "platforms")
    except Exception:
        pass


_fix_qt_plugin_path()

from PyQt5 import QtCore, QtGui, QtWidgets

sys.path.insert(0, str(Path(__file__).parent))

from _version import __version__
from classify import Classification
from config_store import (
    apply_api_key_to_env,
    get_setting,
    load_api_key,
    set_setting,
)
from dialogs import ApiKeyDialog
from llm_client import LLMClient
from logger import attach_qt_handler, get_logger
from paths import config_path, resource_path
from ui_widgets import (
    LOW_CONF_THRESHOLD,
    ConfidenceBadge,
    HeaderBar,
    PlaceholderTable,
)
from workers import ArchiveWorker, ClassifyWorker

ROLES = ["原告", "被告", "第三人", "申请人", "被申请人"]
SIDE_CHOICES = ["", "我方", "对方", "待确认"]


# ============================================================
# 全局样式表（GitHub Primer 风格）
# ============================================================
def _load_stylesheet() -> str:
    """从外部 style.qss 读取样式表，便于不改 Python 即可调整 UI。
    打包/缺失时回退到内置最小样式。"""
    try:
        qss_path = resource_path("style.qss")
        if qss_path.exists():
            return qss_path.read_text(encoding="utf-8")
    except Exception as e:
        get_logger().warning("读取 style.qss 失败，使用内置样式：%s", e)
    return _FALLBACK_STYLESHEET


# 最小回退样式（style.qss 缺失时使用）
_FALLBACK_STYLESHEET = """
QWidget { font-family: "Microsoft YaHei", "Segoe UI", sans-serif; font-size: 10pt; color: #1f2328; }
QMainWindow, QWidget#centralWidget { background-color: #f6f8fa; }
QGroupBox { background:#fff; border:1px solid #d0d7de; border-radius:8px; margin-top:14px; padding:18px 16px 12px; font-weight:600; }
QPushButton { background:#f6f8fa; border:1px solid #d0d7de; border-radius:6px; padding:6px 14px; }
QPushButton#primaryButton { background:#1f883d; color:#fff; border:1px solid #1a7f37; }
QPushButton#accentButton { background:#0969da; color:#fff; }
QLineEdit, QComboBox { background:#fff; border:1px solid #d0d7de; border-radius:6px; padding:6px 10px; }
"""


# ============================================================
# 自定义控件
# ============================================================
# ============================================================
# 主窗口
# ============================================================
class MainWindow(QtWidgets.QMainWindow):
    TABLE_HEADERS = ["#", "文件名", "归入项目", "我方/对方", "置信度"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("律师案件归档")
        self.resize(1280, 820)
        self.setAcceptDrops(True)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, False)

        self.results: List[Classification] = []
        self.case_dir: Optional[Path] = None
        self._classify_worker: Optional[ClassifyWorker] = None
        self._archive_worker: Optional[ArchiveWorker] = None

        self._load_categories()
        self._build_ui()
        self._build_menu()
        self._attach_logging()

        self.log_info("程序就绪。请填写案件信息并选择案件文件夹（或拖入主窗口）。")
        self._refresh_api_key_status()

        # 启动时若未配置 API Key，自动弹出设置对话框
        if not load_api_key():
            QtCore.QTimer.singleShot(300, self.on_open_api_key)

    # ---------------- UI 构造 ----------------
    def _load_categories(self):
        try:
            import yaml
            with open(config_path(), "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            self.categories = cfg["categories"]
            self.category_choices = [
                (c["id"], f"{c['id']:02d} {c.get('short_name', c['name'])}")
                for c in self.categories
            ]
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "配置加载失败", f"无法读取 categories.yaml：{e}")
            self.categories = []
            self.category_choices = []

    def _build_ui(self):
        central = QtWidgets.QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ----- 顶部品牌栏（兼自定义标题栏）-----
        self.header = HeaderBar(self)
        root.addWidget(self.header)

        # ----- 主内容区 -----
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)
        root.addWidget(content, stretch=1)

        # ----- 案件信息卡片 -----
        info_box = QtWidgets.QGroupBox("案件信息")
        info_layout = QtWidgets.QVBoxLayout(info_box)
        info_layout.setContentsMargins(16, 8, 16, 12)
        info_layout.setSpacing(10)

        form = QtWidgets.QFormLayout()
        form.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.input_case_no = QtWidgets.QLineEdit()
        self.input_case_no.setPlaceholderText("例如：(2024)琼0106民初XXX号")
        form.addRow("案号", self.input_case_no)

        self.input_case_name = QtWidgets.QLineEdit()
        self.input_case_name.setPlaceholderText("例如：张三诉李四合同纠纷")
        form.addRow("案由 / 当事人", self.input_case_name)

        self.combo_role = QtWidgets.QComboBox()
        self.combo_role.addItems(ROLES)
        form.addRow("我方角色", self.combo_role)

        dir_row = QtWidgets.QHBoxLayout()
        dir_row.setSpacing(8)
        self.label_case_dir = QtWidgets.QLabel("拖入文件夹到此处，或点击右侧按钮选择")
        self.label_case_dir.setObjectName("pathPlaceholder")
        self.btn_pick_dir = QtWidgets.QPushButton("📁 选择文件夹…")
        self.btn_pick_dir.clicked.connect(self.on_pick_dir)
        dir_row.addWidget(self.label_case_dir, stretch=1)
        dir_row.addWidget(self.btn_pick_dir)
        form.addRow("案件文件夹", self._wrap(dir_row))

        info_layout.addLayout(form)
        layout.addWidget(info_box)

        # ----- 分类结果卡片 -----
        table_box = QtWidgets.QGroupBox("分类结果")
        tb_layout = QtWidgets.QVBoxLayout(table_box)
        tb_layout.setContentsMargins(16, 8, 16, 12)
        tb_layout.setSpacing(8)

        hint = QtWidgets.QLabel("可直接下拉修改归类与角色 · 低置信度项已用黄色徽章标出 · 点击表头可排序")
        hint.setObjectName("hintLabel")
        tb_layout.addWidget(hint)

        self.table = PlaceholderTable(0, 5)
        self.table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)  # 自定义启用，避免行错乱
        self.table.verticalHeader().setDefaultSectionSize(36)
        tb_layout.addWidget(self.table)
        layout.addWidget(table_box, stretch=1)

        # ----- 操作栏 -----
        op_row = QtWidgets.QHBoxLayout()
        op_row.setSpacing(10)

        self.check_local_only = QtWidgets.QCheckBox("🔒 纯本地模式")
        self.check_local_only.setToolTip(
            "勾选后：仅用文件名分类，绝不上传任何材料内容到 DeepSeek。\n"
            "适合涉密案件。代价：文件名无关键词的材料会归到「其他」需人工调整。"
        )
        self.check_local_only.setChecked(bool(get_setting("local_only", False)))
        self.check_local_only.toggled.connect(self._on_local_only_toggled)
        op_row.addWidget(self.check_local_only)

        self.check_auto_write = QtWidgets.QCheckBox("自动补写缺件（代理词 / 办案小结）")
        self.check_auto_write.setToolTip("缺第 8 项或第 11 项时，调用 LLM 自动撰写")
        op_row.addWidget(self.check_auto_write)

        # 进度条（隐藏直到分类/归档开始）
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMaximumWidth(280)
        self.progress_bar.setMinimumWidth(180)
        self.progress_bar.setVisible(False)
        op_row.addWidget(self.progress_bar)

        op_row.addStretch(1)

        self.btn_reclassify = QtWidgets.QPushButton("🔄 重新分类")
        self.btn_reclassify.clicked.connect(self.on_classify)
        op_row.addWidget(self.btn_reclassify)

        self.btn_archive = QtWidgets.QPushButton("✓ 确认归档")
        self.btn_archive.setObjectName("primaryButton")
        self.btn_archive.clicked.connect(self.on_archive)
        self.btn_archive.setEnabled(False)
        op_row.addWidget(self.btn_archive)
        layout.addLayout(op_row)

        # ----- 日志面板 -----
        log_box = QtWidgets.QGroupBox("运行日志")
        log_layout = QtWidgets.QVBoxLayout(log_box)
        log_layout.setContentsMargins(16, 8, 16, 12)
        log_layout.setSpacing(6)
        self.text_log = QtWidgets.QTextEdit()
        self.text_log.setObjectName("logBox")
        self.text_log.setReadOnly(True)
        self.text_log.setMinimumHeight(140)
        self.text_log.setMaximumHeight(200)
        log_layout.addWidget(self.text_log)
        layout.addWidget(log_box)

        # 状态栏
        self.status = self.statusBar()
        self.status.showMessage("就绪")

    def _wrap(self, layout: QtWidgets.QLayout) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        w.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)
        return w

    def _build_menu(self):
        menubar = self.menuBar()
        m_settings = menubar.addMenu("设置(&S)")
        act_key = QtWidgets.QAction("DeepSeek API Key 设置…", self)
        act_key.setShortcut("Ctrl+K")
        act_key.triggered.connect(self.on_open_api_key)
        m_settings.addAction(act_key)

        m_help = menubar.addMenu("帮助(&H)")
        act_about = QtWidgets.QAction("关于", self)
        act_about.triggered.connect(self.on_about)
        m_help.addAction(act_about)

    def on_open_api_key(self):
        dlg = ApiKeyDialog(self, current_key=load_api_key() or "")
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self._refresh_api_key_status()

    def on_about(self):
        QtWidgets.QMessageBox.about(
            self,
            "关于 律师案件归档",
            f"<h3>律师案件归档 v{__version__}</h3>"
            "<p>按中国律所标准 <b>13 项卷内目录</b>自动分类、重命名、生成卷内目录。</p>"
            "<p>支持 <b>DeepSeek</b> 大模型自动补写代理词与办案小结。</p>"
            "<p style='color:#656d76; font-size:9pt;'>隐私本地模式 · Key 加密 · 归档审计清单</p>",
        )

    def _refresh_api_key_status(self):
        key = load_api_key()
        if key:
            masked = key[:7] + "…" + key[-4:] if len(key) > 12 else "(已设置)"
            self.log_info(f"API Key 已配置：{masked}")
            self.header.status_pill.set_state("ok", "● DeepSeek 已连接")
        else:
            self.log_info("⚠ 未配置 DEEPSEEK_API_KEY。LLM 兜底分类与自动补写将不可用。")
            self.log_info("  在菜单【设置 → DeepSeek API Key 设置…】可填写（Ctrl+K）。")
            self.header.status_pill.set_state("warn", "● 未配置 API Key")

    # ---------------- 拖拽支持 ----------------
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(Path(u.toLocalFile()).is_dir() for u in urls):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent):
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                self.case_dir = p
                self.label_case_dir.setText(str(p))
                self.label_case_dir.setObjectName("pathActive")
                self.label_case_dir.style().unpolish(self.label_case_dir)
                self.label_case_dir.style().polish(self.label_case_dir)
                self.log_info(f"已拖入文件夹：{p}")
                if self.input_case_no.text().strip() and self.input_case_name.text().strip():
                    self.on_classify()
                else:
                    self.log_info("  请先填写案号和案由 / 当事人，再点击「重新分类」。")
                event.acceptProposedAction()
                return
        event.ignore()

    # ---------------- 日志桥接 ----------------
    def _attach_logging(self):
        self._log_signal = _LogBridge()
        self._log_signal.line.connect(self.log_line)
        attach_qt_handler(self._log_signal.line.emit)

    def log_info(self, msg: str):
        self.text_log.append(msg)

    def log_line(self, msg: str):
        self.text_log.append(msg)
        self.text_log.verticalScrollBar().setValue(self.text_log.verticalScrollBar().maximum())

    # ---------------- 事件 ----------------
    def on_pick_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "选择案件文件夹")
        if not d:
            return
        self.case_dir = Path(d)
        self.label_case_dir.setText(str(self.case_dir))
        self.label_case_dir.setObjectName("pathActive")
        self.label_case_dir.style().unpolish(self.label_case_dir)
        self.label_case_dir.style().polish(self.label_case_dir)
        self.log_info(f"已选择案件文件夹：{self.case_dir}")
        self.on_classify()

    def _on_local_only_toggled(self, checked: bool):
        set_setting("local_only", bool(checked))
        if checked:
            self.log_info("🔒 已开启纯本地模式：后续分类不会上传任何材料内容。")
        else:
            self.log_info("已关闭纯本地模式：文件名无法识别的材料将采样内容交 DeepSeek 判断。")

    def _validate_inputs(self) -> Optional[str]:
        if not self.case_dir or not self.case_dir.exists():
            return "请先选择案件文件夹"
        if not self.input_case_no.text().strip():
            return "请填写案号"
        if not self.input_case_name.text().strip():
            return "请填写案由 / 当事人"
        return None

    def on_classify(self):
        err = self._validate_inputs()
        if err:
            QtWidgets.QMessageBox.warning(self, "信息不全", err)
            return
        self.btn_reclassify.setEnabled(False)
        self.btn_archive.setEnabled(False)
        self.table.setRowCount(0)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("准备扫描…")
        self.status.showMessage("扫描与分类中…")

        if self.check_local_only.isChecked():
            llm = None
            self.log_info("🔒 纯本地模式：仅用文件名分类，不上传任何内容。")
        else:
            llm = LLMClient()
            self.log_info(f"LLM 状态：{'已就绪' if llm.ready else '不可用 — ' + (llm.init_error or '')}")
        self._classify_llm = llm   # 留引用以便分类后读用量
        self._classify_worker = ClassifyWorker(self.case_dir, self.combo_role.currentText(), llm)
        self._classify_worker.progress.connect(self._on_classify_progress)
        self._classify_worker.finished_ok.connect(self._on_classify_done)
        self._classify_worker.failed.connect(self._on_classify_failed)
        self._classify_worker.start()

    def _on_classify_progress(self, cur: int, total: int, name: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(cur)
        truncated = name if len(name) < 36 else name[:33] + "…"
        self.progress_bar.setFormat(f"{cur}/{total}  {truncated}")
        self.status.showMessage(f"分类中 {cur}/{total}：{name}")

    def _on_classify_done(self, results: list):
        self.results = results
        self._populate_table(results)
        self.btn_reclassify.setEnabled(True)
        self.btn_archive.setEnabled(bool(results))
        low = sum(1 for c in results if c.confidence < LOW_CONF_THRESHOLD)
        self.progress_bar.setVisible(False)
        self.status.showMessage(f"分类完成：共 {len(results)} 份，低置信度 {low} 份")
        self.log_info(f"✓ 分类完成：{len(results)} 份，低置信度 {low} 份，请人工核对后点击「确认归档」")
        llm = getattr(self, "_classify_llm", None)
        if llm is not None and getattr(llm, "ready", False):
            self.log_info(f"💰 {llm.usage_summary()}")

    def _on_classify_failed(self, err: str):
        self.btn_reclassify.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status.showMessage("分类失败")
        QtWidgets.QMessageBox.critical(self, "分类失败", err)

    def _populate_table(self, results: List[Classification]):
        self.table.setRowCount(len(results))
        for row, c in enumerate(results):
            # 序号
            item_idx = QtWidgets.QTableWidgetItem(str(row + 1))
            item_idx.setTextAlignment(QtCore.Qt.AlignCenter)
            item_idx.setForeground(QtGui.QColor("#8c959f"))
            self.table.setItem(row, 0, item_idx)

            # 文件名
            item_name = QtWidgets.QTableWidgetItem(c.file_path.name)
            item_name.setToolTip(str(c.file_path))
            self.table.setItem(row, 1, item_name)

            # 归入项目 下拉
            combo_cat = QtWidgets.QComboBox()
            for cat_id, label in self.category_choices:
                combo_cat.addItem(label, cat_id)
            for i, (cat_id, _) in enumerate(self.category_choices):
                if cat_id == c.category_id:
                    combo_cat.setCurrentIndex(i)
                    break
            combo_cat.currentIndexChanged.connect(
                lambda _i, r=row, cb=combo_cat: self._on_category_changed(r, cb)
            )
            self.table.setCellWidget(row, 2, combo_cat)

            # 我方/对方 下拉
            combo_side = QtWidgets.QComboBox()
            combo_side.addItems(SIDE_CHOICES)
            combo_side.setCurrentText(c.side or "")
            combo_side.setEnabled(c.category_id == 4)
            self._style_side_combo(combo_side, c.side or "")
            combo_side.currentTextChanged.connect(
                lambda text, r=row, cb=combo_side: self._on_side_changed(r, text, cb)
            )
            self.table.setCellWidget(row, 3, combo_side)

            # 置信度徽章
            badge = ConfidenceBadge(c.confidence, c.method)
            badge.setToolTip(c.note or f"分类方式：{c.method}")
            # 用 cellWidget 居中显示徽章
            wrapper = QtWidgets.QWidget()
            wl = QtWidgets.QHBoxLayout(wrapper)
            wl.setContentsMargins(8, 4, 8, 4)
            wl.addStretch(1)
            wl.addWidget(badge)
            wl.addStretch(1)
            self.table.setCellWidget(row, 4, wrapper)

            self._apply_row_highlight(row, c)

    def _apply_row_highlight(self, row: int, c: Classification):
        # 行底色（低置信度浅黄）
        low = c.confidence < LOW_CONF_THRESHOLD and c.method != "人工"
        color = QtGui.QColor("#fffbe6") if low else QtGui.QColor("#ffffff")
        for col in [0, 1]:
            item = self.table.item(row, col)
            if item:
                item.setBackground(color)

    def _on_category_changed(self, row: int, combo: QtWidgets.QComboBox):
        new_id = combo.currentData()
        c = self.results[row]
        old = c.category_id
        c.category_id = int(new_id)
        for cat in self.categories:
            if cat["id"] == c.category_id:
                c.category_name = cat["name"]
                c.short_name = cat.get("short_name", "")
                break
        c.confidence = max(c.confidence, 0.99)
        c.method = "人工"
        c.note = f"人工从第{old}项改为第{c.category_id}项"
        self.log_info(f"已修改：{c.file_path.name} → 第 {c.category_id} 项")

        side_combo = self.table.cellWidget(row, 3)
        if side_combo:
            side_combo.setEnabled(c.category_id == 4)
            if c.category_id != 4:
                side_combo.setCurrentText("")
                c.side = ""

        # 更新徽章
        wrapper = self.table.cellWidget(row, 4)
        if wrapper:
            for badge in wrapper.findChildren(ConfidenceBadge):
                badge.update_badge(c.confidence, c.method)
        self._apply_row_highlight(row, c)

    @staticmethod
    def _style_side_combo(combo: QtWidgets.QComboBox, side: str):
        """待确认时红色高亮，提醒律师必须人工确认。"""
        if side == "待确认":
            combo.setStyleSheet(
                "QComboBox{background:#ffebe9; color:#cf222e; border:1px solid #ff8182;"
                "border-radius:6px; font-weight:600;}"
            )
        else:
            combo.setStyleSheet("")

    def _on_side_changed(self, row: int, text: str, combo: QtWidgets.QComboBox = None):
        c = self.results[row]
        c.side = text
        if combo is not None:
            self._style_side_combo(combo, text)
        self.log_info(f"已修改：{c.file_path.name} 我方/对方 → {text or '（空）'}")

    def on_archive(self):
        err = self._validate_inputs()
        if err:
            QtWidgets.QMessageBox.warning(self, "信息不全", err)
            return
        if not self.results:
            QtWidgets.QMessageBox.warning(self, "无数据", "请先完成分类")
            return

        low = [c for c in self.results if c.confidence < LOW_CONF_THRESHOLD]
        if low:
            ok = QtWidgets.QMessageBox.question(
                self,
                "存在低置信度项",
                f"有 {len(low)} 份材料置信度偏低（黄色徽章），是否仍然继续归档？\n"
                "建议先人工在表格中调整。",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if ok != QtWidgets.QMessageBox.Yes:
                return

        auto_write = self.check_auto_write.isChecked()
        if auto_write and self.check_local_only.isChecked():
            QtWidgets.QMessageBox.information(
                self,
                "纯本地模式",
                "已开启纯本地模式，自动补写需上传材料到 DeepSeek，本次将跳过补写。",
            )
            auto_write = False
        llm = LLMClient() if auto_write else None
        if auto_write and not llm.ready:
            QtWidgets.QMessageBox.warning(
                self,
                "无法自动补写",
                f"自动补写需要 DeepSeek API：{llm.init_error}\n将继续归档，但不生成代理词 / 办案小结。",
            )
            auto_write = False
            llm = None

        self.btn_archive.setEnabled(False)
        self.btn_reclassify.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(0)  # 不确定进度条
        self.progress_bar.setFormat("归档中…")
        self.status.showMessage("归档中…")
        self.log_info("=== 开始归档 ===")

        self._archive_worker = ArchiveWorker(
            results=self.results,
            case_dir=self.case_dir,
            case_no=self.input_case_no.text().strip(),
            case_name=self.input_case_name.text().strip(),
            role=self.combo_role.currentText(),
            auto_write=auto_write,
            llm=llm,
        )
        self._archive_worker.progress.connect(self.log_info)
        self._archive_worker.finished_ok.connect(self._on_archive_done)
        self._archive_worker.failed.connect(self._on_archive_failed)
        self._archive_worker.start()

    def _on_archive_done(self, output_dir: Path, total: int):
        self.btn_archive.setEnabled(True)
        self.btn_reclassify.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status.showMessage("归档完成")
        self.log_info(f"✓ 归档完成，共 {total} 份文件")
        QtWidgets.QMessageBox.information(
            self,
            "归档完成",
            f"已归档 {total} 份文件到：\n{output_dir}\n\n卷内目录：00_卷内目录.docx",
        )
        self._open_folder(output_dir)

    def _on_archive_failed(self, err: str):
        self.btn_archive.setEnabled(True)
        self.btn_reclassify.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status.showMessage("归档失败")
        QtWidgets.QMessageBox.critical(self, "归档失败", err)


    # ---------------- 无边框窗口：标题栏拖动 / 边缘 resize / Aero Snap ----------------
    RESIZE_MARGIN = 6

    def nativeEvent(self, eventType, message):
        if eventType != b"windows_generic_MSG" and eventType != "windows_generic_MSG":
            return super().nativeEvent(eventType, message)
        try:
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
        except Exception:
            return super().nativeEvent(eventType, message)
        if msg.message == 0x0084:  # WM_NCHITTEST
            x = ctypes.c_short(msg.lParam & 0xFFFF).value
            y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
            pos = self.mapFromGlobal(QtCore.QPoint(x, y))
            w, h = self.width(), self.height()
            m = self.RESIZE_MARGIN
            # 仅在非最大化时启用边缘 resize
            if not self.isMaximized():
                top = pos.y() < m
                bottom = pos.y() > h - m
                left = pos.x() < m
                right = pos.x() > w - m
                if top and left:
                    return True, 13       # HTTOPLEFT
                if top and right:
                    return True, 14       # HTTOPRIGHT
                if bottom and left:
                    return True, 16       # HTBOTTOMLEFT
                if bottom and right:
                    return True, 17       # HTBOTTOMRIGHT
                if left:
                    return True, 10       # HTLEFT
                if right:
                    return True, 11       # HTRIGHT
                if top:
                    return True, 12       # HTTOP
                if bottom:
                    return True, 15       # HTBOTTOM
            # 头部区域作为标题栏：允许拖动 + 双击最大化 + Win+方向键 Snap
            # 但不要包括右上角窗口控制按钮区域
            header_h = self.header.height() if self.header else 160
            if pos.y() < header_h:
                # 动态计算窗口控制按钮区域（DPI 安全），避免硬编码像素
                ctrl = self.header.controls
                ctrl_w = ctrl.width()
                ctrl_top = ctrl.mapTo(self, QtCore.QPoint(0, 0)).y()
                ctrl_bottom = ctrl_top + ctrl.height()
                in_controls = (pos.x() > w - ctrl_w) and (ctrl_top <= pos.y() <= ctrl_bottom)
                if not in_controls:
                    return True, 2        # HTCAPTION
        return super().nativeEvent(eventType, message)

    def closeEvent(self, event: QtGui.QCloseEvent):
        """运行中关闭时拒绝，避免 QThread 被销毁导致崩溃。"""
        running = [
            w for w in (self._classify_worker, self._archive_worker)
            if w is not None and w.isRunning()
        ]
        if running:
            QtWidgets.QMessageBox.warning(
                self, "任务进行中",
                "分类或归档正在进行，请等待完成后再关闭窗口。",
            )
            event.ignore()
            return
        event.accept()

    @staticmethod
    def _open_folder(path: Path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            get_logger().warning("打开目录失败：%s", e)


class _LogBridge(QtCore.QObject):
    line = QtCore.pyqtSignal(str)


def main():
    get_logger()
    apply_api_key_to_env()
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(_load_stylesheet())
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
