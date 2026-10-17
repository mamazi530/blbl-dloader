"""
视频详情页 · 批量选择（对照设计稿 02/06）
大封面 + 画质/格式/字幕 chips + 弹幕开关 + 分 P 列表 + 底部操作栏
"""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from ..downloader import fmt_duration
from ..queue_manager import Task
from .widgets import Switch, fetch_cover_async


class PagesWorker(QThread):
    """flat-playlist 解析分 P 列表"""
    ok = Signal(dict)
    fail = Signal(str)

    def __init__(self, dl, url, cookie, parent=None):
        super().__init__(parent)
        self.dl, self.url, self.cookie = dl, url, cookie

    def run(self):
        try:
            self.ok.emit(self.dl.fetch_pages(self.url, self.cookie))
        except Exception as exc:
            self.fail.emit(str(exc))


class OptionChips(QWidget):
    """一行互斥选项 chips（画质/格式/字幕），返回当前选中值"""

    changed = Signal(str)

    def __init__(self, options: list, palette, disabled_items: dict = None):
        super().__init__()
        self.p = palette
        self._selected = options[0] if options else ""
        self._buttons: dict[str, QPushButton] = {}
        self._disabled_items = disabled_items or {}
        self._enabled = True

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        for opt in options:
            b = QPushButton(opt)
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
            b.setChecked(opt == self._selected)
            b.clicked.connect(lambda _, o=opt: self.select(o))
            if opt in self._disabled_items:
                b.setEnabled(False)
                b.setToolTip(self._disabled_items[opt])
            lay.addWidget(b)
            self._buttons[opt] = b
        lay.addStretch(1)
        self.retheme(palette)

    def select(self, opt: str):
        if opt in self._disabled_items:
            return
        self._selected = opt
        self._sync()
        self.changed.emit(opt)

    def value(self) -> str:
        return self._selected

    def set_enabled(self, on: bool):
        self._enabled = on
        self._sync()

    def _sync(self):
        for opt, b in self._buttons.items():
            b.setChecked(opt == self._selected and self._enabled)
        self.retheme(self.p)

    def retheme(self, p):
        self.p = p
        for opt, b in self._buttons.items():
            disabled = opt in self._disabled_items
            on = opt == self._selected and self._enabled
            if disabled:
                b.setStyleSheet(f"""
                    QPushButton {{ background:{p.bg_subtle}; color:{p.text_faint};
                        border:1px solid {p.border_divider}; border-radius:7px;
                        padding:6px 16px; font-size:12px; }}
                """)
            elif on:
                b.setStyleSheet(f"""
                    QPushButton {{ background:{p.accent_soft}; color:{p.accent_text};
                        border:1px solid {p.accent}; border-radius:7px;
                        padding:6px 16px; font-size:12px; font-weight:600; }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{ background:{p.bg_input}; color:{p.text_secondary};
                        border:1px solid {p.border}; border-radius:7px;
                        padding:6px 16px; font-size:12px; }}
                    QPushButton:hover {{ background:{p.bg_control}; }}
                """)


class PageRow(QFrame):
    """分 P 行：复选框 + 名称 + 时长 + 大小"""

    def __init__(self, index: int, entry: dict, palette, checked=False):
        super().__init__()
        self.p = palette
        self.entry = entry
        self.index = index                      # 1 起
        self.setObjectName("PageRow")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 9, 14, 9)
        lay.setSpacing(10)

        title = entry.get("title") or f"P{index}"
        dur = fmt_duration(entry.get("duration"))
        size = entry.get("filesize") or entry.get("filesize_approx")

        self.chk = QCheckBox(f"P{index:02d} {title}")
        self.chk.setChecked(checked)
        self.chk.toggled.connect(self._restyle)
        lay.addWidget(self.chk, 1)

        self.dur_label = QLabel(dur)
        lay.addWidget(self.dur_label)
        self.size_label = QLabel(f"{size/1048576:.0f} MB" if size else "")
        self.size_label.setFixedWidth(64)
        self.size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.size_label)

        self.retheme(palette)
        self._restyle()

    def _restyle(self):
        p = self.p
        self.dur_label.setStyleSheet(f"color:{p.text_muted}; font-size:11px; background:transparent;")
        self.size_label.setStyleSheet(f"color:{p.text_muted}; font-size:11px; background:transparent;")
        self.chk.setStyleSheet(f"""
            QCheckBox {{ color:{p.text}; font-size:13px; spacing:9px; background:transparent; }}
            QCheckBox::indicator {{
                width:16px; height:16px; border-radius:5px;
                border:1.5px solid {p.border_hi}; background:{p.bg_input};
            }}
            QCheckBox::indicator:hover {{ border-color:{p.accent}; }}
            QCheckBox::indicator:checked {{ background:{p.accent}; border-color:{p.accent}; }}
        """)
        self.setStyleSheet(f"""
            QFrame#PageRow {{
                background:{p.surface}; border:1px solid {p.border_card};
                border-radius:10px;
            }}
            QFrame#PageRow QLabel {{ background:transparent; border:none; }}
        """)

    def retheme(self, p):
        self.p = p
        self._restyle()


class DetailView(QWidget):
    """视频详情页"""

    back_home = Signal()

    def __init__(self, ctx, palette):
        super().__init__()
        self.ctx = ctx
        self.p = palette
        self.dl = ctx["dl"]
        self.settings = ctx["settings"]
        self.manager = ctx["manager"]

        self.info = None
        self.pages: list[dict] = []
        self._cover = None
        self._worker = None

        self._build()
        self.retheme(palette)

    # ---------- 构建 ----------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 0)
        root.setSpacing(14)

        # 标题行
        head = QHBoxLayout()
        self.head_title = QLabel("视频详情")
        head.addWidget(self.head_title)
        self.head_meta = QLabel("")
        head.addWidget(self.head_meta)
        head.addStretch(1)
        root.addLayout(head)

        # 上半部：封面 + 选项
        top = QHBoxLayout()
        top.setSpacing(16)

        self.cover = QLabel()
        self.cover.setFixedSize(400, 225)
        self.cover.setAlignment(Qt.AlignCenter)
        top.addWidget(self.cover, 0, Qt.AlignTop)

        opts = QVBoxLayout()
        opts.setSpacing(12)

        self.card = QFrame()
        self.card.setObjectName("OptionCard")
        card_lay = QVBoxLayout(self.card)
        card_lay.setContentsMargins(18, 16, 18, 16)
        card_lay.setSpacing(12)

        self.v_title = QLabel("")
        self.v_title.setWordWrap(True)
        card_lay.addWidget(self.v_title)
        self.v_meta = QLabel("")
        card_lay.addWidget(self.v_meta)
        card_lay.addSpacing(2)

        for label in ("画质", "格式", "字幕"):
            row = QHBoxLayout()
            lab = QLabel(label)
            lab.setObjectName("optLabel")
            lab.setFixedWidth(34)
            row.addWidget(lab)
            card_lay.addLayout(row)
            setattr(self, f"_row_{label}", row)
            setattr(self, f"_label_{label}", lab)

        # 弹幕开关行
        dm_row = QHBoxLayout()
        dm_lab = QLabel("弹幕")
        dm_lab.setObjectName("optLabel")
        dm_lab.setFixedWidth(34)
        dm_row.addWidget(dm_lab)
        self.switch_danmaku = Switch(False, self.p)
        dm_row.addWidget(self.switch_danmaku)
        self.dm_hint = QLabel("同时下载 XML 弹幕文件")
        dm_row.addWidget(self.dm_hint)
        dm_row.addStretch(1)
        card_lay.addLayout(dm_row)

        top.addWidget(self.card, 1)
        root.addLayout(top)

        # 分 P 选择
        pages_head = QHBoxLayout()
        self.pages_title = QLabel("分 P 选择")
        pages_head.addWidget(self.pages_title)
        self.pages_summary = QLabel("")
        pages_head.addWidget(self.pages_summary)
        pages_head.addStretch(1)
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.setObjectName("ghost")
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.clicked.connect(self._select_all)
        pages_head.addWidget(self.btn_select_all)
        root.addLayout(pages_head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.pages_inner = QWidget()
        self.pages_lay = QVBoxLayout(self.pages_inner)
        self.pages_lay.setContentsMargins(0, 0, 6, 6)
        self.pages_lay.setSpacing(8)
        self.pages_lay.addStretch(1)
        self.pages_loading = QLabel("正在解析分 P 列表…")
        self.pages_loading.setAlignment(Qt.AlignCenter)
        self.pages_lay.insertWidget(0, self.pages_loading)
        scroll.setWidget(self.pages_inner)
        root.addWidget(scroll, 1)

        # 底部操作栏
        footer = QFrame()
        footer.setObjectName("DetailFooter")
        f = QHBoxLayout(footer)
        f.setContentsMargins(16, 10, 16, 10)
        self.f_summary = QLabel("")
        f.addWidget(self.f_summary)
        f.addStretch(1)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("outline")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self.back_home.emit)
        f.addWidget(self.btn_cancel)
        self.btn_download = QPushButton("下载所选")
        self.btn_download.setObjectName("primary")
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.setMinimumHeight(36)
        self.btn_download.setEnabled(False)
        self.btn_download.clicked.connect(self._download_selected)
        f.addWidget(self.btn_download)
        self.detail_footer = footer
        root.addWidget(footer)
        root.addSpacing(0)

        # 选项 chips（构建时还没有 palette 外的依赖，retheme 统一着色）
        self.chips_quality = OptionChips(
            ["360P", "720P", "1080P 高码率", "4K · 大会员"], self.p,
            disabled_items={"4K · 大会员": "需要大会员账号登录后可用"})
        self.chips_quality.changed.connect(lambda _: self._update_summary())
        self.chips_format = OptionChips(["MP4", "FLV", "仅音频 MP3"], self.p,
                                        disabled_items={"FLV": "B 站已淘汰 FLV，即将移除"})
        self.chips_sub = OptionChips(["不下载", "简体中文", "中英双语"], self.p)
        self.chips_sub.changed.connect(lambda _: self._update_summary())
        self._insert_chip_rows()

    def _insert_chip_rows(self):
        # 把 chips 插入卡内预留行
        self._row_画质.addWidget(self.chips_quality, 1)
        self._row_格式.addWidget(self.chips_format, 1)
        self._row_字幕.addWidget(self.chips_sub, 1)

    # ---------- 数据 ----------
    def load(self, info: dict):
        """主界面解析完成后进入此页"""
        self.info = info
        self._cover = None
        self.v_title.setText(info.get("title", ""))
        dur = fmt_duration(info.get("duration"))
        self.v_meta.setText(
            " · ".join(x for x in (
                info.get("id", ""), info.get("uploader", ""),
                f"发布于 {info.get('upload_date','')[:10]}" if info.get("upload_date") else "",
                f"共 {len(info.get('pages') or [])} P" if len(info.get("pages") or []) > 1 else dur,
            ) if x))
        self.head_meta.setText(info.get("id", ""))
        if info.get("thumbnail"):
            fetch_cover_async(info["thumbnail"], "detail", self._on_cover)
        self._paint_cover_placeholder()

        # 清空旧分 P
        while self.pages_lay.count() > 1:
            item = self.pages_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.pages_loading.setVisible(True)

        url = info.get("webpage_url") or self._canon_url(info)
        cookie = self.settings.cookie_file if self.settings.logged_in else None
        self._worker = PagesWorker(self.dl, url, cookie)
        self._worker.ok.connect(self._on_pages)
        self._worker.fail.connect(self._on_pages_fail)
        self._worker.start()

    def _canon_url(self, info):
        vid = info.get("id", "")
        return f"https://www.bilibili.com/video/{vid}" if vid.startswith("BV") else vid

    def _on_cover(self, key, pm: QPixmap):
        self._cover = pm.scaled(400, 225, Qt.KeepAspectRatioByExpanding,
                                Qt.SmoothTransformation)
        self.cover.setPixmap(self._cover)

    def _paint_cover_placeholder(self):
        if self._cover:
            self.cover.setPixmap(self._cover)
            return
        self.cover.setStyleSheet(
            f"background:{self.p.bg_control}; border-radius:12px;")
        self.cover.setText("加载封面…")

    def _on_pages(self, data: dict):
        entries = data.get("entries") or [data]
        self.pages = entries
        self.pages_loading.setVisible(False)
        for i, e in enumerate(entries, 1):
            row = PageRow(i, e, self.p, checked=(i == 1))
            row.chk.toggled.connect(self._update_summary)
            self.pages_lay.insertWidget(self.pages_lay.count() - 1, row)
        self._update_summary()

    def _on_pages_fail(self, msg: str):
        self.pages_loading.setText(f"分 P 解析失败：{msg[:100]}")

    def _selected_rows(self) -> list[PageRow]:
        rows = []
        for i in range(self.pages_lay.count()):
            w = self.pages_lay.itemAt(i).widget()
            if isinstance(w, PageRow) and w.chk.isChecked():
                rows.append(w)
        return rows

    def _select_all(self):
        rows = [w for i in range(self.pages_lay.count())
                if isinstance((w := self.pages_lay.itemAt(i).widget()), PageRow)]
        all_on = all(r.chk.isChecked() for r in rows)
        for r in rows:
            r.chk.setChecked(not all_on)

    def _update_summary(self):
        rows = self._selected_rows()
        n = len(rows)
        q = self.chips_quality.value()
        fmt = "音频" if "仅音频" in self.chips_format.value() else "MP4"
        sub = "" if self.chips_sub.value() == "不下载" else f" · {self.chips_sub.value()}"
        self.f_summary.setText(
            f"已选 {n} 个分 P · {q} · {fmt}{sub}" if n else "尚未选择任何分 P")
        self.btn_download.setText(f"下载所选{' ' + str(n) if n else ''}")
        self.btn_download.setEnabled(n > 0)
        total = sum((r.entry.get("filesize") or r.entry.get("filesize_approx") or 0)
                    for r in rows)
        if total:
            self.pages_summary.setText(
                f"已选 {n} 个 · 预计 {total/1048576:.0f} MB")
        else:
            self.pages_summary.setText(f"已选 {n} 个" if n else "")

    def _download_selected(self):
        rows = self._selected_rows()
        if not rows or not self.info:
            return
        quality = self.chips_quality.value()
        base = self._canon_url(self.info)
        sub_mode = self.chips_sub.value()
        for r in rows:
            url = base if len(self.pages) <= 1 else f"{base}?p={r.index}"
            task = Task(
                url, self.settings.get("download_dir"),
                quality="仅音频" if "仅音频" in self.chips_format.value() else quality,
                subtitle=sub_mode != "不下载",
                thumbnail=True,
                danmaku=self.switch_danmaku.isChecked(),
                page_index=r.index if len(self.pages) > 1 else None,
                page_title=r.entry.get("title") or self.info.get("title", ""),
            )
            task.set(title=task.page_title,
                     cover_url=self.info.get("thumbnail", ""),
                     meta=f"P{r.index:02d} · {quality}")
            self.manager.add_task(task)
        self.back_home.emit()

    # ---------- 主题 ----------
    def retheme(self, p):
        self.p = p
        self.head_title.setStyleSheet(f"color:{p.text}; font-size:15px; font-weight:600; background:transparent;")
        self.head_meta.setStyleSheet(f"color:{p.text_muted}; font-size:12px; background:transparent;")
        self.v_title.setStyleSheet(f"color:{p.text}; font-size:14px; font-weight:600; background:transparent;")
        self.v_meta.setStyleSheet(f"color:{p.text_muted}; font-size:11px; background:transparent;")
        self.card.setStyleSheet(f"""
            QFrame#OptionCard {{
                background:{p.surface}; border:1px solid {p.border_card};
                border-radius:12px;
            }}
            QFrame#OptionCard QLabel {{ background:transparent; border:none; }}
        """)
        for lab in (self._label_画质, self._label_格式, self._label_字幕):
            lab.setStyleSheet(f"color:{p.text_muted}; font-size:12px; background:transparent;")
        self.dm_hint.setStyleSheet(f"color:{p.text_dim}; font-size:12px; background:transparent;")
        self.pages_title.setStyleSheet(f"color:{p.text}; font-size:15px; font-weight:600; background:transparent;")
        self.pages_summary.setStyleSheet(f"color:{p.text_muted}; font-size:12px; background:transparent;")
        self.pages_loading.setStyleSheet(f"color:{p.text_faint}; font-size:12px; background:transparent;")
        self.cover.setStyleSheet(f"background:{p.bg_control}; border:none; border-radius:12px;")
        self.detail_footer.setStyleSheet(f"""
            QFrame#DetailFooter {{
                background:{p.bg_footer}; border:1px solid {p.border_card};
                border-radius:12px;
            }}
            QFrame#DetailFooter QLabel {{ background:transparent; border:none; }}
        """)
        self.f_summary.setStyleSheet(f"color:{p.text_secondary}; font-size:12px; background:transparent;")
        self.switch_danmaku.pal = p
        self.switch_danmaku.update()
        self.chips_quality.retheme(p)
        self.chips_format.retheme(p)
        self.chips_sub.retheme(p)
        for i in range(self.pages_lay.count()):
            w = self.pages_lay.itemAt(i).widget()
            if isinstance(w, PageRow):
                w.retheme(p)
        self._paint_cover_placeholder()
