# 更新日志

本项目版本号遵循 `主.次.修订`。

## [2.4.0]

### 安全
- **API Key 密文存储升级**：系统凭据管理器（keyring）不可用时，改用 **Windows DPAPI**
  （按当前用户加密）替代明文落盘；新增 `secure_store.py`，明文/旧字段自动迁移并抹除。
- **LLM 提示注入防护**：文档内容以分隔标签包裹并在 system 指令中声明为不可信数据，
  中和文档内伪造的闭合标签；自动补写改用安全替换而非 `str.format`。
- **路径安全**：扫描跳过符号链接 / NTFS junction 并校验归属；归档目标做路径穿越校验
  与文件名净化；OFD 内 XML 加大小上限防解压炸弹。
- **Word 宏防护**：提取 `.doc` 前强制禁用宏（`AutomationSecurity`），修复 COM 对象
  与 `CoUninitialize` 泄露。
- **健壮性**：`config.json` 与 LLM 缓存原子写入；缓存/配置文件权限收紧；
  日志不再输出 API Key 尾部字符。

### 修复
- **Qt 平台插件初始化失败**（"no Qt platform plugin could be initialized"）：
  把 `Qt5/bin` 加入 DLL 搜索路径，并用 Qt API 二次登记插件目录。
- 分类/归档**并发竞态**：运行中拒绝重复启动；测试连接移至后台线程避免 UI 冻结。
- LLM **JSON 解析被截断**：非贪婪正则改为大括号配对扫描，正确处理嵌套与字符串内 `}`。
- `logger` 并发重复初始化：双重检查加锁。
- 归档输出目录撞名竞态（TOCTOU）：改用原子创建 + 递增后缀。

### 变更
- `Classification` 改为不可变更新（`dataclasses.replace`）。
- 测试扩充至 **90 项**（新增端到端集成、workers/GUI 冒烟；无桌面环境自动跳过 GUI 用例）。

### UI
- 卡片微阴影（层次感）、拖拽投放视觉反馈、表格行 hover 高亮、头栏收紧、空状态优化。

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
