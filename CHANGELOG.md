# 更新日志

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 风格，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/) `MAJOR.MINOR.PATCH`。

> 版本号的**单一真源**是 `bilidownloader/__init__.py::__version__`，任何文件禁止写死版本号字面量。

## [未发布]

暂无。

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

### 修复

- **BUG-20261016-01 版本号双真源**：`gui.py` 曾独立维护一份版本字面量，与
  `bilidownloader.__version__` 不一致。现统一为单一真源，`verify.py` 增加断言拦截。

## [1.0.0]

初版发布。

### 新增

- 单任务视频下载（粘贴链接解析 → 选画质 → 下载）
- 扫码登录（B 站手机 App 扫码 + 手机确认）
- 亮色 / 暗色主题切换

[未发布]: https://github.com/OWNER/REPO/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/OWNER/REPO/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/OWNER/REPO/releases/tag/v1.0.0
