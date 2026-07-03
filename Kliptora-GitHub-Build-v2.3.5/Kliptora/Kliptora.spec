# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from pathlib import Path

block_cipher = None

datas = [
    ('assets', 'assets'),
    ('update_config.json', '.'),
    ('update_manifest.json', '.'),
    ('THIRD_PARTY_NOTICES.md', '.'),
    ('FFMPEG-NOTICE.txt', '.'),
    ('FFMPEG-LICENSE-LGPL-2.1.txt', '.'),
    ('DENO-LICENSE.md', '.'),
]
binaries = []
hiddenimports = []
for package in ('yt_dlp', 'yt_dlp_ejs', 'curl_cffi'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h

for executable in ('ffmpeg.exe', 'ffprobe.exe'):
    tool_path = f'tools/ffmpeg/bin/{executable}'
    if Path(tool_path).exists():
        binaries.append((tool_path, 'tools/ffmpeg/bin'))

deno_path = 'tools/deno/bin/deno.exe'
if Path(deno_path).exists():
    binaries.append((deno_path, 'tools/deno/bin'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Kliptora',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon='assets/app.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Kliptora',
)
