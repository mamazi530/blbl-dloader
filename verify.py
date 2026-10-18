"""验收测试：主题令牌 + 版本号 + 队列调度 + 设置持久化
+ 静态引用检查 + 分层依赖 + 二维码锐利度"""

import ast
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from bilidownloader import theme
from bilidownloader.downloader import Downloader, parse_size, human_speed, parse_speed
from bilidownloader.queue_manager import QueueManager, Task, TaskState
from bilidownloader.app_settings import AppSettings, CONFIG_FILE

fail = []

# BUG-008：自检会改真实 data/settings.json（曾经把用户的 download_dir 写成
# D:/tmp/test、theme 写成 light，污染分发包）。这里先快照、退出时还原，
# 保证「跑自检」不会改动用户配置（atexit 对 sys.exit(1) 同样生效）。
import atexit

_orig_settings_bytes = CONFIG_FILE.read_bytes() if CONFIG_FILE.exists() else None


def _restore_settings():
    try:
        if _orig_settings_bytes is None:
            CONFIG_FILE.unlink(missing_ok=True)
        else:
            CONFIG_FILE.write_bytes(_orig_settings_bytes)
    except OSError:
        pass


atexit.register(_restore_settings)


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not cond:
        fail.append(name)


app = QApplication(sys.argv)
app.setStyle("Fusion")


class FakeDownloader:
    """假下载引擎：模拟 2 秒下载，验证调度逻辑"""

    def __init__(self):
        self.active = 0
        self.max_active = 0
        self.build_download_cmd = lambda *a, **k: ["fake"]

    def download(self, task_url, out, quality, cookie, want_subtitle=True,
                 want_thumbnail=True, on_log=None, on_progress=None,
                 cancel_flag=None, rate_limit="", proxy=None, auto_merge=True,
                 cmd=None):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        for i in range(20):
            if cancel_flag and cancel_flag():
                self.active -= 1
                return -2
            if on_progress:
                on_progress({"percent": i * 5.0, "speed": "1.0MB/s",
                             "speed_bps": 1048576.0, "eta": "0:01"})
            time.sleep(0.05)
        self.active -= 1
        return 0


print("\n1. 工具函数")
check("parse_size", parse_size("128.4 MB") == 128.4 * 1048576)
check("parse_speed", parse_speed("2.4MB/s") == 2.4 * 1048576)
check("human_speed", "MB/s" in human_speed(2.4 * 1048576))

print("\n2. 主题令牌")
for pal in (theme.LIGHT, theme.DARK):
    check(f"{pal.name} 主色", pal.accent == "#FB7299")
    check(f"{pal.name} 侧边栏/软色存在",
          bool(pal.bg_sidebar and pal.accent_soft and pal.success_soft
               and pal.danger_soft and pal.text_icon))
check("主题解析-暗", theme.resolve("dark", False).is_dark)
check("主题解析-亮", not theme.resolve("light", True).is_dark)
check("主题解析-跟随", theme.resolve("auto", False) is theme.LIGHT)
check("样式表非空", len(theme.stylesheet(theme.LIGHT)) > 3000)
check("样式表无占位符", "{p." not in theme.stylesheet(theme.LIGHT))

print("\n2.1 版本号（单一真源 + 语义化格式）")
import bilidownloader
from bilidownloader import gui as gui_mod

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
pkg_ver = bilidownloader.__version__
gui_ver = getattr(gui_mod, "APP_VERSION", None)
check("版本号单一真源", pkg_ver == gui_ver,
      f"__version__={pkg_ver!r} APP_VERSION={gui_ver!r}")
check("版本号格式 MAJOR.MINOR.PATCH", bool(VERSION_RE.match(str(pkg_ver or ""))),
      str(pkg_ver))

print("\n3. 队列调度（并发上限 / 暂停 / 继续 / 重试 / 清空）")
fake = FakeDownloader()
settings = AppSettings()
settings.set("max_concurrent", 2)
mgr = QueueManager(fake, settings)
mgr.tasks = []
tasks = [Task(f"https://www.bilibili.com/video/BV{i:012d}", "out") for i in range(5)]
for t in tasks:
    mgr.add_task(t)
time.sleep(0.3)
check("并发上限=2", mgr.running_count() == 2, f"running={mgr.running_count()}")
check("其余等待", sum(1 for t in mgr.tasks if t.state == TaskState.WAITING) == 3)
check("假引擎活跃数=2", fake.active == 2)

mgr.pause(tasks[0].id)
deadline = time.time() + 3
while time.time() < deadline and tasks[0].state != TaskState.PAUSED:
    app.processEvents(); time.sleep(0.05)
check("暂停后状态", tasks[0].state == TaskState.PAUSED)
deadline = time.time() + 3
while time.time() < deadline and mgr.running_count() < 2:
    app.processEvents(); time.sleep(0.05)
check("暂停后补位", mgr.running_count() == 2)

mgr.resume(tasks[0].id)
app.processEvents()
check("继续后回队列", tasks[0].state in (TaskState.WAITING, TaskState.RUNNING))

# 等全部完成（5 个 × ~1s，最多等 12s）
deadline = time.time() + 12
while time.time() < deadline and not all(
        t.state == TaskState.DONE for t in mgr.tasks):
    app.processEvents(); time.sleep(0.05)
check("全部完成", all(t.state == TaskState.DONE for t in mgr.tasks),
      str([t.state.value for t in mgr.tasks]))
check("并发从未超限", fake.max_active <= 2, f"max={fake.max_active}")

mgr.add_task(Task("https://www.bilibili.com/video/BV000000000000", "out"))
deadline = time.time() + 5
while time.time() < deadline and mgr.running_count() < 1:
    app.processEvents(); time.sleep(0.05)
# 等这个任务跑完再进入窗口构建，避免线程存活时销毁
mgr.pause_all()
deadline = time.time() + 5
while time.time() < deadline and mgr.running_count() > 0:
    app.processEvents(); time.sleep(0.05)
mgr.clear_done()
check("清空已完成", all(t.state != TaskState.DONE for t in mgr.tasks))

print("\n4. 设置持久化")
settings.set("max_concurrent", 4)
settings.set("download_dir", "D:/tmp/test")
s2 = AppSettings()
check("重新读取生效", s2.get("max_concurrent") == 4 and s2.get("download_dir") == "D:/tmp/test")
settings.set("max_concurrent", 3)

print("\n5. 下载引擎（本机组件）")
dl = Downloader()
check("yt-dlp 可用", dl.available(), str(dl.ytdlp))
cmd = dl.build_download_cmd("https://www.bilibili.com/video/BV1xx411c7mD",
                            Path("out"), "720P", None, rate_limit="1M")
check("命令含画质", "b[height<=720]" in " ".join(cmd) or "height<=720" in " ".join(cmd))
check("命令含限速", "--limit-rate" in cmd)
check("命令含输出模板", "%(title)s [%(id)s].%(ext)s" in " ".join(cmd))

print("\n6. 静态检查：gui/views 的 self.xxx 是否有未定义方法")
qt_builtin = {
    "exec", "setStyleSheet", "setStyle", "setPixmap", "setIcon", "setIconSize",
    "setItem", "setAlignment", "setWordWrap", "setReadOnly", "setFont",
    "setToolTip", "setCursor", "setSizePolicy", "update", "grab", "addWidget",
    "addStretch", "addLayout", "addAction", "setContentsMargins", "setSpacing",
    "setFixedSize", "setFixedWidth", "setFixedHeight", "setMinimumWidth",
    "setMinimumHeight", "setMinimumSize", "setMaximumWidth", "resize",
    "setWindowTitle", "setCentralWidget", "setFrameShape", "setEnabled",
    "setVisible", "setText", "setValue", "setRange", "setPlaceholderText",
    "setCurrentText", "setCurrentIndex", "setObjectName", "setProperty",
    "setChecked", "menuBar", "triggered", "connect", "start", "stop", "wait",
    "is_set", "isRunning", "isVisible", "isChecked", "isMaximized",
    "showNormal", "showMaximized", "showMinimized", "move", "text", "size",
    "currentText", "toPlainText", "close", "open", "show", "window", "style",
    "polish", "unpolish", "setWindowFlags", "setWindowIcon", "frameGeometry",
    "topLeft", "globalPosition", "toPoint", "position", "buttons", "button",
    "deleteLater", "clear", "insertWidget", "insertWidget0", "removeWidget",
    "count", "itemAt", "takeAt", "mapToGlobal", "rect", "bottomLeft",
    "setMinimumHeight0", "reject", "accept", "width", "height", "width0",
    "setClipRect", "save", "restore", "drawPath", "drawRoundedRect",
    "addRoundedRect", "adjusted", "setSelected", "setFixedSize0", "pixmap",
    "setGeometry", "geometry", "setCheckable", "underMouse", "setEnabled0",
    "installEventFilter", "boundedTo", "screen", "showMessage", "singleShot",
    "quit", "processEvents", "takeAt0", "drawEllipse", "drawLine", "drawText",
    # 换肤相关（Backdrop 背景层 / 拖放）
    "setAcceptDrops", "setAttribute", "fillRect", "setClipPath", "drawPixmap0",
    "drawPixmap", "setPen", "setBrush", "setRenderHint", "end", "fill",
    "loadFromData", "scaled", "isNull", "pixelColor", "widget", "terminate",
    "kill", "retheme", "refresh", "restyle", "restyle_row", "set", "value",
    "select", "addTask", "pause", "resume", "retry", "remove", "clear_done",
    "pause_all", "start_all", "running_count", "total_speed_bps", "counts",
    "logs", "tasks", "cookie_file", "logged_in", "proxy_url", "get", "set0",
    "save", "load", "theme_mode", "logout", "username", "available", "succeeded",
    "badge_text", "settings", "manager", "dl", "login", "shell", "navigate",
    "queue_holder", "queue_inner", "queue_lay", "detail_footer", "stage",
    "findChildren", "font", "isEnabled", "minimumHeight", "minimumWidth",
    "setMouseTracking", "windowIcon", "hide", "setLayout", "setParent",
    "toggle", "setChecked0", "setChecked1",
}
missing_all = {}
for f in ("bilidownloader/gui.py", "bilidownloader/views/home.py",
          "bilidownloader/views/detail.py", "bilidownloader/views/settings_page.py",
          "bilidownloader/views/login_page.py", "bilidownloader/queue_manager.py"):
    tree = ast.parse(Path(f).read_text(encoding="utf-8"))
    methods = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    called = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if isinstance(n.func.value, ast.Name) and n.func.value.id == "self":
                called.add(n.func.attr)
    missing = called - methods - qt_builtin
    if missing:
        missing_all[f] = sorted(missing)
check("无未定义 self 调用", not missing_all, str(missing_all))

print("\n6.2 静态检查：views 分层依赖（禁 subprocess / 禁 yt-dlp 直调 / 禁跨页面导入）")
ROOT = Path(__file__).parent
VIEWS_DIR = ROOT / "bilidownloader" / "views"
VIEW_PAGES = {"home", "detail", "settings_page", "login_page"}
YTDLP_TOKENS = ("yt-dlp", "yt_dlp", "YoutubeDL")

cross_imports = {}
subprocess_files = []
ytdlp_files = []
for vf in sorted(VIEWS_DIR.glob("*.py")):
    src = vf.read_text(encoding="utf-8")
    own = vf.stem
    # 跨页面导入：from .home / from bilidownloader.views.home 等（同页自引用除外）
    bad = []
    for node in ast.walk(ast.parse(src)):
        mod = None
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.level == 1:
                mod = node.module.split(".")[0]
            else:
                seg = node.module.split(".")
                if len(seg) > 2 and seg[0] == "bilidownloader" and seg[1] == "views":
                    mod = seg[2]
        if mod in VIEW_PAGES and mod != own:
            bad.append(mod)
    if bad:
        cross_imports[vf.name] = sorted(set(bad))
    if "subprocess" in src:
        subprocess_files.append(vf.name)
    if any(tok in src for tok in YTDLP_TOKENS):
        ytdlp_files.append(vf.name)

check("views 无 subprocess", not subprocess_files, str(subprocess_files))
check("views 无 yt-dlp 直接调用", not ytdlp_files, str(ytdlp_files))
check("views 无跨页面导入", not cross_imports, str(cross_imports))

print("\n7. 窗口构建（真实 MainWindow）")
from bilidownloader.gui import MainWindow
win = MainWindow()
win.show()
app.processEvents()
check("窗口尺寸 1280×840", win.width() == 1280 and win.height() == 840,
      f"{win.width()}x{win.height()}")
check("四个页面就位", win.stack.count() == 4)
win.navigate("detail")
check("详情页导航", win.stack.currentIndex() == 1)
win.navigate("settings")
check("设置页导航", win.stack.currentIndex() == 2)
win.set_theme_mode(theme.THEME_DARK)
check("暗色切换", win.p.is_dark)
win.set_theme_mode(theme.THEME_LIGHT)
check("亮色切换", not win.p.is_dark)
print("\n7.1 换肤（皮肤系统 + 背景层 + 半透明派生）")
from bilidownloader import skin as skin_mod
from bilidownloader.gui import Backdrop

# 半透明派生：表面变 rgba，文字/品牌色保持
pa = theme.LIGHT.with_alpha(0.85)
check("皮肤半透明-背景", pa.bg.startswith("rgba(") and pa.surface.startswith("rgba("))
check("皮肤半透明-文字不变", pa.text == theme.LIGHT.text and pa.accent == theme.LIGHT.accent)
check("皮肤半透明-alpha=1 返回自身", theme.LIGHT.with_alpha(1.0) is theme.LIGHT)

# 预设与皮肤注册表
presets = skin_mod.preset_skins()
check("皮肤预设数量>=6", len(presets) >= 6, f"n={len(presets)}")
check("皮肤按 id 可查", skin_mod.get("pink") is not None and skin_mod.get("night") is not None)
check("皮肤默认无皮肤", skin_mod.get("") is None)

# 缩略图（圆角、尺寸）
thumb = skin_mod.thumbnail(presets[0], 96, 54)
check("皮肤缩略图尺寸", thumb.width() == 96 and thumb.height() == 54)

# 自定义皮肤导入/移除（用程序生成的临时图片）
from PySide6.QtGui import QPainter, QPixmap, QColor
tmp_img = Path("data/_verify_skin.png")
tmp_img.parent.mkdir(parents=True, exist_ok=True)
pm_src = QPixmap(120, 80)
pp = QPainter(pm_src)
pp.fillRect(0, 0, 120, 80, QColor("#336699"))
pp.end()
pm_src.save(str(tmp_img))
imported = skin_mod.install_image(tmp_img)
check("皮肤导入本地图片", imported is not None and imported.is_custom)
check("皮肤导入后可查", imported and skin_mod.get(imported.id) is not None)
bg_pm = skin_mod.background(imported.id, 200, 120, "cover") if imported else None
check("皮肤背景位图生成", bg_pm is not None and not bg_pm.isNull())
if imported:
    skin_mod.remove(imported.id)
check("皮肤移除", imported and skin_mod.get(imported.id) is None)
tmp_img.unlink(missing_ok=True)

# Backdrop 背景层状态机
bd = Backdrop()
check("背景层初始无皮肤", not bd.has_skin)
bd.configure("pink", 0, 20, "cover", QColor("#ffffff"))
check("背景层应用预设", bd.has_skin)
bd.configure("", 0, 0, "cover", QColor("#ffffff"))
check("背景层恢复无皮肤", not bd.has_skin)

# 真实窗口：应用/恢复皮肤
win.settings.set("skin_id", "pink")
win.apply_skin()
app.processEvents()
check("窗口应用皮肤", win.backdrop.has_skin and str(win.p.bg).startswith("rgba"))
win.settings.set("skin_id", "")
win.apply_skin()
app.processEvents()
check("窗口恢复无皮肤", not win.backdrop.has_skin and not str(win.p.bg).startswith("rgba"))

# ---------------------------------------------------------------- 缺陷回归
print("\n7.2 缺陷回归（BUG-001~BUG-005，防止再次漏网）")
win.show()
app.processEvents()

# BUG-001：TaskRow 曾把 QVBoxLayout 当 widget 传给 addWidget，构造即 TypeError 崩溃
from bilidownloader.views.home import TaskRow
try:
    _probe = Task("https://www.bilibili.com/video/BV1xx411c7mD", "out")
    _probe.set(title="回归用例")
    _row = TaskRow(_probe, None, theme.LIGHT)
    check("BUG-001 任务行可构造", True)
    # BUG-004：进度条底轨曾被创建却未挂载
    check("BUG-004 进度条底轨已挂载",
          _row.bar is _row.bar_track and _row.bar_track.layout() is not None
          and _row.bar_track.layout().indexOf(_row.bar_fill) >= 0)
except Exception as _exc:
    check("BUG-001 任务行可构造", False, str(_exc)[:80])
    check("BUG-004 进度条底轨已挂载", False)

# BUG-002：登录页在已登录态必须展示账号卡 + 退出/返回，而不是继续弹二维码
from unittest.mock import PropertyMock, patch
with patch.object(AppSettings, "logged_in", new_callable=PropertyMock) as _m:
    _m.return_value = True
    win.view_login.refresh_state()
    app.processEvents()
    check("BUG-002 已登录隐藏二维码", win.view_login.qr_area.isHidden())
    check("BUG-002 已登录显示账号区", not win.view_login.logged_area.isHidden()
          and win.view_login.qr_area.isHidden())
    check("BUG-002 有退出登录按钮", not win.view_login.btn_logout.isHidden())
    check("BUG-002 有返回按钮", not win.view_login.btn_back.isHidden())
    _m.return_value = False
    win.view_login.refresh_state()
    app.processEvents()
    check("BUG-002 未登录回到二维码",
          not win.view_login.qr_area.isHidden() and win.view_login.logged_area.isHidden())

# BUG-003：登录后「4K · 大会员」必须可选，未登录时禁用
_4k = win.view_detail.chips_quality._buttons["4K · 大会员"]
win.view_detail.sync_login_state(True)
check("BUG-003 登录后 4K 可选", _4k.isEnabled())
win.view_detail.sync_login_state(False)
check("BUG-003 未登录 4K 禁用", not _4k.isEnabled())

# BUG-005：用户名必须持久化，重启后仍在
_s = AppSettings()
_s.username = "回归测试用户"
check("BUG-005 用户名写入", _s.get("username") == "回归测试用户")
check("BUG-005 用户名重载保留", AppSettings().username == "回归测试用户")
_s.username = ""

# ---------------------------------------------------------- 崩溃回归（第二轮）
print("\n7.3 崩溃回归（BUG-006 重入 / BUG-007 封面线程安全）")
import inspect
import types as _types
from PySide6.QtCore import QBuffer, QIODevice, QThread
from PySide6.QtGui import QImage

# BUG-006：解析入口必须防重入，且不能再用「wait(100) 然后覆盖引用」的老写法
_p_src = inspect.getsource(win.view_home.parse_url)
check("BUG-006 parse_url 防重入", "isRunning()" in _p_src and "wait(100)" not in _p_src)
_d_src = inspect.getsource(win.view_detail.load)
check("BUG-006 detail.load 防重入", "isRunning()" in _d_src)

# BUG-007：封面任务不得在非 GUI 线程创建 QPixmap，且不能被线程池静默析构
from bilidownloader.views import widgets as _wg
check("BUG-007 worker 不碰 QPixmap", "QPixmap" not in inspect.getsource(_wg._CoverJob.run))
_job_probe = _wg._CoverJob("http://x/y.png", "probe")
check("BUG-007 封面任务关闭自动析构", _job_probe.autoDelete() is False)

# 运行时验证：注入假 requests，断言回调在 GUI 线程拿到 QPixmap
_img = QImage(64, 36, QImage.Format_RGB32)
_img.fill(0xFF884422)
_buf = QBuffer()
_buf.open(QIODevice.WriteOnly)
_img.save(_buf, "PNG")
_raw_png = bytes(_buf.data())


class _FakeResp:
    content = _raw_png


class _FakeRequests(_types.ModuleType):
    def get(self, *a, **k):
        return _FakeResp()


_orig_requests = sys.modules.get("requests")
sys.modules["requests"] = _FakeRequests("requests")
_got = []
try:
    _main_thread = app.thread()
    _wg.fetch_cover_async(
        "http://fake/cover.png", "verify",
        lambda k, pm: _got.append((k, pm, QThread.currentThread() == _main_thread)))
    _t0 = time.time()
    while time.time() - _t0 < 5 and not _got:
        app.processEvents()
        time.sleep(0.02)
finally:
    if _orig_requests is not None:
        sys.modules["requests"] = _orig_requests
    else:
        sys.modules.pop("requests", None)

check("BUG-007 回调拿到 QPixmap", bool(_got) and isinstance(_got[0][1], QPixmap)
      and _got[0][1].width() == 64)
check("BUG-007 回调在 GUI 线程", bool(_got) and bool(_got[0][2]))
check("BUG-007 任务引用已释放", len(_wg._live_cover_jobs) == 0)

win.view_login.stop_worker()
win.close()
print("\n" + "=" * 46)
if fail:
    print(f"失败 {len(fail)} 项: {fail}")
    sys.exit(1)
print("全部通过")
