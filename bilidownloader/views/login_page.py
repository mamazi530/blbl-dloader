"""
登录页（对照设计稿 04/08）
居中二维码卡片，复用 login.py 的扫码轮询逻辑。
"""

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import theme
from ..qrcode_gen import make_qr_pixmap
from .widgets import icon_pixmap

# 退出时仍未结束的登录线程：保留强引用，避免窗口析构连带销毁运行中的 QThread
_detached_workers: list = []


class LoginWorker(QThread):
    """生成二维码并轮询扫码状态（复用 login.py）"""
    qr_ready = Signal(str)
    status = Signal(str, str)      # status, message
    finished_ok = Signal(bool)

    def __init__(self, login, parent=None):
        super().__init__(parent)
        self.login = login
        self._stop = False
        self.username = ""            # 登录成功后回填，供 LoginView 持久化

    def stop(self):
        self._stop = True

    def run(self):
        try:
            url, key = self.login.generate_qr()
            self.qr_ready.emit(url)

            result = self.login.wait_login(
                key, on_update=lambda r: self.status.emit(r["status"], r["message"]),
                should_stop=lambda: self._stop, timeout=180)
            ok = result["status"] == "success"
            if ok:
                self.username = result.get("username") or ""
                self.login.export_cookies()
                self.status.emit("success", f'登录成功 · {self.username or "凭证已保存"}')
            else:
                self.status.emit(result["status"], result["message"])
            self.finished_ok.emit(ok)
        except Exception as exc:
            self.status.emit("failed", f"登录异常: {exc}")
            self.finished_ok.emit(False)


class LoginView(QWidget):
    login_succeeded = Signal()
    logout_requested = Signal()      # 已登录态点「退出登录」
    back_requested = Signal()        # 点「返回」，回到进入登录页前的页面

    # 单卡片两态：未登录=二维码，已登录=账号信息（BUG-002）
    TITLE_LOGIN = "登录 B 站账号"
    TITLE_LOGGED = "已登录"
    SUB_LOGIN = "登录后可下载 1080P 高码率 / 4K（需大会员）与高清弹幕"
    SUB_LOGGED = "登录信息仅保存在本机，不会上传任何服务器"

    def __init__(self, ctx, palette):
        super().__init__()
        self.ctx = ctx
        self.p = palette
        self.login = ctx["login"]
        self.settings = ctx.get("settings")
        self._worker = None
        self._done = False
        self._build()
        self.retheme(palette)
        # 已登录时不应再弹二维码（BUG-002）：由 refresh_state 判断
        self.refresh_state()

    # ---------- 构建 ----------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # 粉色渐变背景区
        self.stage = QFrame()
        self.stage.setObjectName("LoginStage")
        stage_lay = QVBoxLayout(self.stage)
        stage_lay.addStretch(1)

        # 居中卡片（固定 400 宽）
        self.card = QFrame()
        self.card.setObjectName("LoginCard")
        self.card.setFixedWidth(400)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(30, 28, 30, 22)
        lay.setSpacing(0)

        self.title = QLabel(self.TITLE_LOGIN)
        self.title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.title)

        self.subtitle = QLabel(self.SUB_LOGIN)
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setWordWrap(True)
        lay.addSpacing(6)
        lay.addWidget(self.subtitle)
        lay.addSpacing(18)

        # ---- 未登录态：二维码 + 备选登录 ----
        self.qr_area = QWidget()
        qr_root = QVBoxLayout(self.qr_area)
        qr_root.setContentsMargins(0, 0, 0, 0)
        qr_root.setSpacing(0)

        # 二维码白底容器（不随主题变色）
        self.qr_frame = QFrame()
        self.qr_frame.setObjectName("QRFrame")
        qr_lay = QVBoxLayout(self.qr_frame)
        qr_lay.setContentsMargins(8, 8, 8, 8)
        self.qr_label = QLabel("正在获取二维码…")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setFixedSize(180, 180)
        qr_lay.addWidget(self.qr_label)
        center = QHBoxLayout()
        center.addStretch(1)
        center.addWidget(self.qr_frame)
        center.addStretch(1)
        qr_root.addLayout(center)
        qr_root.addSpacing(14)

        self.status = QLabel("请使用 B 站 App 扫描二维码")
        self.status.setAlignment(Qt.AlignCenter)
        qr_root.addWidget(self.status)
        qr_root.addSpacing(14)
        lay.addWidget(self.qr_area)

        # ---- 未登录态：备选登录方式 ----
        self.alt_area = QWidget()
        alt = QVBoxLayout(self.alt_area)
        alt.setContentsMargins(0, 0, 0, 0)
        alt.setSpacing(0)

        or_row = QHBoxLayout()
        or_row.addStretch(1)
        self.or_label = QLabel("或")
        or_row.addWidget(self.or_label)
        or_row.addStretch(1)
        alt.addLayout(or_row)
        alt.addSpacing(8)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn_password = QPushButton("账号密码登录")
        self.btn_password.setObjectName("outline")
        self.btn_password.setEnabled(False)
        self.btn_password.setToolTip("即将上线")
        btns.addWidget(self.btn_password)
        self.btn_cookie = QPushButton("使用 Cookie 登录")
        self.btn_cookie.setObjectName("outline")
        self.btn_cookie.setCursor(Qt.PointingHandCursor)
        self.btn_cookie.clicked.connect(self._import_cookie)
        btns.addWidget(self.btn_cookie)
        alt.addLayout(btns)
        alt.addSpacing(14)

        # 安全提示
        sec = QHBoxLayout()
        sec.addStretch(1)
        shield = QLabel()
        shield.setPixmap(icon_pixmap("shield-check", "#A0A6AE", 14))
        sec.addWidget(shield)
        self.sec_note = QLabel("登录信息仅保存在本机，不会上传任何服务器")
        sec.addWidget(self.sec_note)
        sec.addStretch(1)
        alt.addLayout(sec)
        lay.addWidget(self.alt_area)

        # ---- 已登录态：账号名 + 退出/返回 ----
        self.logged_area = self._build_logged_area()
        self.logged_area.hide()
        lay.addWidget(self.logged_area)

        stage_lay.addWidget(self.card, 0, Qt.AlignHCenter)
        stage_lay.addStretch(1)

        root.addWidget(self.stage)

    def _build_logged_area(self) -> QWidget:
        """已登录态内容：账号名 + 退出登录 / 返回（BUG-002）"""
        area = QWidget()
        lay = QVBoxLayout(area)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.logged_user = QLabel("B 站用户")
        self.logged_user.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.logged_user)

        self.logged_note = QLabel("大会员专享画质、4K 与高清弹幕已解锁")
        self.logged_note.setAlignment(Qt.AlignCenter)
        self.logged_note.setWordWrap(True)
        lay.addSpacing(6)
        lay.addWidget(self.logged_note)
        lay.addSpacing(20)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.btn_logout = QPushButton("退出登录")
        self.btn_logout.setObjectName("outline")
        self.btn_logout.setCursor(Qt.PointingHandCursor)
        self.btn_logout.clicked.connect(self.logout_requested.emit)
        row.addWidget(self.btn_logout)
        self.btn_back = QPushButton("返回")
        self.btn_back.setObjectName("primary")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self.back_requested.emit)
        row.addWidget(self.btn_back)
        lay.addLayout(row)
        return area

    # ---------- 流程 ----------
    def refresh_state(self):
        """切回登录页 / 登录态变化时调用：已登录展示账号态，否则展示二维码"""
        if self.settings is not None and self.settings.logged_in:
            self._show_logged()
        else:
            self._show_qr()

    def _show_logged(self):
        self.stop_worker()
        name = (getattr(self.settings, "username", "") if self.settings else "") or "B 站用户"
        self.title.setText(self.TITLE_LOGGED)
        self.subtitle.setText(self.SUB_LOGGED)
        self.qr_area.hide()
        self.alt_area.hide()
        self.logged_area.show()
        self.logged_user.setText(name)
        self.retheme(self.p)

    def _show_qr(self):
        self.title.setText(self.TITLE_LOGIN)
        self.subtitle.setText(self.SUB_LOGIN)
        self.logged_area.hide()
        self.qr_area.show()
        self.alt_area.show()
        # 二维码线程没在跑才重启（避免重复起线程 / 打断正在扫的码）
        if not (self._worker and self._worker.isRunning()):
            self._start()

    def _start(self):
        # 防重入：已有登录线程在跑时不覆盖引用（覆盖 = 销毁运行中的 QThread → 崩溃）
        if self._worker is not None and self._worker.isRunning():
            return
        self._done = False
        self.btn_cookie.setEnabled(False)
        self.qr_label.setText("正在获取二维码…")
        self.qr_label.setPixmap(QPixmap())
        self._set_status("正在获取二维码…", self.p.text_dim)

        self._worker = LoginWorker(self.login)
        self._worker.qr_ready.connect(self._on_qr)
        self._worker.status.connect(self._on_status)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.start()

    def _refresh(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
            if self._worker.isRunning():
                # 旧线程卡在网络请求里没退出：不能覆盖引用，否则直接崩溃
                self._set_status("上一次登录会话正在结束，请稍后重试", self.p.danger_text)
                return
        self._start()

    def _on_qr(self, url: str):
        pix = make_qr_pixmap(url, 168)
        self.qr_label.setFixedSize(pix.width(), pix.height())
        self.qr_label.setPixmap(pix)

    def _on_status(self, st: str, msg: str):
        p = self.p
        if st == "waiting":
            self._set_status("请使用 B 站 App 扫描二维码", p.text_dim)
        elif st == "scanned":
            self._set_status("已扫码，请在手机上确认登录", p.warning_text)
        elif st == "success":
            self._set_status(msg, p.success_text)
        elif st == "expired":
            self._set_status("二维码已过期，请刷新", p.danger_text)
        elif st == "failed":
            self._set_status(msg, p.danger_text)

    def _on_done(self, ok: bool):
        self._done = ok
        self.btn_cookie.setEnabled(True)
        if ok:
            name = getattr(self._worker, "username", "") or ""
            if name and self.settings is not None:
                self.settings.username = name     # 持久化，重启后账号卡仍显示（BUG-005）
            QTimer.singleShot(800, self._finish)

    def _finish(self):
        self.login_succeeded.emit()

    def _import_cookie(self):
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from pathlib import Path
        f, _ = QFileDialog.getOpenFileName(
            self, "选择 cookies.txt", "", "Cookie 文件 (*.txt);;所有文件 (*)")
        if not f:
            return
        content = Path(f).read_text(encoding="utf-8", errors="ignore")
        if "SESSDATA" not in content:
            QMessageBox.warning(self, "无效的 Cookie 文件",
                                "文件中未找到 SESSDATA，请确认是 B 站的 cookies.txt")
            return
        self.login.cookie_file.write_text(content, encoding="utf-8")
        self._set_status("Cookie 已导入，登录成功", self.p.success_text)
        self._done = True
        QTimer.singleShot(600, self._finish)

    def _set_status(self, text, color):
        self.status.setStyleSheet(
            f"color:{color}; font-size:13px; background:transparent; border:none;")
        self.status.setText(text)

    # ---------- 主题 ----------
    def retheme(self, p):
        self.p = p
        top = "#FDEEF3" if not p.is_dark else "#2A1D22"
        bottom = p.bg if not p.is_dark else p.bg
        self.stage.setStyleSheet(f"""
            QFrame#LoginStage {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {top}, stop:1 {bottom});
                border:none;
            }}
            QFrame#LoginStage QLabel {{ background:transparent; border:none; }}
        """)
        self.card.setStyleSheet(f"""
            QFrame#LoginCard {{
                background:{p.surface}; border:1px solid {p.border_card};
                border-radius:14px;
            }}
            QFrame#LoginCard QLabel {{ background:transparent; border:none; }}
        """)
        self.title.setStyleSheet(f"color:{p.text}; font-size:17px; font-weight:600; background:transparent;")
        self.subtitle.setStyleSheet(f"color:{p.text_dim}; font-size:12px; background:transparent;")
        # 已登录态卡片（objectName 同为 LoginCard，卡片底板样式自动复用）
        self.logged_user.setStyleSheet(
            f"color:{p.accent_text}; font-size:15px; font-weight:600; background:transparent;")
        self.logged_note.setStyleSheet(
            f"color:{p.text_dim}; font-size:12px; background:transparent;")
        self.or_label.setStyleSheet(f"color:{p.text_faint}; font-size:11px; background:transparent;")
        self.sec_note.setStyleSheet(f"color:{p.text_faint}; font-size:11px; background:transparent;")
        self.qr_frame.setStyleSheet(f"""
            QFrame#QRFrame {{
                background:{self.p.qr_bg}; border:1px solid {p.border_hi};
                border-radius:10px;
            }}
        """)

    def stop_worker(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            if not self._worker.wait(3000):
                # 线程仍未退出：把引用放进模块级列表保住它，
                # 否则窗口析构时会连带销毁运行中的 QThread 而崩溃。
                _detached_workers.append(self._worker)
