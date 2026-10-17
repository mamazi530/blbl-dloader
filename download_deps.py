"""
下载运行所需的第三方二进制（yt-dlp / ffmpeg）到 bin/。

这些文件体积大（约 87MB），不适合放进版本库，
新环境首次运行时执行本脚本即可准备。

按当前平台自动选择对应的构建：
    Windows → yt-dlp.exe + ffmpeg.exe（gyan.dev essentials 构建）
    macOS   → yt-dlp（官方 macOS 构建）+ ffmpeg（evermeet.cx 构建）
    Linux   → yt-dlp（官方二进制）；ffmpeg 请用系统包管理器安装

用法：
    python download_deps.py
    python download_deps.py --force      # 已存在也重新下载
"""

import json
import shutil
import stat
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

BIN_DIR = Path(__file__).parent / "bin"

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

YTDLP_BASE = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/"
YTDLP_ASSETS = {
    "win32": ("yt-dlp.exe", "yt-dlp.exe"),
    "darwin": ("yt-dlp_macos", "yt-dlp"),
    "linux": ("yt-dlp", "yt-dlp"),
}

FFMPEG_WIN_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_MAC_ZIP = "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"

FFMPEG_MIN_SIZE = 15 * 1024 * 1024   # 压缩包下限，过小说明是错误页面


def _report_hook(count, block_size, total_size):
    if total_size > 0:
        done = min(count * block_size, total_size)
        pct = done * 100 // total_size
        mb = done / 1024 / 1024
        print(f"\r  下载中... {mb:6.1f} MB  {pct:3d}%", end="", flush=True)


def _cleanup(path: Path):
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def _make_executable(path: Path):
    """非 Windows 平台必须加可执行位，否则 yt-dlp / ffmpeg 无法运行"""
    if not IS_WIN:
        try:
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        except OSError:
            pass


def _target_name(base: str) -> str:
    return f"{base}.exe" if IS_WIN else base


# ------------------------------------------------------------------
# yt-dlp
# ------------------------------------------------------------------
def download_yt_dlp(force: bool = False) -> bool:
    asset, _ = YTDLP_ASSETS.get(sys.platform, YTDLP_ASSETS["linux"])
    dest = BIN_DIR / _target_name("yt-dlp")
    if dest.exists() and dest.stat().st_size > 5 * 1024 * 1024 and not force:
        print(f"[跳过] {dest.name} 已存在 ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
        _make_executable(dest)
        return True

    print(f"[下载] yt-dlp（{asset}）...")
    try:
        urllib.request.urlretrieve(YTDLP_BASE + asset, dest)
    except Exception as exc:
        print(f"  失败: {exc}")
        return False
    _make_executable(dest)
    print(f"  完成 ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
    return True


# ------------------------------------------------------------------
# ffmpeg
# ------------------------------------------------------------------
def _download_zip(url: str, tmp_zip: Path) -> bool:
    print("[下载] ffmpeg（约 80 MB，耐心等待）...")
    try:
        urllib.request.urlretrieve(url, tmp_zip, _report_hook)
    except Exception as exc:
        print(f"\n  下载失败: {exc}")
        _cleanup(tmp_zip)
        return False
    print()
    size = tmp_zip.stat().st_size
    print(f"  压缩包 {size / 1024 / 1024:.1f} MB")
    if size < FFMPEG_MIN_SIZE:
        print("  文件过小，可能是错误页面而非压缩包")
        _cleanup(tmp_zip)
        return False
    return True


def _pick_member(names: list) -> str | None:
    wanted = "ffmpeg.exe" if IS_WIN else "ffmpeg"
    for n in names:
        if Path(n).name.lower() == wanted:
            return n
    for n in names:
        if Path(n).name.lower().startswith("ffmpeg"):
            return n
    return None


def download_ffmpeg(force: bool = False) -> bool:
    dest = BIN_DIR / _target_name("ffmpeg")
    if dest.exists() and dest.stat().st_size > 20 * 1024 * 1024 and not force:
        print(f"[跳过] {dest.name} 已存在 ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
        _make_executable(dest)
        return True

    if not (IS_WIN or IS_MAC):
        print("[提示] Linux 请用系统包管理器安装 ffmpeg：")
        print("    Debian/Ubuntu: sudo apt install ffmpeg")
        print("    Fedora:        sudo dnf install ffmpeg")
        print("    Arch:          sudo pacman -S ffmpeg")
        if shutil.which("ffmpeg"):
            print("  检测到系统已安装 ffmpeg，可直接使用。")
            return True
        return False

    tmp_zip = BIN_DIR / "_ffmpeg_tmp.zip"
    url = FFMPEG_WIN_URL if IS_WIN else FFMPEG_MAC_ZIP
    if not _download_zip(url, tmp_zip):
        return False

    print("  解压中...")
    found = False
    try:
        with zipfile.ZipFile(tmp_zip) as zf:
            names = [n for n in zf.namelist() if not n.endswith("/")]
            member = _pick_member(names)
            if member:
                with zf.open(member) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                found = True
    except Exception as exc:
        print(f"  解压失败: {exc}")
    _cleanup(tmp_zip)

    if not found:
        print("  压缩包中未找到 ffmpeg 可执行文件")
        return False

    _make_executable(dest)
    print(f"  完成 ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
    return True


# ------------------------------------------------------------------
# 版本清单（便于"exe 与 bin 成对回滚"）
# ------------------------------------------------------------------
def write_manifest():
    try:
        items = {}
        for f in sorted(BIN_DIR.glob("*")):
            if f.is_file() and f.suffix not in (".json", ".zip"):
                items[f.name] = {
                    "size": f.stat().st_size,
                    "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
        (BIN_DIR / "VERSION.json").write_text(
            json.dumps({"platform": sys.platform, "files": items},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception:
        pass


def main():
    import argparse
    ap = argparse.ArgumentParser(description="准备 yt-dlp 与 ffmpeg")
    ap.add_argument("--force", action="store_true", help="已存在也重新下载")
    args = ap.parse_args()

    BIN_DIR.mkdir(parents=True, exist_ok=True)
    print(f"平台: {sys.platform}")
    print(f"依赖目录: {BIN_DIR}\n")

    ok_ytdlp = download_yt_dlp(args.force)
    ok_ffmpeg = download_ffmpeg(args.force)
    write_manifest()

    print()
    if ok_ytdlp and ok_ffmpeg:
        print("依赖准备完成，可以运行: python run.py")
        return 0

    print("部分依赖缺失。程序仍可启动，但下载功能会报错。")
    print("也可改用 pip 安装 yt-dlp 后由代码调用：")
    print("    pip install -r requirements.txt")
    return 1


if __name__ == "__main__":
    sys.exit(main())
