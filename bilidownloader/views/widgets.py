"""
通用小部件：SVG 图标加载、开关、chip、异步封面图。
设计图标来自 设计资产包/icons（24 viewBox，stroke=currentColor）。
"""

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QRectF, Signal, QRunnable, QThreadPool
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QAbstractButton, QFrame, QLabel, QPushButton, QSizePolicy

ICON_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"

_icon_cache: dict[tuple, QIcon] = {}
_pixmap_cache: dict[tuple, QPixmap] = {}


def icon_pixmap(name: str, color: str, size: int = 18) -> QPixmap:
    """渲染 SVG 图标为指定位图（currentColor → 指定颜色）"""
    key = (name, color, size)
    if key in _pixmap_cache:
        return _pixmap_cache[key]

    path = ICON_DIR / f"{name}.svg"
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    if not path.exists():
        return pm
    renderer = QSvgRenderer(str(path))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    renderer.render(p, QRectF(0, 0, size, size))
    p.end()

    # currentColor 默认渲染为黑，用 SourceIn 整体染色
    if color.lower() not in ("#000000", "black"):
        tint = QPixmap(size, size)
        tint.fill(QColor(color))
        p = QPainter(pm)
        p.setCompositionMode(QPainter.CompositionMode_SourceIn)
        p.drawPixmap(0, 0, tint)
        p.end()

    _pixmap_cache[key] = pm
    return pm


def icon(name: str, color: str, size: int = 18) -> QIcon:
    key = (name, color, size)
    if key not in _icon_cache:
        _icon_cache[key] = QIcon(icon_pixmap(name, color, size))
    return _icon_cache[key]


class IconButton(QPushButton):
    """30×30 图标按钮（设计稿任务行操作列样式）"""

    def __init__(self, icon_name: str, palette, tip: str = "", size: int = 30,
                 icon_size: int = 16, parent=None):
        super().__init__(parent)
        self.pal = palette
        self.icon_name = icon_name
        self.icon_size = icon_size
        self._disabled = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        if tip:
            self.setToolTip(tip)
        self.restyle()

    def restyle(self):
        color = self.pal.text_icon if not self._disabled else self.pal.text_faint
        self.setIcon(icon(self.icon_name, color, self.icon_size))
        self.setIconSize(self.iconSize().boundedTo(self.size()))
        self.setStyleSheet(f"""
            QPushButton {{
                background:{self.pal.bg_input}; border:1px solid {self.pal.border_card};
                border-radius:7px;
            }}
            QPushButton:hover {{ background:{self.pal.bg_control}; border-color:{self.pal.border_hi}; }}
            QPushButton:disabled {{ background:{self.pal.bg_subtle}; }}
        """)

    def set_enabled(self, on: bool):
        self._disabled = not on
        self.setEnabled(on)
        self.restyle()


class Switch(QAbstractButton):
    """iOS 风格开关（设置页/详情页弹幕开关）"""

    def __init__(self, checked=False, palette=None, parent=None):
        super().__init__(parent)
        self.pal = palette
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(36, 20)
        self.toggled.connect(lambda _: self.update())

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.pal
        on = self.isChecked()
        track = pal.accent if on else pal.border_hi
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(track))
        p.drawRoundedRect(0, 0, 36, 20, 10, 10)
        # 白色滑块，带阴影感
        p.setBrush(QColor("#ffffff"))
        x = 18 if on else 2
        p.drawRect(QRectF(x, 2, 16, 16).adjusted(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, 2, 16, 16), 8, 8)
        p.drawPath(path)
        p.end()


class Chip(QLabel):
    """圆角小标签（状态徽标 / 画质 chips / 会员标记）"""

    def __init__(self, text: str, bg: str, fg: str, parent=None,
                 bold: bool = False, pad_h: int = 10, pad_v: int = 4, font_px: int = 11):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(f"""
            background:{bg}; color:{fg}; border:none; border-radius:6px;
            padding:{pad_v}px {pad_h}px; font-size:{font_px}px;
            {'font-weight:600;' if bold else ''}
        """)


class StateBadge(QLabel):
    """任务行状态徽标（78×24 圆角 7，soft 底 + 状态色文字）"""

    COLORS = {
        "RUNNING": ("accent", "accent_text"),
        "PAUSED": ("bg_control", "text_dim"),
        "WAITING": ("info_soft", "info_text"),
        "FAILED": ("danger_soft", "danger_text"),
        "DONE": ("success_soft", "success_text"),
    }

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.pal = palette
        self.setFixedSize(78, 24)
        self.setAlignment(Qt.AlignCenter)

    def set_state(self, state_key: str, text: str):
        bg_key, fg_key = self.COLORS.get(state_key, ("bg_control", "text_dim"))
        bg, fg = getattr(self.pal, bg_key), getattr(self.pal, fg_key)
        self.setText(text)
        self.setStyleSheet(f"""
            background:{bg}; color:{fg}; border:none; border-radius:7px;
            font-size:11px; font-weight:500;
        """)


def make_logo_pixmap(size: int = 34, bg: str = "#FB7299") -> QPixmap:
    """品牌 Logo：粉底圆角方块 + 白色下载箭头"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(bg))
    p.drawRoundedRect(0, 0, size, size, size * 0.29, size * 0.29)
    # 下载箭头
    p.setBrush(QColor("#ffffff"))
    pen_w = max(2.0, size * 0.085)
    from PySide6.QtGui import QPen
    p.setPen(QPen(QColor("#ffffff"), pen_w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    c = size / 2
    p.drawLine(c, size * 0.26, c, size * 0.58)
    p.drawLine(c, size * 0.58, c - size * 0.14, size * 0.44)
    p.drawLine(c, size * 0.58, c + size * 0.14, size * 0.44)
    p.drawLine(c - size * 0.18, size * 0.74, c + size * 0.18, size * 0.74)
    p.end()
    return pm


class _CoverSignals(QObject):
    """封面加载信号。有意不带 parent、由 _CoverJob 持有强引用，
    避免 QRunnable 被线程池回收后信号对象一起失效。"""
    loaded = Signal(str, QImage)   # key, image（QImage 可跨线程传递）


class _CoverJob(QRunnable):
    """后台抓取封面图：只下载 + 解码成 QImage，绝不碰 QPixmap"""

    def __init__(self, url: str, key: str):
        super().__init__()
        self.url, self.key = url, key
        self.sig = _CoverSignals()
        # 关掉自动析构：线程池 delete 掉 C++ 对象后，Python 包装仍可能被
        # 队列投递引用，是 BUG-007 崩溃的根因之一。生命周期改为显式引用计数。
        self.setAutoDelete(False)

    def run(self):
        img = QImage()
        try:
            import requests
            data = requests.get(self.url, timeout=15,
                                headers={"User-Agent": "Mozilla/5.0",
                                         "Referer": "https://www.bilibili.com/"}).content
            img = QImage.fromData(data)     # QImage 允许在非 GUI 线程创建
        except Exception:
            img = QImage()
        # 成功或失败都发一次：失败发空图，用于释放 _live_cover_jobs 里的引用
        self.sig.loaded.emit(self.key, img)


class _CoverReceiver(QObject):
    """常驻 GUI 线程的接收器：把 QImage 转成 QPixmap 后再回调。
    QPixmap 只能在 GUI 线程创建；且接收者是 QObject，跨线程投递自动走
    QueuedConnection，保证回调一定在 GUI 线程执行。"""

    def __init__(self, job: "_CoverJob", callback):
        super().__init__()
        self._job = job
        self._callback = callback
        job.sig.loaded.connect(self._on_loaded)

    def _on_loaded(self, key: str, img: QImage):
        _live_cover_jobs.discard(self._job)
        try:
            self._job.sig.loaded.disconnect(self._on_loaded)
        except (RuntimeError, TypeError):
            pass
        pm = QPixmap.fromImage(img) if not img.isNull() else QPixmap()
        if not pm.isNull() and self._callback is not None:
            try:
                self._callback(key, pm)
            except RuntimeError:
                pass            # 接收控件已销毁（窗口关闭），忽略
        self.deleteLater()


# 投递完成前保住 job / receiver / 回调，防止 GC 提前回收
_live_cover_jobs: set = set()


def fetch_cover_async(url: str, key: str, callback) -> None:
    """异步抓取封面，完成后在主线程回调 callback(key, pixmap)"""
    job = _CoverJob(url, key)
    job._receiver = _CoverReceiver(job, callback)   # 引用挂在 job 上，随 job 一起释放
    _live_cover_jobs.add(job)
    QThreadPool.globalInstance().start(job)


class AvatarPixmap:
    """账号卡头像（圆形，人形剪影）"""

    @staticmethod
    def make(size: int, bg: str, fg: str) -> QPixmap:
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(bg))
        p.drawEllipse(0, 0, size, size)
        p.setBrush(QColor(fg))
        c = size / 2
        p.drawEllipse(c - size * 0.16, size * 0.20, size * 0.32, size * 0.32)
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addEllipse(QRectF(c - size * 0.28, size * 0.55, size * 0.56, size * 0.56))
        p.save()
        p.setClipRect(QRectF(0, 0, size, size))
        p.drawPath(path)
        p.restore()
        p.end()
        return pm
