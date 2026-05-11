# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for COPLAN (web/pywebview build)."""

from pathlib import Path

SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parent.parent

APP_NAME = "Coplan"
ENTRYPOINT = str(SPEC_DIR / "coplan_launcher.py")
ICON = str(REPO_ROOT / "cadastro-de-obras.ico")

datas = [
    (str(REPO_ROOT / "Coplan UI.html"), "."),
    (str(REPO_ROOT / "cadastro-de-obras.ico"), "."),
]

hiddenimports = [
    "main_web",
    "webview",
    "webview.platforms.winforms",
    "clr",
    "clr_loader",
    "pythonnet",
    "pandas",
    "openpyxl",
]

a = Analysis(
    [ENTRYPOINT],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "PyQt5", "PyQt6"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
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
    icon=ICON,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
