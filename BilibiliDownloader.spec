# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置（跨平台：Windows onefile / macOS .app）
#
# 产物形态取舍：
#   - Windows 用 onefile：单个 exe 双击即用，最符合"一个安装包直接能运行"；
#     代价是首次启动要解压到临时目录，会慢 2-4 秒。
#   - macOS 用 onedir + BUNDLE：onefile 在 macOS 上启动慢且常被 Gatekeeper/杀软
#     误报；.app 目录结构是 mac 的惯例，再由 CI 打成 dmg 分发。
#
# 红线：
#   - bin/（yt-dlp、ffmpeg 与 ffprobe）必须随包，缺失则下载功能不可用；
#   - bilidownloader/assets/ 必须随包，缺失则界面图标全部变成空白方块；
#   - 不得把 data/ 打进包（含用户 cookies 凭证）。

import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# 版本号单一真源：bilidownloader/__init__.py::__version__
# 注意：spec 由 PyInstaller exec 执行，__file__ 未定义，必须用内置的 SPECPATH
_spec_dir = Path(globals().get('SPECPATH') or '.')
_src = _spec_dir / 'bilidownloader' / '__init__.py'
_m = re.search(r"__version__\s*=\s*['\"]([^'\"]+)", _src.read_text(encoding='utf-8'))
APP_VERSION = _m.group(1) if _m else '0.0.0'

datas = [
    ('bin', 'bin'),
    ('bilidownloader/assets', 'bilidownloader/assets'),
]
binaries = []
hiddenimports = []
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

is_mac = sys.platform == 'darwin'

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if is_mac:
    # macOS：onedir + .app Bundle（PyInstaller 会自动把 a.binaries/a.datas 放进包内）
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='BilibiliDownloader',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name='BilibiliDownloader',
    )
    app = BUNDLE(
        coll,
        name='BilibiliDownloader.app',
        bundle_identifier='com.bilibili.downloader',
        info_plist={
            'NSHighResolutionCapable': True,
            'CFBundleName': 'BilibiliDownloader',
            'CFBundleDisplayName': 'B站下载器',
            'CFBundleShortVersionString': APP_VERSION,
        },
    )
else:
    # Windows 及其它平台：onefile 单可执行文件
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name='BilibiliDownloader',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
