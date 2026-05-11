"""QSS theme helpers + paleta de selecao Windows.

Extraidos de codigo5_coplan.py:
- _resolve_qss_path: busca o .qss em varios paths
- _EMBEDDED_MODERN_QSS: tema fallback embutido
- load_qss_from_file: le QSS do disco
- apply_windows_selection_color: paleta azul-Windows
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from runtime.config import APP_DIRS

LOGGER = logging.getLogger("codigo5_coplan")
MODULE_DIR = Path(__file__).resolve().parent.parent  # apps/coplan/


def _resolve_qss_path(qss_file_path: str) -> str:
    if os.path.isabs(qss_file_path) and os.path.isfile(qss_file_path):
        return qss_file_path

    exe_base = os.path.dirname(
        sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
    )
    app_base = os.path.dirname(os.path.abspath(sys.argv[0]))
    module_base = str(MODULE_DIR)
    candidates = [
        os.path.join(module_base, qss_file_path),
        os.path.join(exe_base, qss_file_path),
        os.path.join(APP_DIRS["config"], qss_file_path),
    ]
    if app_base not in {exe_base, module_base, ""}:
        candidates.append(os.path.join(app_base, qss_file_path))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return ""


# Tema mínimo moderno embutido (fallback caso o custom_style.qss não exista).
_EMBEDDED_MODERN_QSS = """
* { font-family: "Segoe UI", "Inter", "Roboto", sans-serif; font-size: 10pt; color: #1f2937; }
QWidget { background-color: #f5f7fa; selection-background-color: #2563eb; selection-color: #ffffff; }
QMainWindow { background-color: #eef2f7; }
QToolBar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #0f3d7a, stop:1 #0a2e5c); border:none; padding:6px; min-height:42px; }
QToolBar QToolButton { color:#e7edf6; border:1px solid transparent; border-radius:6px; padding:6px 10px; margin:2px; }
QToolBar QToolButton:hover { background:rgba(255,255,255,0.12); color:#ffffff; border:1px solid rgba(255,255,255,0.18); }
QToolBar QToolButton:pressed,QToolBar QToolButton:checked { background:rgba(255,255,255,0.22); color:#ffffff; }
QToolBar::separator { background:rgba(255,255,255,0.18); width:1px; margin:8px 6px; }
QTabWidget::pane { border:1px solid #d1d9e6; border-radius:8px; background:#ffffff; top:-1px; }
QTabBar::tab { background:#e4e9f2; color:#475569; border-top-left-radius:8px; border-top-right-radius:8px; padding:9px 22px; margin-right:3px; font-weight:600; min-width:130px; }
QTabBar::tab:hover { background:#d6deec; color:#0f3d7a; }
QTabBar::tab:selected { background:#ffffff; color:#0f3d7a; border:1px solid #d1d9e6; border-bottom:2px solid #2563eb; }
QPushButton { background-color:#2563eb; color:#ffffff; border:none; border-radius:6px; padding:7px 16px; font-weight:600; }
QPushButton:hover { background-color:#1d4ed8; }
QPushButton:pressed { background-color:#1e40af; }
QPushButton:disabled { background-color:#cbd5e1; color:#64748b; }
QLineEdit,QPlainTextEdit,QTextEdit,QComboBox,QSpinBox,QDoubleSpinBox,QDateEdit { background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:5px 8px; }
QLineEdit:focus,QPlainTextEdit:focus,QTextEdit:focus,QComboBox:focus,QSpinBox:focus,QDoubleSpinBox:focus,QDateEdit:focus { border:2px solid #2563eb; padding:4px 7px; }
QGroupBox { background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; margin-top:18px; padding:14px 12px 10px 12px; font-weight:600; color:#0f3d7a; }
QGroupBox::title { subcontrol-origin:margin; subcontrol-position:top left; left:14px; padding:2px 10px; background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; color:#0f3d7a; font-weight:700; }
QTableView,QTableWidget { background:#ffffff; alternate-background-color:#f8fafc; gridline-color:#e5e7eb; border:1px solid #e2e8f0; border-radius:8px; selection-background-color:#dbeafe; selection-color:#0f3d7a; }
QHeaderView::section { background:#eef2f7; color:#0f3d7a; padding:7px 8px; border:none; border-right:1px solid #d1d9e6; border-bottom:2px solid #cbd5e1; font-weight:700; }
QListView,QListWidget,QTreeView,QTreeWidget { background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:2px; selection-background-color:#dbeafe; selection-color:#0f3d7a; }
QScrollBar:vertical { background:#eef2f7; width:12px; border-radius:6px; }
QScrollBar::handle:vertical { background:#c1cbdb; min-height:30px; border-radius:6px; }
QScrollBar::handle:vertical:hover { background:#94a3b8; }
QScrollBar:horizontal { background:#eef2f7; height:12px; border-radius:6px; }
QScrollBar::handle:horizontal { background:#c1cbdb; min-width:30px; border-radius:6px; }
QScrollBar::add-line,QScrollBar::sub-line { height:0; width:0; background:transparent; }
QProgressBar { background:#e2e8f0; border:none; border-radius:8px; text-align:center; color:#0f3d7a; font-weight:600; min-height:18px; }
QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #2563eb, stop:1 #3b82f6); border-radius:8px; }
QStatusBar { background:#ffffff; border-top:1px solid #d1d9e6; color:#334155; padding:2px 6px; }
QStatusBar QLabel { color:#334155; padding:2px 6px; }
QToolTip { background:#1f2937; color:#ffffff; border:1px solid #111827; padding:6px 10px; border-radius:6px; }
QWidget#appTitleBar { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #0a2e5c, stop:1 #0f3d7a); color:#ffffff; min-height:34px; border:none; }
QLabel#appTitleLabel { color:#ffffff; font-size:13pt; font-weight:700; padding:0 12px; }
QLabel#appSubtitleLabel { color:rgba(255,255,255,0.75); font-size:9pt; padding:0 12px; }
"""


def load_qss_from_file(qss_file_path):
    """Carrega um arquivo .qss e retorna o conteudo como string."""
    resolved_path = _resolve_qss_path(qss_file_path)
    if not resolved_path:
        return ""
    try:
        with open(resolved_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        LOGGER.exception("Erro ao carregar QSS: %s", str(e))
        return ""


def apply_windows_selection_color(app: QtWidgets.QApplication) -> None:
    """Aplica uma cor de seleção azul escura global, semelhante à do Windows."""
    palette = app.palette()
    dark_blue = QtGui.QColor(0, 120, 215)
    palette.setColor(QtGui.QPalette.ColorRole.Highlight, dark_blue)
    palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtCore.Qt.GlobalColor.white)
    app.setPalette(palette)
