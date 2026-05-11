"""Mixin Plano de Obras -- 3 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 1).

Atributos esperados em ``self`` (vindos da MainWindow base):
- ``self.table_obras``: ``VisibleRowTableWidget`` (subclasse de QTableWidget)
- ``self.db_manager``: para ``get_column_names()``
- ``self.btn_cancelar_plano``, ``self.btn_limpar_ganhos`` (opcional)
- estado: ``self.plano_update_active``, ``self.plano_update_params``,
  ``self.plano_rows``, ``self.blocked_rows``

Metodos esperados em ``self``:
- ``self._gate_aprovadas_for_action`` (em ``filtros_paginacao_mixin``
  no futuro Tier 3)

Nota tecnica: a coloracao via ``setBackground(QColor)`` segue o legado
e funciona em PySide6 versoes mais antigas. Em PySide6 6.x recente com
QSS forte no widget pai, pode nao aparecer visualmente -- nao foi
encontrada solucao confiavel (testadas: QBrush, setData/BackgroundRole,
setItemDelegate, setItemDelegateForRow, paintEvent override). Quando
houver bandwidth, considerar trocar a tabela inteira para um modelo
QAbstractTableModel + QTableView com pintura customizada.
"""
from __future__ import annotations

import datetime

from PySide6 import QtGui, QtWidgets


class PlanoObrasMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def abrir_dialogo_plano(self) -> None:
        from ui.main_window import legacy_module
        legacy = legacy_module()
        PlanoObrasDialog = legacy.PlanoObrasDialog
        require_ganhos_ok_or_confirm = legacy.require_ganhos_ok_or_confirm
        require_integrity_or_block = legacy.require_integrity_or_block

        targets, _include_aprovadas, _ignoradas_aprovadas = self._gate_aprovadas_for_action(
            "Atualizar Plano de Obras", self.table_obras
        )
        if not targets:
            return
        if not require_integrity_or_block(self, targets, "Atualizar Plano de Obras"):
            return
        if not require_ganhos_ok_or_confirm(self, targets, "Atualizar Plano de Obras"):
            return
        pacote = None
        ini = None
        fim = None
        params = getattr(self, "plano_update_params", None) or ()
        if len(params) == 3:
            pacote, ini, fim = params
        dialog = PlanoObrasDialog(
            self.db_manager,
            self,
            pacote=pacote,
            data_inicial=ini,
            data_final=fim,
        )
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            combo = getattr(dialog, "combo_pacote", None)
            if combo is None:
                return
            pacote = combo.currentText().strip()
            ini = dialog.dt_inicial.dateTime().toPython()
            fim = dialog.dt_final.dateTime().toPython()
            if ini is None or fim is None:
                return
            if str(fim) < str(ini):
                QtWidgets.QMessageBox.warning(
                    self, "Aviso", "Data/Hora Final deve ser maior que a Inicial."
                )
                return
            self.aplicar_atualizacao_plano(pacote, ini, fim)

    def aplicar_atualizacao_plano(self, pacote, data_inicial, data_final) -> None:
        self.plano_update_active = True
        self.blocked_rows = set()
        self.plano_rows = set()
        self.plano_update_params = (pacote, data_inicial, data_final)
        cols = self.db_manager.get_column_names()
        idx_pacote = cols.index("tipo_pacote") if "tipo_pacote" in cols else -1
        idx_data_mod = cols.index("data_modificacao") if "data_modificacao" in cols else -1
        for row in range(self.table_obras.rowCount()):
            item_pac = self.table_obras.item(row, idx_pacote) if idx_pacote >= 0 else None
            pac = item_pac.text() if item_pac else ""
            if pac.strip() != pacote:
                continue
            self.plano_rows.add(row)
            item_data = self.table_obras.item(row, idx_data_mod) if idx_data_mod >= 0 else None
            data_str = item_data.text() if item_data else ""
            try:
                dt = datetime.datetime.strptime(data_str, "%d/%m/%y %H:%M")
            except Exception:
                dt = None

            color = None
            if dt:
                if dt > data_final:
                    color = QtGui.QColor(144, 238, 144)  # verde claro
                elif dt <= data_inicial:
                    color = None
                else:
                    color = QtGui.QColor(211, 211, 211)  # cinza claro
                    self.blocked_rows.add(row)
            if color:
                for col in range(self.table_obras.columnCount()):
                    item = self.table_obras.item(row, col)
                    if item:
                        item.setBackground(color)
            else:
                for col in range(self.table_obras.columnCount()):
                    item = self.table_obras.item(row, col)
                    if item:
                        item.setBackground(QtGui.QBrush())
        self.btn_cancelar_plano.show()
        if hasattr(self, "btn_limpar_ganhos"):
            self.btn_limpar_ganhos.show()

    def cancelar_atualizacao_plano_obras(self) -> None:
        if not getattr(self, "plano_update_active", False):
            return
        for row in getattr(self, "plano_rows", set()):
            for col in range(self.table_obras.columnCount()):
                item = self.table_obras.item(row, col)
                if item:
                    item.setBackground(QtGui.QBrush())
        self.blocked_rows = set()
        self.plano_rows = set()
        self.plano_update_active = False
        self.plano_update_params = None
        self.btn_cancelar_plano.hide()
        if hasattr(self, "btn_limpar_ganhos"):
            self.btn_limpar_ganhos.hide()
