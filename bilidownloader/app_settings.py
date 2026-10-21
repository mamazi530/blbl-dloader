"""
应用设置：持久化到 data/settings.json，全应用共享一份实例。
"""

import json
import sys
from pathlib import Path

from . import theme

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
CONFIG_FILE = DATA_DIR / "settings.json"

DEFAULTS = {
    "theme": theme.THEME_AUTO,
    "download_dir": str(Path.home() / "Downloads" / "Bilibili"),
    "max_concurrent": 3,
    "auto_merge": True,
    "notify_done": False,
    "default_quality": "1080P 高码率",
    "rate_limit": "",                # '' = 不限速；'500K' / '2M' …
    "proxy_mode": "none",            # none | system | custom
    "proxy_url": "",                 # custom 模式下的代理地址
    # ---------- 皮肤（窗口背景） ----------
    "skin_id": "",                   # '' = 不使用皮肤；预设 id 或 img_xxx
    "skin_alpha": 88,                # 面板不透明度(%)，越低壁纸越明显
    "skin_blur": 0,                  # 背景柔化半径 0-30
    "skin_dim": 28,                  # 遮罩强度(%)，提升文字可读性
    "skin_fit": "cover",             # cover | contain | stretch
    # ---------- 账号（BUG-005：用户名需持久化，重启后不然退回"B 站用户"） ----------
    "username": "",
}


class AppSettings:
    """带属性访问的设置存储"""

    def __init__(self):
        self._data = dict(DEFAULTS)
        self.load()

    # ---------- 读写 ----------
    def load(self):
        try:
            if CONFIG_FILE.exists():
                saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(saved, dict):
                    self._data.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except Exception:
            pass

    def save(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ---------- 访问 ----------
    def get(self, key: str, default=None):
        return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    # ---------- 派生 ----------
    @property
    def cookie_file(self) -> Path:
        return DATA_DIR / "cookies.txt"

    @property
    def logged_in(self) -> bool:
        return self.cookie_file.exists() and "SESSDATA" in self.cookie_file.read_text(
            encoding="utf-8", errors="ignore")

    def logout(self):
        try:
            self.cookie_file.unlink(missing_ok=True)
        except Exception:
            pass
        self.set("username", "")

    @property
    def username(self) -> str:
        """登录用户名（持久化在 settings.json，重启后保留）"""
        return self.get("username", "") or ""

    @username.setter
    def username(self, v: str):
        self.set("username", v or "")

    def proxy_url(self):
        """None = 不传 --proxy（走系统代理）；'' = 显式禁用代理；其他 = 自定义地址"""
        mode = self.get("proxy_mode", "none")
        if mode == "system":
            return None
        if mode == "custom":
            return self.get("proxy_url", "") or None
        return ""   # 不使用代理

    @property
    def theme_mode(self) -> str:
        return self.get("theme", theme.THEME_AUTO)

    @theme_mode.setter
    def theme_mode(self, v: str):
        self.set("theme", v)
