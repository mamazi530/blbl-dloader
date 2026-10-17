# 贡献指南

感谢你愿意为本项目出一份力。动手之前请先读完本文，能省掉大量返工。

---

## 一、开发前必读

这三份文档回答的问题各不相同，按顺序读：

| 文档 | 回答什么 |
|---|---|
| [`开发者指南.md`](开发者指南.md) | **实现细节与 12 条踩过的坑**（改代码前必读，很多坑只有踩过才知道） |
| [`docs/README.md`](docs/README.md) | **团队协作规范的唯一入口**（三份规范的总索引 + 五分钟速查卡） |
| [`docs/01-团队协作规范.md`](docs/01-团队协作规范.md) | 模块边界与禁止依赖、分支策略、提交与版本规范、编码/Qt 风格 |

> 冲突时以 `docs/` 下的规范为准，并回改 `开发者指南.md`。

---

## 二、环境准备

需要 **Python 3.13**：

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS:    source .venv/bin/activate

pip install -r requirements.txt
python download_deps.py     # 准备 bin/ 下的 yt-dlp 与 ffmpeg（约 87MB，不入库）
python run.py               # 启动
```

跑不起来先看 `开发者指南.md`「为什么用 PySide6 而不是 tkinter」一节——本项目的 Python 发行版未编译 Tcl/Tk。

---

## 三、分支策略

| 分支 | 用途 | 从哪里拉 |
|---|---|---|
| `main` | 可发布状态 | — |
| `develop` | 集成分支 | `main` |
| `feature/<短名>` | 新功能 | `develop` |
| `hotfix/<短名>` | 紧急修复 | `main`，修完**双合**回 `main` 和 `develop` |

例：`feature/skin-background`、`hotfix/version-single-source`。

---

## 四、提交信息

使用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/v1.0.0/)：
`feat:` `fix:` `docs:` `refactor:` `test:` `chore:` `perf:`，可带 scope。

```
feat(queue): 支持暂停后断点续传
fix(login): 改为读取内层 data.code 判定登录状态
docs: 补充 README 的 macOS 放行说明
```

---

## 五、提 PR 前必跑

```bash
python verify.py        # 54 项检查，必须全绿、退出码 0
```

只要**改了界面**，再加跑：

```bash
python screenshot.py    # 产出 data/screenshots/ 共 12 张，用于与设计稿核对
```

改了哪些文件要重跑哪些测试，映射表见 `docs/03-质量门禁与验收清单.md` §2.3。

---

## 六、禁止提交清单

提交前务必确认以下内容**不在**变更里：

| 路径 | 原因 |
|---|---|
| `data/` | 用户数据目录，**含 `cookies.txt` 登录凭证**，泄露等同账号被盗 |
| `bin/` | yt-dlp / ffmpeg 二进制，体积大，用 `download_deps.py` 获取 |
| `dist/`、`build/` | 打包产物 |
| `*.spec.bak` | PyInstaller 备份文件 |
| `__pycache__/` | Python 缓存 |

以上均已在 `.gitignore` 中，但仍请提交前扫一眼 `git status`。**误提交了 `data/cookies.txt` 请立刻改密码并在 PR 中说明。**

---

## 七、代码风格要点

- **颜色一律走 `theme.py` 令牌**，禁止在业务代码里硬编码颜色值：

  ```python
  label.setStyleSheet(f"color:{self.p.text_dim}; font-size:12px;")
  ```

- **自定义 `QFrame` 必须用 `#ObjectName` 限定选择器**。`QLabel` 继承自 `QFrame`，写裸的 `QFrame { border: ... }` 会泄漏到所有标签，每个标签都长出方框；同时要补 `QFrame#Xxx QLabel { background:transparent; border:none; }` 清除泄漏。
- **views 层不得直接调用 yt-dlp 或 `subprocess`**。无边框窗口在主线程阻塞会直接冻结且无提示，下载逻辑统一走 `downloader.py` / `queue_manager.py`。
- **views 层禁止跨页面互相 import**（`home` 不能 import `detail`）。
- **后台线程异常必须兜底**。`QThread` 里抛出未捕获异常不会弹窗，表现为「点了没反应」。
- **退出时 `closeEvent` 必须调 `manager.shutdown()`**。运行中销毁 `QThread` 会直接崩进程，且没有 traceback。

---

## 八、Issue 模板建议

**Bug 报告**请至少包含：

```
系统版本：      Windows 11 23H2 / macOS 14.5 ...
应用版本：      v1.1.0（标题栏品牌区可见）
复现步骤：      1. ... 2. ... 3. ...
期望结果：      ...
实际结果：      ...
日志 / 截图：   粘贴 verify.py 输出或界面截图
```

**功能建议**请说明使用场景与期望行为，便于判断是否需要进需求评审。
