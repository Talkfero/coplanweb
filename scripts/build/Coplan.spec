# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for COPLAN (web/pywebview build)."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(SPECPATH).resolve()
REPO_ROOT = SPEC_DIR.parent.parent

APP_NAME = "Coplan"
ENTRYPOINT = str(SPEC_DIR / "coplan_launcher.py")
ICON = str(REPO_ROOT / "frontend" / "assets" / "cadastro-de-obras.ico")

datas = [
    # Bundla a pasta frontend inteira (index.html + js/bridge/*.js + assets)
    # preservando a estrutura; coplan_launcher.py reaponta FRONTEND_DIR/HTML_FILE.
    (str(REPO_ROOT / "frontend"), "frontend"),
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
    # PySide6 removido: a app web e' Qt-free (imports de Qt em runtime.* sao
    # lazy/guardados e so executam no desktop). Ver excludes abaixo.
]

# main_web importa backend/core/shared/runtime de forma lazy (dentro dos
# metodos), o que a analise estatica do PyInstaller nao segue. Coleta explicita
# garante que esses pacotes entrem no bundle do exe web. Para runtime/ listamos
# so os modulos que a web usa (os demais sao Qt-only do desktop e ficam de fora).
for _pkg in ("backend", "core", "shared"):
    hiddenimports += collect_submodules(_pkg)
hiddenimports += [
    "runtime.config", "runtime.text_utils", "runtime.pi_base", "runtime.calc",
    "runtime.database", "runtime.apoio", "runtime.file_io", "runtime.row_helpers",
    "runtime.notify",
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
    excludes=["PyQt5", "PyQt6", "PySide6"],
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
