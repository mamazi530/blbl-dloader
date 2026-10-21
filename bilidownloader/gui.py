"""
B站视频下载器 - 应用外壳
1280×840 无边框窗口：标题栏（52px，macOS 交通灯）+ 侧边栏（220px）
+ 页面栈（主界面 / 视频详情 / 设置 / 登录），对照设计稿实现。
"""

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QSizePolicy, QStackedWidget, QPushButton, QVBoxLayout, QWidget,
)

from . import theme
from . import skin as skin_mod
from . import __version__
from .app_settings import AppSettings
from .downloader import Downloader
from .login import BilibiliLogin
from .queue_manager import QueueManager, TaskState
from .views.home import HomeView
from .views.detail import DetailView
from .views.settings_page import SettingsView
from .views.login_page import LoginView
from .views.widgets import AvatarPixmap, icon, make_logo_pixmap

APP_NAME = "B站下载器"
# 版本号单一真源：bilidownloader.__version__（发布打 tag 时只改 __init__.py）
APP_VERSION = __version__

RESIZE_MARGIN = 6


# ============================================================
# 背景层：绘制自定义皮肤（位于窗口最底，上层面板半透明后可见）
# ============================================================
class Backdrop(QWidget):
    """
    窗口背景层。无皮肤时完全交给样式表（普通纯色主题）；
    有皮肤时绘制壁纸，并按设置做柔化与遮罩。
    位图按当前尺寸缓存，拖动窗口缩放不会重复解码大图。
    """

    def __init__(self):
        super().__init__()
        self._skin_id = ""
        self._blur = 0
        self._dim = 0
        self._fit = "cover"
        self._dim_color = QColor(0, 0, 0)
        self._key = None
        self._buf = None
        self.setAttribute(Qt.WA_StyledBackground, True)

    def configure(self, skin_id: str, blur: int, dim: int, fit: str,
                  dim_color: QColor):
        changed = (self._skin_id != skin_id)
        self._skin_id = skin_id
        self._blur = int(blur)
        self._dim = int(dim)
        self._fit = fit or "cover"
        self._dim_color = dim_color
        if changed:
            self._key, self._buf = None, None
        self.update()

    @property
    def has_skin(self) -> bool:
        return bool(self._skin_id)

    def _render(self) -> QPixmap | None:
        size = self.size()
        if size.width() < 2 or size.height() < 2:
            return None
        key = (self._skin_id, size.width(), size.height(), self._fit, self._blur)
        if key == self._key and self._buf is not None:
            return self._buf
        pm = skin_mod.background(self._skin_id, size.width(), size.height(), self._fit)
        if pm is None or pm.isNull():
            self._key, self._buf = key, None
            return None
        if self._fit == "contain":
            # 适应模式：未覆盖区域用模糊放大的同图铺底，避免露出生硬空底
            base = skin_mod.background(self._skin_id, size.width(), size.height(), "cover")
            if base is not None and not base.isNull():
                base = skin_mod.blur_pixmap(base, max(8, self._blur or 10))
                p = QPainter(base)
                x = (size.width() - pm.width()) // 2
                y = (size.height() - pm.height()) // 2
                p.drawPixmap(x, y, pm)
                p.end()
                pm = base
        if self._blur > 0:
            pm = skin_mod.blur_pixmap(pm, self._blur)
        self._key, self._buf = key, pm
        return pm

    def paintEvent(self, ev):
        if not self._skin_id:
            super().paintEvent(ev)
            return
        pm = self._render()
        if pm is None:
            super().paintEvent(ev)
            return
        p = QPainter(self)
        p.drawPixmap(0, 0, pm)
        # 12% 下限：遮罩过低时浅色壁纸上的文字会失去对比度
        dim = max(12, self._dim)
        c = QColor(self._dim_color)
        c.setAlphaF(max(0.0, min(1.0, dim / 100.0)))
        p.fillRect(self.rect(), c)
        p.end()


# ============================================================
# 无边框窗口：拖动 + 边缘缩放
# ============================================================
class FramelessMixin:
    """QMainWindow 混入：支持拖拽移动与八方向缩放"""

    def _init_frameless(self):
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self._resize_edge = None
        self._resize_start = None
        self._resize_geom = None
        self.setMouseTracking(True)
        self.setWindowIcon(make_logo_pixmap(64))

    def _edge_at(self, pos) -> str | None:
        m = RESIZE_MARGIN
        r = self.rect()
        edges = []
        if pos.y() <= m:
            edges.append("n")
        elif pos.y() >= r.height() - m:
            edges.append("s")
        if pos.x() <= m:
            edges.append("w")
        elif pos.x() >= r.width() - m:
            edges.append("e")
        return "".join(edges) or None

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            edge = self._edge_at(ev.position().toPoint())
            if edge:
                self._resize_edge = edge
                self._resize_start = ev.globalPosition().toPoint()
                self._resize_geom = self.geometry()
                return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._resize_edge and self._resize_start:
            g, d = QRect(self._resize_geom), self._resize_start - ev.globalPosition().toPoint()
            e = self._resize_edge
            min_w, min_h = self.minimumWidth() or 900, self.minimumHeight() or 620
            if "e" in e:
                g.setWidth(max(min_w, self._resize_geom.width() - d.x()))
            if "s" in e:
                g.setHeight(max(min_h, self._resize_geom.height() - d.y()))
            if "w" in e:
                w = max(min_w, self._resize_geom.width() + d.x())
                g.setLeft(self._resize_geom.right() - w)
            if "n" in e:
                h = max(min_h, self._resize_geom.height() + d.y())
                g.setTop(self._resize_geom.bottom() - h)
            self.setGeometry(g)
            return
        edge = self._edge_at(ev.position().toPoint())
        cursors = {"n": Qt.SizeVerCursor, "s": Qt.SizeVerCursor,
                   "w": Qt.SizeHorCursor, "e": Qt.SizeHorCursor,
                   "ns": Qt.SizeVerCursor, "we": Qt.SizeHorCursor,
                   "nw": Qt.SizeFDiagCursor, "se": Qt.SizeFDiagCursor,
                   "ne": Qt.SizeBDiagCursor, "sw": Qt.SizeBDiagCursor}
        self.setCursor(cursors.get(edge, Qt.ArrowCursor))
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._resize_edge = None
        super().mouseReleaseEvent(ev)


# ============================================================
# 侧边栏
# ============================================================
class NavItem(QPushButton):
    """侧边栏导航项：图标 + 文字 + 右侧徽标"""

    def __init__(self, icon_name: str, text: str, palette, enabled=True):
        super().__init__()
        self.p = palette
        self.icon_name = icon_name
        self.text_lbl = text
        self._selected = False
        self._enabled = enabled
        self.setEnabled(enabled)
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        self.setFixedHeight(34)
        self.setIconSize(QSize(18, 18))
        if not enabled:
            self.setToolTip("即将上线")
        self.retheme(palette)

    def set_selected(self, on: bool):
        self._selected = on
        self.retheme(self.p)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.p
        # 背景
        if self._selected:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(pal.accent_soft))
            p.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)
        elif self.isEnabled() and self.underMouse():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(pal.bg_control))
            p.drawRoundedRect(0, 0, self.width(), self.height(), 8, 8)
        # 图标
        icon_color = pal.accent if self._selected else (
            pal.text_faint if not self.isEnabled() else pal.text_icon)
        pm = icon(self.icon_name, icon_color, 18).pixmap(18, 18)
        p.drawPixmap(12, (self.height() - 18) // 2, pm)
        # 文字
        p.setPen(QColor(pal.accent_text if self._selected else
                        (pal.text_faint if not self.isEnabled() else pal.text_secondary)))
        f = QFont(self.font())
        f.setPixelSize(13)
        if self._selected:
            f.setBold(True)
        p.setFont(f)
        p.drawText(QRect(40, 0, self.width() - 60, self.height()),
                   Qt.AlignVCenter, self.text_lbl)
        # 徽标
        badge = getattr(self, "badge_text", "")
        if badge:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(pal.accent))
            bw = max(20, 10 + 7 * len(badge))
            p.drawRoundedRect(self.width() - 14 - bw, (self.height() - 18) // 2,
                              bw, 18, 9, 9)
            p.setPen(QColor("#ffffff"))
            f2 = QFont(self.font())
            f2.setPixelSize(11)
            p.setFont(f2)
            p.drawText(QRect(self.width() - 14 - bw, 0, bw, self.height()),
                       Qt.AlignCenter, badge)
        p.end()

    def retheme(self, pal):
        self.p = pal
        self.setStyleSheet("QPushButton { border:none; background:transparent; text-align:left; }")
        self.update()


class Sidebar(QFrame):
    navigate = Signal(str)          # page key
    login_clicked = Signal()

    def __init__(self, palette):
        super().__init__()
        self.p = palette
        self.setFixedWidth(220)
        self.setObjectName("Sidebar")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 16, 14, 14)
        lay.setSpacing(4)

        # 品牌区
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(make_logo_pixmap(34))
        logo.setFixedSize(34, 34)
        brand.addWidget(logo)
        bcol = QVBoxLayout()
        bcol.setSpacing(0)
        self.brand_name = QLabel(APP_NAME)
        self.brand_ver = QLabel(f"v{APP_VERSION} · Windows")
        bcol.addWidget(self.brand_name)
        bcol.addWidget(self.brand_ver)
        brand.addLayout(bcol)
        brand.addStretch(1)
        lay.addLayout(brand)
        lay.addSpacing(14)

        # 分组标签 + 导航
        def group_label(text):
            l = QLabel(text)
            l.setObjectName("GroupLabel")
            lay.addWidget(l)
            return l

        group_label("下载")
        self.nav_downloading = NavItem("download", "下载中", palette)
        self.nav_done = NavItem("check-circle", "已完成", palette)
        self.nav_fav = NavItem("star", "收藏夹", palette, enabled=False)
        for n in (self.nav_downloading, self.nav_done, self.nav_fav):
            lay.addWidget(n)
        self.nav_downloading.clicked.connect(lambda: self.navigate.emit("home"))
        self.nav_done.clicked.connect(lambda: self.navigate.emit("done"))
        lay.addSpacing(10)

        group_label("工具")
        self.nav_batch = NavItem("layers", "批量下载", palette, enabled=False)
        self.nav_sub = NavItem("subtitle", "字幕与弹幕", palette, enabled=False)
        for n in (self.nav_batch, self.nav_sub):
            lay.addWidget(n)
        lay.addSpacing(10)

        # 设置项（贴底）
        lay.addStretch(1)
        self.nav_settings = NavItem("settings", "设置", palette)
        lay.addWidget(self.nav_settings)
        self.nav_settings.clicked.connect(lambda: self.navigate.emit("settings"))
        lay.addSpacing(8)

        # 账号卡
        self.account = QPushButton()
        self.account.setCursor(Qt.PointingHandCursor)
        self.account.setFixedHeight(52)
        self.account.setIconSize(QSize(30, 30))
        self.account.clicked.connect(self.login_clicked.emit)
        lay.addWidget(self.account)

        self.retheme(palette)

    def refresh_account(self, settings):
        pal = self.p
        logged = settings.logged_in
        name = "未登录"
        desc = "登录解锁 1080P 高码率 / 4K"
        if logged:
            name = getattr(settings, "username", "") or "B 站用户"
            desc = "已登录 · 可下载 1080P 高码率 / 4K"
        self.account.setText("")
        self.account.setIcon(AvatarPixmap.make(30, pal.bg_control, pal.text_faint))
        self.account.setLayout(None)
        # 用子标签绘制两行文字
        if not hasattr(self, "_acc_name"):
            lay = QHBoxLayout(self.account)
            lay.setContentsMargins(10, 0, 8, 0)
            lay.setSpacing(10)
            lay.addStretch(1)
            col = QVBoxLayout()
            col.setSpacing(1)
            self._acc_name = QLabel()
            self._acc_desc = QLabel()
            col.addWidget(self._acc_name)
            col.addWidget(self._acc_desc)
            lay.addLayout(col)
        self._acc_name.setText(name)
        self._acc_desc.setText(desc)
        self._acc_name.setStyleSheet(
            f"color:{pal.text}; font-size:12px; font-weight:600; background:transparent; border:none;")
        self._acc_desc.setStyleSheet(
            f"color:{pal.text_faint}; font-size:10px; background:transparent; border:none;")
        self.account.setStyleSheet(f"""
            QPushButton {{
                background:{pal.surface}; border:1px solid {pal.border_card};
                border-radius:10px; text-align:left;
            }}
            QPushButton:hover {{ background:{pal.bg_subtle}; }}
        """)

    def retheme(self, pal):
        self.p = pal
        self.setStyleSheet(f"""
            QFrame#Sidebar {{
                background:{pal.bg_sidebar}; border:none;
            }}
            QFrame#Sidebar QLabel {{ background:transparent; border:none; }}
        """)
        for n in (self.nav_downloading, self.nav_done, self.nav_fav,
                  self.nav_batch, self.nav_sub, self.nav_settings):
            n.retheme(pal)
        for w in self.findChildren(QLabel):
            if w.objectName() == "GroupLabel":
                w.setStyleSheet(
                    f"color:{pal.text_faint}; font-size:11px; background:transparent; padding-left:12px;")
        self.brand_name.setStyleSheet(
            f"color:{pal.text}; font-size:13px; font-weight:700; background:transparent;")
        self.brand_ver.setStyleSheet(
            f"color:{pal.text_faint}; font-size:10px; background:transparent;")


# ============================================================
# 标题栏
# ============================================================
class TrafficLight(QPushButton):
    """macOS 风格交通灯按钮（12px 圆）"""

    def __init__(self, color: str, hover_color: str, parent=None):
        super().__init__(parent)
        self._color, self._hover = color, hover_color
        self.setFixedSize(14, 14)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QPushButton {{ background:{color}; border:none; border-radius:7px; }}
            QPushButton:hover {{ background:{hover_color}; }}
        """)


class TitleBar(QFrame):
    def __init__(self, shell, palette):
        super().__init__()
        self.shell = shell
        self.p = palette
        self.setFixedHeight(52)
        self.setObjectName("TitleBar")
        self._drag = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 18, 0)

        lay.addStretch(1)
        self.title = QLabel(f"{APP_NAME}")
        lay.addWidget(self.title)
        lay.addStretch(1)

        self.btn_theme = QPushButton()
        self.btn_theme.setObjectName("ghost")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setFixedHeight(28)
        self.btn_theme.clicked.connect(shell.cycle_theme)
        lay.addWidget(self.btn_theme)

        lay.addSpacing(8)
        self.btn_min = TrafficLight("#FEBC2E", "#FFCC55")
        self.btn_min.clicked.connect(shell.showMinimized)
        lay.addWidget(self.btn_min)
        self.btn_max = TrafficLight("#28C840", "#3DD65A")
        self.btn_max.clicked.connect(shell.toggle_max)
        lay.addWidget(self.btn_max)
        self.btn_close = TrafficLight("#FF5F57", "#FF7B73")
        self.btn_close.clicked.connect(shell.close)
        lay.addWidget(self.btn_close)

        self.retheme(palette)

    def retheme(self, pal):
        self.p = pal
        self.setStyleSheet(f"""
            QFrame#TitleBar {{ background:{pal.bg_sidebar}; border:none; }}
            QFrame#TitleBar QLabel {{ background:transparent; border:none; }}
        """)
        self.title.setStyleSheet(
            f"color:{pal.text}; font-size:13px; background:transparent;")
        self.btn_theme.setText("主题：跟随系统")

    # 拖拽移动
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._edge_none(ev):
            self._drag = ev.globalPosition().toPoint() - self.shell.frameGeometry().topLeft()
        super().mousePressEvent(ev)

    def _edge_none(self, ev) -> bool:
        # 只有点在空白处才拖动
        return True

    def mouseMoveEvent(self, ev):
        if self._drag is not None and ev.buttons() & Qt.LeftButton:
            self.shell.move(ev.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        self._drag = None
        super().mouseReleaseEvent(ev)

    def mouseDoubleClickEvent(self, ev):
        self.shell.toggle_max()
        super().mouseDoubleClickEvent(ev)


# ============================================================
# 主窗口
# ============================================================
class MainWindow(FramelessMixin, QMainWindow):
    def __init__(self):
        super().__init__()
        self._init_frameless()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 840)
        self.setMinimumSize(980, 660)

        self.settings = AppSettings()
        self.dl = Downloader()
        self.login = BilibiliLogin(self.settings.cookie_file.parent)
        self.manager = QueueManager(self.dl, self.settings)
        self._prev_page = "home"

        self.p = self._base_p = theme.resolve(self.settings.theme_mode,
                                              self._system_is_dark())

        self._build_ui()
        self.setAcceptDrops(True)
        self.apply_theme(self.p)

        # 队列 → 界面
        self.manager.task_done.connect(self._on_task_done)
        self.manager.stats_changed.connect(self._refresh_nav_badges)

        if not self.dl.available():
            QTimer.singleShot(600, lambda: QMessageBox.warning(
                self, "缺少组件",
                "未找到 yt-dlp，请确认 bin 目录与程序在一起，下载功能不可用。"))

        # 已登录时刷新账号名
        self._fetch_username()

    # ---------- 布局 ----------
    def _build_ui(self):
        central = Backdrop()
        self.backdrop = central
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.titlebar = TitleBar(self, self.p)
        root.addWidget(self.titlebar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.sidebar = Sidebar(self.p)
        self.sidebar.navigate.connect(self.navigate)
        self.sidebar.login_clicked.connect(lambda: self.navigate("login"))
        body.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.view_home = HomeView(self._ctx(), self.p)
        self.view_detail = DetailView(self._ctx(), self.p)
        self.view_settings = SettingsView(self._ctx(), self.p)
        self.view_login = LoginView(self._ctx(), self.p)
        for v in (self.view_home, self.view_detail, self.view_settings, self.view_login):
            self.stack.addWidget(v)
        self.view_home.connect_manager()
        self.view_home.open_detail.connect(self._open_detail)
        self.view_settings.login_requested.connect(lambda: self.navigate("login"))
        self.view_settings.logout_requested.connect(self._logout)
        self.view_login.login_succeeded.connect(self._on_login_success)
        self.view_login.logout_requested.connect(self._logout)
        self.view_login.back_requested.connect(lambda: self.navigate(self._prev_page))
        self.view_home.input_url.installEventFilter(self)
        body.addWidget(self.stack, 1)

        root.addLayout(body, 1)
        self.navigate("home")

    def _ctx(self) -> dict:
        return {"settings": self.settings, "dl": self.dl, "manager": self.manager,
                "login": self.login, "shell": self}

    # ---------- 导航 ----------
    def navigate(self, key: str):
        filter_done = key == "done"
        key = "home" if filter_done else key
        views = {"home": self.view_home, "detail": self.view_detail,
                 "settings": self.view_settings, "login": self.view_login}
        if key != "login":
            self._prev_page = key
        idx = list(views).index(key)
        self.stack.setCurrentIndex(idx)
        if key == "home":
            self.view_home.set_queue_filter(filter_done)
        self._update_nav_selection(key, filter_done)
        if key == "login":
            # BUG-002：进入登录页时按当前登录态展示（已登录则显示账号与退出）
            self.view_login.refresh_state()

    def _update_nav_selection(self, key, done_only=False):
        self.sidebar.nav_downloading.set_selected(key in ("home", "detail") and not done_only)
        self.sidebar.nav_done.set_selected(done_only)
        self.sidebar.nav_settings.set_selected(key == "settings")

    def _open_detail(self, info: dict):
        self.view_detail.load(info)
        self.navigate("detail")

    # ---------- 登录 ----------
    def _on_login_success(self):
        self._refresh_login_state()
        self.navigate(self._prev_page)

    def _logout(self):
        self.settings.logout()
        self._refresh_login_state()
        self.view_login.refresh_state()      # 退出后登录页回到二维码态

    def _refresh_login_state(self):
        logged = self.settings.logged_in
        self.sidebar.refresh_account(self.settings)
        self.view_settings.refresh_account()
        self.view_detail.sync_login_state(logged)   # BUG-003：登录后放开 4K

    def _fetch_username(self):
        """尽力获取登录用户名（失败无碍，仅影响账号卡显示）"""
        if not self.settings.logged_in:
            return
        def _job():
            try:
                import requests
                cookie = self.settings.cookie_file.read_text(encoding="utf-8")
                sess = ""
                for line in cookie.splitlines():
                    parts = line.split("\t")
                    if len(parts) == 7 and parts[5] == "SESSDATA":
                        sess = parts[6]
                if not sess:
                    return
                r = requests.get(
                    "https://api.bilibili.com/x/web-interface/nav",
                    headers={"User-Agent": "Mozilla/5.0",
                             "Referer": "https://www.bilibili.com/",
                             "Cookie": f"SESSDATA={sess}"}, timeout=10)
                name = (r.json().get("data") or {}).get("uname", "")
                if name:
                    self.settings.username = name
                    QTimer.singleShot(0, self._refresh_login_state)
            except Exception:
                pass
        import threading
        threading.Thread(target=_job, daemon=True).start()

    def on_login_changed(self):
        self._refresh_login_state()

    # ---------- 徽标 ----------
    def _refresh_nav_badges(self):
        c = self.manager.counts()
        self.sidebar.nav_downloading.badge_text = str(c["running"]) if c["running"] else ""
        self.sidebar.nav_done.badge_text = str(c["done"]) if c["done"] else ""
        self.sidebar.nav_downloading.update()
        self.sidebar.nav_done.update()

    # ---------- 通知 ----------
    def _on_task_done(self, task):
        if self.settings.get("notify_done", False):
            try:
                from PySide6.QtWidgets import QSystemTrayIcon
                if not hasattr(self, "_tray"):
                    self._tray = QSystemTrayIcon(self.windowIcon(), self)
                    self._tray.show()
                self._tray.showMessage(
                    "下载完成", task.title[:60],
                    QSystemTrayIcon.Information, 4000)
            except Exception:
                pass
        self._refresh_nav_badges()

    # ---------- 主题 ----------
    @staticmethod
    def _system_is_dark() -> bool:
        try:
            return int(QApplication.styleHints().colorScheme()) == 2
        except Exception:
            return False

    def cycle_theme(self):
        order = [theme.THEME_AUTO, theme.THEME_LIGHT, theme.THEME_DARK]
        nxt = order[(order.index(self.settings.theme_mode) + 1) % len(order)]
        self.set_theme_mode(nxt)

    def set_theme_mode(self, mode: str):
        self.settings.theme_mode = mode
        self.apply_theme(theme.resolve(mode, self._system_is_dark()))

    def apply_theme(self, p: theme.Palette):
        """
        p 是"基础调色板"。启用皮肤时先派生一份半透明版本，
        让壁纸从面板下透出来；文字与品牌色不变，保证可读性。
        """
        self._base_p = p
        self._update_backdrop()
        if self.settings.get("skin_id"):
            p = p.with_alpha(self.settings.get("skin_alpha", 88) / 100.0)
        self.p = p
        app = QApplication.instance()
        if app:
            app.setStyleSheet(theme.stylesheet(p))
        self.titlebar.retheme(p)
        self.titlebar.btn_theme.setText(
            {"auto": "主题：跟随系统", "light": "主题：亮色", "dark": "主题：暗色"}[self.settings.theme_mode])
        self.sidebar.retheme(p)
        self.sidebar.refresh_account(self.settings)
        self.view_home.retheme(p)
        self.view_detail.retheme(p)
        self.view_settings.retheme(p)
        self.view_login.retheme(p)
        self._refresh_nav_badges()

    # ---------- 皮肤 ----------
    def _update_backdrop(self):
        """把皮肤设置同步给背景层；遮罩颜色随主题（暗色压暗、亮色提亮）"""
        dark = getattr(self._base_p, "is_dark", False)
        self.backdrop.configure(
            self.settings.get("skin_id", ""),
            self.settings.get("skin_blur", 0),
            self.settings.get("skin_dim", 28),
            self.settings.get("skin_fit", "cover"),
            QColor("#000000") if dark else QColor("#FFFFFF"),
        )

    def apply_skin(self):
        """皮肤设置变更后重算背景与主题（设置页 / 拖拽导入时调用）"""
        self.apply_theme(self._base_p)

    def toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # ---------- 事件 ----------
    def eventFilter(self, obj, ev):
        return super().eventFilter(obj, ev)

    # 拖拽图片到窗口任意位置即应用为皮肤
    def dragEnterEvent(self, ev):
        md = ev.mimeData()
        if md and md.hasUrls():
            for u in md.urls():
                if Path(u.toLocalFile()).suffix.lower() in skin_mod.IMAGE_EXTS:
                    ev.acceptProposedAction()
                    return
        super().dragEnterEvent(ev)

    def dropEvent(self, ev):
        md = ev.mimeData()
        if not md or not md.hasUrls():
            return super().dropEvent(ev)
        path = md.urls()[0].toLocalFile()
        if not path:
            return super().dropEvent(ev)
        if Path(path).suffix.lower() not in skin_mod.IMAGE_EXTS:
            QMessageBox.warning(self, "不支持的文件",
                                "请拖入 PNG / JPG / WEBP / BMP / GIF 图片。")
            return
        sk = skin_mod.install_image(path)
        if sk is None:
            QMessageBox.warning(self, "无法使用该图片",
                                "文件无法读取或不是有效的图片，请换一张试试。")
            return
        self.settings.set("skin_id", sk.id)
        self.apply_skin()
        self.view_settings.refresh_skins()
        self.navigate("settings")
        ev.acceptProposedAction()

    def closeEvent(self, ev):
        self.view_login.stop_worker()
        self.manager.shutdown()
        self.settings.save()
        ev.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
