"""Mixin Apoio (planilha de apoio + alimentadores) -- 17 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 3).
"""
from __future__ import annotations

import os

from PySide6 import QtCore, QtWidgets


class ApoioMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def load_last_support_file(self):
        """Carrega automaticamente a última planilha de apoio salva."""
        from ui.main_window import legacy_module
        legacy = legacy_module()
        DataStateManager = legacy.DataStateManager
        show_user_error = legacy.show_user_error

        caminho_apoio = self.config.get("apoio", "")

        if caminho_apoio and os.path.exists(caminho_apoio):
            sucesso, dados = self.support_manager.load_support_file(caminho_apoio)

            if sucesso:
                self.field_alimentador.clear()
                self.field_alimentador.addItems(dados["alimentadores"])

                self.field_alimentador_benef.clear()
                self.field_alimentador_benef.addItems(dados["alimentadores"])

                self.field_caracteristicas.clear()
                self.field_caracteristicas.addItems(dados["caracteristicas"])

                self.field_projeto_investimento.clear()
                self.field_projeto_investimento.addItems(dados["projetos_investimento"])

                self.populate_combo_nome_projeto(dados.get("nomes_projetos_pre_definidos"))

                for cb in [
                    self.field_projeto_investimento,
                    self.field_alimentador,
                    self.field_caracteristicas,
                    self.field_alimentador_benef,
                    self.combo_nome_projeto,
                ]:
                    cb.setCurrentIndex(-1)
                self._update_apoio_state(caminho_apoio, True)  # [RB-1.1]
                self.update_db_path_label()
            else:
                self._update_apoio_state(
                    caminho_apoio, False, "Falha ao carregar a planilha de apoio."
                )  # [RB-1.1]
                show_user_error(
                    "Falha ao carregar planilha",
                    "Falha ao carregar a última planilha de apoio.",
                    "Verifique o arquivo e selecione novamente.",
                    parent=self,
                )
        else:
            self._set_data_state(
                "apoio", DataStateManager.NAO_CARREGADO, path=caminho_apoio
            )  # [RB-1.1]
            show_user_error(
                "Planilha de apoio não encontrada",
                "Nenhuma planilha de apoio foi encontrada para carregamento automático.",
                "Carregue a planilha de apoio manualmente.",
                parent=self,
            )

    def remover_alimentador_beneficiado(self):
        """Remove os alimentadores selecionados da lista de beneficiados."""
        itens_selecionados = self.list_alimentadores_benef.selectedItems()
        if not itens_selecionados:
            return
        for item in itens_selecionados:
            self.list_alimentadores_benef.takeItem(self.list_alimentadores_benef.row(item))
        self.update_subestacoes_list()

    def copiar_alimentadores_benef(self):
        self.copiar_textos_lista(self.list_alimentadores_benef)

    def _on_load_db_and_apoio_clicked(self):
        with self._with_loading_indicator(button=getattr(self, "btn_load_db_apoio", None)):
            db_path = self.config.get("obras")
            apoio_path = self.config.get("apoio")

            if db_path and os.path.exists(db_path):
                self.load_last_obras()
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Banco não encontrado",
                    "O banco de dados não foi encontrado no caminho salvo.",
                )

            if apoio_path and os.path.exists(apoio_path):
                self.load_last_support_file()
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Planilha de apoio não encontrada",
                    "A planilha de apoio não foi encontrada no caminho salvo.",
                )

    def _norm_alim(self, s: str) -> str:
        """Wrapper -- delega ao core/services/relatorio_criterios_service."""
        from core.services.relatorio_criterios_service import norm_alim as _impl
        return _impl(s)

    def _split_alimentadores_benef(self, s: str) -> list[str]:
        """Wrapper -- delega ao core/services/relatorio_criterios_service."""
        from core.services.relatorio_criterios_service import split_alimentadores_benef as _impl
        return _impl(s)

    def load_support_file(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        ConfigManager = legacy.ConfigManager
        LOGGER = legacy.LOGGER
        show_user_error = legacy.show_user_error

        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Selecionar Planilha de Apoio", "", "Excel Files (*.xlsx *.xls)")
        if not filepath:
            return

        with self._with_loading_indicator(action=getattr(self, "act_apoio", None)):
            try:
                sucesso, dados = self.support_manager.load_support_file(filepath)

                if sucesso:
                    self.field_alimentador.clear()
                    self.field_alimentador.addItems(dados["alimentadores"])

                    self.field_alimentador_benef.clear()
                    self.field_alimentador_benef.addItems(dados["alimentadores"])

                    self.field_caracteristicas.clear()
                    self.field_caracteristicas.addItems(dados["caracteristicas"])

                    self.field_projeto_investimento.clear()
                    self.field_projeto_investimento.addItems(dados["projetos_investimento"])

                    self.populate_combo_nome_projeto(dados.get("nomes_projetos_pre_definidos"))

                    for cb in [
                        self.field_projeto_investimento,
                        self.field_alimentador,
                        self.field_caracteristicas,
                        self.field_alimentador_benef,
                        self.combo_nome_projeto,
                    ]:
                        cb.setCurrentIndex(-1)

                    self.config["apoio"] = filepath
                    ConfigManager.save_config({"apoio": filepath})
                    self._update_apoio_state(filepath, True)  # [RB-1.1]
                    self.update_db_path_label()
                else:
                    self._update_apoio_state(
                        filepath, False, "Falha ao carregar a planilha de apoio."
                    )  # [RB-1.1]
            except Exception as exc:
                LOGGER.exception("Erro inesperado ao carregar planilha de apoio.")
                self._update_apoio_state(filepath, False, str(exc))  # [RB-1.1]
                show_user_error(
                    "Erro ao carregar planilha de apoio",
                    f"Falha ao carregar a planilha: {exc}",
                    "Verifique o arquivo e tente novamente.",
                    parent=self,
                )

    def alimentador_selecionado(self):
        if not self.support_manager.dados_alimentador:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Os dados dos alimentadores ainda não foram carregados!")
            return

        alimentador = self.field_alimentador.currentText().strip()
        if alimentador in self.support_manager.dados_alimentador:
            dados = self.support_manager.dados_alimentador[alimentador]
            self.field_tensao.setText(dados["TENSÃO"])
            self.field_tensao_operacao.setText(dados["TENSÃO"])
            self.field_regional.setText(dados["REGIONAL"])
            self.field_superintendencia.setText(dados["SUPERINTENDÊNCIA"])
            self.field_se.setText(dados["SE"])
        else:
            pass

        self.update_subestacoes_list()
        self.update_subestacoes_list()

    def adicionar_alimentador_benef(self):
        alim = self.field_alimentador_benef.currentText().strip()
        if alim and not self.list_alimentadores_benef.findItems(alim, QtCore.Qt.MatchFlag.MatchExactly):
            self.list_alimentadores_benef.addItem(alim)
            self.update_subestacoes_list()
        else:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Alimentador vazio ou já adicionado.")

    def preencher_novo_al(self):
        """Preenche o projeto com AL_Novo_ e marca Novo Bay como SIM."""
        self.field_projeto.setText("AL_Novo_")
        self.field_novo_bay.setCurrentText("SIM")

    def get_alimentadores(self):
        alim_principal = self.field_alimentador.currentText().strip().lower()
        benef = [self.list_alimentadores_benef.item(i).text().strip().lower() for i in range(self.list_alimentadores_benef.count())]
        return [a for a in [alim_principal] + benef if a]

    @staticmethod
    def alimentadores_nos_arquivos(arquivos, alimentadores):
        """Retorna lista de alimentadores não encontrados nos arquivos."""
        faltando = []
        for alim in alimentadores:
            encontrado = False
            a_proc = alim.lower().replace(" ", "")
            for data in arquivos:
                if any(
                    a_proc in line.lower().replace(" ", "")
                    for line in data
                ):
                    encontrado = True
                    break
            if not encontrado:
                faltando.append(alim)
        return faltando

    def update_subestacoes_list(self):
        """Atualiza a lista de subestações únicas dos alimentadores selecionados."""
        alimentadores = [self.field_alimentador.currentText().strip()] + [
            self.list_alimentadores_benef.item(i).text().strip()
            for i in range(self.list_alimentadores_benef.count())
        ]
        ses = []
        for alim in alimentadores:
            if not alim:
                continue
            dados = self.support_manager.dados_alimentador.get(alim)
            se = dados.get("SE") if dados else ""
            if se and se not in ses:
                ses.append(se)
        self.list_subestacoes.clear()
        self.list_subestacoes.addItems(ses)

    def populate_combo_nome_projeto(self, nomes_extra=None):
        """Atualiza o combo de nomes de projeto com dados da planilha ou banco."""
        combo = getattr(self, "combo_nome_projeto", None)
        if combo is None:
            return

        nomes = []

        if nomes_extra:
            nomes.extend([str(n).strip() for n in nomes_extra if str(n).strip()])

        support_names = []
        if hasattr(self.support_manager, "nomes_projetos_pre_definidos"):
            support_names = self.support_manager.nomes_projetos_pre_definidos
        else:
            support_names = self.support_manager.dados_alimentador.get("nomes_projetos_pre_definidos", [])
        nomes.extend([str(n).strip() for n in support_names if str(n).strip()])

        if getattr(self.db_manager, "conn", None):
            try:
                nomes_db = self.db_manager.get_distinct_values("nome_projeto")
            except Exception:
                nomes_db = []
            nomes.extend([str(n).strip() for n in nomes_db if str(n).strip()])

        vistos = set()
        nomes_normalizados = []
        melhorias_inserido = False
        for nome in nomes:
            chave = nome.upper()
            if chave in vistos:
                continue
            if chave == "MELHORIAS AL":
                if not melhorias_inserido:
                    nomes_normalizados.append("Melhorias AL")
                    melhorias_inserido = True
                vistos.add(chave)
                continue
            nomes_normalizados.append(nome)
            vistos.add(chave)

        if not melhorias_inserido:
            nomes_normalizados.append("Melhorias AL")

        previous = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(nomes_normalizados)

        if previous:
            idx = combo.findText(previous)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(-1)
        else:
            combo.setCurrentIndex(-1)

        combo.blockSignals(False)

    def _preencher_nome_projeto_auto(self, texto):
        """Preenche automaticamente o campo de projeto ao selecionar 'Melhorias AL'."""
        if not hasattr(self, "field_projeto"):
            return

        texto_normalizado = str(texto or "").strip()
        if texto_normalizado.upper() == "MELHORIAS AL":
            self.field_projeto.setText("Melhorias_AL_")

    def buscar_projetos(self):
        from ui.main_window import legacy_module
        ProjectSelectionDialog = legacy_module().ProjectSelectionDialog

        dialog = ProjectSelectionDialog(self.db_manager, self)
        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            projeto_selecionado = dialog.selected_project
            if projeto_selecionado:
                self.field_projeto.setText(projeto_selecionado)
                self.carregar_dados_projeto(projeto_selecionado)

    def carregar_dados_projeto(self, nome_projeto):
        if not self.ensure_db_connected():
            return
        try:
            obras = self.db_manager.fetch_by_project(nome_projeto)
            obra = obras[0] if obras else None
            if obra:
                cols = self.db_manager.get_column_names()
                self.field_ano.setCurrentText(str(obra[cols.index("ano_")]))
                self.field_alimentador.setCurrentText(obra[cols.index("alimentador_principal")])
                self.field_regional.setText(obra[cols.index("nome_regional")])
                self.field_superintendencia.setText(obra[cols.index("nome_superintendencia")])
                self.field_tensao.setText(obra[cols.index("nivel_tensao_obra")])
                if "tensao_operacao" in cols:
                    self.field_tensao_operacao.setText(obra[cols.index("tensao_operacao")])
                else:
                    self.field_tensao_operacao.setText(obra[cols.index("nivel_tensao_obra")])
                self.field_se.setText(obra[cols.index("subestacao")])
                novo_item = self.calcular_numero_item(nome_projeto)
                self.field_item.setText(str(novo_item))
            else:
                QtWidgets.QMessageBox.warning(self, "Aviso", "Nenhuma obra encontrada para o projeto selecionado.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao carregar dados do projeto: {str(e)}")
