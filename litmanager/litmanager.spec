# PyInstaller spec for the Personal Literature Manager.
# Build with:  pyinstaller litmanager.spec
# Produces a single executable in dist/LiteratureManager (or .exe on Windows).

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hidden_imports = (
    collect_submodules("sklearn")
    + collect_submodules("anthropic")
    + ["pymupdf", "fitz"]
)

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=[
        ("app/templates", "app/templates"),
        ("app/static", "app/static"),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
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
    name="LiteratureManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keep a console window so the user can see the server URL/logs;
                   # set to False for a fully silent background app once you trust it
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
