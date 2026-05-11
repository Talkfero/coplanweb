"""Mixin Atualizar Obra -- 10 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 4).
"""
from __future__ import annotations

import os
import subprocess
import tempfile

import pandas as pd
from PySide6 import QtWidgets


class AtualizarObraMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def atualizar_obras(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        _selected_ids_from_view = legacy._selected_ids_from_view
        sort_processing_rows = legacy.sort_processing_rows
        _row_has_any_key = legacy._row_has_any_key
        _row_integrity_reasons = legacy._row_integrity_reasons
        get_row_value_by_key = legacy.get_row_value_by_key
        get_pi_base = legacy.get_pi_base
        get_pi_extra_module_keys = legacy.get_pi_extra_module_keys
        _format_processing_summary = legacy._format_processing_summary
        ConfigManager = legacy.ConfigManager
        read_excel_cached = legacy.read_excel_cached
        REGIONAL_MAP = legacy.REGIONAL_MAP

        indices = self.table_obras.selectedVisibleRows()
        if not indices:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Selecione pelo menos uma obra visível para atualizar.")
            return

        targets, include_aprovadas, ignoradas_aprovadas = self._gate_aprovadas_for_action(
            "Atualizar Obras", self.table_obras
        )
        if not targets:
            return
        selected_ids = _selected_ids_from_view(self.table_obras)
        rows_sorted = sort_processing_rows(targets, selected_ids, include_aprovadas)

        if not self.ensure_db_connected():
            return

        resp_desc = QtWidgets.QMessageBox.question(
            self,
            "Atualizar descrição?",
            "Deseja atualizar também a Descrição da Obra (refazer a descrição)?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No
        )
        atualizar_descricao = (resp_desc == QtWidgets.QMessageBox.StandardButton.Yes)

        # -- Pergunta opcional sobre o uso de chaves extras --
        extra_key_map: dict[str, list[str]] = {}
        resp_extra = QtWidgets.QMessageBox.question(
            self,
            "Chaves Adicionais",
            "Deseja utilizar alguma chave extra além daquelas criadas pelas configurações das obras?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if resp_extra == QtWidgets.QMessageBox.StandardButton.Yes:
            keys_text, ok = QtWidgets.QInputDialog.getText(
                self,
                "Chaves Adicionais",
                "Informe as chaves extras (sem _REGXXXX) separadas por ';':",
            )
            if ok and keys_text.strip():
                keys_list = [k.strip().upper() for k in keys_text.split(";") if k.strip()]

                db_pis = sorted(
                    set(str(r).strip().upper() for r in self.db_manager.get_distinct_values("pi_base") if r)
                )

                for key in keys_list:
                    dialog = QtWidgets.QDialog(self)
                    dialog.setWindowTitle(f"Selecionar PIs para {key}")
                    layout = QtWidgets.QVBoxLayout(dialog)

                    lista = QtWidgets.QListWidget()
                    lista.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
                    lista.addItems(db_pis)
                    layout.addWidget(lista)

                    btns = QtWidgets.QDialogButtonBox(
                        QtWidgets.QDialogButtonBox.StandardButton.Ok
                        | QtWidgets.QDialogButtonBox.StandardButton.Cancel
                    )
                    layout.addWidget(btns)
                    btns.accepted.connect(dialog.accept)
                    btns.rejected.connect(dialog.reject)

                    if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
                        selecionados = [
                            lista.item(i).text()
                            for i in range(lista.count())
                            if lista.item(i).isSelected()
                        ]
                        if selecionados:
                            extra_key_map[key] = selecionados

        chaves_inexistentes = set()
        config = ConfigManager.load_config()
        caminho_planilha = config.get("apoio", "")
        if not os.path.exists(caminho_planilha):
            QtWidgets.QMessageBox.critical(None, "Erro", "O caminho da planilha de apoio não foi definido corretamente.")
            return

        try:
            xls = pd.ExcelFile(caminho_planilha)
            abas = {str(aba).lower(): aba for aba in xls.sheet_names}

            if "modulo" not in abas:
                QtWidgets.QMessageBox.warning(None, "Erro", "A aba 'MODULO' não foi encontrada na planilha de apoio.")
                return

            df_modulo = read_excel_cached(caminho_planilha, abas["modulo"])
            colunas = {col.lower(): col for col in df_modulo.columns}

            if "carac+modulo_regional" not in colunas or "valor_item" not in colunas:
                QtWidgets.QMessageBox.warning(None, "Erro", "A aba 'MODULO' não possui as colunas necessárias.")
                return

            regional_map = REGIONAL_MAP

            from core.services.atualizar_obra_service import (
                calcular_valor_obra,
                extrair_obra_input,
            )

            processadas_ok = 0
            ignoradas_integridade = 0
            falhas: list[str] = []
            falhas_total = 0
            requires_municipio = any(
                _row_has_any_key(row, ["municipio", "município"]) for row in rows_sorted
            )
            cols = self.db_manager.get_column_names()
            col_chave_modulo = colunas["carac+modulo_regional"]
            col_valor_modulo = colunas["valor_item"]

            for row in rows_sorted:
                integridade_reasons = _row_integrity_reasons(row, requires_municipio)
                if integridade_reasons:
                    ignoradas_integridade += 1
                    continue
                cod = get_row_value_by_key(row, "cod")
                obra = self.db_manager.fetch_by_cod(cod)
                if not obra:
                    falhas_total += 1
                    if len(falhas) < 5:
                        falhas.append(f"COD={cod or 'N/D'}: obra não encontrada")
                    continue

                inp = extrair_obra_input(
                    obra,
                    cols,
                    pi_base_fallback_fn=lambda pi: get_pi_base(pi, prompt_user=False),
                )
                extra_keys = list(get_pi_extra_module_keys(inp.pi_base))
                for key, pi_list in extra_key_map.items():
                    if inp.pi_base in pi_list:
                        extra_keys.append(key)

                result = calcular_valor_obra(
                    inp,
                    df_modulo,
                    col_chave=col_chave_modulo,
                    col_valor=col_valor_modulo,
                    regional_map=regional_map,
                    extra_keys_for_pi=extra_keys,
                )

                for motivo in result.motivos_falha:
                    if motivo == "quantidade inválida":
                        QtWidgets.QMessageBox.warning(
                            self, "Aviso",
                            f"Quantidade inválida para a obra {result.cod}.",
                        )
                    elif motivo.startswith("valor inválido para "):
                        chave_msg = motivo[len("valor inválido para "):]
                        QtWidgets.QMessageBox.warning(
                            None, "Erro",
                            f"Valor inválido para a chave '{chave_msg}'.",
                        )

                for motivo in result.motivos_falha:
                    falhas_total += 1
                    if len(falhas) < 5:
                        falhas.append(f"COD={result.cod or 'N/D'}: {motivo}")
                for ch in result.chaves_inexistentes:
                    chaves_inexistentes.add(ch)

                if not result.sucesso_base:
                    continue

                descricao = ""
                if atualizar_descricao:
                    descricao = self.calc_manager.gerar_descricao_obra(
                        inp.pi_base,
                        dict(inp.obra_data_map),
                    )

                dados_atualizados = {"valor_obra": result.valor_obra_formatado}
                if atualizar_descricao:
                    dados_atualizados["descricao_obra"] = descricao
                self.db_manager.update_obra(
                    dados_atualizados, result.cod, skip_blank=True,
                )
                processadas_ok += 1

            self.load_obras_into_table()

            resumo = _format_processing_summary(
                "Atualizar Obras",
                processadas_ok,
                ignoradas_aprovadas,
                ignoradas_integridade,
                falhas_total,
                falhas,
            )
            QtWidgets.QMessageBox.information(self, "Atualizar Obras", resumo)

            if chaves_inexistentes:
                unique_chaves = sorted(chaves_inexistentes)
                resposta = QtWidgets.QMessageBox.question(
                    self, "Chaves Inexistentes",
                    f"Foram encontradas {len(unique_chaves)} chaves inexistentes. Deseja gerar um relatório em TXT?",
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No,
                )

                if resposta == QtWidgets.QMessageBox.StandardButton.Yes:
                    try:
                        import tempfile
                        import subprocess

                        with tempfile.NamedTemporaryFile(
                            mode="w",
                            delete=False,
                            suffix=".txt",
                            encoding="utf-8",
                        ) as tmp:
                            tmp.write("\n".join(unique_chaves))
                            temp_path = tmp.name
                        subprocess.run(["notepad.exe", temp_path], check=False)
                    except Exception as e:
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Erro",
                            f"Erro ao gerar o relatório TXT: {str(e)}",
                        )
        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Erro", f"Erro ao atualizar obras: {str(e)}")

    def _open_editar_obra_by_cod(self, cod: str) -> None:
        editar_obra = getattr(self, "editar_obra", None)
        if callable(editar_obra):
            editar_obra(cod)
            return
        carregar_obra = getattr(self, "_carregar_obra_para_edicao", None)
        if callable(carregar_obra):
            carregar_obra(cod)
            return

        try:
            obra = self.db_manager.fetch_by_cod(cod)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Erro", f"Falha ao buscar obra COD={cod}.\n{e}"
            )
            return

        if obra:
            if hasattr(self, "tabs") and hasattr(self, "tab_cadastro"):
                try:
                    self.tabs.setCurrentWidget(self.tab_cadastro)
                except Exception:
                    pass
            self.preencher_campos_obra(obra)
            return

        QtWidgets.QMessageBox.warning(
            self,
            "Aviso",
            "Nenhuma obra encontrada para edição.",
        )

    def abrir_editar_obra(self, index):
        if getattr(self, "_visualizar_readonly", False):
            return
        row = index.row()
        if getattr(self, "plano_update_active", False) and row in getattr(self, "blocked_rows", set()):
            return

        if getattr(self, "plano_update_active", False):
            try:
                col_nome = self.db_manager.get_column_names().index("nome_projeto")
                item_nome = self.table_obras.item(row, col_nome) if col_nome >= 0 else None
                nome_projeto = item_nome.text().strip() if item_nome else ""
            except Exception:
                nome_projeto = ""
            if nome_projeto:
                self.iniciar_atualizacao_projeto(row)
                return

        idx_cod = self.col_index("cod")
        item_cod = self.table_obras.item(row, idx_cod) if idx_cod >= 0 else None
        cod = item_cod.text() if item_cod else ""
        obra = self.db_manager.fetch_by_cod(cod)

        if obra:
            self.preencher_campos_obra(obra)
            self.tabs.setCurrentWidget(self.tab_cadastro)

        else:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Nenhuma obra encontrada para edição.")

    def iniciar_atualizacao_projeto(self, row):
        if not self.ensure_db_connected():
            return
        cols_db = self.db_manager.get_column_names()
        col_nome = cols_db.index("nome_projeto")
        idx_pacote = cols_db.index("tipo_pacote") if "tipo_pacote" in cols_db else -1

        item_nome = self.table_obras.item(row, col_nome)
        if item_nome is None:
            return
        nome_projeto = item_nome.text().strip()

        if not nome_projeto:
            col_cod = self.col_index("cod")
            self.abrir_editar_obra(self.table_obras.model().index(row, col_cod))
            return
        item_pacote = self.table_obras.item(row, idx_pacote) if idx_pacote >= 0 else None
        pacote_ref = item_pacote.text().strip() if item_pacote else ""

        todas_obras = self.db_manager.fetch_by_project(
            nome_projeto,
            order_by_codigo_item=True,
        )

        if not todas_obras:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Nenhuma obra encontrada para o projeto.")
            return

        if idx_pacote >= 0:
            self.projeto_obras = [o for o in todas_obras if str(o[idx_pacote]).strip() == pacote_ref]
            if not self.projeto_obras:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Aviso",
                    "Nenhuma obra encontrada para o projeto com o mesmo tipo_pacote.",
                )
                return
            if len(self.projeto_obras) != len(todas_obras):
                QtWidgets.QMessageBox.information(
                    self,
                    "Aviso",
                    f"Existem obras com tipo_pacote diferente. Apenas o tipo '{pacote_ref}' será carregado.",
                )
        else:
            self.projeto_obras = todas_obras

        self.projeto_temp_data = []
        self.projeto_index = 0
        self.projeto_novo_ano = None
        self.projeto_novo_nome = None
        self.projeto_motivo_critico = None
        self.field_ano.setEnabled(True)
        self.field_projeto.setEnabled(True)
        for w in [self.btn_prev_proj, self.btn_next_proj, self.btn_cancelar_proj, self.label_nav_proj, self.label_msg_proj]:
            w.show()
        self.btn_finalizar_proj.hide()
        self.load_projeto_obra()
        self.tabs.setCurrentWidget(self.tab_cadastro)

    def load_projeto_obra(self):
        if not self.projeto_obras or self.projeto_index >= len(self.projeto_obras):
            return
        obra = self.projeto_obras[self.projeto_index]
        self.preencher_campos_obra(obra)
        if self.projeto_novo_ano is not None and self.projeto_index > 0:
            self.field_ano.setCurrentText(str(self.projeto_novo_ano))
            self.field_ano.setEnabled(False)
        else:
            self.field_ano.setEnabled(True)
        if self.projeto_novo_nome is not None and self.projeto_index > 0:
            self.field_projeto.setText(self.projeto_novo_nome)
            self.field_projeto.setEnabled(False)
        else:
            self.field_projeto.setEnabled(True)
        self.update_navegacao_projeto()

    def update_navegacao_projeto(self):
        obras = self.projeto_obras or []
        total = len(obras)
        self.label_nav_proj.setText(f"Obra {self.projeto_index + 1} de {total}")
        self.btn_prev_proj.setEnabled(self.projeto_index > 0)
        if self.projeto_index < len(self.projeto_temp_data):
            self.btn_next_proj.setEnabled(True)
            self.enable_cadastro_fields(True)
            self.label_msg_proj.clear()
        elif self.projeto_index == len(self.projeto_temp_data):
            self.btn_next_proj.setEnabled(False)
            self.enable_cadastro_fields(True)
            self.label_msg_proj.clear()
        else:
            self.btn_next_proj.setEnabled(False)
            self.enable_cadastro_fields(False)
            self.label_msg_proj.setText("Preencha a obra anterior para habilitar esta etapa.")
        if len(self.projeto_temp_data) == total:
            self.btn_finalizar_proj.show()
            self.enable_cadastro_fields(False)

    def prev_projeto_obra(self):
        if self.projeto_obras and self.projeto_index > 0:
            self.projeto_index -= 1
            self.load_projeto_obra()

    def next_projeto_obra(self):
        if self.projeto_obras and self.projeto_index < len(self.projeto_obras) - 1 and self.projeto_index < len(self.projeto_temp_data):
            self.projeto_index += 1
            self.load_projeto_obra()

    def finalizar_atualizacao_projeto(self):
        for dados in self.projeto_temp_data:
            cod = dados.get("cod")
            if self.db_manager.fetch_by_cod(cod):
                try:
                    self.db_manager.update_obra(dados, cod, skip_blank=True)
                except PermissionError:
                    continue
            else:
                try:
                    self.db_manager.insert_obra(dados)
                except PermissionError:
                    continue
        QtWidgets.QMessageBox.information(self, "Sucesso", "Projeto salvo no banco de dados!")
        self.projeto_obras = None
        self.projeto_temp_data = []
        self.projeto_index = 0
        self.projeto_novo_ano = None
        self.projeto_novo_nome = None
        self.projeto_motivo_critico = None
        self.field_ano.setEnabled(True)
        self.field_projeto.setEnabled(True)
        for w in [self.btn_prev_proj, self.btn_next_proj, self.btn_cancelar_proj, self.label_nav_proj, self.label_msg_proj, self.btn_finalizar_proj]:
            w.hide()
        self.enable_cadastro_fields(True)
        self.load_obras_into_table()
        self.limpar_campos_cadastro()

    def cancelar_atualizacao_projeto(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Cancelar atualização",
            "Deseja cancelar a atualização do projeto atual?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        self.projeto_obras = None
        self.projeto_temp_data = []
        self.projeto_index = 0
        self.projeto_novo_ano = None
        self.projeto_novo_nome = None
        self.projeto_motivo_critico = None
        self.field_ano.setEnabled(True)
        self.field_projeto.setEnabled(True)
        for w in [
            self.btn_prev_proj,
            self.btn_next_proj,
            self.btn_cancelar_proj,
            self.label_nav_proj,
            self.label_msg_proj,
            self.btn_finalizar_proj,
        ]:
            w.hide()
        self.enable_cadastro_fields(True)
        self.limpar_campos_cadastro()
