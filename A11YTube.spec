# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
import glob

# Define source directory
current_dir = os.getcwd()
source_dir = os.path.join(current_dir, 'source')

# Gather all DLLs and EXEs from source root
binaries_list = []
for file_path in glob.glob(os.path.join(source_dir, '*.dll')):
    filename = os.path.basename(file_path).lower()
    # Filter out redundant FFmpeg DLLs if we have static executable
    if filename.startswith('avcodec') or filename.startswith('avfilter') or \
       filename.startswith('avformat') or filename.startswith('avutil') or \
       filename.startswith('avdevice') or filename.startswith('swresample') or \
       filename.startswith('swscale') or filename.startswith('postproc'):
        continue
    binaries_list.append((file_path, '.'))
for file_path in glob.glob(os.path.join(source_dir, '*.exe')):
    filename = os.path.basename(file_path).lower()
    # Filter out ffplay
    if 'ffplay' in filename:
        continue
    binaries_list.append((file_path, '.'))

# Analysis configuration
a = Analysis(
    [os.path.join(source_dir, 'A11YTube.py')],
    pathex=[source_dir],
    binaries=binaries_list,
    datas=[
        (os.path.join(source_dir, 'assets'), 'assets'),
        (os.path.join(source_dir, 'docs'), 'docs'),
        (os.path.join(source_dir, 'languages'), 'languages'),
        (os.path.join(source_dir, 'plugins'), 'plugins'),
        (os.path.join(source_dir, 'youtube_browser'), 'youtube_browser'),
        (os.path.join(source_dir, 'gui'), 'gui'),
        (os.path.join(source_dir, 'media_player'), 'media_player'),
        (os.path.join(source_dir, 'nvda_client'), 'nvda_client'),
        (os.path.join(source_dir, 'download_handler'), 'download_handler'),
        # database.py and others are collected via analysis
    ],
    hiddenimports=['wx', 'vlc', 'yt_dlp', 'pyperclip', 'requests', 'bs4', 'json', 're', 'threading', 'subprocess', 'shutil', 'os', 'sys', 'ctypes', 'locale', 'webbrowser', 'pyaudio', 'speech_recognition'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'torchaudio', 'torchvision', 'pandas', 'matplotlib', 'scipy', 'tkinter', 'PyQt5', 'PySide2', 'ipython', 'notebook', 'numpy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='A11YTube',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements=None,
    version=os.path.join(source_dir, 'assets', 'version_info.txt'),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='A11YTube',
)
