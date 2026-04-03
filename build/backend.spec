# PyInstaller spec for the AutoSlice FastAPI backend
# Build with: pyinstaller build/backend.spec  (run from repo root)

import sys
from pathlib import Path

block_cipher = None

BACKEND_DIR = Path('backend').resolve()

a = Analysis(
    [str(BACKEND_DIR / 'run.py')],
    pathex=[str(BACKEND_DIR), str(BACKEND_DIR / 'app')],
    binaries=[],
    datas=[
        # Bundle the data directory (printer profiles etc.)
        (str(BACKEND_DIR / 'data'), 'data'),
    ],
    hiddenimports=[
        # FastAPI / Starlette internals
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.responses',
        'multipart',
        'multipart.multipart',
        # Crypto (python-jose)
        'jose',
        'jose.backends',
        'cryptography',
        # Trimesh optional deps
        'trimesh.geometry',
        'trimesh.triangles',
        'scipy.spatial',
        'scipy.spatial.transform',
        'scipy.spatial._ckdtree',
        'scipy.sparse',
        'scipy.sparse.csgraph',
        'numpy',
        # Email validation (pydantic[email])
        'email_validator',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'test', 'unittest'],
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
    name='autoslice_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,           # keep console so errors are visible during troubleshooting
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# One-folder bundle (not single-file) for easier debugging
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='autoslice_backend',
)
