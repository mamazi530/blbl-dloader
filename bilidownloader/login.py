"""
B站登录模块
扫码登录（二维码）方式。登录成功后导出 Netscape 格式 cookies.txt 供 yt-dlp 使用，
从而解锁 1080P 及以上清晰度。

接口要点（已实测）：
- poll 接口外层 code 恒为 0，仅代表"请求成功"
- 真实登录状态在 data.code 内层：
    0     = 登录成功（cookie 从 data.url 的 query 参数中提取）
    86101 = 未扫码
    86090 = 已扫码，待手机确认
    86038 = 二维码过期
"""

import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Referer": "https://www.bilibili.com/",
    "Origin": "https://www.bilibili.com",
}

GEN_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
POLL_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"

# data.code 语义
ST_SUCCESS = 0
ST_WAIT = 86101
ST_CONFIRM = 86090
ST_EXPIRED = 86038


class BilibiliLogin:
    """B站扫码登录器"""

    def __init__(self, cookie_dir: Path):
        self.cookie_dir = Path(cookie_dir)
        self.cookie_dir.mkdir(parents=True, exist_ok=True)
        self.cookie_file = self.cookie_dir / "cookies.txt"
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.username = ""
        self._auth_cookies: dict[str, str] = {}

    def generate_qr(self) -> tuple[str, str]:
        """生成登录二维码，返回 (二维码内容, qrcode_key)"""
        resp = self.session.get(GEN_URL, timeout=15)
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"生成二维码失败: {data.get('message')}")
        payload = data["data"]
        return payload["url"], payload["qrcode_key"]

    def _parse_auth_cookies(self, url: str) -> dict[str, str]:
        """
        从登录成功返回的跳转链接中解析 cookie。
        该链接形如 https://passport.biligame.com/...?
            DedeUserID=xxx&Expires=xxx&SESSDATA=xxx&bili_jct=xxx
        """
        out: dict[str, str] = {}
        if not url:
            return out
        query = urlparse(url).query
        if not query:
            return out
        for k, v in parse_qsl(query, keep_blank_values=False):
            if k in ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5",
                     "sid", "buvid3", "buvid4"):
                out[k] = v

        # 合并会话 cookie（buvid3 等可能来自 Set-Cookie）
        for c in self.session.cookies:
            if c.name not in out:
                out[c.name] = c.value
        return out

    def poll(self, qrcode_key: str) -> dict:
        """
        轮询扫码状态。
        返回 {status, message, username}
        status: waiting | scanned | success | expired | failed
        """
        resp = self.session.get(POLL_URL, params={"qrcode_key": qrcode_key}, timeout=15)
        outer = resp.json()

        # 外层非 0 表示请求本身出错
        if outer.get("code") != 0:
            return {
                "status": "failed",
                "message": f"请求失败: {outer.get('message')}",
                "username": "",
            }

        payload = outer.get("data", {})
        inner = payload.get("code")
        message = payload.get("message", "")

        if inner == ST_SUCCESS:
            cookies = self._parse_auth_cookies(payload.get("url", ""))
            if "SESSDATA" not in cookies:
                return {
                    "status": "failed",
                    "message": "登录异常：未获取到登录凭证，请重试",
                    "username": "",
                }
            self._auth_cookies = cookies
            self.username = payload.get("uname", "") or ""
            return {
                "status": "success",
                "message": "登录成功",
                "username": self.username,
            }

        if inner == ST_WAIT:
            return {"status": "waiting", "message": "请用 B 站 App 扫描二维码", "username": ""}
        if inner == ST_CONFIRM:
            return {"status": "scanned", "message": "已扫码，请在手机上确认", "username": ""}
        if inner == ST_EXPIRED:
            return {"status": "expired", "message": "二维码已过期，请重新获取", "username": ""}
        return {"status": "failed", "message": message or "登录失败", "username": ""}

    def wait_login(self, qrcode_key: str, on_update=None, interval: float = 2.0,
                   should_stop=None, timeout: int = 180) -> dict:
        """循环轮询直到成功/过期/失败/超时"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if should_stop and should_stop():
                return {"status": "cancelled", "message": "已取消登录", "username": ""}
            try:
                result = self.poll(qrcode_key)
            except Exception as exc:
                result = {"status": "waiting", "message": f"网络重试中…", "username": ""}
                if on_update:
                    on_update(result)
                time.sleep(interval)
                continue

            if on_update:
                on_update(result)
            if result["status"] in ("success", "expired", "failed"):
                return result
            time.sleep(interval)

        return {"status": "failed", "message": "二维码已过期，请重新获取", "username": ""}

    def export_cookies(self) -> Path:
        """导出 Netscape 格式 cookies.txt，供 yt-dlp --cookies 使用"""
        lines = [
            "# Netscape HTTP Cookie File",
            "# Generated by Bilibili Downloader",
            "",
        ]
        # 登录态 cookie 在 .bilibili.com，其余辅助 cookie 用宽泛域
        for name, value in self._auth_cookies.items():
            lines.append("\t".join([
                ".bilibili.com", "TRUE", "/", "TRUE", "0", name, value
            ]))
        # 附加 buvid 等设备标识，提升稳定性
        for c in self.session.cookies:
            if c.name in ("buvid3", "buvid4", "b_nut", "b_lsid", "buvid_fp"):
                lines.append("\t".join([
                    ".bilibili.com", "TRUE", "/", "FALSE", "0", c.name, c.value
                ]))

        self.cookie_file.write_text("\n".join(lines), encoding="utf-8")
        return self.cookie_file

    def is_logged_in(self) -> bool:
        """检查本地 cookie 文件是否含有效凭证（SESSDATA 必须有实际值）"""
        if not self.cookie_file.exists():
            return False
        for line in self.cookie_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.strip().split("\t")
            # Netscape 格式: domain, flag, path, secure, expires, name, value
            if len(parts) == 7 and parts[5] == "SESSDATA" and parts[6]:
                return True
        return False