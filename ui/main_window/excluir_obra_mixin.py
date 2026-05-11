"""Mixin Excluir Obra -- 2 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 2).

Atributos esperados em ``self``:
- ``self.table_obras``: ``VisibleRowTableWidget``
- ``self.db_manager``: para ``delete_obra``, ``update_obra``

Metodos esperados em ``self``:
- ``self.require_state``, ``self.ensure_db_connected``
- ``self._confirmar_exclusao_excepcional``, ``self._registrar_exclusao_excepcional``
- ``self.load_obras_into_table``, ``self.col_index``
"""
from __future__ import annotations

import datetime

from PySide6 import QtWidgets


class ExcluirObraMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def delete_selected_obras(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        DataStateManager = legacy.DataStateManager
        get_selected_or_visible_rows = legacy.get_selected_or_visible_rows
        is_aprovada = legacy.is_aprovada
        get_row_value_by_key = legacy.get_row_value_by_key

        if not self.require_state(
            "Excluir obras", {"db": DataStateManager.CARREGADO_VALIDADO}
        ):  # [RB-1.1]
            return
        if not self.ensure_db_connected():
            return

        indices = self.table_obras.selectedVisibleRows()
        if not indices:
            QtWidgets.QMessageBox.warning(
                self,
                "Aviso",
                "Selecione pelo menos uma obra visível para excluir."
            )
            return

        rows = get_selected_or_visible_rows(self.table_obras)
        if not rows:
            QtWidgets.QMessageBox.warning(
                self,
                "Aviso",
                "Selecione pelo menos uma obra visível para excluir."
            )
            return

        aprovadas = [row for row in rows if is_aprovada(row)]
        nao_aprovadas = [row for row in rows if not is_aprovada(row)]
        incluir_aprovadas = False

        if aprovadas:
            msg = QtWidgets.QMessageBox(self)
            msg.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            msg.setWindowTitle("Exclusão")
            msg.setText("Obra APROVADA não pode ser excluída.")
            msg.setInformativeText("Somente exclusão excepcional mediante desbloqueio.")
            btn_unlock = msg.addButton(
                "Desbloqueio excepcional...", QtWidgets.QMessageBox.ButtonRole.AcceptRole
            )
            btn_continue = msg.addButton(
                "Continuar sem aprovadas", QtWidgets.QMessageBox.ButtonRole.ActionRole
            )
            btn_cancel = msg.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)
            msg.setDefaultButton(btn_cancel)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == btn_unlock:
                if not self._confirmar_exclusao_excepcional():
                    return
                incluir_aprovadas = True
            elif clicked == btn_continue:
                incluir_aprovadas = False
            else:
                return

        rows_para_excluir = list(nao_aprovadas)
        if incluir_aprovadas:
            rows_para_excluir.extend(aprovadas)

        if not rows_para_excluir:
            QtWidgets.QMessageBox.information(
                self,
                "Aviso",
                "Nenhuma obra elegível para exclusão."
            )
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirmação",
            f"Deseja excluir {len(rows_para_excluir)} obra(s)?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            erros = []
            for row in rows_para_excluir:
                cod = get_row_value_by_key(row, "cod")
                if not cod:
                    continue
                try:
                    if incluir_aprovadas and is_aprovada(row):
                        self._registrar_exclusao_excepcional(cod)
                    self.db_manager.delete_obra(cod)
                except PermissionError as e:
                    erros.append(str(e))
                except Exception as e:
                    erros.append(str(e))
            if erros:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erro",
                    "Erro ao excluir obras:\n" + "\n".join(erros)
                )
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Sucesso",
                    "Obra(s) excluída(s) com sucesso!"
                )
            self.load_obras_into_table()

    def marcar_obras_correcao(self):
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        if not self.require_state(
            "Marcar como CORREÇÃO", {"db": DataStateManager.CARREGADO_VALIDADO}
        ):  # [RB-1.1]
            return
        if not self.ensure_db_connected():
            return

        indices = self.table_obras.selectedVisibleRows()
        if not indices:
            QtWidgets.QMessageBox.warning(
                self,
                "Aviso",
                "Selecione pelo menos uma obra visível para marcar como CORREÇÃO.",
            )
            return

        idx_cod = self.col_index("cod")
        cods = []
        for index in indices:
            item = self.table_obras.item(index.row(), idx_cod) if idx_cod >= 0 else None
            if item and item.text().strip():
                cods.append(item.text().strip())
        cods = list(dict.fromkeys(cods))
        if not cods:
            QtWidgets.QMessageBox.warning(
                self,
                "Aviso",
                "Nenhuma obra válida foi selecionada.",
            )
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirmação",
            f"Deseja marcar {len(cods)} obra(s) como CORREÇÃO?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        motivo, ok = QtWidgets.QInputDialog.getText(
            self,
            "Motivo da correção",
            "Informe o motivo da correção (obrigatório).",
        )
        if not ok or not motivo.strip():
            return

        now_iso = datetime.datetime.now().isoformat(timespec="seconds")
        despacho_ref = f"CORRECAO: {motivo.strip()}"
        erros = []
        for cod in cods:
            try:
                self.db_manager.update_obra(
                    {
                        "despacho_status": "CORRECAO",
                        "despacho_em": now_iso,
                        "despacho_ref": despacho_ref,
                    },
                    cod,
                    skip_blank=True,
                )
            except Exception as exc:
                erros.append(f"{cod}: {exc}")

        if erros:
            QtWidgets.QMessageBox.critical(
                self,
                "Erro",
                "Erro ao marcar obras como CORREÇÃO:\n" + "\n".join(erros),
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Sucesso",
                "Obra(s) marcada(s) como CORREÇÃO com sucesso!",
            )
        self.load_obras_into_table()
