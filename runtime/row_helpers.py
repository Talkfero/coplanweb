"""Wrappers de row helpers + Qt confirmations.

Extraidos de codigo5_coplan.py. 28 funcoes top-level que estavam soltas
no monolito. A maioria (~22) sao thin wrappers para core.services.row_helpers
e core.services.obra_rules. Os 5 restantes:

- require_tecnico_clean_or_confirm  (Qt -- mostra QMessageBox de aviso)
- get_selected_or_visible_rows      (Qt -- le QTableWidget)
- get_selected_rows                 (Qt -- le QTableWidget)
- _selected_ids_from_view           (Qt indireto via get_selected_rows)
- _format_processing_summary        (wrapper)
- _get_ganhos_tolerancia            (wrapper + ConfigManager)
- require_ganhos_ok_or_confirm      (Qt -- 2 caminhos de QMessageBox)
- require_integrity_or_block        (Qt -- bloqueio com QMessageBox)
- find_duplicate_in_db              (delega a core.repositories.obra_query_repo)
"""
from __future__ import annotations

from typing import Any, Sequence

try:  # Qt e' opcional: a app web (headless) nao instala PySide6.
    from PySide6 import QtCore, QtWidgets  # type: ignore[import-not-found]
except ModuleNotFoundError:  # os helpers que abrem QMessageBox so rodam no desktop
    QtCore = QtWidgets = None  # type: ignore[assignment]

from runtime.config import DEFAULT_GANHOS_TOLERANCIA, ConfigManager


# ---------------------------------------------------------------------------
# Wrappers leves -- core.services.obra_rules
# ---------------------------------------------------------------------------
def is_aprovada(row: dict) -> bool:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import is_aprovada as _impl
    return _impl(row)


def build_scope_key(row: dict) -> str:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import build_scope_key as _impl
    return _impl(row)


def filter_targets_by_aprovacao(
    rows: list[dict], include_aprovadas: bool
) -> tuple[list[dict], int]:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import filter_targets_by_aprovacao as _impl
    return _impl(rows, include_aprovadas)


def _row_integrity_reasons(row: dict, requires_municipio: bool) -> list[str]:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import row_integrity_reasons as _impl
    return _impl(row, requires_municipio)


def _row_id_value(row: dict) -> str:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import row_id_value as _impl
    return _impl(row)


def _is_tecnico_dirty_value(value: str) -> bool:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import is_tecnico_dirty_value as _impl
    return _impl(value)


def _sort_row_id(value: str) -> tuple[int, Any]:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import sort_row_id as _impl
    return _impl(value)


def sort_processing_rows(
    rows: list[dict], selected_ids: set, include_aprovadas: bool
) -> list[dict]:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import sort_processing_rows as _impl
    return _impl(rows, selected_ids, include_aprovadas)


def _format_processing_summary(
    action_label: str,
    processadas_ok: int,
    ignoradas_aprovadas: int,
    ignoradas_integridade: int,
    falhas_total: int,
    falhas: list[str],
) -> str:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import format_processing_summary as _impl
    return _impl(
        action_label, processadas_ok, ignoradas_aprovadas,
        ignoradas_integridade, falhas_total, falhas,
    )


def build_dup_key(row: dict) -> str:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import build_dup_key as _impl
    return _impl(row)


def validate_min_integrity(rows: list[dict]) -> tuple[bool, dict[str, int], list[str]]:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import validate_min_integrity as _impl
    return _impl(rows)


def validate_ganhos_consistency(row: dict, tolerancia: float) -> tuple[bool, list[str]]:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import validate_ganhos_consistency as _impl
    return _impl(row, tolerancia)


# ---------------------------------------------------------------------------
# Wrappers leves -- core.services.row_helpers
# ---------------------------------------------------------------------------
def get_row_value_by_key(row: dict, key: str) -> str:
    """Wrapper -- delega ao core/services/row_helpers."""
    from core.services.row_helpers import get_row_value_by_key as _impl
    return _impl(row, key)


def _row_has_any_key(row: dict, keys: Sequence[str]) -> bool:
    """Wrapper -- delega ao core/services/row_helpers."""
    from core.services.row_helpers import row_has_any_key as _impl
    return _impl(row, keys)


def _first_non_empty_value(row: dict, keys: Sequence[str]) -> str:
    """Wrapper -- delega ao core/services/row_helpers."""
    from core.services.row_helpers import first_non_empty_value as _impl
    return _impl(row, keys)


def _normalize_description(text: str) -> str:
    """Wrapper -- delega ao core/services/row_helpers."""
    from core.services.row_helpers import normalize_description as _impl
    return _impl(text)


def _find_column_name(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    """Wrapper -- delega ao core/services/row_helpers."""
    from core.services.row_helpers import find_column_name as _impl
    return _impl(columns, candidates)


def _expand_key_variants(keys: Sequence[str]) -> list[str]:
    """Wrapper -- delega ao core/services/row_helpers."""
    from core.services.row_helpers import expand_key_variants as _impl
    return _impl(keys)


def _parse_float(value: str | None) -> float | None:
    """Wrapper -- delega ao core/services/row_helpers."""
    from core.services.row_helpers import parse_float_brl as _impl
    return _impl(value)


def _has_any_value(row: dict, keys: Sequence[str]) -> bool:
    """Wrapper -- delega ao core/services/row_helpers."""
    from core.services.row_helpers import has_any_value as _impl
    return _impl(row, keys)


# ---------------------------------------------------------------------------
# Wrappers que dependem de db_manager (core.repositories.obra_query_repo)
# ---------------------------------------------------------------------------
def find_duplicate_in_db(db, row: dict) -> dict | None:
    """Wrapper -- delega ao core/repositories/obra_query_repo.

    Abre conexao via ``db._with_connection()`` e chama ``find_duplicate``
    do core, que opera sobre cursor + lista de colunas + row.
    """
    if not db:
        return None
    cols = db.get_column_names()
    if not cols:
        return None
    from core.repositories.obra_query_repo import find_duplicate as _impl
    with db._with_connection():
        cursor = db._get_cursor()
        if not cursor:
            return None
        return _impl(cursor, cols, row)


# ---------------------------------------------------------------------------
# Helpers que tocam Qt (QTableWidget reads + QMessageBox)
# ---------------------------------------------------------------------------
def get_selected_or_visible_rows(view) -> list[dict]:
    if view is None:
        return []
    selected = []
    if hasattr(view, "selectedVisibleRows"):
        selected = list(view.selectedVisibleRows() or [])
    elif view.selectionModel():
        selected = list(view.selectionModel().selectedRows() or [])
    if selected:
        row_indices = [idx.row() for idx in selected]
    else:
        row_indices = [row for row in range(view.rowCount()) if not view.isRowHidden(row)]
    columns = []
    for col in range(view.columnCount()):
        header_item = view.horizontalHeaderItem(col)
        if header_item:
            columns.append(header_item.text().strip())
        else:
            header = view.model().headerData(col, QtCore.Qt.Orientation.Horizontal)
            columns.append(str(header).strip() if header is not None else f"col_{col}")
    rows = []
    for row in row_indices:
        row_data = {}
        for col, col_name in enumerate(columns):
            value = ""
            if hasattr(view, "item"):
                item = view.item(row, col)
                value = item.text().strip() if item else ""
            else:
                index = view.model().index(row, col)
                value = str(view.model().data(index) or "").strip()
            row_data[col_name] = value
        rows.append(row_data)
    return rows


def get_selected_rows(view) -> list[dict]:
    if view is None:
        return []
    selected = []
    if hasattr(view, "selectedVisibleRows"):
        selected = list(view.selectedVisibleRows() or [])
    elif view.selectionModel():
        selected = list(view.selectionModel().selectedRows() or [])
    if not selected:
        return []
    columns = []
    for col in range(view.columnCount()):
        header_item = view.horizontalHeaderItem(col)
        if header_item:
            columns.append(header_item.text().strip())
        else:
            header = view.model().headerData(col, QtCore.Qt.Orientation.Horizontal)
            columns.append(str(header).strip() if header is not None else f"col_{col}")
    rows = []
    for index in selected:
        row_data = {}
        for col, col_name in enumerate(columns):
            value = ""
            if hasattr(view, "item"):
                item = view.item(index.row(), col)
                value = item.text().strip() if item else ""
            else:
                idx = view.model().index(index.row(), col)
                value = str(view.model().data(idx) or "").strip()
            row_data[col_name] = value
        rows.append(row_data)
    return rows


def _selected_ids_from_view(view) -> set[str]:
    selected_rows = get_selected_rows(view)
    selected_ids: set[str] = set()
    for row in selected_rows:
        row_id = _row_id_value(row)
        if row_id:
            selected_ids.add(row_id)
    return selected_ids


def _get_ganhos_tolerancia(config: dict | None = None) -> float:
    if config is None or not isinstance(config, dict):
        config = ConfigManager.load_config()
    raw = None
    if isinstance(config, dict):
        raw = config.get("ganhos_tolerancia")
    parsed = _parse_float(raw)
    return parsed if parsed is not None else DEFAULT_GANHOS_TOLERANCIA


def require_tecnico_clean_or_confirm(parent, db_manager, action_name: str) -> bool:
    count = 0
    if db_manager:
        try:
            with db_manager._with_connection():
                cursor = db_manager._get_cursor()
                if cursor:
                    cursor.execute(
                        "SELECT COUNT(*) FROM obras "
                        "WHERE tecnico_dirty = 1 OR tecnico_dirty = '1' OR tecnico_dirty = 'SIM'"
                    )
                    row = cursor.fetchone()
                    count = int(row[0]) if row else 0
        except Exception:
            count = 0
    if count <= 0:
        return True
    msg = QtWidgets.QMessageBox(parent)
    msg.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    msg.setWindowTitle(action_name)
    msg.setText(
        f"Há {count} obras com dados técnicos desatualizados. Deseja continuar mesmo assim?"
    )
    msg.setStandardButtons(
        QtWidgets.QMessageBox.StandardButton.Yes
        | QtWidgets.QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QtWidgets.QMessageBox.StandardButton.No)
    return msg.exec() == QtWidgets.QMessageBox.StandardButton.Yes


def require_ganhos_ok_or_confirm(parent, rows: list[dict], action_name: str) -> bool:
    tolerancia = _get_ganhos_tolerancia()
    counters: dict[str, int] = {}
    samples: list[str] = []
    total_errors = 0

    for row in rows:
        ok, reasons = validate_ganhos_consistency(row, tolerancia)
        if ok:
            continue
        total_errors += 1
        cod = _first_non_empty_value(row, ["cod", "codigo", "codigo_item", "id"])
        for reason in reasons:
            counters[reason] = counters.get(reason, 0) + 1
            if len(samples) < 5:
                samples.append(f"COD={cod or 'N/D'}, motivo={reason}")

    if not total_errors:
        return True

    summary_lines = [f"- {label}: {count}" for label, count in counters.items()]
    message = (
        f"{action_name} detectou inconsistências em ganhos.\n\nResumo:\n"
        + "\n".join(summary_lines)
    )
    if samples:
        message += "\n\nExemplos:\n" + "\n".join(samples)

    only_dados_insuficientes = (
        len(counters) == 1
        and "Critérios insuficientes para exportação dependente de ganhos" in counters
    )

    block_actions = {"Atualizar Plano de Obras", "Exportar para Banco"}
    if action_name in block_actions:
        if action_name == "Exportar para Banco":
            QtWidgets.QMessageBox.warning(parent, action_name, message)
            return True
        # "Atualizar Plano de Obras": SEMPRE pergunta Yes/No, mesmo com erros
        # severos (antes/depois vazio). Mudanca aprovada pelo usuario.
        confirm = QtWidgets.QMessageBox.question(
            parent,
            action_name,
            message + "\n\nDeseja continuar mesmo assim?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        return confirm == QtWidgets.QMessageBox.StandardButton.Yes

    QtWidgets.QMessageBox.warning(parent, action_name, message)
    return True


def require_integrity_or_block(parent, rows: list[dict], action_name: str) -> bool:
    ok, counters, samples = validate_min_integrity(rows)
    if ok:
        return True
    summary_lines = [
        f"- {label}: {count}"
        for label, count in counters.items()
    ]
    message = (
        f"{action_name} bloqueado por integridade mínima.\n\nResumo:\n"
        + "\n".join(summary_lines)
    )
    if samples:
        message += "\n\nExemplos:\n" + "\n".join(samples)
    QtWidgets.QMessageBox.warning(parent, action_name, message)
    return False
