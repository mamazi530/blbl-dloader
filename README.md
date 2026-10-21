# BilibiliDownloader

**BilibiliDownloader** — 一个 B 站（bilibili）视频下载器桌面应用。直连 B 站 DASH 分轨原始流，画面**无水印、不经第三方中转**；登录大会员账号后可解锁 4K 与高码率画质。

A desktop downloader for bilibili.com. It pulls the **original DASH streams** straight from Bilibili's servers — no watermark, no third-party relay. Sign in with your account to unlock 4K and high-bitrate formats.

- 用户使用手册（中文）：[`使用说明.md`](使用说明.md)
- 工程实现与踩坑（中文）：[`开发者指南.md`](开发者指南.md)
- 团队协作规范总入口（中文）：[`docs/README.md`](docs/README.md)
- 贡献代码前请读：[`CONTRIBUTING.md`](CONTRIBUTING.md) · 版本历史：[`CHANGELOG.md`](CHANGELOG.md)

---

## Features / 特性

**解析**

- 粘贴链接自动解析：标题、UP 主、时长、BV 号、封面，多 P 视频自动展开分 P 列表

**下载队列**

- 多任务下载队列：并发调度（1–5 可配），其余任务排队显示「等待中」
- 五状态任务行：下载中 / 已暂停 / 等待中 / 失败 / 已完成
- **暂停即断点续传**，已下载部分不浪费；失败可一键重试
- 分 P 批量勾选后一次性入队

**画质与输出**

- 画质预设：最高可用 / 4K（大会员）/ 1080P 高码率 / 720P / 480P / 360P / 仅音频
- 字幕与封面嵌入
- XML 弹幕下载（与视频同名 `.xml` 相伴保存）

**账号**

- 扫码登录（B 站手机 App 扫码 + 手机确认），解锁 1080P 高码率 / 4K
- 也支持导入 `cookies.txt`；凭证仅存本机 `data/cookies.txt`

**外观**

- 三态主题：**亮色 / 暗色 / 跟随系统**，选择持久化到 `data/settings.json`
- **自定义皮肤背景**：内置渐变预设 + 本地图片导入 + 直接拖拽图片到窗口，可调**透明度**与**模糊**强度

**网络**

- 单任务限速
- 网络代理支持

---

## Quick Start / 快速开始

### 方式一：直接运行打包产物（推荐，无需 Python）

从仓库的 **Releases** 页面下载对应平台的产物：

| 平台      | 产物                       | 怎么用                                                 |
| ------- | ------------------------ | --------------------------------------------------- |
| Windows | `BilibiliDownloader.exe` | 单文件，双击即可运行（无需安装）                                    |
| macOS   | `BilibiliDownloader.dmg` | 打开 dmg，把 `BilibiliDownloader.app` 拖入 `Applications` |

> 注意：`bin/` 目录（内含 yt-dlp、ffmpeg 与 ffprobe）必须与可执行文件平级存在，缺了会提示「未找到 yt-dlp」。

### 方式二：从源码运行

需要 **Python 3.13**。

```bash
# 1) 创建并激活虚拟环境
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 2) 安装 Python 依赖
pip install -r requirements.txt

# 3) 准备 bin/ 下的 yt-dlp、ffmpeg 与 ffprobe（约 218MB，不入库）
python download_deps.py

# 4) 启动
python run.py
```

开发者自检（提 PR 前必跑，见 `CONTRIBUTING.md`）：

```bash
python verify.py        # 54 项检查，必须全绿、退出码 0
python screenshot.py    # 四个页面自动截图，产出到 data/screenshots/
```

---

## Platform Support / 平台支持

| 平台      | 版本要求                          | 说明           |
| ------- | ----------------------------- | ------------ |
| Windows | 10 / 11 x64                   | 单文件 exe，双击运行 |
| macOS   | 11+（Intel 与 Apple Silicon 均可） | 提供 `.dmg`    |

### macOS 首次启动

应用**未做代码签名**，Gatekeeper 会拦截。任选一种方式放行：

1. 在访达中右键「打开」，或在「系统设置 → 隐私与安全性」中点击**仍要打开**；
2. 或解除隔离属性：

```bash
xattr -cr /Applications/BilibiliDownloader.app
```

---

## Screenshots / 截图

截图**不随仓库提交**（`data/` 已在 `.gitignore` 中）。本地生成：

```bash
python screenshot.py
```

默认输出到 `data/screenshots/`，共 12 张——四个页面（主界面 / 视频详情 / 设置 / 登录）× 两种主题（亮色 / 暗色），命名形如 `light-home.png`、`dark-settings.png`。

想预览界面长什么样，先跑一次上面的命令再看图。

---

## Project Layout / 目录结构

```
BilibiliDownloader/
├── run.py                  入口（PyInstaller 也用它）
├── verify.py               验收自检（54 项：主题/队列/持久化/静态检查）
├── screenshot.py           四页面自动截图
├── download_deps.py        下载 yt-dlp / ffmpeg / ffprobe 到 bin/
├── requirements.txt        Python 依赖
├── BilibiliDownloader.spec PyInstaller 打包配置
├── README.md               本文件
├── CONTRIBUTING.md         贡献指南
├── CHANGELOG.md            版本历史
├── LICENSE                 MIT
├── 使用说明.md              用户手册（中文）
├── 开发者指南.md            实现细节与踩坑（中文）
├── docs/                   团队协作 / 交付流程 / 质量门禁
└── bilidownloader/
    ├── theme.py            设计令牌 + 三态主题
    ├── gui.py              应用外壳：无边框窗口 / 标题栏 / 侧边栏 / 页面导航
    ├── queue_manager.py    下载队列：五状态、并发调度、断点续传
    ├── app_settings.py     设置持久化（data/settings.json）
    ├── downloader.py       yt-dlp 封装：进度 / 限速 / 代理 / 分P / 弹幕
    ├── login.py            扫码登录 + cookie 解析导出
    ├── qrcode_gen.py       二维码生成
    ├── assets/icons/       设计稿 SVG 图标
    └── views/              四个页面 + 通用部件（home/detail/settings_page/login_page）
```

---

## FAQ / 常见问题

**Q：未登录最高能下什么画质？**  
A：通常到 **1080P**。1080P 高码率及以上需要登录，4K 需要大会员账号。最终可用画质还取决于视频源本身。

**Q：4K / 高码率怎么解锁？**  
A：登录页用 B 站手机 App 扫码，并在手机上点「确认登录」。登录成功后重新解析链接即可看到更高画质选项。

**Q：提示「未找到 yt-dlp」怎么办？**  
A：说明 `bin/` 没跟着程序一起走。源码运行时先执行 `python download_deps.py`；用打包产物时确保 `bin/` 与可执行文件平级。

**Q：下载很慢，或者频繁失败？**  
A：B 站对高频请求有限流。把设置里的「同时下载任务数」调到 1–2，或开启单任务限速。

**Q：macOS 上打不开，提示已损坏 / 无法验证开发者？**  
A：应用未签名，属于 Gatekeeper 拦截，按上文「macOS 首次启动」放行即可（`xattr -cr /Applications/BilibiliDownloader.app`）。

**Q：进度条卡住不动了？**  
A：先看是「等待中」还是「下载中」。等待中说明并发数占满，前面任务完成后会自动补位；下载中长时间无进展，通常是网络或限流，暂停后重试即可（已下部分保留）。

**Q：登录凭证存放在哪？**  
A：`data/cookies.txt`，仅保存在本机。它等同于你的 B 站登录凭证，**不要外传、不要提交到仓库**（已在 `.gitignore` 中）。

**Q：能批量下载整个合集 / UP 主全部视频吗？**  
A：不支持，也不建议。跨视频脚本化批量会触发 B 站风控，可能导致账号受限。多 P 视频可在详情页批量勾选。

---

## Disclaimer / 免责声明

> **本项目仅供学习与技术交流使用。**

- 通过本工具下载的内容，其**著作权归原作者及版权方所有**，本项目不对任何下载内容主张权利。
- 请遵守 **bilibili 用户协议** 与你所在国家/地区的法律法规。
- **不得**将下载内容用于商业传播、二次发布或任何侵犯他人合法权益的用途。
- 因使用者滥用本工具而引发的任何法律责任与纠纷，**由使用者自行承担**，本项目开发者与贡献者不承担任何责任。
- 建议仅用于个人学习、研究与备份自己上传的内容，**并在下载后 24 小时内删除**。
- 本项目不是 bilibili 官方产品，与 bilibili 无任何 affiliation、授权或合作关系。

---

## License

Released under the **MIT License**. See [`LICENSE`](LICENSE) for the full text.
