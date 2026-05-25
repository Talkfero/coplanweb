"""Mixin Outros (helpers de scope da Visualizar) -- 4 metodos, ~82 linhas.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 1).

Metodos esperados em ``self``:
- ``self.col_index(nome)`` (em ``visualizar_mixin`` no futuro Tier 4)

Atributos esperados em ``self``:
- ``self.table_obras``: ``QTableWidget``
"""
from __future__ import annotations

from PySide6 import QtCore


class OutrosMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def _get_visualizar_scope_rows(self, scope: str) -> list[int]:
        tabela = getattr(self, "table_obras", None)
        if tabela is None or tabela.rowCount() == 0:
            return []
        if scope == "selected":
            if not tabela.selectionModel():
                return []
            return [
                i.row()
                for i in tabela.selectionModel().selectedRows()
                if not tabela.isRowHidden(i.row())
            ]
        if scope == "visible":
            return [row for row in range(tabela.rowCount()) if not tabela.isRowHidden(row)]
        return list(range(tabela.rowCount()))

    def _get_visualizar_scope_cods(self, rows: list[int]) -> list[str]:
        tabela = getattr(self, "table_obras", None)
        if tabela is None or tabela.rowCount() == 0:
            return []
        idx_cod = self.col_index("cod")
        if idx_cod < 0:
            return []
        cods: list[str] = []
        seen: set[str] = set()
        for row in rows:
            item = tabela.item(row, idx_cod)
            if not item:
                continue
            cod = item.text().strip()
            if not cod or cod in seen:
                continue
            seen.add(cod)
            cods.append(cod)
        return cods

    def _get_visualizar_scope_ids(self, scope: str) -> list[str]:
        # Acessa _row_id_value via legacy_module() -- ver explicacao em
        # plano_obras_mixin.abrir_dialogo_plano.
        from ui.main_window import legacy_module
        _row_id_value = legacy_module()._row_id_value

        tabela = getattr(self, "table_obras", None)
        if tabela is None or tabela.rowCount() == 0:
            return []
        row_indices = self._get_visualizar_scope_rows(scope)
        if not row_indices:
            return []

        headers: list[str] = []
        for col in range(tabela.columnCount()):
            header_item = tabela.horizontalHeaderItem(col)
            if header_item:
                headers.append(header_item.text().strip())
            else:
                header = tabela.model().headerData(col, QtCore.Qt.Orientation.Horizontal)
                headers.append(str(header).strip() if header is not None else f"col_{col}")

        ids: list[str] = []
        seen: set[str] = set()
        for row in row_indices:
            row_data: dict[str, str] = {}
            for col, header in enumerate(headers):
                item = tabela.item(row, col)
                row_data[header] = item.text().strip() if item else ""
            row_id = _row_id_value(row_data)
            if not row_id or row_id in seen:
                continue
            seen.add(row_id)
            ids.append(row_id)
        return ids

    def _get_visualizar_scope_years(self, scope: str) -> list[str]:
        tabela = getattr(self, "table_obras", None)
        if tabela is None or tabela.rowCount() == 0:
            return []
        idx_ano = self.col_index("ano_")
        if idx_ano < 0:
            return []
        row_indices = self._get_visualizar_scope_rows(scope)
        years: list[str] = []
        seen: set[str] = set()
        for row in row_indices:
            item = tabela.item(row, idx_ano)
            ano_txt = item.text().strip() if item else ""
            if not ano_txt or ano_txt in seen:
                continue
            seen.add(ano_txt)
            years.append(ano_txt)
        return years
