# 律师案件归档 (Case Archiver)

按中国律所标准 **13 项卷内目录** 自动对案件材料分类、重命名、排序，生成卷内目录 Word，并可调用大模型自动补写代理词与办案小结。

提供 **桌面 GUI**（PyQt5）和 **命令行** 两种入口。

---

## 功能特性

- **两层智能分类**：文件名关键词规则（快、零成本）→ LLM 内容采样兜底（准）
- **我方/对方识别**：第 4 项诉讼文书自动判断提交方，按诉讼推进顺序排序
- **缺件自动补写**：缺代理词（第 8 项）/办案小结（第 11 项）时调用 DeepSeek 撰写
- **卷内目录生成**：标准 13 项目录 Word，空项也列出
- **归档审计清单**：`归档清单.json/.txt` 记录每份文件归类依据，可事后追溯
- **多格式提取**：pdf / docx / txt / xlsx / ofd，可选 .doc（Word COM）与图片 OCR
- **隐私与安全**：
  - 🔒 **纯本地模式**：仅用文件名分类，绝不上传任何材料内容
  - API Key 优先存入系统凭据管理器（keyring）；不可用时回退 **Windows DPAPI** 按用户加密，历史明文自动迁移
- **性能与成本**：并发分类（线程池）、分类结果本地缓存、API 用量与费用提示

---

## 安装

需要 Python 3.9+，**推荐 3.11 / 3.12**（CI 覆盖范围）。更高版本（如 3.14）PyQt5 官方未保证，可能遇到 Qt 兼容问题。

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

可选依赖（缺失时对应格式优雅降级为仅文件名分类）：

```bash
pip install pywin32           # 提取旧版 .doc（需安装 Word）
pip install pytesseract       # 图片 OCR（另需安装 Tesseract-OCR 引擎 + chi_sim 语言包）
```

---

## 使用

### 桌面 GUI

```bash
python gui.py
```

1. 填案号、案由/当事人，选我方角色
2. 拖入案件文件夹（或点「选择文件夹」）→ 自动扫描分类
3. 黄色徽章 = 低置信度，可下拉人工调整；待确认角色为红色高亮
4. （可选）勾选自动补写 / 纯本地模式 → 点「确认归档」
5. 完成后自动打开归档目录

首次启动会弹出 API Key 设置（不配也能用，仅文件名分类）。快捷键 `Ctrl+K` 重新配置。

### 命令行

```bash
python archive.py <案件文件夹> \
  --case-no "(2024)琼0106民初XXX号" \
  --case-name "张三诉李四合同纠纷" \
  --role 原告 \
  --dry-run            # 先预览分类，确认无误后去掉此参数正式归档

# 自动补写缺件
python archive.py <案件文件夹> --case-no ... --case-name ... --role 原告 --auto-write
```

> **首次务必 `--dry-run`**：律师文件不容出错，先看分类报告再正式归档。

---

## 架构

```
gui.py            桌面入口（窗口、事件、表格）
archive.py        命令行入口
├─ workers.py     后台线程（并发分类 / 归档执行）
├─ dialogs.py     API Key 对话框
├─ ui_widgets.py  自定义控件（头栏 / 徽章 / 空状态表格）
└─ style.qss      外部样式表（改 UI 不改代码）

archive_engine.py 归档核心（扫描/排序/复制/补写/卷内目录/审计清单）
classify.py       两层分类器
llm_client.py     DeepSeek 封装（用量统计 / 超时 / 退避）
llm_cache.py      分类结果本地缓存
extractors.py     多格式文本提取
config_store.py   配置 + API Key（keyring）
paths.py          路径解析（含 PyInstaller 资源定位）
build_cover.py    卷内目录 Word 生成
auto_write.py     文书自动补写
logger.py         统一日志
categories.yaml   13 项分类规则（关键词 / 角色规则 / 排序权重）
```

数据流：`扫描 → 分类(文件名→LLM) → 人工核对 → 复制重命名 → 补写缺件 → 卷内目录 + 审计清单`

---

## 开发

```bash
pip install -r requirements-dev.txt
pip install pytest ruff

pytest            # 运行测试（90 项；无桌面环境会自动跳过 GUI 用例）
ruff check .      # 代码检查
```

CI（GitHub Actions）在 push/PR 时跑 ruff + pytest（Windows × Python 3.11/3.12）。

---

## 打包

```bash
build_exe.bat     # PyInstaller 打包为单 exe，自动带上 categories.yaml 与 style.qss
```

产物：`dist\案件归档.exe`

---

## 隐私说明

非纯本地模式下，分类时会把材料**前几页内容**上传至 DeepSeek API 用于判断归类与我方/对方。
涉密案件请勾选「🔒 纯本地模式」——该模式仅用文件名分类，不上传任何内容。

API Key 默认加密存储于系统凭据管理器；keyring 不可用时回退 Windows DPAPI 密文。`config.json` 永不含明文密钥。

---

## 许可证

本项目采用 [MIT License](LICENSE)。
