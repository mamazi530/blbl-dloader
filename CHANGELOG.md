# 更新日志

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/) `MAJOR.MINOR.PATCH`。

> 版本号的**单一真源**是 `bilidownloader/__init__.py::__version__`，任何文件禁止写死版本号字面量。
> 打包产物（`dist/`）**不入库**：体积 124MB 且可随时由 `python build.py` 重新生成。

## [未发布]

暂无。

## [1.1.2] - 2026-10-17

依据第三方全盘测试（`QA-BilibiliDownloader/QA-测试报告.md`，Horizon）修复全部 5 个缺陷。
测试结论原为「质量门禁不通过、禁止发版」（P0×1 + P1×1，自动化针对性通过率 22%）。

### 修复

- **BUG-001（P0 · 致命）添加下载任务即崩溃**
  `TaskRow.__init__` 把 `QVBoxLayout` 当 widget 传给 `lay.addWidget()`（`:110`、`:125`），
  抛 `TypeError`，「解析 → 加入队列」核心链路完全不可用。改用 `lay.addLayout()`。
  修复过程中另发现同类隐患：`TaskRow._paint_placeholder` 使用了未导入的 `QColor`（同样会崩溃），已补导入。

- **BUG-002（P1 · 严重）登录页无"已登录"状态、无退出/返回按钮**
  `LoginView.__init__` 无条件生成二维码、`refresh_state()` 是空实现 `pass`。
  现重构为**单卡片两态**：已登录显示账号名 + 「退出登录」「返回」按钮，
  未登录显示二维码；`navigate("login")` 时按登录态切换；退出后自动回到二维码态。

- **BUG-003（P2）详情页「4K · 大会员」登录后仍禁用**
  `OptionChips` 新增 `set_item_enabled()` 支持动态启用/禁用单个选项；
  登录态变化时同步刷新（`DetailView.sync_login_state`），选中项被禁用时自动回退到可用项。

- **BUG-004（P3）任务行进度条无背景轨道**
  `bar_track` 创建后从未加入布局。重构为 track 容器 + fill 内嵌，填充宽度按轨道实际宽度计算。

- **BUG-005（P4）登录用户名不持久化**
  `DEFAULTS` 增加 `username`，`AppSettings.username` 改为可读写属性（自动落盘），
  登录成功即保存、退出登录即清空，重启后账号卡仍显示用户名。

### 验证

- `verify.py` **65 项**全绿（新增 §7.2 缺陷回归 11 项，BUG-001~005 逐条断言，防止再次漏网）
- 第三方复现脚本 `repro_test.py` **9/9 通过**（修复前 2/9）
- 截图核对：任务行渲染正常（缩略图/底轨/徽标/操作列）、登录页已登录态展示正确
- `screenshot.py` 12 张全量重拍通过

## [1.1.1] - 2026-10-17

本次为**打包可用性修复**：v1.1.0 的代码能正常跑，但打成 Windows 单文件 exe 后 download 功能会失效。

### 修复

- **BUG-20261017-01 · 打包版找不到 yt-dlp / ffmpeg（P0）**
  Windows onefile 打包时，`bin/` 会被解压到临时目录 `sys._MEIPASS`，**不在 exe 同级**；
  而 `downloader._app_bin_dir()` 原先只查 exe 同级目录，导致打包版一进下载就报"未找到 yt-dlp"。
  现改为依次查找 `sys._MEIPASS/bin` → exe 同级 `bin` → macOS `.app/Contents/Resources/bin`。

- **BUG-20261017-02 · PyInstaller 构建直接崩溃（P0）**
  `BilibiliDownloader.spec` 中用 `__file__` 定位版本号，但 spec 是被 PyInstaller `exec` 执行的，
  其命名空间**不含 `__file__`**，PyInstaller 6.x 必报 `NameError: name '__file__' is not defined`。
  现改用 PyInstaller 内置变量 `SPECPATH` 读取 `bilidownloader/__init__.py`。

- **文档泄露本机绝对路径**
  `docs/03-质量门禁与验收清单.md` 与 `docs/README.md` 中写有真实用户名与工作区绝对路径，
  公开后会暴露环境信息。已替换为 `<你的用户名>` / `<项目目录>` 占位，并重建提交历史彻底清除。

### 加固

- `.gitignore` 新增「私钥 / 证书 / 环境变量」整段兜底规则：`id_rsa*`、`id_ed25519*`、`*.pem`、
  `*.key`、`*.p12`、`*.pfx`、`*.ppk`、`*.keystore`、`.env`、`secrets.json` 等，防止误提交密钥。
- `docs/04-打包与发布.md` 常见问题表补记上述两个打包坑（含根因与修法）。

### 验证

- Windows 单文件 exe 构建成功：**`dist/BilibiliDownloader.exe`，124.2 MB**，构建耗时约 80 秒。
- 解包核对：包内含 `bin\yt-dlp.exe`、`bin\ffmpeg.exe`、21 个 SVG 图标、120 个 Qt 插件；
  **不含** `cookies.txt` / `settings.json`（凭证红线校验通过）。
- 启动冒烟：运行 30 秒进程存活、自动创建数据目录，窗口正常显示未崩溃。
- `verify.py` **54 项**验收全绿，退出码 0。

## [1.1.0] - 2026-10-16

当前基线版本。

### 新增

- **1280×840 多页面 UI**：左侧导航 + 右侧四个页面（主界面 / 视频详情 / 设置 / 登录）
- **下载队列**：任务五状态（下载中 / 已暂停 / 等待中 / 失败 / 已完成）与并发调度
- **暂停即断点续传**：已下载部分保留，继续时不重新开始
- **分 P 批量选择**：视频详情页逐条勾选，支持全选后一次入队
- **设置持久化**：下载目录、并发数、画质、限速、代理等写入 `data/settings.json`
- **主题令牌对齐设计稿**：亮 / 暗 / 跟随系统三态，全部颜色走 `theme.py` 令牌
- **自定义皮肤背景**：内置渐变预设 + 本地图片导入 + 拖拽图片，可调透明度与模糊强度
- **macOS 平台支持**与双平台打包产物（Windows `.exe` / macOS `.dmg`）
- **开源仓库基建**：`README.md`、`LICENSE`(MIT)、`CONTRIBUTING.md`、`.gitattributes`、
  `.editorconfig`、PR / Issue 模板、GitHub Actions 矩阵构建

### 修复

- **BUG-20261016-01 版本号双真源**：`gui.py` 曾独立维护一份版本字面量，与
  `bilidownloader.__version__` 不一致。现统一为单一真源，`verify.py` 增加断言拦截。

## [1.0.0]

初版发布。

### 新增

- 单任务视频下载（粘贴链接解析 → 选画质 → 下载）
- 扫码登录（B 站手机 App 扫码 + 手机确认）
- 亮色 / 暗色主题切换

[未发布]: https://github.com/OWNER/REPO/compare/v1.1.2...HEAD
[1.1.2]: https://github.com/OWNER/REPO/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/OWNER/REPO/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/OWNER/REPO/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/OWNER/REPO/releases/tag/v1.0.0
