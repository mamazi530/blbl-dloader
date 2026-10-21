"""
下载引擎
封装 yt-dlp 调用，支持进度解析、速度显示、格式选择、字幕下载、
分 P 解析、限速、代理与弹幕下载。
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

# Windows 上隐藏子进程控制台窗口（打包成 GUI 程序后不会闪黑窗）；其它平台为 0
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _bin_names(base: str) -> list:
    """按平台给出可能的二进制文件名（Windows 带 .exe，macOS/Linux 不带）"""
    if sys.platform == "win32":
        return [f"{base}.exe", base]
    return [base, f"{base}.exe"]


def _app_bin_dir() -> Path:
    """项目自带 bin 目录（源码模式与打包模式都适用）"""
    if getattr(sys, "frozen", False):
        # onefile 打包：bin/ 会随程序解压到 sys._MEIPASS（临时目录），
        # 不在 exe 同级 —— 必须优先查这里，否则打包后找不到 yt-dlp / ffmpeg。
        meipass = getattr(sys, "_MEIPASS", None)
        exe_dir = Path(sys.executable).parent
        cands = []
        if meipass:
            cands.append(Path(meipass) / "bin")
        cands += [
            exe_dir / "bin",                              # onedir / Windows 手动放置
            exe_dir.parent / "Resources" / "bin",         # macOS .app 结构
        ]
        for cand in cands:
            if cand.exists():
                return cand
        return Path(meipass) / "bin" if meipass else exe_dir / "bin"
    return Path(__file__).resolve().parent.parent / "bin"


def resource_bin_dir() -> Path:
    """定位 ffmpeg / yt-dlp 所在目录"""
    app_bin = _app_bin_dir()
    for name in _bin_names("ffmpeg") + _bin_names("yt-dlp"):
        if (app_bin / name).exists():
            return app_bin
    home = Path.home() / ".workbuddy" / "binaries"
    return home / "ffmpeg" / "bin"


QUALITY_MAP = {
    "最高画质": "bv*+ba/b",
    "1080P 高码率": "bv*[height<=1080]+ba/b[height<=1080]",
    "1080P": "bv*[height<=1080]+ba/b[height<=1080]",
    "720P": "bv*[height<=720]+ba/b[height<=720]",
    "480P": "bv*[height<=480]+ba/b[height<=480]",
    "360P": "bv*[height<=480]+ba/b[height<=480]",
    "仅音频": "ba/b",
}

# 设置页「默认画质」下拉
QUALITY_CHOICES = ["最高画质", "1080P 高码率", "720P", "480P", "仅音频"]

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def find_ytdlp() -> Optional[Path]:
    """在打包目录、venv 与 PATH 中寻找 yt-dlp 可执行文件"""
    dirs = [
        _app_bin_dir(),
        resource_bin_dir(),
        Path.home() / ".workbuddy" / "binaries" / "python" / "envs" / "default" / "Scripts",
        Path.home() / ".workbuddy" / "binaries" / "python" / "envs" / "default" / "bin",
    ]
    seen = set()
    for d in dirs:
        for name in _bin_names("yt-dlp"):
            c = d / name
            if c in seen:
                continue
            seen.add(c)
            if c.exists():
                return c
    found = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    return Path(found) if found else None


def human_size(n) -> str:
    """字节数 → 可读大小"""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} GB"


def parse_speed(text: str) -> float:
    """'2.4MB/s' → 字节/秒；无法解析返回 0"""
    m = re.search(r"([\d.]+)\s*(B|KB|MB|GB|KiB|MiB|GiB)/s", text, re.I)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2).upper().replace("IB", "B")
    mult = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[unit]
    return val * mult


def human_speed(bps: float) -> str:
    """字节/秒 → 可读速度"""
    if bps <= 0:
        return "—"
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if bps < 1024 or unit == "GB/s":
            return f"{bps:.1f} {unit}"
        bps /= 1024
    return f"{bps:.1f} GB/s"


def parse_size(text: str) -> float:
    """'128.4 MB' → 字节；无法解析返回 0"""
    if not text:
        return 0.0
    m = re.search(r"([\d.]+)\s*(B|KB|MB|GB|KiB|MiB|GiB)", text, re.I)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2).upper().replace("IB", "B")
    return val * {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3}[unit]


def fmt_duration(sec) -> str:
    """秒 → '12:34' 或 '1:02:34'"""
    try:
        sec = int(sec)
    except (TypeError, ValueError):
        return ""
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


_MEDIA_EXTS = {".mp4", ".mkv", ".flv", ".webm", ".mov", ".m4a", ".mp3", ".aac", ".opus"}


def looks_complete(out_path: Optional[Path], min_bytes: int = 200_000) -> bool:
    """成片是否已完整落盘（排除 .part 与过小的残片）"""
    if not out_path:
        return False
    p = Path(out_path)
    try:
        return (p.exists() and p.suffix.lower() in _MEDIA_EXTS
                and not p.name.endswith(".part") and p.stat().st_size >= min_bytes)
    except OSError:
        return False


def resolve_exit_code(rc: int, out_path: Optional[Path]) -> tuple:
    """
    把 yt-dlp 退出码翻译成「任务结果」。
    视频已完整落盘时，非 0 只可能来自后处理（嵌封面/嵌字幕失败等），
    产物本身可用，视为成功，避免「下载成功却显示失败」（BUG-009）。
    返回 (结果码, 备注)；备注非空时应在日志里提示。
    """
    if rc == 0:
        return 0, ""
    if looks_complete(out_path):
        return 0, f"后处理未完成，但视频已保存（{human_size(out_path.stat().st_size)}）"
    return rc, ""


class Downloader:
    """yt-dlp 封装"""

    def __init__(self, ffmpeg_dir: Path = None):
        self.ffmpeg_dir = ffmpeg_dir or resource_bin_dir()
        self.ytdlp = find_ytdlp()
        # 最近一次下载的成片路径（尽力而为，供 UI「打开文件」用）
        self.last_output: Optional[Path] = None
        # bin/ 里应有 ffprobe（download_deps.py 会一并下载）；嵌封面必须 ffmpeg + ffprobe 都在
        self.has_ffprobe = self._detect_ffprobe()

    def _detect_ffprobe(self) -> bool:
        for name in _bin_names("ffprobe"):
            if (Path(self.ffmpeg_dir) / name).exists():
                return True
        return shutil.which("ffprobe") is not None

    def available(self) -> bool:
        return self.ytdlp is not None

    # ---------- 基础 ----------
    def _base_cmd(self, cookie_file: Optional[Path] = None,
                  proxy: Optional[str] = None) -> list:
        cmd = [str(self.ytdlp), "--ffmpeg-location", str(self.ffmpeg_dir)]
        if cookie_file and Path(cookie_file).exists():
            cmd += ["--cookies", str(cookie_file)]
        if proxy:
            cmd += ["--proxy", proxy]
        return cmd

    # ---------- 信息解析 ----------
    def fetch_info(self, url: str, cookie_file: Optional[Path] = None,
                   proxy: Optional[str] = None) -> dict:
        """获取单视频信息（标题、时长、封面、UP 主等）"""
        if not self.ytdlp:
            raise RuntimeError("未找到 yt-dlp")
        cmd = self._base_cmd(cookie_file, proxy) + ["-J", "--no-playlist", url]

        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=90,
                              creationflags=_NO_WINDOW)
        if proc.returncode != 0:
            err = _ANSI.sub("", proc.stderr or "").strip()
            raise RuntimeError(err.splitlines()[-1] if err else "获取视频信息失败")
        return json.loads(proc.stdout)

    def fetch_pages(self, url: str, cookie_file: Optional[Path] = None,
                    proxy: Optional[str] = None) -> dict:
        """
        解析视频分 P 列表（flat 模式，速度快）。
        返回 yt-dlp 的信息 dict，entries 为各 P（单 P 视频返回仅一项）。
        """
        if not self.ytdlp:
            raise RuntimeError("未找到 yt-dlp")
        cmd = self._base_cmd(cookie_file, proxy) + ["-J", "--flat-playlist", url]

        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=120,
                              creationflags=_NO_WINDOW)
        if proc.returncode != 0:
            err = _ANSI.sub("", proc.stderr or "").strip()
            raise RuntimeError(err.splitlines()[-1] if err else "解析分 P 失败")
        return json.loads(proc.stdout)

    def list_formats(self, url: str, cookie_file: Optional[Path] = None) -> str:
        """列出可用格式，供界面展示"""
        if not self.ytdlp:
            raise RuntimeError("未找到 yt-dlp")
        cmd = self._base_cmd(cookie_file) + ["-F", "--no-playlist", url]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=90,
                              creationflags=_NO_WINDOW)
        return _ANSI.sub("", proc.stdout + proc.stderr)

    # ---------- 下载 ----------
    def build_download_cmd(
        self,
        url: str,
        output_dir: Path,
        quality: str = "最高画质",
        cookie_file: Optional[Path] = None,
        want_subtitle: bool = True,
        want_thumbnail: bool = True,
        rate_limit: str = "",
        proxy: Optional[str] = None,
        auto_merge: bool = True,
    ) -> list:
        """拼装 yt-dlp 下载命令（暂停/继续就是重启同一命令，天然断点续传）"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        fmt = QUALITY_MAP.get(quality, "bv*+ba/b")

        cmd = self._base_cmd(cookie_file, proxy) + [
            "-f", fmt,
            "--merge-output-format", "mp4" if auto_merge else "mkv",
            "--no-playlist",
            "--newline",
            "--no-warnings",
            "--concurrent-fragments", "4",
            "-o", str(output_dir / "%(title)s [%(id)s].%(ext)s"),
        ]
        if rate_limit:
            cmd += ["--limit-rate", rate_limit]
        if want_subtitle:
            cmd += ["--write-subs", "--write-auto-subs", "--sub-langs", "zh.*,en.*", "--embed-subs"]
        if want_thumbnail:
            # 只保存封面，不强嵌。嵌封面（--embed-thumbnail）需要 ffmpeg + ffprobe，
            # 缺 ffprobe 时 yt-dlp 末尾报
            # "Unable to embed using ffprobe & ffmpeg" 并以非 0 退出，
            # 此时视频其实已合并完成，会被误判为失败（BUG-009）。有 ffprobe 才嵌。
            cmd += ["--write-thumbnail"]
            if self.has_ffprobe:
                cmd += ["--embed-thumbnail"]
        cmd.append(url)
        return cmd

    def download(
        self,
        url: str,
        output_dir: Path,
        quality: str = "最高画质",
        cookie_file: Optional[Path] = None,
        want_subtitle: bool = True,
        want_thumbnail: bool = True,
        on_log: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[dict], None]] = None,
        cancel_flag: Optional[Callable[[], bool]] = None,
        rate_limit: str = "",
        proxy: Optional[str] = None,
        auto_merge: bool = True,
        cmd: Optional[list] = None,
    ) -> int:
        """
        执行下载。
        返回进程退出码，0 为成功，-2 为用户中止（暂停/取消由调用方区分）。
        传入 cmd 可复用 build_download_cmd 的结果（暂停后继续时保持一致）。
        """
        if not self.ytdlp:
            raise RuntimeError("未找到 yt-dlp")

        if cmd is None:
            cmd = self.build_download_cmd(
                url, output_dir, quality, cookie_file,
                want_subtitle, want_thumbnail, rate_limit, proxy, auto_merge,
            )

        if on_log:
            on_log(f"命令: yt-dlp {' '.join(cmd[1:4])} ...")

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self._last_proc = proc
        self.last_output = None
        out_path: Optional[Path] = None        # 本次下载的成片（合并后路径优先）

        pct_re = re.compile(r"\[download\]\s+(\d+\.\d)%")
        speed_re = re.compile(r"([\d.]+\w?i?B/s)")
        eta_re = re.compile(r"ETA\s+([\d:]+)")
        size_re = re.compile(r"of\s+~?\s*([\d.]+\w?i?B)")

        for line in proc.stdout:
            if cancel_flag and cancel_flag():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                if on_log:
                    on_log("已中止下载（断点已保留，可继续）")
                return -2

            line = _ANSI.sub("", line.rstrip())
            if not line:
                continue

            # 记录成片路径：合并后的路径优先（Merger 一定出现在各分片之后）
            if "[Merger]" in line and " into " in line:
                cand = line.split(" into ", 1)[1].strip().strip('"')
                if cand:
                    out_path = Path(cand)
            elif line.startswith("[download] Destination:") or line.startswith("[ExtractAudio] Destination:"):
                cand = line.split("Destination:", 1)[1].strip().strip('"')
                if cand and not cand.endswith(".part"):
                    out_path = Path(cand)
            elif "has already been downloaded" in line:
                m2 = re.search(r"\[download\]\s+(.+?)\s+has already been downloaded", line)
                if m2:
                    out_path = Path(m2.group(1).strip('"'))

            if on_progress:
                m = pct_re.search(line)
                if m:
                    info = {"percent": float(m.group(1))}
                    s = speed_re.search(line)
                    e = eta_re.search(line)
                    z = size_re.search(line)
                    if s:
                        info["speed"] = s.group(1)
                        info["speed_bps"] = parse_speed(s.group(1))
                    if e:
                        info["eta"] = e.group(1)
                    if z:
                        info["size"] = z.group(1)
                    on_progress(info)
                elif "[Merger]" in line or "[ExtractAudio]" in line:
                    on_progress({"stage": "合并音视频中"})

            if on_log and line.startswith(("[", "[download]  0", "ERROR", "WARNING")):
                on_log(line)

        proc.wait()

        if looks_complete(out_path):
            self.last_output = out_path

        code, note = resolve_exit_code(proc.returncode, out_path)
        if note and on_log:
            on_log(f"提示：{note}")
        return code

    def stop(self):
        """强制终止当前下载进程（暂停的第一步）"""
        proc = getattr(self, "_last_proc", None)
        if proc and proc.poll() is None:
            proc.terminate()

    def check_update(self) -> str:
        """检查 yt-dlp 版本信息"""
        if not self.ytdlp:
            return "未安装"
        try:
            proc = subprocess.run([str(self.ytdlp), "--version"], capture_output=True,
                                  text=True, encoding="utf-8", errors="replace",
                                  timeout=30, creationflags=_NO_WINDOW)
            return proc.stdout.strip()
        except Exception:
            return "未知"


def fetch_danmaku(bvid: str, page: int = 1, output_path: Optional[Path] = None) -> Optional[Path]:
    """
    下载某 P 的 XML 弹幕（仅供详情页「弹幕」开关使用，失败静默返回 None）。
    B站弹幕接口随时可能变动，因此永不抛异常。
    """
    try:
        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
            "Referer": "https://www.bilibili.com/",
        }
        # 1. bvid → cid
        r = requests.get(
            "https://api.bilibili.com/x/player/pagelist",
            params={"bvid": bvid}, headers=headers, timeout=15,
        )
        pages = r.json().get("data") or []
        if not pages or page < 1 or page > len(pages):
            return None
        cid = pages[page - 1]["cid"]

        # 2. cid → 弹幕 XML
        r = requests.get(
            f"https://api.bilibili.com/x/v1/dm/list.so?oid={cid}",
            headers=headers, timeout=20,
        )
        xml = r.content.decode("utf-8", errors="ignore")
        if "<d " not in xml:
            return None

        out = Path(output_path) if output_path else Path.cwd() / f"danmaku_{bvid}_P{page}.xml"
        out.write_text(xml, encoding="utf-8")
        return out
    except Exception:
        return None
