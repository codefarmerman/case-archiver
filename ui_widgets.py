"""
ui_widgets.py — 自定义 PyQt5 控件
从 gui.py 抽出的纯展示控件：状态徽章、窗口控制按钮、品牌 logo、
品牌头栏、置信度徽章、空状态表格。仅依赖 PyQt5 + LOW_CONF_THRESHOLD。
"""
from __future__ import annotations

from PyQt5 import QtCore, QtGui, QtWidgets

LOW_CONF_THRESHOLD = 0.7


class StatusPill(QtWidgets.QLabel):
    """状态徽章（DeepSeek 已连接 / 未配置）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusPill")
        self.set_state("warn", "● 未配置 API Key")

    def set_state(self, state: str, text: str):
        self.setProperty("state", state)
        self.setText(text)
        self.style().unpolish(self)
        self.style().polish(self)


class WindowControls(QtWidgets.QWidget):
    """Windows 11 风格的最小化/最大化/关闭按钮组。"""

    BTN_W = 46
    BTN_H = 36

    def __init__(self, window: QtWidgets.QMainWindow):
        super().__init__()
        self._win = window

        h = QtWidgets.QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        self.btn_min = self._make_btn("—", "最小化")  # em dash
        self.btn_min.clicked.connect(window.showMinimized)
        h.addWidget(self.btn_min)

        self.btn_max = self._make_btn("□", "最大化")  # white square
        self.btn_max.clicked.connect(self._toggle_max)
        h.addWidget(self.btn_max)

        self.btn_close = self._make_btn("✕", "关闭", danger=True)  # multiplication x
        self.btn_close.clicked.connect(window.close)
        h.addWidget(self.btn_close)

    def _make_btn(self, text: str, tip: str, danger: bool = False) -> QtWidgets.QPushButton:
        b = QtWidgets.QPushButton(text)
        b.setToolTip(tip)
        b.setFixedSize(self.BTN_W, self.BTN_H)
        b.setFocusPolicy(QtCore.Qt.NoFocus)
        font = QtGui.QFont("Segoe UI Symbol", 10)
        b.setFont(font)
        base = (
            "QPushButton { background: transparent; border: none; color: #1f2328; }"
        )
        if danger:
            b.setStyleSheet(
                base +
                "QPushButton:hover { background: #cf222e; color: white; }"
                "QPushButton:pressed { background: #a40e26; color: white; }"
            )
        else:
            b.setStyleSheet(
                base +
                "QPushButton:hover { background: #eaeef2; }"
                "QPushButton:pressed { background: #d0d7de; }"
            )
        return b

    def _toggle_max(self):
        if self._win.isMaximized():
            self._win.showNormal()
            self.btn_max.setText("□")
            self.btn_max.setToolTip("最大化")
        else:
            self._win.showMaximized()
            self.btn_max.setText("❐")  # double square (restore)
            self.btn_max.setToolTip("还原")


class BrandLogo(QtWidgets.QLabel):
    """品牌色块标志：深绿底 + 白色"档"字，圆角矩形，类 Linear / Notion 工作区图标风格。"""

    def __init__(self, parent=None):
        super().__init__("档", parent)
        self.setFixedSize(64, 64)
        self.setAlignment(QtCore.Qt.AlignCenter)

        font = QtGui.QFont("Microsoft YaHei", 30)
        font.setWeight(QtGui.QFont.Bold)
        self.setFont(font)

        self.setStyleSheet(
            "QLabel {"
            "  background-color: #1a7f37;"
            "  color: #ffffff;"
            "  border-radius: 14px;"
            "  border: 1px solid #197935;"
            "  border-bottom: 2px solid #136829;"
            "  padding-bottom: 2px;"
            "}"
        )


class HeaderBar(QtWidgets.QFrame):
    """应用顶部品牌栏（兼任自定义标题栏）：
    顶部窗口控制条 + 下半品牌区，按 UI 设计师标准重新排版。
    """

    def __init__(self, window: QtWidgets.QMainWindow):
        super().__init__()
        self.setObjectName("headerBar")
        self.setFixedHeight(138)  # 36 (top) + 102 (brand)，收紧以让结果表格更高
        self._win = window

        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # 顶部窗口控制条（36px）
        topbar = QtWidgets.QWidget()
        topbar.setObjectName("titleBarTop")
        topbar.setFixedHeight(36)
        top_h = QtWidgets.QHBoxLayout(topbar)
        top_h.setContentsMargins(20, 0, 0, 0)
        top_h.setSpacing(10)

        app_label = QtWidgets.QLabel("CASE ARCHIVER")
        app_label_font = QtGui.QFont("Segoe UI", 8)
        app_label_font.setWeight(QtGui.QFont.Medium)
        app_label_font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 1.5)
        app_label.setFont(app_label_font)
        app_label.setStyleSheet("color: #656d76; background: transparent;")  # a11y 对比度
        top_h.addWidget(app_label)
        top_h.addStretch(1)

        self.controls = WindowControls(window)
        top_h.addWidget(self.controls)
        v.addWidget(topbar)

        # 品牌区（124px）
        brand_area = QtWidgets.QWidget()
        brand_area.setObjectName("titleBarBrand")
        ba = QtWidgets.QHBoxLayout(brand_area)
        ba.setContentsMargins(32, 14, 32, 14)
        ba.setSpacing(22)

        logo = BrandLogo()
        ba.addWidget(logo, alignment=QtCore.Qt.AlignVCenter)

        brand_text = QtWidgets.QVBoxLayout()
        brand_text.setSpacing(6)
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setAlignment(QtCore.Qt.AlignVCenter)

        title = QtWidgets.QLabel("律师案件归档")
        title_font = QtGui.QFont("Microsoft YaHei", 22)
        title_font.setWeight(QtGui.QFont.DemiBold)
        title_font.setHintingPreference(QtGui.QFont.PreferDefaultHinting)
        title.setFont(title_font)
        title.setStyleSheet("color: #1f2328; background: transparent;")
        title.setMinimumHeight(46)
        brand_text.addWidget(title)

        subtitle = QtWidgets.QLabel("CASE FILING & ARCHIVAL  ·  13 项卷内目录  ·  智能分类")
        subtitle_font = QtGui.QFont("Microsoft YaHei", 11)
        subtitle_font.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 0.4)
        subtitle.setFont(subtitle_font)
        subtitle.setStyleSheet("color: #656d76; background: transparent;")
        subtitle.setMinimumHeight(26)
        brand_text.addWidget(subtitle)

        ba.addLayout(brand_text)
        ba.addStretch(1)

        divider = QtWidgets.QFrame()
        divider.setFrameShape(QtWidgets.QFrame.VLine)
        divider.setStyleSheet("color: #eaeef2; background-color: #eaeef2; max-width: 1px;")
        divider.setFixedHeight(48)
        ba.addWidget(divider, alignment=QtCore.Qt.AlignVCenter)

        self.status_pill = StatusPill()
        pill_font = QtGui.QFont("Microsoft YaHei", 10)
        pill_font.setWeight(QtGui.QFont.Medium)
        self.status_pill.setFont(pill_font)
        self.status_pill.setMinimumWidth(150)
        self.status_pill.setMinimumHeight(32)
        self.status_pill.setAlignment(QtCore.Qt.AlignCenter)
        ba.addWidget(self.status_pill, alignment=QtCore.Qt.AlignVCenter)

        v.addWidget(brand_area, stretch=1)

    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent):
        if event.button() == QtCore.Qt.LeftButton:
            if self._win.isMaximized():
                self._win.showNormal()
                self.controls.btn_max.setText("□")
            else:
                self._win.showMaximized()
                self.controls.btn_max.setText("❐")
        super().mouseDoubleClickEvent(event)


class ConfidenceBadge(QtWidgets.QLabel):
    """彩色置信度徽章。"""

    def __init__(self, confidence: float, method: str, parent=None):
        super().__init__(parent)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.update_badge(confidence, method)

    def update_badge(self, confidence: float, method: str):
        if method == "人工":
            bg, fg, border = "#fbefff", "#8250df", "#d8b9ff"
            label = "✎ 人工"
        elif confidence >= 0.9:
            bg, fg, border = "#dafbe1", "#1a7f37", "#aceebb"
            label = f"✓ 高 {confidence:.2f}"
        elif confidence >= LOW_CONF_THRESHOLD:
            bg, fg, border = "#ddf4ff", "#0969da", "#80ccff"
            label = f"中 {confidence:.2f}"
        else:
            bg, fg, border = "#fff8c5", "#7d4e00", "#d4a72c"
            label = f"⚠ 低 {confidence:.2f}"

        self.setText(label)
        self.setStyleSheet(
            f"background-color: {bg}; color: {fg}; border: 1px solid {border};"
            f"border-radius: 11px; padding: 3px 12px; font-weight: 500;"
            f"font-size: 9pt; min-height: 20px;"
        )


class PlaceholderTable(QtWidgets.QTableWidget):
    """空状态时在视口中央绘制图标 + 提示文字，引导更友好。"""

    placeholder_icon = "🗂"
    placeholder_text = "拖入案件文件夹，或点击「选择文件夹」开始分类"

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.rowCount() != 0:
            return
        rect = self.viewport().rect()
        painter = QtGui.QPainter(self.viewport())
        painter.save()
        painter.setPen(QtGui.QColor("#afb8c1"))

        # 图标（略偏上）
        icon_font = QtGui.QFont("Segoe UI Emoji", 40)
        painter.setFont(icon_font)
        icon_rect = rect.adjusted(0, -28, 0, -28)
        painter.drawText(icon_rect, QtCore.Qt.AlignCenter, self.placeholder_icon)

        # 提示文字（略偏下）
        painter.setPen(QtGui.QColor("#656d76"))  # a11y：满足 WCAG AA 对比度
        text_font = QtGui.QFont("Microsoft YaHei", 11)
        painter.setFont(text_font)
        text_rect = rect.adjusted(0, 44, 0, 44)
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, self.placeholder_text)
        painter.restore()
