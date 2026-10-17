"""
一键构建当前平台的发布产物。

用法：
    python build.py                # 完整构建（清理 -> PyInstaller -> 校验）
    python build.py --no-clean     # 跳过清理（加快迭代）
    python build.py --prepare-deps # bin/ 缺失时自动执行 download_deps.py

产物：
    Windows → dist/BilibiliDownloader.exe        （单文件，双击即用）
    macOS   → dist/BilibiliDownloader.app        （拖入 Applications）

构建前请确保已安装：pip install -r requirements.txt pyinstaller
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SPEC = ROOT / "BilibiliDownloader.spec"
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

MIN_EXE_SIZE = 50 * 1024 * 1024   # 产物下限（PySide6 + ffmpeg 约 130MB）


def log(msg: str):
    print(f"[build] {msg}", flush=True)


def die(msg: str):
    print(f"[build] 错误: {msg}", file=sys.stderr)
    sys.exit(1)


def check_bin(force_prepare: bool) -> None:
    """bin/ 下必须有 yt-dlp 与 ffmpeg，缺失则提示（或自动）准备"""
    def have(base: str) -> bool:
        names = (f"{base}.exe", base) if IS_WIN else (base, f"{base}.exe")
        return any((ROOT / "bin" / n).exists() for n in names)

    if have("yt-dlp") and have("ffmpeg"):
        log("bin/ 依赖齐备")
        return
    if not force_prepare:
        log("bin/ 缺少 yt-dlp 或 ffmpeg。请先执行： python download_deps.py")
        log("或使用 --prepare-deps 参数自动下载")
        die("依赖缺失")
    log("自动下载 bin/ 依赖 ...")
    r = subprocess.run([sys.executable, str(ROOT / "download_deps.py"), "--force"])
    if r.returncode != 0:
        die("download_deps.py 执行失败")


def clean() -> None:
    for d in ("build", "dist"):
        p = ROOT / d
        if p.exists():
            log(f"清理 {d}/")
            shutil.rmtree(p, ignore_errors=True)


def run_pyinstaller() -> None:
    log("PyInstaller 构建中（约 2-5 分钟）...")
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", str(SPEC)],
        cwd=ROOT,
    )
    if r.returncode != 0:
        die("PyInstaller 构建失败，请查看上方输出")


def validate() -> Path:
    """校验产物存在、体积合理、不含用户凭证文件"""
    if IS_MAC:
        out = ROOT / "dist" / "BilibiliDownloader.app"
        if not out.exists():
            die(f"产物不存在: {out}")
        inner = out / "Contents" / "MacOS" / "BilibiliDownloader"
        if not inner.exists():
            die("产物缺少主可执行文件（Contents/MacOS/BilibiliDownloader）")
        size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
        main_ok = inner.stat().st_size > 0
    else:
        out = ROOT / "dist" / "BilibiliDownloader.exe"
        if not out.exists():
            die(f"产物不存在: {out}")
        size = out.stat().st_size
        main_ok = size > MIN_EXE_SIZE

    if not main_ok or size < MIN_EXE_SIZE:
        die(f"产物体积异常（{size / 1024 / 1024:.1f} MB），可能缺少 PySide6 或 bin/")

    # 凭证红线：dist 内不得出现任何用户数据
    dist = ROOT / "dist"
    for bad in ("cookies.txt", "settings.json"):
        hits = list(dist.rglob(bad))
        if hits:
            die("发布物中发现用户数据文件（凭证红线）: " +
                ", ".join(str(h.relative_to(ROOT)) for h in hits))

    # bin/ 是否随包（onefile 打进 exe 内无法直接列出，跳过；onedir 可校验）
    if IS_MAC:
        bin_dir = out / "Contents" / "MacOS" / "bin"
        if not bin_dir.exists():
            die("产物缺少 bin/（yt-dlp 与 ffmpeg 未随包）")

    log(f"产物校验通过: {out.relative_to(ROOT)} ({size / 1024 / 1024:.1f} MB)")
    return out


def main():
    ap = argparse.ArgumentParser(description="一键构建当前平台发布产物")
    ap.add_argument("--no-clean", action="store_true", help="跳过清理旧构建")
    ap.add_argument("--prepare-deps", action="store_true",
                    help="bin/ 缺失时自动执行 download_deps.py")
    args = ap.parse_args()

    if not (IS_WIN or IS_MAC):
        die(f"不支持的当前平台: {sys.platform}（支持 win32 / darwin）")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        die("未安装 PyInstaller：pip install pyinstaller")

    log(f"平台: {'Windows' if IS_WIN else 'macOS'} | "
        f"模式: {'onedir(.app)' if IS_MAC else 'onefile'}")
    check_bin(args.prepare_deps)
    if not args.no_clean:
        clean()
    run_pyinstaller()
    validate()
    log("构建完成")


if __name__ == "__main__":
    main()
