"""
设置页（对照设计稿 03/07）
外观与皮肤 / 通用 / 画质与网络 / 账号 四组卡片
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QSlider, QSpinBox,
    QVBoxLayout, QWidget,
)

from .. import skin as skin_mod
from ..downloader import QUALITY_CHOICES
from .widgets import AvatarPixmap, Switch


class SettingRow(QFrame):
    """设置行：标题 + 说明 + 右侧控件"""

    def __init__(self, title: str, desc: str, editor: QWidget, palette):
        super().__init__()
        self.p = palette
        self.setObjectName("SettingRow")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 12, 18, 12)
        lay.setSpacing(10)

        left = QVBoxLayout()
        left.setSpacing(3)
        t = QLabel(title)
        t.setObjectName("rowTitle")
        d = QLabel(desc)
        d.setObjectName("rowDesc")
        left.addWidget(t)
        left.addWidget(d)
        lay.addLayout(left, 1)
        lay.addWidget(editor)

        self.title_lbl, self.desc_lbl = t, d
        self.retheme(palette)

    def retheme(self, p):
        self.p = p
        self.setStyleSheet(f"""
            QFrame#SettingRow QLabel {{ background:transparent; border:none; }}
            QFrame#SettingRow {{ background:transparent; border:none; }}
        """)
        self.title_lbl.setStyleSheet(f"color:{p.text}; font-size:13px; font-weight:500; background:transparent;")
        self.desc_lbl.setStyleSheet(f"color:{p.text_muted}; font-size:11px; background:transparent;")


def divider():
    d = QFrame()
    d.setFixedHeight(1)
    return d


class SkinCell(QPushButton):
    """皮肤缩略图单元：预览图 + 名称，选中态用主色描边"""

    W, H = 96, 54

    def __init__(self, sk, palette):
        super().__init__()
        self.skin = sk
        self.pal = palette
        self._selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(self.W + 14, self.H + 34)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 4)
        lay.setSpacing(4)
        self.thumb = QLabel()
        self.thumb.setFixedSize(self.W, self.H)
        self.thumb.setPixmap(skin_mod.thumbnail(sk, self.W, self.H))
        lay.addWidget(self.thumb, 0, Qt.AlignCenter)
        self.name = QLabel(sk.name)
        self.name.setAlignment(Qt.AlignCenter)
        self.name.setFixedWidth(self.W + 2)
        lay.addWidget(self.name)
        self.apply_style()

    def set_selected(self, on: bool):
        self._selected = on
        self.apply_style()

    def apply_style(self):
        p = self.pal
        border = p.accent if self._selected else p.border_card
        bw = 2 if self._selected else 1
        self.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:{bw}px solid {border}; border-radius:10px;
            }}
            QPushButton:hover {{ background:{p.bg_control}; border-color:{p.border_hi}; }}
            QPushButton QLabel {{ background:transparent; border:none; }}
        """)
        self.name.setStyleSheet(
            f"color:{p.accent_text if self._selected else p.text_secondary};"
            f" font-size:11px; font-weight:{'600' if self._selected else '400'};"
            f" background:transparent;")

    def retheme(self, pal):
        self.pal = pal
        self.apply_style()


class SettingsView(QWidget):
    logout_requested = Signal()
    login_requested = Signal()

    def __init__(self, ctx, palette):
        super().__init__()
        self.ctx = ctx
        self.p = palette
        self.settings = ctx["settings"]
        self._skin_cells: list = []
        # 先占位，网格构建早于按钮创建（网格中需要引用它）
        self.btn_remove_skin = None
        self.skin_tip = None
        self._build()
        self.retheme(palette)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        container = QWidget()
        # 容器保持透明，启用皮肤时壁纸才能透出来
        container.setStyleSheet("background:transparent;")
        root = QVBoxLayout(container)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)
        outer.addWidget(scroll)

        self.page_title = QLabel("设置")
        root.addWidget(self.page_title)
        self.page_hint = QLabel("所有修改即时生效并自动保存")
        root.addWidget(self.page_hint)

        # ===== 外观与皮肤 =====
        g0 = self._card("外观与皮肤")

        self.skin_grid = QWidget()
        self.skin_grid.setStyleSheet("background:transparent;")
        self.skin_lay = QGridLayout(self.skin_grid)
        self.skin_lay.setContentsMargins(18, 4, 18, 6)
        self.skin_lay.setSpacing(10)
        g0.addWidget(self.skin_grid)
        self._rebuild_skin_grid()

        btns = QWidget()
        btns.setStyleSheet("background:transparent;")
        hb = QHBoxLayout(btns)
        hb.setContentsMargins(18, 0, 18, 8)
        hb.setSpacing(8)
        self.btn_import_skin = QPushButton("导入本地图片…")
        self.btn_import_skin.setObjectName("outline")
        self.btn_import_skin.setCursor(Qt.PointingHandCursor)
        self.btn_import_skin.clicked.connect(self._import_skin)
        hb.addWidget(self.btn_import_skin)
        self.btn_remove_skin = QPushButton("移除当前皮肤")
        self.btn_remove_skin.setObjectName("ghost")
        self.btn_remove_skin.setCursor(Qt.PointingHandCursor)
        self.btn_remove_skin.clicked.connect(self._remove_skin)
        hb.addWidget(self.btn_remove_skin)
        hb.addStretch(1)
        self.skin_tip = QLabel("也可以把图片直接拖到窗口任意位置")
        hb.addWidget(self.skin_tip)
        g0.addWidget(btns)

        g0.addWidget(divider())
        self.row_alpha = self._slider_row(
            "面板不透明度", "数值越低，背景图片越明显", "skin_alpha", 40, 100)
        g0.addWidget(self.row_alpha)

        g0.addWidget(divider())
        self.row_blur = self._slider_row(
            "背景柔化", "让背景图更柔和，突出文字", "skin_blur", 0, 30)
        g0.addWidget(self.row_blur)

        g0.addWidget(divider())
        self.row_dim = self._slider_row(
            "遮罩强度", "在背景图上叠一层底色，保证文字清晰（最低 12%）", "skin_dim", 12, 60)
        g0.addWidget(self.row_dim)

        g0.addWidget(divider())
        combo_fit = QComboBox()
        combo_fit.addItems(["填充（裁切铺满）", "适应（完整显示）", "拉伸（铺满变形）"])
        combo_fit.setFixedWidth(170)
        combo_fit.setCurrentText({"cover": "填充（裁切铺满）", "contain": "适应（完整显示）",
                                  "stretch": "拉伸（铺满变形）"}.get(
                                      self.settings.get("skin_fit", "cover"),
                                      "填充（裁切铺满）"))
        combo_fit.currentTextChanged.connect(self._on_fit)
        self.row_fit = SettingRow("填充方式", "背景图如何适配窗口尺寸", combo_fit, self.p)
        g0.addWidget(self.row_fit)
        root.addWidget(self._wrap_card(g0))

        # ===== 通用 =====
        g1 = self._card("通用")

        btn_dir = QPushButton("更改")
        btn_dir.setObjectName("outline")
        btn_dir.setCursor(Qt.PointingHandCursor)
        btn_dir.setFixedWidth(76)
        btn_dir.clicked.connect(self._choose_dir)
        self.row_dir = SettingRow("下载目录", "", btn_dir, self.p)
        self.row_dir.desc_lbl.setText(self.settings.get("download_dir"))
        btn_dir.clicked.connect(lambda: self.row_dir.desc_lbl.setText(self.settings.get("download_dir")))
        g1.addWidget(self.row_dir)

        g1.addWidget(divider())
        spin = QSpinBox()
        spin.setRange(1, 5)
        spin.setValue(int(self.settings.get("max_concurrent", 3)))
        spin.setFixedWidth(88)
        spin.valueChanged.connect(lambda v: self.settings.set("max_concurrent", v))
        self.row_conc = SettingRow("同时下载任务数", "同时进行的最大下载任务数量", spin, self.p)
        g1.addWidget(self.row_conc)

        g1.addWidget(divider())
        sw_merge = Switch(self.settings.get("auto_merge", True), self.p)
        sw_merge.toggled.connect(lambda v: self.settings.set("auto_merge", v))
        self.row_merge = SettingRow("自动合并视频", "使用 ffmpeg 合并分离的音视频轨道", sw_merge, self.p)
        g1.addWidget(self.row_merge)

        g1.addWidget(divider())
        sw_notify = Switch(self.settings.get("notify_done", False), self.p)
        sw_notify.toggled.connect(lambda v: self.settings.set("notify_done", v))
        self.row_notify = SettingRow("完成后系统通知", "任务下载完成时发送系统通知", sw_notify, self.p)
        g1.addWidget(self.row_notify)
        root.addWidget(self._wrap_card(g1))

        # ===== 画质与网络 =====
        g2 = self._card("画质与网络")

        combo_q = QComboBox()
        combo_q.addItems(QUALITY_CHOICES)
        combo_q.setCurrentText(self.settings.get("default_quality"))
        combo_q.setFixedWidth(150)
        combo_q.currentTextChanged.connect(lambda v: self.settings.set("default_quality", v))
        self.row_quality = SettingRow("默认画质", "粘贴链接后自动选择的画质", combo_q, self.p)
        g2.addWidget(self.row_quality)

        g2.addWidget(divider())
        combo_rate = QComboBox()
        combo_rate.addItems(["不限速", "500KB/s", "1MB/s", "2MB/s", "5MB/s"])
        combo_rate.setFixedWidth(150)
        cur = self.settings.get("rate_limit", "")
        combo_rate.setCurrentText({"": "不限速", "500K": "500KB/s", "1M": "1MB/s",
                                   "2M": "2MB/s", "5M": "5MB/s"}.get(cur, "不限速"))
        combo_rate.currentTextChanged.connect(self._on_rate)
        self.row_rate = SettingRow("单任务限速", "限制单个任务的下载速度", combo_rate, self.p)
        g2.addWidget(self.row_rate)

        g2.addWidget(divider())
        combo_proxy = QComboBox()
        combo_proxy.addItems(["不使用", "使用系统代理", "自定义"])
        combo_proxy.setFixedWidth(150)
        combo_proxy.setCurrentText({"none": "不使用", "system": "使用系统代理",
                                    "custom": "自定义"}.get(self.settings.get("proxy_mode", "none")))
        combo_proxy.currentTextChanged.connect(self._on_proxy_mode)
        self.row_proxy = SettingRow("网络代理", "使用系统代理或自定义代理服务器", combo_proxy, self.p)
        g2.addWidget(self.row_proxy)

        self.edit_proxy = QLineEdit()
        self.edit_proxy.setPlaceholderText("http://127.0.0.1:7890")
        self.edit_proxy.setFixedWidth(220)
        self.edit_proxy.setText(self.settings.get("proxy_url", ""))
        self.edit_proxy.textChanged.connect(
            lambda v: self.settings.set("proxy_url", v.strip()))
        self.row_proxy_url = SettingRow(
            "代理地址", "支持 http:// 或 socks5:// 前缀", self.edit_proxy, self.p)
        self.row_proxy_url.setVisible(self.settings.get("proxy_mode", "none") == "custom")
        g2.addWidget(self.row_proxy_url)
        root.addWidget(self._wrap_card(g2))

        # ===== 账号 =====
        g3 = self._card("账号")
        self.btn_login = QPushButton("去登录")
        self.btn_login.setObjectName("primary")
        self.btn_login.setCursor(Qt.PointingHandCursor)
        self.btn_login.clicked.connect(self.login_requested.emit)
        self.row_account = SettingRow("B 站账号", "", self.btn_login, self.p)
        g3.addWidget(self.row_account)

        self.btn_logout = QPushButton("退出登录")
        self.btn_logout.setObjectName("outline")
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.clicked.connect(self.logout_requested.emit)
        self.btn_logout.setVisible(False)
        self.row_account.layout().addWidget(self.btn_logout)

        self.btn_cookie_import = QPushButton("导入 Cookie 文件")
        self.btn_cookie_import.setObjectName("ghost")
        self.btn_cookie_import.setCursor(Qt.PointingHandCursor)
        self.btn_cookie_import.clicked.connect(self._import_cookie)
        self.row_account.layout().addWidget(self.btn_cookie_import)
        root.addWidget(self._wrap_card(g3))
        root.addStretch(1)

        scroll.setWidget(container)

    # ---------- 辅助 ----------
    def _card(self, title: str) -> QVBoxLayout:
        card = QFrame()
        card.setObjectName("GroupCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(0, 14, 0, 6)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("groupTitle")
        t.setContentsMargins(18, 0, 0, 8)
        lay.addWidget(t)
        self._card_lay = lay
        self._current_card = card
        return lay

    def _wrap_card(self, lay) -> QFrame:
        return self._current_card

    def _slider_row(self, title: str, desc: str, key: str,
                    min_v: int, max_v: int) -> SettingRow:
        """带数值显示的滑块设置行"""
        sl = QSlider(Qt.Horizontal)
        sl.setRange(min_v, max_v)
        sl.setValue(int(self.settings.get(key, min_v)))
        sl.setFixedWidth(150)
        val = QLabel(str(sl.value()))
        val.setFixedWidth(28)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        box = QWidget()
        box.setStyleSheet("background:transparent;")
        hb = QHBoxLayout(box)
        hb.setContentsMargins(0, 0, 0, 0)
        hb.setSpacing(8)
        hb.addWidget(sl)
        hb.addWidget(val)
        row = SettingRow(title, desc, box, self.p)
        row.slider, row.value_label = sl, val

        def on_change(v, _k=key, _l=val):
            self.settings.set(_k, v)
            _l.setText(str(v))
            self.ctx["shell"].apply_skin()

        sl.valueChanged.connect(on_change)
        return row

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择下载目录",
                                             self.settings.get("download_dir"))
        if d:
            self.settings.set("download_dir", d)
            self.row_dir.desc_lbl.setText(d)

    def _on_rate(self, text):
        mapping = {"不限速": "", "500KB/s": "500K", "1MB/s": "1M",
                   "2MB/s": "2M", "5MB/s": "5M"}
        self.settings.set("rate_limit", mapping.get(text, ""))

    def _on_proxy_mode(self, text):
        mapping = {"不使用": "none", "使用系统代理": "system", "自定义": "custom"}
        self.settings.set("proxy_mode", mapping.get(text, "none"))
        self.row_proxy_url.setVisible(text == "自定义")

    def _on_fit(self, text):
        mapping = {"填充（裁切铺满）": "cover", "适应（完整显示）": "contain",
                   "拉伸（铺满变形）": "stretch"}
        self.settings.set("skin_fit", mapping.get(text, "cover"))
        self.ctx["shell"].apply_skin()

    def _import_cookie(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "选择 cookies.txt", "", "Cookie 文件 (*.txt);;所有文件 (*)")
        if not f:
            return
        from pathlib import Path
        content = Path(f).read_text(encoding="utf-8", errors="ignore")
        if "SESSDATA" not in content:
            QMessageBox.warning(self, "无效的 Cookie 文件",
                                "文件中未找到 SESSDATA，请确认是 B 站的 cookies.txt")
            return
        self.settings.cookie_file.write_text(content, encoding="utf-8")
        self.refresh_account()
        self.ctx["shell"].on_login_changed()

    # ---------- 皮肤 ----------
    def _rebuild_skin_grid(self):
        """重建皮肤网格：'无' + 内置预设 + 用户导入"""
        while self.skin_lay.count():
            item = self.skin_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._skin_cells = []

        current = self.settings.get("skin_id", "")
        items = [skin_mod.Skin(id="", name="无", kind="none")] + skin_mod.list_skins()
        per_row = 6
        for i, sk in enumerate(items):
            cell = SkinCell(sk, self.p)
            cell.set_selected(sk.id == current)
            cell.clicked.connect(lambda _=False, s=sk: self._pick_skin(s))
            self.skin_lay.addWidget(cell, i // per_row, i % per_row)
            self._skin_cells.append(cell)
        if self.btn_remove_skin is not None:
            self._sync_skin_buttons()

    def _pick_skin(self, sk):
        self.settings.set("skin_id", sk.id)
        for c in self._skin_cells:
            c.set_selected(c.skin.id == sk.id)
        self._sync_skin_buttons()
        self.ctx["shell"].apply_skin()

    def _sync_skin_buttons(self):
        cur = self.settings.get("skin_id", "")
        self.btn_remove_skin.setEnabled(cur.startswith("img_"))

    def _import_skin(self):
        f, _ = QFileDialog.getOpenFileName(self, "选择背景图片", "", skin_mod.FILE_FILTER)
        if not f:
            return
        sk = skin_mod.install_image(f)
        if sk is None:
            QMessageBox.warning(self, "无法使用该图片",
                                "文件无法读取或不是有效的图片，请换一张试试。")
            return
        self.settings.set("skin_id", sk.id)
        self._rebuild_skin_grid()
        self.ctx["shell"].apply_skin()

    def _remove_skin(self):
        sid = self.settings.get("skin_id", "")
        if not sid.startswith("img_"):
            return
        if skin_mod.remove(sid):
            self.settings.set("skin_id", "")
            self._rebuild_skin_grid()
            self.ctx["shell"].apply_skin()

    def refresh_skins(self):
        """皮肤列表发生变化（如拖拽导入）后刷新网格"""
        self._rebuild_skin_grid()

    # ---------- 账号 ----------
    def refresh_account(self):
        p = self.p
        logged = self.settings.logged_in
        if logged:
            self.row_account.desc_lbl.setText("已登录 · 可下载 1080P 高码率 / 4K（需大会员）与高清弹幕")
            self.btn_login.setText("重新登录")
            self.btn_logout.setVisible(True)
        else:
            self.row_account.desc_lbl.setText("未登录 · 登录后可下载 1080P 高码率 / 4K（需大会员）与高清弹幕")
            self.btn_login.setText("去登录")
            self.btn_logout.setVisible(False)

    # ---------- 主题 ----------
    def retheme(self, p):
        self.p = p
        self.page_title.setStyleSheet(f"color:{p.text}; font-size:16px; font-weight:700; background:transparent;")
        self.page_hint.setStyleSheet(
            f"color:{p.text_muted}; font-size:12px; background:transparent;")
        for w in self.findChildren(QFrame):
            if w.objectName() == "GroupCard":
                w.setStyleSheet(f"""
                    QFrame#GroupCard {{
                        background:{p.surface}; border:1px solid {p.border_card};
                        border-radius:12px;
                    }}
                    QFrame#GroupCard QLabel {{ background:transparent; border:none; }}
                """)
        for w in self.findChildren(QLabel):
            if w.objectName() == "groupTitle":
                w.setStyleSheet(f"color:{p.text}; font-size:14px; font-weight:600; background:transparent;")
        for c in self._skin_cells:
            c.retheme(p)
        self.skin_tip.setStyleSheet(
            f"color:{p.text_faint}; font-size:11px; background:transparent;")
        for row in (self.row_alpha, self.row_blur, self.row_dim, self.row_fit):
            row.retheme(p)
        self.row_dir.retheme(p)
        self.row_conc.retheme(p)
        self.row_merge.retheme(p)
        self.row_notify.retheme(p)
        self.row_quality.retheme(p)
        self.row_rate.retheme(p)
        self.row_proxy.retheme(p)
        self.row_account.retheme(p)
        self.switch_merge(p)
        self.refresh_account()

    def switch_merge(self, p):
        for sw in self.findChildren(Switch):
            sw.pal = p
            sw.update()
