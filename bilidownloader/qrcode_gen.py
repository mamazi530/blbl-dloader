"""二维码生成

独立模块，供主界面与扫码对话框共用，避免循环导入。
"""

import os
import tempfile

from PySide6.QtGui import QPixmap

# 期望显示边长（实际取最接近的整数倍原生尺寸）
QR_TARGET = 168
QR_BOX_MIN, QR_BOX_MAX = 3, 8


def make_qr_pixmap(url: str, target: int = QR_TARGET) -> QPixmap:
    """
    生成二维码位图。

    核心约束：绝不做二次缩放，也不可把 PIL 缓冲直接交给 QImage——
    两者都会让模块变形或像素错乱，手机识别率骤降。

    做法：
    1. 用 box_size=1 探出模块网格（模块数 + 两侧各 2 边框）
    2. 在整数倍 box_size 中选最接近 target 的，原生渲染
    3. 经 PNG 文件编解码交给 Qt，保证像素完全确定

    实测：经PNG 后图像唯一色值恰为 2（纯黑白），边缘锐利可扫。
    """
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L

    def render(box_size: int):
        qr = qrcode.QRCode(error_correction=ERROR_CORRECT_L,
                           box_size=box_size, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        return qr.make_image(fill_color="black", back_color="white").convert("RGB")

    units = render(1).width
    best_box = min(
        range(QR_BOX_MIN, QR_BOX_MAX + 1),
        key=lambda b: abs(units * b - target),
    )
    img = render(best_box)

    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        img.save(tmp, format="PNG")
        return QPixmap(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass