# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec для Yandex Music Downloader.
Режим ONEFILE → один самодостаточный exe.
"""
import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ─── Что упаковываем внутрь exe ───
datas = [
    ('web', 'web'),                 # вся папка web/ (index.html, style.css, app.js)
]
if os.path.exists('icon.ico'):
    datas.append(('icon.ico', '.'))
if os.path.exists('icon.png'):
    datas.append(('icon.png', '.'))

# ─── Скрытые импорты (PyInstaller их не находит автоматически) ───
hiddenimports = [
    'webview',
    'webview.platforms.edgechromium',
    'webview.platforms.winforms',
    'webview.platforms.cef',
    'webview.platforms.gtk',
    'webview.platforms.qt',
    'mutagen.mp3',
    'mutagen.flac',
    'mutagen.id3',
    'PIL.Image',
    'PIL.ImageDraw',
]

hiddenimports += collect_submodules('yandex_music')
hiddenimports += collect_submodules('keyring.backends')
hiddenimports += collect_submodules('pystray')

datas += collect_data_files('yandex_music')

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'scipy',
        'pandas', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'IPython', 'jupyter', 'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='YandexMusicDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                       # ← UPX выключен (антивирус часто ругается)
    runtime_tmpdir=None,
    console=False,                   # без консольного окна
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)