# 更新日志

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/) `MAJOR.MINOR.PATCH`。

> 版本号的**单一真源**是 `bilidownloader/__init__.py::__version__`，任何文件禁止写死版本号字面量。
> 打包产物（`dist/`）**不入库**：体积 124MB 且可随时由 `python build.py` 重新生成。

## [未发布]

暂无。

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

[未发布]: https://github.com/OWNER/REPO/compare/v1.1.1...HEAD
[1.1.1]: https://github.com/OWNER/REPO/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/OWNER/REPO/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/OWNER/REPO/releases/tag/v1.0.0
