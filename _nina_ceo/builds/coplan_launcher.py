"""PyInstaller launcher for COPLAN.

Runs the same `main()` that `main_web.py` exposes, with two adjustments
required when running from a one-folder PyInstaller bundle on Windows:

1. `_unblock_motw()` strips the "Mark of the Web" Zone.Identifier
   alternate data stream from every `.dll` / `.exe` / `.pyd` shipped
   inside `sys._MEIPASS`. Windows refuses to load native libraries with
   MOTW from "remote" zones (downloaded zip, network share), so without
   this the bundle fails to import `pythonnet` / WebView2 dependencies.

2. Patches `main_web.HTML_FILE` so the bundled `Coplan UI.html` resolves
   relative to `sys._MEIPASS` instead of the source tree.

`CONFIG_FILE` is *not* patched: ConfigManager in `runtime/config.py`
intentionally writes to `%LOCALAPPDATA%/COPLAN/config/config.json` for
both the .exe and the source-run workflow.
"""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path


def _unblock_motw(root: Path) -> None:
    """Recursively clear Zone.Identifier ADS on native binaries under `root`."""
    if not root.exists():
        return

    delete_file = ctypes.windll.kernel32.DeleteFileW if os.name == "nt" else None
    if delete_file is None:
        return

    suffixes = {".dll", ".exe", ".pyd"}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in suffixes:
            continue
        ads = f"{path}:Zone.Identifier"
        try:
            delete_file(ads)
        except OSError:
            pass


def _patch_paths() -> None:
    """Point `HTML_FILE` at the bundled asset inside `_MEIPASS`."""
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return

    bundle_dir = Path(meipass)
    html_path = bundle_dir / "Coplan UI.html"

    import main_web  # noqa: PLC0415 -- imported after sys.path is set by PyInstaller

    if html_path.exists():
        main_web.HTML_FILE = html_path


def main() -> None:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            _unblock_motw(Path(meipass))
        _patch_paths()

    import main_web  # noqa: PLC0415

    main_web.main()


if __name__ == "__main__":
    main()
