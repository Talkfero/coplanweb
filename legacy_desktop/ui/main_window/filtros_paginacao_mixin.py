"""Mixin Filtros / Paginacao -- 17 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 3).
"""
from __future__ import annotations

import datetime
import getpass
import logging
import re
from typing import Any, Optional

from PySide6 import QtCore, QtGui, QtWidgets


class FiltrosPaginacaoMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def schedule_filter_table(self):
        """Aplica debounce nos filtros para evitar recálculo a cada tecla."""
        if hasattr(self, "filter_timer"):
            self.filter_timer.start()
        else:
            self.filter_table()

    def focus_global_filter(self):
        """Foca o campo de busca global para filtrar rapidamente."""
        if hasattr(self, "filter_global"):
            self.filter_global.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
            self.filter_global.selectAll()

    def clear_all_filters(self):
        """Limpa todos os filtros da aba Visualizar e reaplica a listagem."""
        fields = [
            self.filter_cod,
            self.filter_ano,
            self.filter_pi,
            self.filter_nome_projeto,
            self.filter_alimentador,
            self.filter_alimentadores_benef,
            self.filter_regional,
            self.filter_superintendencia,
            self.filter_subestacao,
            self.filter_pacote,
            self.filter_tecnico_dirty,
            self.filter_global,
        ]
        for widget in fields:
            widget.blockSignals(True)
            widget.clear()
            widget.blockSignals(False)
        self.schedule_filter_table()

    def _collect_active_filters(self) -> list[str]:
        mapping = [
            ("COD", self.filter_cod),
            ("Ano", self.filter_ano),
            ("PI", self.filter_pi),
            ("Projeto", self.filter_nome_projeto),
            ("Alimentador", self.filter_alimentador),
            ("Beneficiados", self.filter_alimentadores_benef),
            ("Regional", self.filter_regional),
            ("Superintendência", self.filter_superintendencia),
            ("Subestação", self.filter_subestacao),
            ("Pacote", self.filter_pacote),
            ("Técnico", self.filter_tecnico_dirty),
            ("Geral", self.filter_global),
        ]
        active: list[str] = []
        for label, widget in mapping:
            value = widget.text().strip() if isinstance(widget, QtWidgets.QLineEdit) else ""
            if value:
                active.append(f"{label}: {value}")
        return active

    def _update_filter_feedback(self, visible_count: int) -> None:
        """Atualiza feedback visual sobre filtros ativos e total visível."""
        if not hasattr(self, "filter_feedback"):
            return
        active_filters = self._collect_active_filters()
        if active_filters:
            resumo = " • ".join(active_filters[:3])
            sufixo = " …" if len(active_filters) > 3 else ""
            self.filter_feedback.setText(
                f"{visible_count} resultado(s) | {len(active_filters)} filtro(s): {resumo}{sufixo}"
            )
        else:
            self.filter_feedback.setText(f"Sem filtros ativos | {visible_count} resultado(s)")

    def _on_page_size_changed(self, page_size_text: str) -> None:
        try:
            self._visualizar_page_size = max(1, int(page_size_text))
        except (TypeError, ValueError):
            self._visualizar_page_size = 300
        self._visualizar_current_page = 1
        self._render_visualizar_page()

    def _go_to_previous_page(self) -> None:
        self._visualizar_current_page -= 1
        self._render_visualizar_page()

    def _go_to_next_page(self) -> None:
        self._visualizar_current_page += 1
        self._render_visualizar_page()

    def _render_visualizar_page(self) -> None:
        from ui.main_window import legacy_module
        legacy = legacy_module()
        paginate_visualizar_rows = legacy.paginate_visualizar_rows
        format_pagination_label = legacy.format_pagination_label

        if not hasattr(self, "table_obras") or self.table_obras is None:
            return
        page_rows, total_items, total_pages, normalized_page = paginate_visualizar_rows(
            self._visualizar_filtered_rows,
            self._visualizar_current_page,
            self._visualizar_page_size,
        )
        self._visualizar_current_page = normalized_page

        self.table_obras.setRowCount(0)
        for row_data, atende in page_rows:
            row_position = self.table_obras.rowCount()
            self.table_obras.insertRow(row_position)
            if atende is None:
                color = QtGui.QColor("gray")
            else:
                color = QtGui.QColor("black" if atende else "red")
            for col_index, cell in enumerate(row_data):
                item = QtWidgets.QTableWidgetItem(str(cell))
                item.setForeground(color)
                self.table_obras.setItem(row_position, col_index, item)

        if hasattr(self, "pagination_label"):
            self.pagination_label.setText(
                format_pagination_label(
                    self._visualizar_current_page, total_pages, total_items
                )
            )
        if hasattr(self, "btn_prev_page"):
            self.btn_prev_page.setEnabled(self._visualizar_current_page > 1)
        if hasattr(self, "btn_next_page"):
            self.btn_next_page.setEnabled(self._visualizar_current_page < total_pages)
        self._update_filter_feedback(total_items)
        self.table_obras.resizeColumnsToContents()
        self.apply_visualizar_columns_config()

    @staticmethod
    def matches_filter(cell_text, filter_text, exact=False):
        """Avalia o texto de ``cell_text`` contra ``filter_text``.

        Retorna ``True`` se ``filter_text`` estiver vazio ou se **qualquer** um
        dos termos separados por ponto e vírgula atender ao critério. Se
        ``exact`` for ``True`` a comparação é de igualdade, caso contrário é
        verificada a ocorrência do termo dentro de ``cell_text``.
        """
        if not filter_text:
            return True
        termos = [t.strip().lower() for t in re.split(r"[;,]", filter_text) if t.strip()]
        if exact:
            return any(term == cell_text for term in termos)
        return any(term in cell_text for term in termos)

    def _gate_aprovadas_for_action(
        self, action_label: str, view
    ) -> tuple[list[dict], bool, int]:
        from ui.main_window import legacy_module
        legacy = legacy_module()
        get_selected_or_visible_rows = legacy.get_selected_or_visible_rows
        filter_targets_by_aprovacao = legacy.filter_targets_by_aprovacao

        include_aprovadas = (
            getattr(self, "chk_incluir_aprovadas", None) is not None
            and self.chk_incluir_aprovadas.isChecked()
        )
        rows = get_selected_or_visible_rows(view)
        targets, ignoradas = filter_targets_by_aprovacao(rows, include_aprovadas)
        if not targets:
            QtWidgets.QMessageBox.information(
                self,
                action_label,
                "Nenhuma obra NÃO aprovada para processar. "
                "Marque 'Incluir aprovadas' para incluir.",
            )
            return [], include_aprovadas, 0
        if ignoradas > 0 and not include_aprovadas:
            QtWidgets.QMessageBox.information(
                self,
                action_label,
                f"{ignoradas} obras aprovadas foram ignoradas "
                "(marque 'Incluir aprovadas' para incluir).",
            )
        return targets, include_aprovadas, ignoradas

    def _confirmar_exclusao_excepcional(self) -> bool:
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Exclusão excepcional",
            "Você está tentando excluir uma obra APROVADA.\n"
            "Isso pode comprometer rastreabilidade. Deseja continuar?",
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if confirm != QtWidgets.QMessageBox.StandardButton.Yes:
            return False
        texto, ok = QtWidgets.QInputDialog.getText(
            self, "Exclusão excepcional", "Digite EXCLUIR para confirmar"
        )
        if not ok or texto.strip().upper() != "EXCLUIR":
            QtWidgets.QMessageBox.warning(
                self,
                "Aviso",
                "Confirmação inválida. Exclusão cancelada.",
            )
            return False
        return True

    def _registrar_exclusao_excepcional(self, cod: str) -> None:
        from ui.main_window import legacy_module
        LOGGER = legacy_module().LOGGER

        usuario = getpass.getuser()
        timestamp = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        nota = f"EXCLUSAO EXCEPCIONAL em {timestamp} por {usuario}"
        cols = self.db_manager.get_column_names() if self.db_manager else []
        coluna_log = None
        for col in ("ultima_acao", "observacoes", "observacoes_gerais", "log"):
            if col in cols:
                coluna_log = col
                break
        if coluna_log:
            try:
                obra = self.db_manager.fetch_by_cod(cod)
                if obra:
                    idx = cols.index(coluna_log)
                    atual = str(obra[idx] or "").strip()
                    novo = f"{atual}\n{nota}" if atual else nota
                    self.db_manager.update_obra(
                        {coluna_log: novo}, cod, skip_blank=True
                    )
            except Exception as exc:
                LOGGER.warning(
                    "Falha ao registrar observação de exclusão excepcional para cod=%s: %s",
                    cod,
                    exc,
                )
        logging.warning(
            "EXCLUSAO EXCEPCIONAL: obra aprovada cod=%s usuario=%s",
            cod,
            usuario,
        )

    def filter_table(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        matches_cod_terms = legacy.matches_cod_terms
        matches_filter_value = legacy.matches_filter_value

        if not hasattr(self, "table_obras") or self.table_obras is None:
            self._update_filter_feedback(0)
            return
        if not self._visualizar_source_rows:
            self._visualizar_filtered_rows = []
            self._render_visualizar_page()
            return

        filter_cod = self.filter_cod.text().lower()
        filter_ano = self.filter_ano.text().lower() if hasattr(self, 'filter_ano') else ""
        filter_pi = self.filter_pi.text().lower()
        filter_nome_projeto = self.filter_nome_projeto.text().lower()
        filter_alimentador = self.filter_alimentador.text().lower()
        filter_alimentadores_benef = self.filter_alimentadores_benef.text().lower()
        filter_regional = self.filter_regional.text().lower()
        filter_superintendencia = self.filter_superintendencia.text().lower()
        filter_subestacao = self.filter_subestacao.text().lower() if hasattr(self, 'filter_subestacao') else ""
        filter_pacote = self.filter_pacote.text().lower() if hasattr(self, 'filter_pacote') else ""
        filter_tecnico_dirty = self.filter_tecnico_dirty.text().lower() if hasattr(self, "filter_tecnico_dirty") else ""
        filter_global = self.filter_global.text().lower() if hasattr(self, 'filter_global') else ""

        idx_cod = self.col_index("cod")
        idx_ano = self.col_index("ano_")
        idx_pi = self.col_index("projeto_investimento")
        idx_nome = self.col_index("nome_projeto")
        idx_alim = self.col_index("alimentador_principal")
        idx_benef = self.col_index("alimentadores_beneficiados")
        idx_reg = self.col_index("nome_regional")
        idx_super = self.col_index("nome_superintendencia")
        idx_sub = self.col_index("subestacao")
        idx_pac = self.col_index("tipo_pacote")
        idx_tecnico_dirty = self.col_index("tecnico_dirty")

        filtered_rows: list[tuple[tuple[Any, ...], Optional[bool]]] = []
        for row_data, atende in self._visualizar_source_rows:
            def get_cell(idx):
                if idx < 0 or idx >= len(row_data):
                    return ""
                return str(row_data[idx]).lower()

            item_cod = get_cell(idx_cod)
            cod_match = matches_cod_terms(item_cod, filter_cod)

            item_ano = get_cell(idx_ano)
            item_pi = get_cell(idx_pi)
            item_nome_projeto = get_cell(idx_nome)
            item_alimentador = get_cell(idx_alim)
            item_alimentadores_benef = get_cell(idx_benef)
            item_regional = get_cell(idx_reg)
            item_superintendencia = get_cell(idx_super)
            item_subestacao = get_cell(idx_sub)
            item_pacote = get_cell(idx_pac)
            item_tecnico_dirty = get_cell(idx_tecnico_dirty)

            global_string = " ".join([
                item_cod, item_ano, item_pi, item_nome_projeto,
                item_alimentador, item_alimentadores_benef,
                item_regional, item_superintendencia, item_subestacao,
                item_pacote, item_tecnico_dirty,
            ])
            global_match = matches_filter_value(global_string, filter_global)

            if (cod_match and global_match
                and matches_filter_value(item_ano, filter_ano)
                and matches_filter_value(item_pi, filter_pi)
                and matches_filter_value(item_nome_projeto, filter_nome_projeto)
                and matches_filter_value(item_alimentador, filter_alimentador)
                and matches_filter_value(item_alimentadores_benef, filter_alimentadores_benef)
                and matches_filter_value(item_regional, filter_regional)
                and matches_filter_value(item_superintendencia, filter_superintendencia)
                and matches_filter_value(item_subestacao, filter_subestacao)
                and matches_filter_value(item_pacote, filter_pacote)
                and matches_filter_value(item_tecnico_dirty, filter_tecnico_dirty)):
                filtered_rows.append((row_data, atende))

        self._visualizar_filtered_rows = filtered_rows
        self._visualizar_current_page = 1
        self._render_visualizar_page()

        obras_visiveis = self._obter_obras_visiveis_resumo()
        self.popular_volumetria_financeiro(obras_visiveis)

        obras_visiveis_rs = self._obter_obras_visiveis_resumo_regional_se()
        self.popular_resumo_regional_se(obras_visiveis_rs)

    def show_filter_dialog(self):
        """Exibe uma janela para definir filtros individuais."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Filtros")
        form = QtWidgets.QFormLayout(dialog)

        fields = [
            ("COD", self.filter_cod),
            ("Ano", self.filter_ano),
            ("PI", self.filter_pi),
            ("Projeto", self.filter_nome_projeto),
            ("Alimentador", self.filter_alimentador),
            ("Alim. Benef.", self.filter_alimentadores_benef),
            ("Regional", self.filter_regional),
            ("Superintendência", self.filter_superintendencia),
            ("Subestação", self.filter_subestacao),
            ("Pacote", self.filter_pacote),
            ("Técnico Atualizado", self.filter_tecnico_dirty),
        ]

        editors = {}
        for label, orig_edit in fields:
            cb = QtWidgets.QCheckBox()
            cb.setChecked(bool(orig_edit.text()))
            le = QtWidgets.QLineEdit(orig_edit.text())
            le.setEnabled(cb.isChecked())
            cb.toggled.connect(le.setEnabled)
            row = QtWidgets.QHBoxLayout()
            row.addWidget(cb)
            row.addWidget(le)
            form.addRow(label, row)
            editors[orig_edit] = (cb, le)

        btn_ok = QtWidgets.QPushButton("Aplicar")
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        form.addRow(btn_layout)

        btn_ok.clicked.connect(dialog.accept)
        btn_cancel.clicked.connect(dialog.reject)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            for orig_edit, (cb, le) in editors.items():
                if cb.isChecked():
                    orig_edit.setText(le.text())
                else:
                    orig_edit.clear()
            self.filter_table()

    def _filtrar_ids_por_anos(self, ids: list[str], anos: list[str]) -> list[str]:
        ids_norm: list[str] = []
        seen_ids: set[str] = set()
        for raw_id in ids or []:
            cod = str(raw_id or "").strip()
            if not cod or cod in seen_ids:
                continue
            seen_ids.add(cod)
            ids_norm.append(cod)
        anos_norm = {str(a or "").strip() for a in (anos or []) if str(a or "").strip()}
        if not ids_norm or not anos_norm:
            return ids_norm
        try:
            with self.db_manager._with_connection():
                cursor = self.db_manager._get_cursor()
                if not cursor:
                    return ids_norm
                id_col = self.db_manager._resolve_obra_id_column()
                cols = set(self.db_manager.get_column_names() or [])
                if not id_col or "ano_" not in cols:
                    return ids_norm
                id_col_sql = self.db_manager._escape_identifier(id_col)
                ano_col_sql = self.db_manager._escape_identifier("ano_")
                permitidos: set[str] = set()
                chunk_size = 900
                for start in range(0, len(ids_norm), chunk_size):
                    chunk = ids_norm[start : start + chunk_size]
                    placeholders = ",".join(["?"] * len(chunk))
                    cursor.execute(
                        f"SELECT {id_col_sql}, {ano_col_sql} FROM obras "
                        f"WHERE {id_col_sql} IN ({placeholders})",
                        chunk,
                    )
                    for row in cursor.fetchall():
                        cod = str((row[0] if row else "") or "").strip()
                        ano = str((row[1] if row and len(row) > 1 else "") or "").strip()
                        if cod and ano in anos_norm:
                            permitidos.add(cod)
                return [cod for cod in ids_norm if cod in permitidos]
        except Exception:
            return ids_norm

    def _filtrar_ids_por_aprovacao(
        self,
        ids: list[str],
        incluir_aprovadas: bool,
    ) -> tuple[list[str], int]:
        from ui.main_window import legacy_module
        LOGGER = legacy_module().LOGGER

        ids_norm: list[str] = []
        seen: set[str] = set()
        for raw_id in ids or []:
            cod = str(raw_id or "").strip()
            if not cod or cod in seen:
                continue
            seen.add(cod)
            ids_norm.append(cod)
        if not ids_norm:
            return [], 0
        if incluir_aprovadas:
            return ids_norm, 0

        aprovadas: set[str] = set()
        try:
            with self.db_manager._with_connection():
                cursor = self.db_manager._get_cursor()
                if not cursor:
                    return ids_norm, 0

                cols = {str(c) for c in (self.db_manager.get_column_names() or [])}
                if "obra_aprovada" not in cols:
                    return ids_norm, 0

                id_col = self.db_manager._resolve_obra_id_column()
                if not id_col:
                    return ids_norm, 0

                id_col_sql = self.db_manager._escape_identifier(id_col)
                aprov_sql = self.db_manager._escape_identifier("obra_aprovada")
                chunk_size = 900
                for start in range(0, len(ids_norm), chunk_size):
                    chunk = ids_norm[start : start + chunk_size]
                    placeholders = ",".join(["?"] * len(chunk))
                    cursor.execute(
                        f"SELECT {id_col_sql}, {aprov_sql} FROM obras "
                        f"WHERE {id_col_sql} IN ({placeholders})",
                        chunk,
                    )
                    for row_id, obra_aprovada in cursor.fetchall():
                        cod = str(row_id or "").strip()
                        status = str(obra_aprovada or "").strip().upper()
                        if cod and status == "SIM":
                            aprovadas.add(cod)
        except Exception as exc:
            LOGGER.warning(
                "Falha ao filtrar obras aprovadas para geração de COD_PEP: %s",
                exc,
            )
            return ids_norm, 0

        filtrados: list[str] = []
        ignoradas = 0
        for cod in ids_norm:
            if cod in aprovadas:
                ignoradas += 1
                continue
            filtrados.append(cod)
        return filtrados, ignoradas
