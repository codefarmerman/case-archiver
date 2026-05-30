"""
dialogs.py — 对话框
ApiKeyDialog：DeepSeek API Key 配置（输入、显示切换、测试连接、清除、保存）。
从 gui.py 抽出。
"""
from __future__ import annotations

import os

from PyQt5 import QtWidgets

from config_store import config_file_path, save_api_key
from llm_client import LLMClient


class ApiKeyDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, current_key: str = ""):
        super().__init__(parent)
        self.setWindowTitle("DeepSeek API Key 设置")
        self.setMinimumWidth(560)
        self._build_ui(current_key)

    def _build_ui(self, current_key: str):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QtWidgets.QLabel("配置 DeepSeek API Key")
        title.setStyleSheet("font-size: 14pt; font-weight: 600; color: #1f2328;")
        layout.addWidget(title)

        tip = QtWidgets.QLabel(
            "请输入你的 DeepSeek API Key（以 sk- 开头）。\n"
            "获取地址：https://platform.deepseek.com/api_keys"
        )
        tip.setObjectName("dialogTip")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        input_label = QtWidgets.QLabel("API Key")
        input_label.setStyleSheet("color: #57606a; font-size: 9pt; font-weight: 500;")
        layout.addWidget(input_label)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.input_key = QtWidgets.QLineEdit()
        self.input_key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.input_key.setPlaceholderText("sk-...")
        self.input_key.setText(current_key or "")
        self.input_key.setMinimumHeight(34)
        row.addWidget(self.input_key, stretch=1)

        self.check_show = QtWidgets.QCheckBox("显示")
        self.check_show.toggled.connect(self._on_toggle_show)
        row.addWidget(self.check_show)
        layout.addLayout(row)

        warn = QtWidgets.QLabel(
            f"⚠ Key 将明文保存至 {config_file_path()}，请勿分享或提交到 Git。"
        )
        warn.setObjectName("dialogWarn")
        warn.setWordWrap(True)
        layout.addWidget(warn)

        self.label_status = QtWidgets.QLabel("")
        self.label_status.setMinimumHeight(20)
        layout.addWidget(self.label_status)

        layout.addSpacing(4)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)

        self.btn_test = QtWidgets.QPushButton("测试连接")
        self.btn_test.clicked.connect(self._on_test)
        btn_row.addWidget(self.btn_test)

        self.btn_clear = QtWidgets.QPushButton("清除已保存")
        self.btn_clear.setObjectName("dangerButton")
        self.btn_clear.clicked.connect(self._on_clear)
        btn_row.addWidget(self.btn_clear)

        btn_row.addStretch(1)

        self.btn_cancel = QtWidgets.QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_save = QtWidgets.QPushButton("保存")
        self.btn_save.setObjectName("accentButton")
        self.btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(self.btn_save)

        layout.addLayout(btn_row)

    def _on_toggle_show(self, checked: bool):
        self.input_key.setEchoMode(
            QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password
        )

    def _on_test(self):
        key = self.input_key.text().strip()
        if not key:
            self._set_status("请先输入 Key", err=True)
            return
        self.btn_test.setEnabled(False)
        self._set_status("正在测试 …", info=True)
        QtWidgets.QApplication.processEvents()
        old = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = key
        try:
            client = LLMClient()
            if not client.ready:
                self._set_status(f"初始化失败：{client.init_error}", err=True)
                return
            r = client.write_document("你是测试助手，只回 OK。", "请回复 OK", max_tokens=10)
            if r and "OK" in r.upper():
                self._set_status("✓ 连接成功，API 工作正常")
            elif r:
                self._set_status(f"✓ 已连通（返回：{r[:30]}）")
            else:
                self._set_status("✗ 调用失败，详见日志面板", err=True)
        finally:
            if old is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = old
            self.btn_test.setEnabled(True)

    def _on_clear(self):
        ok = QtWidgets.QMessageBox.question(
            self, "确认清除",
            "确定要从本地删除已保存的 API Key 吗？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if ok != QtWidgets.QMessageBox.Yes:
            return
        save_api_key("")
        self.input_key.clear()
        self._set_status("已清除本地保存的 Key")

    def _on_save(self):
        key = self.input_key.text().strip()
        if key and not key.startswith("sk-"):
            ok = QtWidgets.QMessageBox.question(
                self, "格式提醒",
                "Key 通常以 sk- 开头，是否仍要保存？",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if ok != QtWidgets.QMessageBox.Yes:
                return
        save_api_key(key)
        self.accept()

    def _set_status(self, msg: str, err: bool = False, info: bool = False):
        self.label_status.setText(msg)
        if err:
            color = "#cf222e"
        elif info:
            color = "#0969da"
        else:
            color = "#1a7f37"
        self.label_status.setStyleSheet(f"color: {color}; font-size: 9pt; font-weight: 500;")
