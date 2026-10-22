# 更新日志

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/) `MAJOR.MINOR.PATCH`。

> 版本号的**单一真源**是 `bilidownloader/__init__.py::__version__`，任何文件禁止写死版本号字面量。
> 打包产物（`dist/`）**不入库**：体积 261MB 且可随时由 `python build.py` 重新生成。

## [未发布]

### 修复

- **BUG-010 画质选项不一致与映射错误**
  详情页少了 480P / 仅音频、多了实际不可用的 360P；`QUALITY_MAP["360P"]` 误映射到
  `height<=480`，选 360P 会下到 480P；「4K · 大会员」没有显式映射。现已统一为
  最高画质 / 4K · 大会员 / 1080P 高码率 / 720P / 480P / 360P / 仅音频，并修正映射。
- **BUG-011 设置页「默认画质」不生效**
  `default_quality` 只存不读，主界面下拉硬编码。现主界面启动时按该设置选中。
- **BUG-012 字幕「简体中文」与「中英双语」结果相同**
  两个选项都固定下发 `--sub-langs zh.*,en.*`。现分别传 `zh.*` 与 `zh.*,en.*`。
- **BUG-013 侧边栏「已完成」是死按钮**
  点击只回到下载页、选中态恒为 False。现点击回到主界面并只显示已完成任务，
  「下载中」恢复显示全部。
- **BUG-014 弹幕文件名与文档不符**
  原为 `{标题}_P{n} 弹幕.xml`，不含 BV 号且与成片不同名。现改为与成片同 stem 的
  `.xml`（README 所述「与视频同名」）。
- **BUG-015 皮肤遮罩调低后文字对比度不足**
  遮罩强度下限由 0 提到 12%，并在渲染层兜底（历史配置为 0 时同样按 12% 绘制）。
- **BUG-016 `qr_dialog.py` 引用不存在的调色板字段**
  `Palette` 没有 `surface_hi`，该路线一旦启用即抛 AttributeError；改用 `bg_subtle`。
- **BUG-017 代理选「自定义」后没有地址输入**
  设置页新增「代理地址」行，仅在自定义模式显示，写入 `proxy_url` 并即时保存。
- **BUG-018 解析失败只有一行裸文本**
  统一为危险色、加粗、可换行的错误提示；解析中/成功/失败共用同一套状态样式。
- **BUG-019 账号权益文案三处不一致**
  侧边栏、设置页、登录页统一为「1080P 高码率 / 4K（需大会员）与高清弹幕」。
- **BUG-020 解析进行中按钮无反馈、可重复点击**
  解析期间「解析」按钮改为禁用并显示「解析中…」，成功/失败后恢复，避免重复触发。
- **BUG-021 设置页没有保存反馈**
  标题下新增「所有修改即时生效并自动保存」，明确无「保存」按钮的交互预期。
- **BUG-022 选择字幕后无产物却无任何提示**
  B 站多数视频没有 CC 字幕，未登录时也拿不到 AI 字幕，yt-dlp 会静默跳过。
  现在下载完成后用 ffprobe 检查成片字幕流（含同名外挂字幕），缺失时在任务行
  标注「未获取到字幕」，并提示登录后可能提供 AI 字幕。

## [1.1.4] - 2026-10-18

### 修复

- **BUG-009（P1 · 严重）视频下载成功，应用却显示「失败」**
  根因：`bin/` 只有 `ffmpeg.exe`、没有 `ffprobe.exe`。命令里带的
  `--embed-thumbnail` 在缺 ffprobe 时无法嵌入封面，yt-dlp 末尾抛
  `ERROR: Postprocessing: Unable to embed using ffprobe & ffmpeg` 并以**退出码 1** 结束；
  而此刻 mp4 早已合并完成 —— 应用只看退出码，于是把成功判成失败。
  修复分三层：
  1. **不强行嵌封面**：检测到无 ffprobe 时只 `--write-thumbnail`（封面存为同名 .jpg），
     有 ffprobe 才加 `--embed-thumbnail`；
  2. **以产物为准**：新增 `resolve_exit_code()`，非 0 退出码但成片已完整落盘
     （≥200KB、非 `.part`、媒体扩展名）时判为成功，并在日志提示「后处理未完成，但视频已保存」；
  3. **记录成片路径**：`Downloader.last_output` 回填到 `Task.filepath` / `size_text`。

### 优化（下载完成后的界面）

- 完成行副标题改为 `画质 · 体积 · 已保存`（成功绿），完整路径放进 tooltip，不再被长文件名挤乱；
- 主按钮变成「▶ 播放视频」，点一下用系统播放器打开成片；双击任务行同样可播放；
- 「更多」菜单新增**播放视频**/**复制文件路径**，路径失效时自动回退到所在文件夹；
- 长标题按行宽自动省略，避免挤掉右侧状态与按钮。

### 修复（工具链）

- **BUG-008（P3）`verify.py` 污染用户真实配置**
  自检脚本直接改真实 `data/settings.json` 做持久化测试，跑完不回滚，
  导致用户的 `download_dir` 被写成 `D:/tmp/test`、主题被改成亮色，
  分发包里也带着测试值。现改为**运行前快照、退出时还原**（`atexit`，
  对 `sys.exit(1)` 同样生效），自检跑完配置字节完全一致。

## [1.1.3] - 2026-10-18

针对「输入链接后应用闪退」的第二轮修复。崩溃为**原生段错误**（`exit 127/139`），
无 Python 回溯，属于典型的 Qt 线程生命周期问题，共两处根因，均已修复并补回归断言。

### 修复

- **BUG-006（P0 · 致命）粘贴链接后解析重入，销毁运行中的 QThread 崩溃**
  `HomeView.parse_url()` 无防重入保护：`textChanged` 会在 700ms 后自动解析，
  回车/点「解析」又会立即解析；第二次进入时旧代码只 `wait(100)`（yt-dlp 抓取需 1~2s），
  随后 `self._parse_worker = ParseWorker(...)` 覆盖引用，运行中的 `QThread` 被析构，
  Qt 直接终止进程（`QThread: Destroyed while thread is still running`）。
  现改为**解析线程在跑时忽略本次请求**；`DetailView.load()` 的分 P 解析有同类隐患，一并加保护；
  登录页 `_start()` / `_refresh()` 同样补了防重入与"线程未退出就不覆盖引用"。

- **BUG-007（P0 · 致命）封面图在非 GUI 线程创建 QPixmap，且信号对象被提前回收**
  两处叠加：①`_CoverJob.run()` 在 `QThreadPool` 工作线程里 `QPixmap.loadFromData()`，
  `QPixmap` 只允许在 GUI 线程使用；②`QRunnable` 被线程池 `autoDelete` 析构后，
  其内部 `Signals` 对象连同 Python 包装一起失效，队列投递落到已释放内存，
  报 `AttributeError: 'function' object has no attribute 'event'` 后崩溃。
  现改为：worker 只下载并解码成 **`QImage`**（可跨线程），由 GUI 线程上的
  `_CoverReceiver` 转成 `QPixmap` 再回调；`QRunnable` 关闭自动析构、
  并在投递完成前用 `_live_cover_jobs` 保住引用，回调结束即释放。
  修复前用假 `requests` 压测 **exit 139（SIGSEGV）**，修复后 12/12 回调、exit 0。

### 测试

- `verify.py` 新增 §7.3「崩溃回归」7 项（重入防护源码断言、worker 不碰 QPixmap、
  自动析构已关闭、回调在主线程拿到 QPixmap、任务引用已释放），总数 65 → **72 项全绿**。
- QA 侧：`regression_test.py` 16/16、`repro_crash.py` 重入复现 exit 0、
  `e2e_verify.py` 真实链接端到端解析+入队正常。

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

[未发布]: https://github.com/OWNER/REPO/compare/v1.1.4...HEAD
[1.1.4]: https://github.com/OWNER/REPO/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/OWNER/REPO/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/OWNER/REPO/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/OWNER/REPO/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/OWNER/REPO/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/OWNER/REPO/releases/tag/v1.0.0
