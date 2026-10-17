"""
皮肤系统：窗口背景皮肤。

两类皮肤：
- 内置预设（preset）：程序生成的渐变，无需任何素材文件，开箱即用
- 本地图片（image）：用户从磁盘选择 / 拖拽进窗口，复制进 data/skins/ 统一管理

皮肤文件与清单都放在 DATA_DIR/skins/（data/ 已被 .gitignore 排除，不会入库）。
所有位图生成都带缓存，窗口拖动缩放时不会重复解码大图。
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath, QPixmap, QRadialGradient,
)

from .app_settings import DATA_DIR

SKIN_DIR = DATA_DIR / "skins"
MANIFEST = SKIN_DIR / "manifest.json"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
# 文件选择对话框用的过滤器
FILE_FILTER = "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;所有文件 (*)"

NO_SKIN = ""     # skin_id 为空 = 不使用皮肤


# ------------------------------------------------------------------
# 内置预设（渐变：起点色 → 中间色 → 终点色，另加两处柔和光晕）
# ------------------------------------------------------------------
@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    colors: tuple
    glow: tuple = ()        # ((x_ratio, y_ratio, color, alpha), ...)


PRESETS: tuple = (
    Preset("pink", "粉雾", ("#FFE3EE", "#FFB8D2", "#F4719C"),
           ((0.18, 0.22, "#FFFFFF", 0.45), (0.86, 0.78, "#FF6FA5", 0.30))),
    Preset("night", "夜空", ("#1B2035", "#2A2E52", "#0E1120"),
           ((0.22, 0.18, "#6C7BFF", 0.35), (0.80, 0.82, "#00D2FF", 0.18))),
    Preset("aurora", "极光", ("#0F2A2E", "#1E6F6A", "#123A4C"),
           ((0.30, 0.30, "#7CFFCB", 0.28), (0.75, 0.70, "#3FA9F5", 0.22))),
    Preset("dawn", "晨曦", ("#FFF1E6", "#FFD6C0", "#FFB4A2"),
           ((0.20, 0.25, "#FFFFFF", 0.50), (0.82, 0.75, "#FF9E7A", 0.25))),
    Preset("ink", "水墨", ("#E9EDF2", "#C9D2DE", "#8E9AAE"),
           ((0.25, 0.20, "#FFFFFF", 0.35), (0.78, 0.80, "#4A5A70", 0.20))),
    Preset("bamboo", "竹青", ("#EAF6EF", "#BFE3CE", "#6FB894"),
           ((0.24, 0.26, "#FFFFFF", 0.40), (0.80, 0.72, "#2E8B6F", 0.22))),
)


@dataclass
class Skin:
    id: str
    name: str
    kind: str                      # "preset" | "image"
    file: str = ""                 # image：skins/ 下的文件名
    colors: tuple = ()             # preset：渐变色
    glow: tuple = ()
    added: float = field(default=0.0)

    @property
    def is_custom(self) -> bool:
        return self.kind == "image"

    @property
    def path(self) -> Path:
        return SKIN_DIR / self.file


# ------------------------------------------------------------------
# 清单读写
# ------------------------------------------------------------------
def _load_manifest() -> list:
    try:
        if MANIFEST.exists():
            data = json.loads(MANIFEST.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict) and d.get("id")]
    except Exception:
        pass
    return []


def _save_manifest(items: list) -> None:
    try:
        SKIN_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def preset_skins() -> list:
    return [Skin(id=p.id, name=p.name, kind="preset",
                 colors=p.colors, glow=p.glow) for p in PRESETS]


def custom_skins() -> list:
    out = []
    for d in _load_manifest():
        out.append(Skin(id=d.get("id", ""), name=d.get("name", "自定义"),
                        kind="image", file=d.get("file", ""),
                        added=float(d.get("added", 0))))
    return out


def list_skins() -> list:
    """内置预设在前，用户导入在后"""
    return preset_skins() + custom_skins()


def get(skin_id: str) -> Skin | None:
    if not skin_id:
        return None
    for s in list_skins():
        if s.id == skin_id:
            return s
    return None


def install_image(src: str | Path) -> Skin | None:
    """
    导入一张本地图片为皮肤：复制进 skins/ 并登记清单。
    失败（不是图片 / 无法读取 / 写入失败）返回 None。
    """
    src = Path(src)
    if not src.exists():
        return None
    if src.suffix.lower() not in IMAGE_EXTS:
        return None
    pm = QPixmap(str(src))
    if pm.isNull():
        return None

    try:
        SKIN_DIR.mkdir(parents=True, exist_ok=True)
        stem = "".join(ch for ch in src.stem if ch not in '\\/:*?"<>|')[:24] or "skin"
        sid = f"img_{int(time.time() * 1000) % 10**9}"
        dest = SKIN_DIR / f"{sid}{src.suffix.lower()}"
        shutil.copy2(src, dest)
        if QPixmap(str(dest)).isNull():
            dest.unlink(missing_ok=True)
            return None
    except Exception:
        return None

    items = _load_manifest()
    items.append({"id": sid, "name": stem, "file": dest.name, "added": time.time()})
    _save_manifest(items)
    return Skin(id=sid, name=stem, kind="image", file=dest.name, added=time.time())


def remove(skin_id: str) -> bool:
    """删除自定义皮肤（内置预设不可删）"""
    items = _load_manifest()
    rest, hit = [], None
    for d in items:
        if d.get("id") == skin_id:
            hit = d
        else:
            rest.append(d)
    if hit is None:
        return False
    try:
        (SKIN_DIR / hit.get("file", "")).unlink(missing_ok=True)
    except Exception:
        pass
    _save_manifest(rest)
    return True


# ------------------------------------------------------------------
# 位图生成（带缓存）
# ------------------------------------------------------------------
_pix_cache: dict = {}
_CACHE_MAX = 48


def _cache_put(key, pm: QPixmap) -> QPixmap:
    if len(_pix_cache) > _CACHE_MAX:
        _pix_cache.clear()
    _pix_cache[key] = pm
    return pm


def clear_cache() -> None:
    _pix_cache.clear()


def _gradient(skin: Skin, w: int, h: int) -> QPixmap:
    pm = QPixmap(max(2, w), max(2, h))
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)

    g = QLinearGradient(QPointF(0, 0), QPointF(w, h))
    colors = skin.colors or ("#FFFFFF", "#EEEEEE")
    n = max(1, len(colors) - 1)
    for i, c in enumerate(colors):
        g.setColorAt(i / n, QColor(c))
    p.fillRect(0, 0, w, h, g)

    for gx, gy, color, alpha in (skin.glow or ()):
        radius = max(w, h) * 0.55
        rg = QRadialGradient(QPointF(w * gx, h * gy), radius)
        c = QColor(color)
        c.setAlphaF(float(alpha))
        rg.setColorAt(0.0, c)
        c2 = QColor(color)
        c2.setAlphaF(0.0)
        rg.setColorAt(1.0, c2)
        p.fillRect(0, 0, w, h, rg)
    p.end()
    return pm


def _fit_pixmap(pm: QPixmap, w: int, h: int, fit: str) -> QPixmap:
    if fit == "stretch":
        return pm.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    if fit == "contain":
        return pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    # cover：等比放大填满后居中裁剪
    if pm.width() <= 0 or pm.height() <= 0:
        return pm
    scaled = pm.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    if scaled.width() > w:
        x = (scaled.width() - w) // 2
        return scaled.copy(x, 0, w, h)
    if scaled.height() > h:
        y = (scaled.height() - h) // 2
        return scaled.copy(0, y, w, h)
    return scaled


def background(skin_id: str, w: int, h: int, fit: str = "cover") -> QPixmap | None:
    """按窗口尺寸生成背景位图；无皮肤/失败返回 None"""
    skin = get(skin_id)
    if skin is None:
        return None
    key = ("bg", skin.id, w, h, fit)
    if key in _pix_cache:
        return _pix_cache[key]

    if skin.kind == "preset":
        pm = _gradient(skin, w, h)
        return _cache_put(key, pm)

    src = QPixmap(str(skin.path))
    if src.isNull():
        return None
    return _cache_put(key, _fit_pixmap(src, w, h, fit))


def thumbnail(skin: Skin, w: int = 96, h: int = 54, radius: int = 7) -> QPixmap:
    """皮肤选择用的圆角缩略图（角上透明，方便叠在任意底色上）"""
    key = ("thumb", skin.id, w, h, radius)
    if key in _pix_cache:
        return _pix_cache[key]

    if skin.kind == "preset":
        base = _gradient(skin, w, h)
    else:
        src = QPixmap(str(skin.path)) if skin.file else QPixmap()
        if src.isNull():
            # 无皮肤 / 图片丢失：画一个占位斜纹
            base = QPixmap(w, h)
            base.fill(QColor("#E9EBEE"))
            pp = QPainter(base)
            pp.setRenderHint(QPainter.Antialiasing)
            pp.setPen(QColor("#C6CAD2"))
            pp.drawLine(0, h, w, 0)
            pp.end()
        else:
            base = _fit_pixmap(src, w, h, "cover")

    out = QPixmap(w, h)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.setClipPath(path)
    p.drawPixmap(0, 0, base)
    p.end()
    return _cache_put(key, out)


def blur_pixmap(pm: QPixmap, radius: int) -> QPixmap:
    """
    快速柔化（降采样再放大，近似高斯模糊）。
    Qt 无内置的 QPixmap 模糊 API，用 QGraphicsBlurEffect 需要挂到控件上，
    且会在边缘产生透明溢出，这里用缩放法更可控、性能也更好。
    """
    r = max(0, min(30, int(radius)))
    if r == 0 or pm.isNull():
        return pm
    k = max(2, r // 2 + 1)
    w, h = max(1, pm.width() // k), max(1, pm.height() // k)
    small = pm.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return small.scaled(pm.width(), pm.height(),
                        Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
