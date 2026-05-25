# -*- coding: utf-8 -*-
"""Helpers de notificacao / abertura de arquivo SEM importar Qt no topo.

A app web (pywebview, headless quanto a Qt) usa estes helpers para nao
arrastar PySide6. O desktop continua usando ``runtime.dialogs`` diretamente.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import Any


def open_file(path: str) -> None:
    """Abre arquivo/pasta no app padrao do SO, sem dependencia de Qt.

    Equivalente headless de ``runtime.dialogs.open_file`` (que usa
    QDesktopServices e exige um QApplication ativo).
    """
    target = os.path.abspath(path)
    try:
        if os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]  # noqa: PLC0415
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
    except Exception as e:  # noqa: BLE001
        logging.error("Erro ao abrir arquivo %s: %s", path, e)


def show_user_error(title: str, details: Any, hint: str, parent: Any = None) -> None:
    """Erro padronizado. No desktop delega para o QMessageBox de
    ``runtime.dialogs``; sem Qt instalado (web), apenas registra em log."""
    try:
        import PySide6  # noqa: F401,PLC0415
    except ModuleNotFoundError:
        logging.error("[%s] %s | %s", title, details, hint)
        return
    from runtime.dialogs import show_user_error as _impl  # noqa: PLC0415
    _impl(title, details, hint, parent)
