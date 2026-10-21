"""
主界面页
URL 输入行 → 解析结果卡 → 下载队列 → 底部汇总栏（对照设计稿 01/05）
"""

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ..downloader import QUALITY_CHOICES, human_speed, parse_size, fmt_duration
from ..queue_manager import Task, TaskState
from .widgets import Chip, IconButton, StateBadge, fetch_cover_async


# ---------- 后台解析线程 ----------
class ParseWorker(QThread):
    ok = Signal(dict)
    fail = Signal(str)

    def __init__(self, dl, url, cookie, parent=None):
        super().__init__(parent)
        self.dl, self.url, self.cookie = dl, url, cookie

    def run(self):
        try:
            self.ok.emit(self.dl.fetch_info(self.url, self.cookie))
        except Exception as exc:
            self.fail.emit(str(exc))


def normalize_url(url: str) -> str:
    """把任意形态的 B 站链接归一为 canonical 视频页链接"""
    import re
    m = re.search(r"(BV[0-9A-Za-z]{10})", url)
    if m:
        return f"https://www.bilibili.com/video/{m.group(1)}"
    m = re.search(r"av(\d+)", url)
    if m:
        return f"https://www.bilibili.com/video/av{m.group(1)}"
    return url.strip()


def url_is_valid(text: str) -> bool:
    return bool(text) and ("bilibili.com" in text or "b23.tv" in text) \
        and ("BV" in text or "/av" in text or "b23.tv" in text)


# ---------- 任务行 ----------
class TaskRow(QFrame):
    """队列任务行：缩略图 + 信息/进度 + 速度列 + 状态徽标 + 操作按钮"""

    THUMB_H = 54

    def __init__(self, task: Task, view, palette):
        super().__init__()
        self.task = task
        self.view = view          # HomeView，用于回调
        self.p = palette
        self.setObjectName("TaskRow")
        self._cover_pm = None
        self._title_full = task.title

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(14)

        # 缩略图
        self.thumb = QLabel()
        self.thumb.setFixedSize(96, self.THUMB_H)
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setStyleSheet("border-radius:6px;")
        lay.addWidget(self.thumb)

        # 信息列
        mid = QVBoxLayout()
        mid.setSpacing(5)
        self.title = QLabel(task.title)
        self.title.setStyleSheet("font-size:13px; font-weight:500;")
        mid.addWidget(self.title)

        # 进度条：bar_track 作底轨容器，bar_fill 叠在其内按百分比伸缩
        self.bar_track = QFrame()
        self.bar_track.setFixedHeight(6)
        bar_lay = QHBoxLayout(self.bar_track)
        bar_lay.setContentsMargins(0, 0, 0, 0)
        bar_lay.setSpacing(0)
        self.bar_fill = QFrame()
        self.bar_fill.setFixedHeight(6)
        bar_lay.addWidget(self.bar_fill)
        bar_lay.addStretch(1)
        self.bar = self.bar_track      # refresh() 用 self.bar.width() 计算填充宽度
        mid.addWidget(self.bar)

        self.sub = QLabel()
        self.sub.setStyleSheet("font-size:11px;")
        mid.addWidget(self.sub)
        lay.addLayout(mid, 1)

        # 进度% + 速度列
        right = QVBoxLayout()
        right.setSpacing(3)
        right.addStretch(1)
        self.pct = QLabel("0%")
        self.pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pct.setStyleSheet("font-size:12px;")
        right.addWidget(self.pct)
        self.speed = QLabel("—")
        self.speed.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.speed.setStyleSheet("font-size:11px;")
        right.addWidget(self.speed)
        right.addStretch(1)
        # right / act 是 QVBoxLayout 而非 QWidget，必须用 addLayout
        lay.addLayout(right)

        # 状态徽标
        self.badge = StateBadge(self.p)
        lay.addWidget(self.badge)

        # 操作列
        act = QVBoxLayout()
        act.setSpacing(6)
        self.btn_main = IconButton("pause", self.p, tip="暂停")
        self.btn_main.clicked.connect(self._on_main_action)
        act.addWidget(self.btn_main)
        self.btn_more = IconButton("more", self.p, tip="更多")
        self.btn_more.clicked.connect(self._on_more)
        act.addWidget(self.btn_more)
        # act 是 QVBoxLayout，必须用 addLayout（写成 addWidget 会 TypeError 崩溃）
        lay.addLayout(act)

        task.updated.connect(self.refresh)
        self.refresh()
        self._load_cover()

    # ---------- 行为 ----------
    def _on_main_action(self):
        st = self.task.state
        if st == TaskState.RUNNING:
            self.view.manager.pause(self.task.id)
        elif st == TaskState.PAUSED:
            self.view.manager.resume(self.task.id)
        elif st == TaskState.FAILED:
            self.view.manager.retry(self.task.id)
        elif st == TaskState.DONE:
            self._open_file()

    def _on_more(self):
        import os
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        if self.task.state == TaskState.DONE:
            if self.task.filepath:
                a_play = menu.addAction("播放视频")
                a_play.triggered.connect(self._open_file)
                a_copy = menu.addAction("复制文件路径")
                a_copy.triggered.connect(self._copy_path)
                menu.addSeparator()
            a_open = menu.addAction("打开所在文件夹")
            a_open.triggered.connect(self._open_folder)
            a_retry = menu.addAction("重新下载")
            a_retry.triggered.connect(lambda: self.view.manager.retry(self.task.id))
        else:
            a_retry = menu.addAction("重试")
            a_retry.triggered.connect(lambda: self.view.manager.retry(self.task.id))
            a_top = menu.addAction("打开下载目录")
            a_top.triggered.connect(self.view.open_download_dir)
        menu.addSeparator()
        a_del = menu.addAction("移除任务")
        a_del.triggered.connect(lambda: self.view.manager.remove(self.task.id))
        menu.exec(self.btn_more.mapToGlobal(self.btn_more.rect().bottomLeft()))

    def _open_file(self):
        """用系统默认播放器打开成片；文件已被移动则退回归属文件夹"""
        import os
        from pathlib import Path
        p = Path(self.task.filepath) if self.task.filepath else None
        if p and p.exists():
            try:
                os.startfile(str(p))
                return
            except OSError:
                pass
        self._open_folder()

    def _copy_path(self):
        from PySide6.QtWidgets import QApplication
        if self.task.filepath:
            QApplication.clipboard().setText(self.task.filepath)

    def _open_folder(self):
        import os
        from pathlib import Path
        p = Path(self.task.filepath) if self.task.filepath else None
        d = p.parent if p and p.exists() else Path(self.task.output_dir)
        if d.exists():
            os.startfile(d)

    def _load_cover(self):
        url = self.task.cover_url
        if url:
            fetch_cover_async(url, self.task.id, self._on_cover)
        self._paint_placeholder()

    def _on_cover(self, key: str, pm: QPixmap):
        if key != self.task.id:
            return
        self._cover_pm = pm.scaled(
            96, self.THUMB_H, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.refresh()

    def _paint_placeholder(self):
        if self._cover_pm:
            self.thumb.setPixmap(self._cover_pm)
            return
        p = self.p
        pm = QPixmap(96, self.THUMB_H)
        pm.fill(Qt.transparent)
        from PySide6.QtGui import QPainter, QLinearGradient
        from PySide6.QtCore import QPointF
        pa = QPainter(pm)
        pa.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(QPointF(0, 0), QPointF(96, self.THUMB_H))
        g.setColorAt(0, QColor("#FB7299") if not p.is_dark else QColor("#3D2530"))
        g.setColorAt(1, QColor("#8A5CF6") if not p.is_dark else QColor("#2A3C5A"))
        pa.setBrush(g)
        pa.setPen(Qt.NoPen)
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(0, 0, 96, self.THUMB_H, 6, 6)
        pa.drawPath(path)
        pa.end()
        self.thumb.setPixmap(pm)

    # ---------- 刷新 ----------
    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._fit_title()

    def mouseDoubleClickEvent(self, ev):
        # 双击已完成的任务 = 直接播放；下载中/失败则忽略
        if self.task.state == TaskState.DONE and self.task.filepath:
            self._open_file()
        super().mouseDoubleClickEvent(ev)

    def _fit_title(self):
        """长标题按可用宽度省略，不挤掉右侧的速度/徽标/按钮"""
        avail = self.width() - 96 - 14 * 4 - 96 - 92 - 64
        if avail < 120:
            avail = max(80, self.width() - 300)
        self.title.setText(self.title.fontMetrics().elidedText(
            self._title_full, Qt.ElideRight, avail))

    def refresh(self):
        t = self.task
        p = self.p
        self._title_full = t.title
        self.title.setText(t.title)

        st = t.state
        running = st == TaskState.RUNNING

        self.pct.setText(f"{t.percent:.0f}%")
        self.speed.setText(
            human_speed(t.speed_bps) if running else
            (f"剩余 {t.eta}" if running and t.eta else
             (t.size_text if st == TaskState.DONE else "—")))

        # 副信息
        if running:
            self.sub.setText(t.meta or f"{t.quality} · {t.size_text}")
        elif st == TaskState.DONE:
            # 完成态：画质 + 体积 + 状态；完整路径放 tooltip，避免长文件名挤乱行
            size = t.size_text or "已保存"
            self.sub.setText(f"{t.quality} · {size} · 已保存")
            self.sub.setToolTip(t.filepath or t.output_dir)
        elif st == TaskState.FAILED:
            self.sub.setText(t.error or "下载失败")
            self.sub.setToolTip(t.error or "")
        elif st == TaskState.PAUSED:
            self.sub.setText(f"{t.quality} · 已暂停，可继续下载")
        else:
            self.sub.setText(f"{t.quality} · 等待中")

        # 进度条
        self.bar_track.setStyleSheet(
            f"background:{p.border_progress}; border-radius:3px;")
        color = p.accent
        if st == TaskState.DONE:
            color = p.success
        elif st == TaskState.FAILED:
            color = p.danger
        elif st == TaskState.PAUSED:
            color = p.text_faint
        self.bar_fill.setStyleSheet(f"background:{color}; border-radius:3px;")
        self.bar_fill.setFixedHeight(6)
        self.bar_fill.setFixedWidth(
            int(self.bar.width() * t.percent / 100) if self.bar.width() > 20 else 0)

        # 徽标
        badge_text = {TaskState.RUNNING: "下载中", TaskState.PAUSED: "已暂停",
                      TaskState.WAITING: "等待中",
                      TaskState.FAILED: t.error[:4] if t.error else "失败",
                      TaskState.DONE: "已完成"}[st]
        self.badge.set_state(st.name, badge_text)

        # 主操作按钮
        if running:
            self.btn_main.icon_name = "pause"
            self.btn_main.setToolTip("暂停")
        elif st == TaskState.PAUSED:
            self.btn_main.icon_name = "play"
            self.btn_main.setToolTip("继续")
        elif st == TaskState.FAILED:
            self.btn_main.icon_name = "retry"
            self.btn_main.setToolTip("重试")
        elif st == TaskState.DONE:
            # 有成品就播一下，没有就退回归属文件夹
            if t.filepath:
                self.btn_main.icon_name = "play"
                self.btn_main.setToolTip("播放视频")
            else:
                self.btn_main.icon_name = "folder"
                self.btn_main.setToolTip("打开文件夹")
        else:
            self.btn_main.icon_name = "more"
            self.btn_main.setToolTip("等待中")
        self.btn_main.restyle()
        self.restyle_row()
        self._fit_title()

    def restyle_row(self):
        p = self.p
        self.setStyleSheet(f"""
            QFrame#TaskRow {{
                background:{p.surface}; border:1px solid {p.border_card};
                border-radius:12px;
            }}
            QFrame#TaskRow QLabel {{ background:transparent; border:none; }}
        """)
        self.title.setStyleSheet(f"color:{p.text}; font-size:13px; font-weight:500; background:transparent;")
        sub_color = p.text_muted
        if self.task.state == TaskState.DONE:
            sub_color = p.success_text
        elif self.task.state == TaskState.FAILED:
            sub_color = p.danger_text
        self.sub.setStyleSheet(f"color:{sub_color}; font-size:11px; background:transparent;")
        self.pct.setStyleSheet(f"color:{p.text_secondary}; font-size:12px; background:transparent;")
        self.speed.setStyleSheet(f"color:{p.text_muted}; font-size:11px; background:transparent;")
        self.badge.pal = p


# ---------- 解析结果卡 ----------
class ParseCard(QFrame):
    """解析结果：封面 176×99 + 标题/meta/chips + 画质下拉 + 加入队列"""

    def __init__(self, view, palette):
        super().__init__()
        self.view = view
        self.p = palette
        self.setObjectName("ParseCard")
        self.info = None
        self._cover = None

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)

        self.cover = QLabel()
        self.cover.setFixedSize(176, 99)
        self.cover.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.cover)

        mid = QVBoxLayout()
        mid.setSpacing(6)
        self.title = QLabel()
        self.title.setWordWrap(True)
        mid.addWidget(self.title)

        self.meta = QLabel()
        mid.addWidget(self.meta)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addStretch(1)
        self.chips_lay = chips
        mid.addLayout(chips)
        lay.addLayout(mid, 1)

        right = QVBoxLayout()
        right.setSpacing(10)
        self.quality = QComboBox()
        self.quality.addItems(QUALITY_CHOICES)
        default_q = self.view.settings.get("default_quality") or "最高画质"
        idx = self.quality.findText(default_q)
        if idx >= 0:
            self.quality.setCurrentIndex(idx)
        right.addWidget(self.quality)
        self.btn_add = QPushButton(" 加入下载队列")
        self.btn_add.setObjectName("primary")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setMinimumHeight(36)
        self.btn_add.clicked.connect(self._add_to_queue)
        right.addWidget(self.btn_add)
        right.addStretch(1)
        lay.addLayout(right)
        self.hide()

    def _add_to_queue(self):
        if self.info:
            self.view.enqueue_parsed(self.info, self.quality.currentText())

    def show_info(self, info: dict):
        self.info = info
        p = self.p
        # 清空 chips
        while self.chips_lay.count():
            item = self.chips_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        title = info.get("title", "")
        uploader = info.get("uploader", "")
        dur = fmt_duration(info.get("duration"))
        views = info.get("view_count") or 0
        views_s = f"{views/10000:.1f} 万播放" if views >= 10000 else (f"{views} 播放" if views else "")
        bvid = info.get("id", "")
        meta_parts = [x for x in (uploader, views_s, dur, bvid) if x]
        self.meta.setText(" · ".join(meta_parts))

        # chips
        pages = info.get("pages") or []
        if len(pages) > 1:
            self.chips_lay.addWidget(Chip(f"共 {len(pages)} P", p.bg_control, p.text_dim))
        q = info.get("format_note") or info.get("format", "")
        if q:
            self.chips_lay.addWidget(Chip(q, p.accent_soft, p.accent_text, bold=True))
        if "会员" in (info.get("subtitle") or ""):
            self.chips_lay.addWidget(Chip("大会员专享", p.warning_soft, p.warning_text))

        self.title.setText(title)
        self.cover.setText("")
        if info.get("thumbnail"):
            fetch_cover_async(info["thumbnail"], "parse", self._on_cover)
        self._paint_placeholder_cover()
        self.setVisible(True)

    def _on_cover(self, key, pm: QPixmap):
        self._cover = pm.scaled(176, 99, Qt.KeepAspectRatioByExpanding,
                                Qt.SmoothTransformation)
        self.cover.setPixmap(self._cover)

    def _paint_placeholder_cover(self):
        if self._cover:
            self.cover.setPixmap(self._cover)
            return
        self.cover.setStyleSheet(f"background:{self.p.bg_control}; border-radius:8px;")
        self.cover.setText("解析中…")

    def retheme(self, p):
        self.p = p
        self.setStyleSheet(f"""
            QFrame#ParseCard {{
                background:{p.surface}; border:1px solid {p.border_card};
                border-radius:12px;
            }}
            QFrame#ParseCard QLabel {{ background:transparent; border:none; }}
        """)
        self.title.setStyleSheet(f"color:{p.text}; font-size:14px; font-weight:600; background:transparent;")
        self.meta.setStyleSheet(f"color:{p.text_muted}; font-size:11px; background:transparent;")
        self._cover = None
        self.cover.setStyleSheet(f"background:{p.bg_control}; border:none; border-radius:8px;")
        if self.info:
            self.show_info(self.info)


# ---------- 主界面 ----------
class HomeView(QWidget):
    open_detail = Signal(dict)      # 携带解析信息，请求打开详情页
    request_login = Signal()

    def __init__(self, ctx, palette):
        super().__init__()
        self.ctx = ctx              # dict: manager, settings, dl, shell
        self.p = palette
        self.manager = ctx["manager"]
        self.settings = ctx["settings"]
        self.dl = ctx["dl"]
        self._parse_worker = None
        self._info_timer = None
        self._rows: dict[str, TaskRow] = {}
        self._done_only = False     # 侧边栏「已完成」筛选
        self._build()
        self.retheme(palette)

        # 队列已有任务（主题重建后恢复）
        for t in self.manager.tasks:
            self._add_row(t)

    # ---------- 构建 ----------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 0)
        root.setSpacing(14)

        root.addWidget(self._url_row())
        self.parse_card = ParseCard(self, self.p)
        root.addWidget(self.parse_card)
        self.parse_hint = QLabel("")
        self.parse_hint.setWordWrap(True)
        root.addWidget(self.parse_hint)

        root.addWidget(self._queue_header())
        root.addWidget(self._queue_list(), 1)
        root.addWidget(self._footer())
        root.addSpacing(0)

    def _url_row(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.input_url = QLineEdit()
        self.input_url.setPlaceholderText("粘贴 B 站视频链接，回车或点击「解析」")
        self.input_url.setFixedHeight(40)
        self.input_url.textChanged.connect(self._on_url_changed)
        self.input_url.returnPressed.connect(self.parse_url)
        lay.addWidget(self.input_url, 1)

        self.btn_paste = QPushButton("粘贴")
        self.btn_paste.setObjectName("outline")
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.setFixedHeight(40)
        self.btn_paste.clicked.connect(self._paste)
        lay.addWidget(self.btn_paste)

        self.btn_parse = QPushButton(" 解析")
        self.btn_parse.setObjectName("primary")
        self.btn_parse.setCursor(Qt.PointingHandCursor)
        self.btn_parse.setFixedHeight(40)
        self.btn_parse.setEnabled(False)
        self.btn_parse.clicked.connect(self.parse_url)
        lay.addWidget(self.btn_parse)

        self.btn_batch = QPushButton(" 批量")
        self.btn_batch.setObjectName("outline")
        self.btn_batch.setFixedHeight(40)
        self.btn_batch.setEnabled(False)
        self.btn_batch.setToolTip("批量下载即将上线")
        lay.addWidget(self.btn_batch)
        return w

    def _paste(self):
        from PySide6.QtWidgets import QApplication
        text = QApplication.clipboard().text()
        if text:
            self.input_url.setText(text.strip())
            self.parse_url()

    def _queue_header(self):
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        self.q_title = QLabel("下载队列")
        lay.addWidget(self.q_title)
        self.q_stats = QLabel("")
        lay.addWidget(self.q_stats)
        lay.addStretch(1)

        self.btn_pause_all = QPushButton(" 全部暂停")
        self.btn_pause_all.setObjectName("outline")
        self.btn_pause_all.setCursor(Qt.PointingHandCursor)
        self.btn_pause_all.clicked.connect(self.manager.pause_all)
        lay.addWidget(self.btn_pause_all)

        self.btn_clear = QPushButton(" 清空已完成")
        self.btn_clear.setObjectName("outline")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_done)
        lay.addWidget(self.btn_clear)
        return w

    def _queue_list(self):
        holder = QFrame()
        holder.setObjectName("QueueHolder")
        outer = QVBoxLayout(holder)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.queue_inner = QWidget()
        self.queue_lay = QVBoxLayout(self.queue_inner)
        self.queue_lay.setContentsMargins(0, 0, 6, 12)
        self.queue_lay.setSpacing(10)
        self.queue_lay.addStretch(1)

        self.empty_hint = QLabel("暂无下载任务——粘贴链接并解析后，加入队列即可开始")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.queue_lay.insertWidget(0, self.empty_hint)

        scroll.setWidget(self.queue_inner)
        outer.addWidget(scroll)
        self.queue_holder = holder
        return holder

    def _footer(self):
        w = QFrame()
        w.setObjectName("Footer")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(10)

        self.f_total = QLabel("共 0 个任务")
        lay.addWidget(self.f_total)
        self.f_done = QLabel("")
        lay.addWidget(self.f_done)
        lay.addStretch(1)

        self.f_speed = QLabel("总速度 —")
        lay.addWidget(self.f_speed)

        self.btn_open_dir = QPushButton(" 打开下载目录")
        self.btn_open_dir.setObjectName("ghost")
        self.btn_open_dir.setCursor(Qt.PointingHandCursor)
        self.btn_open_dir.clicked.connect(self.open_download_dir)
        lay.addWidget(self.btn_open_dir)

        self.btn_start_all = QPushButton(" 全部开始")
        self.btn_start_all.setObjectName("primary")
        self.btn_start_all.setCursor(Qt.PointingHandCursor)
        self.btn_start_all.clicked.connect(self.manager.start_all)
        lay.addWidget(self.btn_start_all)

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_footer)
        self._stats_timer.start(1000)
        return w

    # ---------- 解析 ----------
    def _set_parse_hint(self, text, error=False):
        """统一的解析状态提示：错误用危险色，其余用弱化色"""
        self.parse_hint.setText(text)
        color = self.p.danger if error else self.p.text_muted
        weight = "600" if error else "400"
        self.parse_hint.setStyleSheet(
            f"color:{color}; font-size:12px; font-weight:{weight}; background:transparent;")

    def _on_url_changed(self, text):
        self.btn_parse.setEnabled(url_is_valid(text))
        if not url_is_valid(text):
            self.parse_card.hide()
            self._set_parse_hint("")
            return
        if self._info_timer:
            self._info_timer.stop()
        self._info_timer = QTimer(self)
        self._info_timer.setSingleShot(True)
        self._info_timer.timeout.connect(self.parse_url)
        self._info_timer.start(700)

    def parse_url(self):
        url = normalize_url(self.input_url.text())
        if not url_is_valid(url):
            return
        # 防重入：自动解析定时器（700ms）与回车/点击「解析」可能在解析进行中
        # 再次触发。此时若覆盖 self._parse_worker，会销毁仍在运行的 QThread
        # （Qt 直接崩溃：QThread: Destroyed while thread is still running）。
        # 已有一个解析线程在跑时，忽略本次请求，等它结束后再触发即可。
        if self._parse_worker is not None and self._parse_worker.isRunning():
            return
        self._set_parse_hint("解析中…")
        self.parse_card.hide()
        self._parse_worker = ParseWorker(
            self.dl, url,
            self.settings.cookie_file if self.settings.logged_in else None)
        self._parse_worker.ok.connect(self._on_parsed)
        self._parse_worker.fail.connect(self._on_parse_fail)
        self._parse_worker.start()

    def _on_parse_fail(self, msg):
        self._set_parse_hint(f"解析失败：{msg[:120]}", error=True)

    def _on_parsed(self, info: dict):
        self._set_parse_hint("")
        self.parse_card.show_info(info)

    def enqueue_parsed(self, info: dict, quality: str):
        pages = info.get("pages") or []
        if len(pages) > 1:
            self.open_detail.emit(info)
            return
        task = Task(
            normalize_url(self.input_url.text()) if not info.get("webpage_url")
            else info["webpage_url"],
            self.settings.get("download_dir"),
            quality=quality,
            subtitle=True, thumbnail=True,
            danmaku=False,
        )
        task.set(title=info.get("title", "未命名"),
                 cover_url=info.get("thumbnail", ""),
                 meta=f"{info.get('uploader','')} · {fmt_duration(info.get('duration'))}")
        self.manager.add_task(task)

    # ---------- 队列渲染 ----------
    def set_queue_filter(self, done_only: bool):
        """侧边栏「已完成」= 只显示已完成；「下载中」恢复显示全部"""
        self._done_only = done_only
        self._apply_filter()

    def _apply_filter(self):
        visible = 0
        for row in self._rows.values():
            show = not self._done_only or row.task.state == TaskState.DONE
            row.setVisible(show)
            visible += 1 if show else 0
        if visible == 0:
            self.empty_hint.setText(
                "暂无已完成任务" if self._done_only
                else "暂无下载任务——粘贴链接并解析后，加入队列即可开始")
        self.empty_hint.setVisible(visible == 0)

    def _on_task_updated(self):
        if self._done_only:
            self._apply_filter()

    def _add_row(self, task: Task):
        row = TaskRow(task, self, self.p)
        self._rows[task.id] = row
        self.queue_lay.insertWidget(self.queue_lay.count() - 1, row)
        task.updated.connect(self._on_task_updated)
        self.empty_hint.setVisible(False)
        self._refresh_footer()
        self._apply_filter()

    def _remove_row(self, task_id: str):
        row = self._rows.pop(task_id, None)
        if row:
            self.queue_lay.removeWidget(row)
            row.deleteLater()
        if not self._rows:
            self.empty_hint.setVisible(True)
        self._refresh_footer()
        self._apply_filter()

    def _clear_done(self):
        self.manager.clear_done()

    def _refresh_footer(self):
        c = self.manager.counts()
        self.f_total.setText(f"共 {c['total']} 个任务")
        parts = []
        if c["running"]:
            parts.append(f"{c['running']} 个进行中")
        if c["failed"]:
            parts.append(f"{c['failed']} 个失败")
        self.q_stats.setText(" · ".join(parts))
        self.f_done.setText(f"已完成 {c['done']} 个" if c["done"] else "")
        total = self.manager.total_speed_bps()
        self.f_speed.setText(f"总速度 {human_speed(total)}" if total > 0 else "总速度 —")
        self.btn_start_all.setEnabled(
            any(t.state in (TaskState.PAUSED, TaskState.FAILED, TaskState.WAITING)
                for t in self.manager.tasks))
        self.btn_pause_all.setEnabled(c["running"] > 0)
        self.btn_clear.setEnabled(c["done"] > 0)
        # 队列标题徽标
        self.q_title.setText("已完成任务" if self._done_only else "下载队列")

    def open_download_dir(self):
        import os
        from pathlib import Path
        d = Path(self.settings.get("download_dir"))
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(d)

    def connect_manager(self):
        self.manager.task_added.connect(self._add_row)
        self.manager.task_removed.connect(self._remove_row)
        self.manager.stats_changed.connect(self._refresh_footer)

    # ---------- 主题 ----------
    def retheme(self, p):
        self.p = p
        self.parse_card.retheme(p)
        self.empty_hint.setStyleSheet(f"color:{p.text_faint}; font-size:12px; background:transparent;")
        self.q_title.setStyleSheet(f"color:{p.text}; font-size:15px; font-weight:600; background:transparent;")
        self.q_stats.setStyleSheet(f"color:{p.text_muted}; font-size:12px; background:transparent;")
        self.parse_hint.setStyleSheet(f"color:{p.text_muted}; font-size:12px; background:transparent;")
        self.queue_holder.setStyleSheet(f"""
            QFrame#QueueHolder {{
                background:{p.surface}; border:1px solid {p.border_card};
                border-radius:12px;
            }}
        """)
        self.queue_inner.setStyleSheet(f"background:{p.surface};")
        w = self._footer_parent()
        if w:
            w.setStyleSheet(f"""
                QFrame#Footer {{
                    background:{p.bg_footer}; border:1px solid {p.border_card};
                    border-radius:12px;
                }}
                QFrame#Footer QLabel {{ background:transparent; border:none; }}
            """)
            self.f_total.setStyleSheet(f"color:{p.text_secondary}; font-size:12px; background:transparent;")
            self.f_done.setStyleSheet(f"color:{p.text_muted}; font-size:12px; background:transparent;")
            self.f_speed.setStyleSheet(f"color:{p.text_secondary}; font-size:12px; background:transparent;")
        for row in self._rows.values():
            row.p = p
            row.badge.pal = p
            row.refresh()

    def _footer_parent(self):
        return self.f_total.parent() if hasattr(self, "f_total") else None
