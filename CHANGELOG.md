# 更新日志

本项目版本号遵循 `主.次.修订`。

## [2.3.0]

### 新增
- **归档审计清单**：归档时生成 `归档清单.json` / `归档清单.txt`，记录每份文件
  原始路径 → 新名 → 分类 → 置信度 → 方式 → 理由，律师可事后追溯归类依据。
- **LLM 用量/成本统计**：累计 token 用量并按 DeepSeek 价格估算费用，分类后日志提示。
- **诉讼角色规则外置**：我方/对方粗判规则从代码移到 `categories.yaml` 的 `side_rules`。
- **统一版本号**：单一 `_version.py` 来源；CLI 新增 `--version`。

### 修复
- 修复 PyInstaller `--onefile` 打包后 `style.qss` / `categories.yaml` 资源定位
  （`resource_path` 支持 `sys._MEIPASS`）。

## [2.2.x]

### 新增
- **隐私「纯本地模式」**：仅用文件名分类，绝不上传材料内容；API Key 设置增加隐私告知。
- **API Key 加密存储**：改用系统凭据管理器（keyring），历史明文自动迁移并抹除。
- **LLM 缓存 + 超时**：分类/角色判断结果按输入哈希本地缓存；请求 60s 超时 + 指数退避重试。
- **多格式内容提取**：新增 xlsx / ofd / .doc（可选）/ 图片 OCR（可选），优雅降级。
- **测试与 CI**：pytest 测试套件、ruff、GitHub Actions（Windows × py3.11/3.12）。

### 变更
- **架构重构**：`gui.py` 1385 → ~640 行，拆分 `ui_widgets` / `workers` / `dialogs` /
  `paths` / `archive_engine`，样式表外置 `style.qss`。
- **并发分类**：线程池并发调用 LLM，约 5 倍提速。
- 迁移 LLM 供应商：Anthropic Claude → DeepSeek（OpenAI 兼容）。

### 修复
- 无边框窗口拖动失效（`ctypes.wintypes` 未导入）。
- 运行中关闭窗口导致 QThread 崩溃（新增 `closeEvent`）。
- 自动补写截断与 markdown/AI 前言污染；输出目录同名覆盖；复制数量校验。

## [2.0 – 2.1]

- 初始版本：13 项分类、卷内目录生成、我方/对方识别、缺件自动补写、PyQt5 GUI。
