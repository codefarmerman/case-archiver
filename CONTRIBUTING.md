# 贡献指南

感谢你对**律师案件归档 (Case Archiver)** 的关注！欢迎以 Issue、讨论或 Pull Request 的形式参与。

> 本项目处理律师案件材料，**正确性与隐私优先**。涉及分类逻辑、归档流程、密钥存储的改动请格外谨慎，并附测试。

---

## 开发环境

需要 Python 3.9+（**推荐 3.11 / 3.12**，CI 覆盖范围；3.14 等更高版本 PyQt5 官方未保证）。

```bash
git clone https://github.com/codefarmerman/case-archiver.git
cd case-archiver
python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

运行：

```bash
python gui.py                    # 桌面 GUI
python archive.py <案件夹> --case-no ... --case-name ... --role 原告 --dry-run   # 命令行
```

---

## 提交前自检

PR 必须通过以下检查（CI 也会跑）：

```bash
ruff check .                     # 代码风格（行长 120，规则见 pyproject.toml）
pytest                           # 测试（默认跑 80 项；GUI 测试需 opt-in）
```

GUI / worker 冒烟测试在 headless 环境（CI）下默认跳过——Qt 控件 teardown 在无桌面会话时易触发原生崩溃。**在真实桌面**上验证 GUI 改动时显式开启：

```bash
# Windows PowerShell
$env:RUN_GUI_TESTS = "1"; pytest tests/test_gui_smoke.py tests/test_workers.py
```

---

## 代码约定

- **不可变优先**：返回新对象而非就地修改（参见 `classify.py` 用 `dataclasses.replace`）。
- **多小文件 > 少大文件**：函数 < 50 行，文件 < 800 行，按功能组织。
- **显式错误处理**：系统边界校验输入；面向用户给友好提示，服务端记录详细日志；不静默吞错。
- **安全**：禁止硬编码密钥；API Key 走 `config_store`（keyring → DPAPI），永不明文落盘；处理外部文件/LLM 输出时按不可信数据对待。
- **UI**：样式集中在 `style.qss`（顶部有设计令牌注释），尽量不改代码即可调外观；注意文本对比度满足 WCAG AA。

新功能 / 改 bug 请**补对应测试**（单元 / 集成；关键流程可加端到端）。

---

## 提交信息

遵循约定式提交（Conventional Commits）：

```
<type>: <简述>

<可选正文>
```

`type` ∈ `feat` / `fix` / `refactor` / `docs` / `test` / `chore` / `perf` / `ci` / `style`。

---

## Pull Request 流程

1. Fork 并基于 `main` 新建分支（`feat/xxx`、`fix/xxx`）。
2. 完成改动并通过 `ruff` + `pytest`。
3. 提交 PR，说明**动机、改了什么、如何验证**；UI 改动请附前后截图。
4. 关联相关 Issue（`Closes #123`）。

CI 通过且无 CRITICAL / HIGH 问题后即可合并。

---

## 报告问题

- **Bug**：用「Bug 报告」模板，附复现步骤、期望/实际行为、环境（OS / Python 版本）、相关日志（**请先脱敏，勿粘贴真实案件信息或 API Key**）。
- **新功能**：用「功能建议」模板，说明使用场景与价值。

> ⚠️ **隐私提醒**：提交 Issue / 日志时务必移除真实当事人信息、案号、文件内容与密钥。

感谢你的贡献！🎉
