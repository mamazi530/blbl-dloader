"""
扫码登录对话框
独立窗口显示二维码，尺寸充裕不会被裁切。
支持刷新二维码、取消登录。
"""

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from .login import BilibiliLogin
from . import theme
from .qrcode_gen import make_qr_pixmap


class _LoginThread(QThread):
    """在对话框内执行扫码轮询"""

    qr_ready = Signal(str)          # 二维码内容（URL）
    status = Signal(str, str)       # status, message
    finished_ok = Signal(bool)

    def __init__(self, login: BilibiliLogin, parent=None):
        super().__init__(parent)
        self.login = login
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            url, key = self.login.generate_qr()
            self.qr_ready.emit(url)

            def on_update(res):
                self.status.emit(res["status"], res["message"])

            result = self.login.wait_login(
                key, on_update=on_update,
                should_stop=lambda: self._stop,
                timeout=180,
            )
            ok = result["status"] == "success"
            if ok:
                self.login.export_cookies()
                self.status.emit("success",
                                 f'登录成功 · {result["username"] or "账号已保存"}')
            else:
                self.status.emit(result["status"], result["message"])
            self.finished_ok.emit(ok)
        except Exception as exc:
            self.status.emit("failed", f"登录异常: {exc}")
            self.finished_ok.emit(False)


class QRLoginDialog(QDialog):
    """二维码登录对话框"""

    def __init__(self, login: BilibiliLogin, palette: theme.Palette, parent=None):
        super().__init__(parent)
        self.login = login
        self.p = palette
        self._thread = None
        self._done = False

        self.setWindowTitle("扫码登录 B 站")
        self.setModal(True)
        self.setFixedWidth(392)
        self.setStyleSheet(theme.stylesheet(palette))

        self._build()
        self._start()

    # ---------- UI ----------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 26, 30, 22)
        root.setSpacing(0)

        title = QLabel("扫码登录")
        title.setStyleSheet(
            f"color:{self.p.text}; font-size:17px; font-weight:600;"
            f"background:transparent; border:none;"
        )
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        sub = QLabel("请使用 B 站手机客户端扫描下方二维码")
        sub.setStyleSheet(
            f"color:{self.p.text_dim}; font-size:12px;"
            f"background:transparent; border:none;"
        )
        sub.setAlignment(Qt.AlignCenter)
        root.addSpacing(5)
        root.addWidget(sub)
        root.addSpacing(18)

        # 二维码容器：固定尺寸并显式设置最小/最大，避免被布局压缩
        self.qr_frame = QFrame()
        self.qr_frame.setStyleSheet(
            f"QFrame {{ background:{self.p.qr_bg}; border:1px solid {self.p.border_hi};"
            f"border-radius:10px; }}"
        )
        frame_lay = QVBoxLayout(self.qr_frame)
        frame_lay.setContentsMargins(10, 10, 10, 10)
        frame_lay.setAlignment(Qt.AlignCenter)

        self.qr_label = QLabel("正在获取二维码…")
        self.qr_label.setAlignment(Qt.AlignCenter)
        self.qr_label.setScaledContents(False)
        self.qr_label.setFixedSize(220, 220)
        self.qr_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        frame_lay.addWidget(self.qr_label, 0, Qt.AlignCenter)

        # 居中显示容器
        qr_center = QHBoxLayout()
        qr_center.setContentsMargins(0, 0, 0, 0)
        qr_center.addStretch(1)
        qr_center.addWidget(self.qr_frame)
        qr_center.addStretch(1)
        root.addLayout(qr_center)
        root.addSpacing(18)

        self.status_label = QLabel("准备中…")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(20)
        self.status_label.setStyleSheet(
            f"color:{self.p.text}; font-size:13px;"
            f"background:transparent; border:none;"
        )
        root.addWidget(self.status_label)

        # 倒计时/过期进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)          # 忙碌指示器
        self.progress.setFixedHeight(3)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            f"QProgressBar {{ background:{self.p.surface_hi}; border:none;"
            f"border-radius:2px; }} QProgressBar::chunk {{ background:{self.p.accent};"
            f"border-radius:2px; }}"
        )
        root.addSpacing(10)
        root.addWidget(self.progress)

        root.addSpacing(16)

        # 底部按钮
        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn_refresh = QPushButton("刷新二维码")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._on_refresh)
        btns.addWidget(self.btn_refresh)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("ghost")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setMinimumHeight(32)
        self.btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_cancel)
        root.addLayout(btns)

        self._set_status("等待扫码…", self.p.text_dim)

    def _set_status(self, text, color=None):
        color = color or self.p.text
        self.status_label.setStyleSheet(
            f"color:{color}; font-size:13px; background:transparent; border:none;"
        )
        self.status_label.setText(text)

    # ---------- 流程 ----------
    def _start(self):
        self._done = False
        self.progress.setVisible(True)
        self.btn_refresh.setEnabled(False)
        self._set_status("正在获取二维码…", self.p.text_dim)
        self.qr_label.setText("正在获取二维码…")
        self.qr_label.setPixmap(QPixmap())

        self._thread = _LoginThread(self.login, self)
        self._thread.qr_ready.connect(self._on_qr)
        self._thread.status.connect(self._on_status)
        self._thread.finished_ok.connect(self._on_done)
        self._thread.start()

    def _on_qr(self, url: str):
        pix = make_qr_pixmap(url, 220)
        # 明确按二维码实际像素设置控件尺寸，杜绝缩放与裁切
        self.qr_label.setFixedSize(pix.width(), pix.height())
        self.qr_label.setPixmap(pix)
        self.qr_label.setScaledContents(False)

    def _on_status(self, status, message):
        color_map = {
            "waiting": self.p.text_dim,
            "scanned": self.p.warning,
            "success": self.p.success,
            "expired": self.p.danger,
            "failed": self.p.danger,
        }
        if status == "waiting":
            self._set_status("等待扫码…", self.p.text_dim)
        elif status == "scanned":
            self._set_status("已扫码，请在手机上确认登录", self.p.warning)
        elif status == "success":
            self._set_status(message, self.p.success)
        elif status == "expired":
            self._set_status("二维码已过期，请点击刷新", self.p.danger)
            self.progress.setVisible(False)
            self.btn_refresh.setEnabled(True)
        elif status == "failed":
            self._set_status(message, self.p.danger)
            self.progress.setVisible(False)
            self.btn_refresh.setEnabled(True)

    def _on_done(self, ok):
        self._done = ok
        self.progress.setVisible(False)
        if ok:
            QTimer.singleShot(700, self.accept)
        else:
            self.btn_refresh.setEnabled(True)

    def _on_refresh(self):
        if self._thread and self._thread.isRunning():
            self._thread.stop()
            self._thread.wait(3000)
        self._start()

    # ---------- 关闭 ----------
    def succeeded(self) -> bool:
        """登录是否成功。

        命名注意：不能叫 done()，那会覆盖 QDialog.done(int) 导致关闭时崩溃。
        """
        return self._done

    def reject(self):
        if self._thread and self._thread.isRunning():
            self._thread.stop()
            self._thread.wait(3000)
        super().reject()

    def closeEvent(self, event):
        if self._thread and self._thread.isRunning():
            self._thread.stop()
            self._thread.wait(3000)
        event.accept()


def QTimer_singleShot_close(dlg, delay_ms):
    """登录成功后延迟关闭对话框，让用户看到成功提示"""
    from PySide6.QtCore import QTimer
    QTimer.singleShot(delay_ms, dlg.accept)