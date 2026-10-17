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


class LoginWorker(QThread):
    """生成二维码并轮询扫码状态（复用 login.py）"""
    qr_ready = Signal(str)
    status = Signal(str, str)      # status, message
    finished_ok = Signal(bool)

    def __init__(self, login, parent=None):
        super().__init__(parent)
        self.login = login
        self._stop = False

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
                self.login.export_cookies()
                self.status.emit("success", f'登录成功 · {result["username"] or "凭证已保存"}')
            else:
                self.status.emit(result["status"], result["message"])
            self.finished_ok.emit(ok)
        except Exception as exc:
            self.status.emit("failed", f"登录异常: {exc}")
            self.finished_ok.emit(False)


class LoginView(QWidget):
    login_succeeded = Signal()

    def __init__(self, ctx, palette):
        super().__init__()
        self.ctx = ctx
        self.p = palette
        self.login = ctx["login"]
        self._worker = None
        self._done = False
        self._build()
        self.retheme(palette)
        self._start()

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

        self.title = QLabel("登录 B 站账号")
        self.title.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.title)

        self.subtitle = QLabel("登录后可下载 4K 高码率、大会员专享视频与高清弹幕")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setWordWrap(True)
        lay.addSpacing(6)
        lay.addWidget(self.subtitle)
        lay.addSpacing(18)

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
        lay.addLayout(center)
        lay.addSpacing(14)

        self.status = QLabel("请使用 B 站 App 扫描二维码")
        self.status.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.status)
        lay.addSpacing(14)

        # 备选登录
        or_row = QHBoxLayout()
        or_row.addStretch(1)
        self.or_label = QLabel("或")
        or_row.addWidget(self.or_label)
        or_row.addStretch(1)
        lay.addLayout(or_row)
        lay.addSpacing(8)

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
        lay.addLayout(btns)
        lay.addSpacing(14)

        # 安全提示
        sec = QHBoxLayout()
        sec.addStretch(1)
        shield = QLabel()
        shield.setPixmap(icon_pixmap("shield-check", "#A0A6AE", 14))
        sec.addWidget(shield)
        self.sec_note = QLabel("登录信息仅保存在本机，不会上传任何服务器")
        sec.addWidget(self.sec_note)
        sec.addStretch(1)
        lay.addLayout(sec)

        stage_lay.addWidget(self.card, 0, Qt.AlignHCenter)
        stage_lay.addStretch(1)

        root.addWidget(self.stage)

    # ---------- 流程 ----------
    def _start(self):
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
        self.or_label.setStyleSheet(f"color:{p.text_faint}; font-size:11px; background:transparent;")
        self.sec_note.setStyleSheet(f"color:{p.text_faint}; font-size:11px; background:transparent;")
        self.qr_frame.setStyleSheet(f"""
            QFrame#QRFrame {{
                background:{self.p.qr_bg}; border:1px solid {p.border_hi};
                border-radius:10px;
            }}
        """)

    def refresh_state(self):
        """从其他页面切回时，如已登录则提示"""
        pass

    def stop_worker(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(3000)
