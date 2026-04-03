# PyInstaller spec for the AutoSlice launcher (tray app)
# Build with: pyinstaller build/launcher.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['launcher.py'],
    pathex=[str(Path('build').resolve())],
    binaries=[],
    datas=[('loading.html', '.')],
    hiddenimports=[
        'webview',
        'webview.platforms',
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',
        'webview.js',
        'webview.js.css',
        'clr',
        'clr._clr',
        'pythonnet',
        'System',
        'System.Windows.Forms',
        'System.Threading',
    ],
    collect_all=['webview'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='AutoSlice',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # show errors during debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # replace with 'icon.ico' if you have one
)
