"""Mixin Ganhos -- 16 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 4).
"""
from __future__ import annotations

import math
import os
import re
import sys
import subprocess
import tempfile
from typing import Any

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QStyle


class GanhosMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def _ganhos_folder(self) -> str:
        return self.field_caminho_pasta.text().strip() if hasattr(self, "field_caminho_pasta") else ""  # [RB-RESTORE-OLD]

    def _schedule_ganhos_refresh(self) -> None:
        if getattr(self, "_ganhos_refresh_pending", False):
            return
        self._ganhos_refresh_pending = True
        QtCore.QTimer.singleShot(150, self._flush_ganhos_refresh)  # [RB-RESTORE-OLD]

    def _flush_ganhos_refresh(self) -> None:
        self._ganhos_refresh_pending = False
        self.refresh_action_availability()  # [RB-RESTORE-OLD]

    def _validate_ganhos_files(self, action_name: str, required_files: list[str]) -> bool:
        from ui.main_window import legacy_module
        _l = legacy_module()
        DataStateManager = _l.DataStateManager
        show_user_error = _l.show_user_error
        ler_arquivo_com_codificacoes = _l.ler_arquivo_com_codificacoes
        """Garante arquivos mínimos antes de ações de ganhos."""  # [RB-1.1]
        pasta = self._ganhos_folder()  # [RB-RESTORE-OLD]
        if not pasta or not os.path.isdir(pasta):
            self._set_data_state(
                "ganhos",
                DataStateManager.INVALIDADO,
                path=pasta,
                error="Pasta de ganhos inexistente ou inválida.",
            )
            show_user_error(
                "Pasta de ganhos inválida",
                f"Pasta não encontrada: {pasta}",
                "Selecione uma pasta válida para os arquivos de ganhos.",
                parent=self,
            )
            return False
        missing = [
            name
            for name in required_files
            if not os.path.isfile(os.path.join(pasta, name))
        ]
        if missing:
            self._set_data_state(
                "ganhos",
                DataStateManager.INVALIDADO,
                path=pasta,
                error="Arquivos ausentes: " + ", ".join(missing),
                version_token=self._compute_folder_token(pasta, required_files),
            )
            show_user_error(
                "Pré-requisito ausente",
                "Arquivos técnicos obrigatórios não encontrados:\n"
                f"- {', '.join(missing)}",
                "Verifique a pasta e selecione novamente.",
                parent=self,
            )
            return False
        unreadable = []
        for name in required_files:
            caminho = os.path.join(pasta, name)
            try:
                ler_arquivo_com_codificacoes(caminho)
            except Exception as exc:
                unreadable.append((name, str(exc)))
        if unreadable:
            detalhes = "\n".join(f"{nome}: {erro}" for nome, erro in unreadable)
            self._set_data_state(
                "ganhos",
                DataStateManager.INVALIDADO,
                path=pasta,
                error="Falha ao ler arquivos técnicos.",
                version_token=self._compute_folder_token(pasta, required_files),
            )
            show_user_error(
                "Erro ao ler arquivos técnicos",
                detalhes,
                "Verifique a codificação e integridade dos arquivos.",
                parent=self,
            )
            return False
        return True

    def load_last_ganhos_path(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        DataStateManager = _l.DataStateManager
        show_user_error = _l.show_user_error
        """Carrega automaticamente o último caminho salvo da pasta dos arquivos para a aba Ganhos"""
        ultimo_caminho = self.config.get("caminho_pasta_ganhos", "")
        if ultimo_caminho:
            if os.path.exists(ultimo_caminho):
                self.field_caminho_pasta.setText(ultimo_caminho)
                self._update_ganhos_path_state(ultimo_caminho)  # [RB-1.1]
                self.refresh_action_availability()  # [RB-RESTORE-OLD]
            else:
                self._set_data_state(
                    "ganhos",
                    DataStateManager.INVALIDADO,
                    path=ultimo_caminho,
                    error="Caminho salvo não existe.",
                )  # [RB-1.1]
                show_user_error(
                    "Pasta de ganhos inválida",
                    f"O caminho salvo '{ultimo_caminho}' não existe.",
                    "Selecione uma nova pasta.",
                    parent=self,
                )
        else:
            self._set_data_state(
                "ganhos", DataStateManager.NAO_CARREGADO, path=""
            )  # [RB-1.1]
            self.field_caminho_pasta.clear()  # Se não houver caminho salvo, limpa o campo
            self.refresh_action_availability()  # [RB-RESTORE-OLD]

    def setup_tab_ganhos(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        _as_tool_button = _l._as_tool_button
        scroll_area_ganhos = QtWidgets.QScrollArea(self.tab_ganhos)
        scroll_area_ganhos.setWidgetResizable(True)
        scroll_area_ganhos.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        scroll_area_ganhos.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        container = QtWidgets.QWidget()
        self.ganhos_layout = QtWidgets.QVBoxLayout(container)
        scroll_area_ganhos.setWidget(container)
        self.group_param = QtWidgets.QGroupBox("Parâmetros")
        grid = QtWidgets.QGridLayout(self.group_param)

        # Campos antes/depois
        self.field_contas_antes = QtWidgets.QLineEdit()
        self.field_contas_depois = QtWidgets.QLineEdit()
        self.field_carregamento_antes = QtWidgets.QLineEdit()
        self.field_carregamento_depois = QtWidgets.QLineEdit()
        self.field_perdas_antes = QtWidgets.QLineEdit()
        self.field_perdas_depois = QtWidgets.QLineEdit()
        self.field_tensao_media_antes = QtWidgets.QLineEdit()
        self.field_tensao_media_depois = QtWidgets.QLineEdit()
        self.field_tensao_min_antes = QtWidgets.QLineEdit()
        self.field_tensao_min_depois = QtWidgets.QLineEdit()
        self.field_tensao_min_linha_antes = QtWidgets.QLineEdit()
        self.field_tensao_min_linha_depois = QtWidgets.QLineEdit()
        self.field_chi_antes = QtWidgets.QLineEdit()
        self.field_chi_depois = QtWidgets.QLineEdit()
        self.field_ci_antes = QtWidgets.QLineEdit()
        self.field_ci_depois = QtWidgets.QLineEdit()
        self.field_tensao_max_antes = QtWidgets.QLineEdit()
        self.field_tensao_max_depois = QtWidgets.QLineEdit()

        # Campos extras
        self.field_contas_benef = QtWidgets.QLineEdit()
        self.field_cc_benef_chi_ci = QtWidgets.QLineEdit()
        # Campos para registrar os ganhos totais por alimentador
        self.field_ganhos_totais_antes = QtWidgets.QLineEdit()
        self.field_ganhos_totais_depois = QtWidgets.QLineEdit()

        pares = [
            ("Contas Contratos", self.field_contas_antes, self.field_contas_depois),
            ("Carregamento (%)", self.field_carregamento_antes, self.field_carregamento_depois),
            ("Perdas kW", self.field_perdas_antes, self.field_perdas_depois),
            ("Tensão Média (pu)", self.field_tensao_media_antes, self.field_tensao_media_depois),
            ("Tensão Min. (pu)", self.field_tensao_min_antes, self.field_tensao_min_depois),
            ("Tensão Linha Min. (pu)", self.field_tensao_min_linha_antes, self.field_tensao_min_linha_depois),
            ("CHI", self.field_chi_antes, self.field_chi_depois),
            ("CI", self.field_ci_antes, self.field_ci_depois),
            ("Tensão Máxima", self.field_tensao_max_antes, self.field_tensao_max_depois),
            ("Ganhos Totais", self.field_ganhos_totais_antes, self.field_ganhos_totais_depois),
        ]

        # Cabeçalho
        header_parametro = QtWidgets.QLabel("Parâmetro")
        header_parametro.setFixedHeight(20)
        header_parametro.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header_antes = QtWidgets.QLabel("Antes")
        header_antes.setFixedHeight(20)
        header_antes.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header_depois = QtWidgets.QLabel("Depois")
        header_depois.setFixedHeight(20)
        header_depois.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(header_parametro, 0, 0)
        grid.addWidget(header_antes, 0, 1)
        grid.addWidget(header_depois, 0, 2)

        for i, (lbl, antes, depois) in enumerate(pares, start=1):
            grid.addWidget(QtWidgets.QLabel(lbl), i, 0)
            grid.addWidget(antes, i, 1)
            grid.addWidget(depois, i, 2)

        row = len(pares) + 1
        grid.addWidget(QtWidgets.QLabel("Contas Contratos Beneficiadas"), row, 0)
        grid.addWidget(self.field_contas_benef, row, 1, 1, 2)
        row += 1
        grid.addWidget(QtWidgets.QLabel("CC_benef_CHI_CI"), row, 0)
        grid.addWidget(self.field_cc_benef_chi_ci, row, 1, 1, 2)
        row += 1
        self.btn_limpar_ganhos = QtWidgets.QPushButton("Limpar Ganhos")
        self.btn_limpar_ganhos.setAutoDefault(False)
        self.btn_limpar_ganhos.clicked.connect(self.limpar_campos_ganhos)
        grid.addWidget(
            self.btn_limpar_ganhos,
            row,
            0,
            1,
            3,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter,
        )
        self.btn_limpar_ganhos.hide()

        self.ganhos_layout.addWidget(self.group_param)

        self.btn_seta_antes = _as_tool_button(
            None,
            self,
            "Inserir Ganhos Antes",
            QStyle.StandardPixmap.SP_ArrowUp,
            self.preencher_campos_antes,
        )
        self.btn_seta_depois = _as_tool_button(
            None,
            self,
            "Inserir Ganhos Depois",
            QStyle.StandardPixmap.SP_ArrowUp,
            self.preencher_campos_depois,
        )

        setas_layout = QtWidgets.QHBoxLayout()
        setas_layout.addWidget(self.btn_seta_antes)
        setas_layout.addWidget(self.btn_seta_depois)
        self.ganhos_layout.addLayout(setas_layout)

        self.group_ganhos_atuais = QtWidgets.QGroupBox("Ganhos Atuais")
        layout_atuais = QtWidgets.QFormLayout(self.group_ganhos_atuais)
        self.edit_tensao_reg_atual = QtWidgets.QLineEdit()
        self.edit_carreg_reg_atual = QtWidgets.QLineEdit()
        self.edit_ganhos_totais_atual = QtWidgets.QLineEdit()
        layout_atuais.addRow(
            "Mín/Máx Tensão Registrada Atual:", self.edit_tensao_reg_atual
        )
        layout_atuais.addRow(
            "Carregamento Registrado Atual:", self.edit_carreg_reg_atual
        )
        layout_atuais.addRow(
            "Ganhos Totais (Atual):", self.edit_ganhos_totais_atual
        )
        self.btn_preencher_atuais = _as_tool_button(
            None,
            self,
            "Preencher parâmetros atuais",
            QStyle.StandardPixmap.SP_ArrowUp,
            self.preencher_parametros_atuais,
        )
        hbox_atuais = QtWidgets.QHBoxLayout()
        hbox_atuais.addWidget(self.group_ganhos_atuais)
        hbox_atuais.addWidget(self.btn_preencher_atuais)
        self.ganhos_layout.addLayout(hbox_atuais)

        self.field_caminho_pasta = QtWidgets.QLineEdit()
        self.field_caminho_pasta.textChanged.connect(
            self._schedule_ganhos_refresh
        )  # [RB-RESTORE-OLD]
        caminho_layout = QtWidgets.QHBoxLayout()
        caminho_layout.addWidget(QtWidgets.QLabel("Caminho da Pasta dos Arquivos"))
        caminho_layout.addWidget(self.field_caminho_pasta)
        btn_selecionar_pasta = _as_tool_button(
            None,
            self,
            "Selecionar Pasta",
            QStyle.StandardPixmap.SP_DirOpenIcon,
            self.selecionar_pasta_arquivos,
        )
        caminho_layout.addWidget(btn_selecionar_pasta)
        self.ganhos_layout.addLayout(caminho_layout)

        self.label_planejamento = QtWidgets.QLabel()
        self.ganhos_layout.addWidget(self.label_planejamento)

        self.label_posterga = QtWidgets.QLabel()
        self.ganhos_layout.addWidget(self.label_posterga)

        self.ganhos_layout.addStretch(1)

        self.btn_ganhos_massa = QtWidgets.QPushButton("Ganhos em Massa")
        self.btn_ganhos_massa.setAutoDefault(False)
        self.btn_ganhos_massa.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Fixed,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.btn_ganhos_massa.setMinimumWidth(150)  # ajuste conforme necessário
        self.btn_ganhos_massa.setMinimumHeight(32)  # altura padrão confortável
        self.btn_ganhos_massa.clicked.connect(self.preencher_ganhos_massa)

        aba_ganhos_layout = QtWidgets.QVBoxLayout(self.tab_ganhos)
        aba_ganhos_layout.addWidget(scroll_area_ganhos)
        aba_ganhos_layout.addWidget(self.btn_ganhos_massa)

    def _parse_ganhos_totais_depois(self, txt: str) -> dict[str, dict[str, float]]:
        """Wrapper -- delega ao core/services/relatorio_criterios_service (parser V4)."""
        from core.services.relatorio_criterios_service import parse_ganhos_rsplit as _impl
        return _impl(txt)

    def _parse_ganhos_totais_metricas(self, ganhos_str: str) -> dict[str, dict[str, float]]:
        """Wrapper -- delega ao core/services/relatorio_criterios_service (parser V5)."""
        from core.services.relatorio_criterios_service import parse_ganhos_metricas_float as _impl
        return _impl(ganhos_str)

    def limpar_campos_ganhos(self):
        """Limpa todos os campos da aba Ganhos."""
        self.field_contas_antes.clear()
        self.field_contas_depois.clear()
        self.field_carregamento_antes.clear()
        self.field_carregamento_depois.clear()
        self.field_perdas_antes.clear()
        self.field_perdas_depois.clear()
        self.field_tensao_media_antes.clear()
        self.field_tensao_media_depois.clear()
        self.field_tensao_min_antes.clear()
        self.field_tensao_min_depois.clear()
        self.field_tensao_min_linha_antes.clear()
        self.field_tensao_min_linha_depois.clear()
        self.field_chi_antes.clear()
        self.field_chi_depois.clear()
        self.field_ci_antes.clear()
        self.field_ci_depois.clear()
        self.field_tensao_max_antes.clear()
        self.field_tensao_max_depois.clear()
        self.field_contas_benef.clear()
        self.field_cc_benef_chi_ci.clear()
        self.edit_tensao_reg_atual.clear()
        self.edit_carreg_reg_atual.clear()
        self.field_ganhos_totais_antes.clear()
        self.field_ganhos_totais_depois.clear()
        self.edit_ganhos_totais_atual.clear()

    def gerar_ganhos_totais(
        self,
        alimentadores,
        data_flow,
        data_topo,
        data_conf,
        projeto_investimento,
        etapa="antes",
    ):
        """Gera string resumindo todos os ganhos por alimentador."""
        demanda_max_por_alim = self.calc_manager.calcular_demanda_maxima(
            data_flow, alimentadores
        )
        resultados = []
        for alim in alimentadores:
            tensao_min, tensao_media = self.calc_manager.calcular_tensoes(data_flow, [alim])
            tensao_min_linha = self.calc_manager.calcular_tensao_linha_minima(data_flow, [alim])
            tensao_max, _ = self.calc_manager.calcular_tensoes_max(data_flow, [alim])
            carreg = self.calc_manager.calcular_carregamento(data_topo, [alim])
            _, perda = self.calc_manager.calcular_perdas(data_flow, [alim])
            cont_antes, cont_depois = self.calc_manager.calcular_contas_contratos(data_conf, [alim])
            chi, ci = self.calc_manager.calcular_chi_ci(data_conf, [alim])
            if etapa == "antes":
                benef = self.calc_manager.calcular_contas_contratos_beneficiadas(
                    data_topo, data_conf, [alim], projeto_investimento
                )
                resultados.extend([
                    f"{alim}_contas_{cont_antes}",
                    f"{alim}_contasbenef_{benef}",
                ])
            else:
                resultados.append(f"{alim}_contas_{cont_depois}")
            resultados.extend([
                f"{alim}_carregamento_{round(carreg or 0, 2)}",
                f"{alim}_perdas_{round(perda or 0, 2)}",
                f"{alim}_tensaomedia_{round(tensao_media or 0, 4)}",
                f"{alim}_tensaominima_{round(tensao_min or 0, 4)}",
                f"{alim}_tensaolinhaminima_{round(tensao_min_linha or 0, 4)}",
                f"{alim}_tensaomax_{round(tensao_max or 0, 4)}",
                f"{alim}_chi_{round(chi or 0, 4)}",
                f"{alim}_ci_{round(ci or 0, 4)}",
            ])
            demanda_max_mw = demanda_max_por_alim.get(alim)
            if demanda_max_mw is not None:
                valor_formatado = f"{demanda_max_mw:.2f}"
                resultados.append(f"{alim}_Demand_MAX_{valor_formatado}")
        return ";".join(resultados)

    def gerar_ganhos_totais_atual(self, alimentadores, tensao_min, tensao_min_linha, tensao_max, carregamento):
        """Gera string de ganhos atuais para cada alimentador."""
        resultados = []
        for alim in alimentadores:
            resultados.extend([
                f"{alim}_carrg_atual_{round(carregamento or 0, 4)}",
                f"{alim}_tensao_min_atual_{round(tensao_min or 0, 4)}",
                f"{alim}_tensao_linha_min_atual_{round(tensao_min_linha or 0, 4)}",
                f"{alim}_tensao_max_atual_{round(tensao_max or 0, 4)}",
            ])
        return ";".join(resultados)

    def preencher_campos_antes(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        DataStateManager = _l.DataStateManager
        LOGGER = _l.LOGGER
        show_user_error = _l.show_user_error
        carregar_arquivos = _l.carregar_arquivos
        pasta = self._ganhos_folder()  # [RB-RESTORE-OLD]
        if not self._path_exists(pasta):
            QtWidgets.QMessageBox.warning(
                self, "Aviso", "Selecione uma pasta válida para os arquivos."
            )  # [RB-RESTORE-OLD]
            return
        if not self._validate_ganhos_files(
            "Preencher ganhos 'Antes'",
            ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"],
        ):  # [RB-1.1]
            return

        # Identificar alimentadores considerados
        alimentadores_considerados = self.get_alimentadores()
        if not alimentadores_considerados:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Selecione ao menos um alimentador para preencher os ganhos 'Antes'.")
            return

        try:
            dados = carregar_arquivos(pasta, ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"])
            data_flow = dados["FlowMT.TXT"]
            data_topo = dados["Topologia.TXT"]
            data_conf = dados["Confiabilidade.TXT"]
            if not self._update_tecnico_state(
                pasta,
                ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"],
                dados,
            ):  # [RB-1.1]
                show_user_error(
                    "Arquivos técnicos inválidos",
                    "Arquivos técnicos não puderam ser validados.",
                    "Verifique a pasta e tente novamente.",
                    parent=self,
                )
                return

            faltando = self.alimentadores_nos_arquivos(
                [data_flow, data_topo, data_conf], alimentadores_considerados
            )
            if faltando:
                alimentadores_considerados = [
                    a for a in alimentadores_considerados if a not in faltando
                ]
                if not alimentadores_considerados:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Ganhos",
                        "Nenhum dos alimentadores informados foi encontrado nos arquivos.",
                    )
                    return

            faltando = self.alimentadores_nos_arquivos(
                [data_flow, data_topo, data_conf], alimentadores_considerados
            )
            if faltando:
                # Alimentadores ausentes são ignorados silenciosamente
                alimentadores_considerados = [
                    a for a in alimentadores_considerados if a not in faltando
                ]
                if not alimentadores_considerados:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Ganhos",
                        "Nenhum dos alimentadores informados foi encontrado nos arquivos.",
                    )
                    return

            # Depuração: verificar se os arquivos foram carregados corretamente
            LOGGER.debug("Conteúdo FlowMT.TXT: %s", data_flow[:10])
            LOGGER.debug("Conteúdo Topologia.TXT: %s", data_topo[:10])
            LOGGER.debug("Conteúdo Confiabilidade.TXT: %s", data_conf[:10])

            # Extração de dados
            tensao_min, tensao_media = self.calc_manager.calcular_tensoes(data_flow, alimentadores_considerados)
            tensao_min_linha = self.calc_manager.calcular_tensao_linha_minima(data_flow, alimentadores_considerados)
            tensao_max, _ = self.calc_manager.calcular_tensoes_max(data_flow, alimentadores_considerados)
            carregamento = self.calc_manager.calcular_carregamento(data_topo, alimentadores_considerados)
            perdas_por_patamar, maior_perda = self.calc_manager.calcular_perdas(data_flow, alimentadores_considerados)
            contas_antes, _ = self.calc_manager.calcular_contas_contratos(data_conf, alimentadores_considerados)
            
            # Obter o projeto de investimento para o cálculo dos contratos beneficiados
            projeto_investimento = self.field_projeto_investimento.currentText().strip()
            total_benef = self.calc_manager.calcular_contas_contratos_beneficiadas(
                data_topo, data_conf, alimentadores_considerados, projeto_investimento
            )
            
            chi_total, ci_total = self.calc_manager.calcular_chi_ci(data_conf, alimentadores_considerados)

            # Depuração dos valores extraídos
            LOGGER.debug(
                "Tensão mínima: %s, Tensão média: %s",
                tensao_min,
                tensao_media,
            )
            LOGGER.debug("Carregamento: %s, Maior perda: %s", carregamento, maior_perda)
            LOGGER.debug(
                "Contas (previas): %s, Contas Beneficiadas: %s, CHI: %s, CI: %s",
                contas_antes,
                total_benef,
                chi_total,
                ci_total,
            )

            # Preenchimento dos campos da aba "Ganhos"
            self.field_tensao_min_antes.setText(str(round(tensao_min, 4)) if tensao_min is not None else "")
            self.field_tensao_media_antes.setText(str(round(tensao_media, 4)) if tensao_media is not None else "")
            self.field_tensao_min_linha_antes.setText(str(round(tensao_min_linha, 4)) if tensao_min_linha is not None else "")
            self.field_tensao_max_antes.setText(str(round(tensao_max, 4)) if tensao_max is not None else "")
            self.field_carregamento_antes.setText(str(round(carregamento, 2)) if carregamento is not None else "")
            self.field_perdas_antes.setText(str(round(maior_perda, 2)) if maior_perda is not None else "")
            self.field_contas_antes.setText(str(contas_antes) if contas_antes is not None else "")
            # Novo campo: Contas Contratos Beneficiadas
            self.field_contas_benef.setText(str(total_benef) if total_benef is not None else "")
            self.field_chi_antes.setText(str(round(chi_total, 4)) if chi_total is not None else "")
            self.field_ci_antes.setText(str(round(ci_total, 4)) if ci_total is not None else "")
            # Novo campo: CC_benef_CHI_CI – se não houver cálculo específico, deixa em branco ou atribui um valor padrão
            self.field_cc_benef_chi_ci.setText("")

            # Compilação de ganhos por alimentador
            ganhos_antes = self.gerar_ganhos_totais(
                alimentadores_considerados,
                data_flow,
                data_topo,
                data_conf,
                projeto_investimento,
                etapa="antes",
            )
            self.field_ganhos_totais_antes.setText(ganhos_antes)

            QtWidgets.QMessageBox.information(self, "Sucesso", "Ganhos 'Antes' inseridos com sucesso!")

        except FileNotFoundError as e:
            LOGGER.exception("Arquivo técnico ausente.")
            self._set_data_state(
                "tecnico_txt",
                DataStateManager.INVALIDADO,
                path=pasta,
                error=str(e),
            )
            show_user_error(
                "Arquivo técnico ausente",
                f"Arquivo {e.args[0]} não encontrado na pasta.",
                "Verifique a pasta dos arquivos técnicos.",
                parent=self,
            )
        except Exception as e:
            LOGGER.exception("Erro ao preencher ganhos 'Antes'.")
            self._set_data_state(
                "tecnico_txt",
                DataStateManager.INVALIDADO,
                path=pasta,
                error=str(e),
            )
            show_user_error(
                "Erro ao preencher ganhos 'Antes'",
                str(e),
                "Verifique os arquivos técnicos e tente novamente.",
                parent=self,
            )

    def preencher_campos_depois(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        DataStateManager = _l.DataStateManager
        LOGGER = _l.LOGGER
        show_user_error = _l.show_user_error
        carregar_arquivos = _l.carregar_arquivos
        """
        Preenche os campos da aba 'Ganhos Depois' com base nos arquivos de dados processados.
        """
        """" Selecionar obra
        indices = self.table_obras.selectionModel().selectedRows()
        if len(indices) != 1:
            QtWidgets.QMessageBox.information(self, "Ganhos", "Selecione exatamente uma obra para preencher os ganhos 'Depois'.")
            return"""


        # Verifica se a pasta foi definida
        pasta = self._ganhos_folder()  # [RB-RESTORE-OLD]
        if not self._path_exists(pasta):
            QtWidgets.QMessageBox.warning(
                self, "Aviso", "Selecione uma pasta válida para os arquivos."
            )  # [RB-RESTORE-OLD]
            return
        if not self._validate_ganhos_files(
            "Preencher ganhos 'Depois'",
            ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"],
        ):  # [RB-1.1]
            return

        # Identificar alimentadores considerados
        alimentadores_considerados = self.get_alimentadores()
        if not alimentadores_considerados:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Selecione ao menos um alimentador para preencher os ganhos 'Depois'.")
            return

        try:
            dados = carregar_arquivos(pasta, ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"])
            data_flow = dados["FlowMT.TXT"]
            data_topo = dados["Topologia.TXT"]
            data_conf = dados["Confiabilidade.TXT"]
            if not self._update_tecnico_state(
                pasta,
                ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"],
                dados,
            ):  # [RB-1.1]
                show_user_error(
                    "Arquivos técnicos inválidos",
                    "Arquivos técnicos não puderam ser validados.",
                    "Verifique a pasta e tente novamente.",
                    parent=self,
                )
                return

            faltando = self.alimentadores_nos_arquivos(
                [data_flow, data_topo, data_conf], alimentadores_considerados
            )
            if faltando:
                alimentadores_considerados = [
                    a for a in alimentadores_considerados if a not in faltando
                ]
                if not alimentadores_considerados:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Ganhos",
                        "Nenhum dos alimentadores informados foi encontrado nos arquivos.",
                    )
                    return

            # Depuração: verificar se os arquivos foram carregados corretamente
            LOGGER.debug("Conteúdo FlowMT.TXT: %s", data_flow[:10])
            LOGGER.debug("Conteúdo Topologia.TXT: %s", data_topo[:10])
            LOGGER.debug("Conteúdo Confiabilidade.TXT: %s", data_conf[:10])

            # Extração de dados
            tensao_min, tensao_media = self.calc_manager.calcular_tensoes(data_flow, alimentadores_considerados)
            tensao_min_linha = self.calc_manager.calcular_tensao_linha_minima(data_flow, alimentadores_considerados)
            tensao_max, _ = self.calc_manager.calcular_tensoes_max(data_flow, alimentadores_considerados)
            carregamento = self.calc_manager.calcular_carregamento(data_topo, alimentadores_considerados)
            perdas_por_patamar, maior_perda = self.calc_manager.calcular_perdas(data_flow, alimentadores_considerados)
            contas_antes, contas_depois = self.calc_manager.calcular_contas_contratos(data_conf, alimentadores_considerados)
            chi_total, ci_total = self.calc_manager.calcular_chi_ci(data_conf, alimentadores_considerados)

            # Depuração dos valores extraídos
            LOGGER.debug(
                "Tensão mínima: %s, Tensão média: %s",
                tensao_min,
                tensao_media,
            )
            LOGGER.debug("Carregamento: %s, Maior perda: %s", carregamento, maior_perda)
            LOGGER.debug(
                "Contas Antes: %s, Contas Depois: %s, CHI: %s, CI: %s",
                contas_antes,
                contas_depois,
                chi_total,
                ci_total,
            )

            # Preenchimento dos campos da aba "Ganhos Depois"
            self.field_tensao_min_depois.setText(str(round(tensao_min, 4)) if tensao_min is not None else "")
            self.field_tensao_media_depois.setText(str(round(tensao_media, 4)) if tensao_media is not None else "")
            self.field_tensao_min_linha_depois.setText(str(round(tensao_min_linha, 4)) if tensao_min_linha is not None else "")
            self.field_tensao_max_depois.setText(str(round(tensao_max, 4)) if tensao_max is not None else "")
            self.field_carregamento_depois.setText(str(round(carregamento, 4)) if carregamento is not None else "")
            self.field_perdas_depois.setText(str(round(maior_perda, 4)) if maior_perda is not None else "")
            self.field_contas_depois.setText(str(contas_depois) if contas_depois is not None else "")
            self.field_chi_depois.setText(str(round(chi_total, 4)) if chi_total is not None else "")
            self.field_ci_depois.setText(str(round(ci_total, 4)) if ci_total is not None else "")

            projeto_invest = self.field_projeto_investimento.currentText().strip()
            ganhos_depois = self.gerar_ganhos_totais(
                alimentadores_considerados,
                data_flow,
                data_topo,
                data_conf,
                projeto_invest,
                etapa="depois",
            )
            self.field_ganhos_totais_depois.setText(ganhos_depois)

            QtWidgets.QMessageBox.information(self, "Sucesso", "Ganhos 'Depois' inseridos com sucesso!")

        except FileNotFoundError as e:
            LOGGER.exception("Arquivo técnico ausente.")
            self._set_data_state(
                "tecnico_txt",
                DataStateManager.INVALIDADO,
                path=pasta,
                error=str(e),
            )
            show_user_error(
                "Arquivo técnico ausente",
                f"Arquivo {e.args[0]} não encontrado na pasta.",
                "Verifique a pasta dos arquivos técnicos.",
                parent=self,
            )
        except Exception as e:
            LOGGER.exception("Erro ao preencher ganhos 'Depois'.")
            self._set_data_state(
                "tecnico_txt",
                DataStateManager.INVALIDADO,
                path=pasta,
                error=str(e),
            )
            show_user_error(
                "Erro ao preencher ganhos 'Depois'",
                str(e),
                "Verifique os arquivos técnicos e tente novamente.",
                parent=self,
            )

    def preencher_parametros_atuais(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        DataStateManager = _l.DataStateManager
        LOGGER = _l.LOGGER
        show_user_error = _l.show_user_error
        carregar_arquivos = _l.carregar_arquivos
        pasta = self._ganhos_folder()  # [RB-RESTORE-OLD]
        if not self._path_exists(pasta):
            QtWidgets.QMessageBox.warning(
                self, "Aviso", "Selecione uma pasta válida para os arquivos."
            )  # [RB-RESTORE-OLD]
            return
        if not self._validate_ganhos_files(
            "Preencher parâmetros atuais",
            ["FlowMT.TXT", "Topologia.TXT"],
        ):  # [RB-1.1]
            return
        try:
            dados = carregar_arquivos(pasta, ["FlowMT.TXT", "Topologia.TXT"])
            data_flow = dados["FlowMT.TXT"]
            data_topo = dados["Topologia.TXT"]
            if not self._update_tecnico_state(
                pasta,
                ["FlowMT.TXT", "Topologia.TXT"],
                dados,
            ):  # [RB-1.1]
                show_user_error(
                    "Arquivos técnicos inválidos",
                    "Arquivos técnicos não puderam ser validados.",
                    "Verifique a pasta e tente novamente.",
                    parent=self,
                )
                return
            alimentadores = self.get_alimentadores()
            tensao_min, _ = self.calc_manager.calcular_tensoes(data_flow, alimentadores)
            tensao_min_linha = self.calc_manager.calcular_tensao_linha_minima(data_flow, alimentadores)
            tensao_max, _ = self.calc_manager.calcular_tensoes_max(data_flow, alimentadores)
            carregamento = self.calc_manager.calcular_carregamento(data_topo, alimentadores)
            # Preenche o campo com ambos os valores: tensão mínima e tensão máxima.
            self.edit_tensao_reg_atual.setText(
                f"{round(tensao_min or 0, 4)}/{round(tensao_max or 0, 4)}"
            )
            self.edit_carreg_reg_atual.setText(str(round(carregamento or 0, 4)))
            ganhos_atual = self.gerar_ganhos_totais_atual(
                alimentadores,
                tensao_min,
                tensao_min_linha,
                tensao_max,
                carregamento,
            )
            self.edit_ganhos_totais_atual.setText(ganhos_atual)
        except FileNotFoundError as e:
            LOGGER.exception("Arquivo técnico ausente.")
            self._set_data_state(
                "tecnico_txt",
                DataStateManager.INVALIDADO,
                path=pasta,
                error=str(e),
            )
            show_user_error(
                "Arquivo técnico ausente",
                f"Arquivo {e.args[0]} não encontrado na pasta.",
                "Verifique a pasta dos arquivos técnicos.",
                parent=self,
            )
        except Exception as e:
            LOGGER.exception("Erro ao preencher parâmetros atuais.")
            self._set_data_state(
                "tecnico_txt",
                DataStateManager.INVALIDADO,
                path=pasta,
                error=str(e),
            )
            show_user_error(
                "Erro ao preencher parâmetros atuais",
                str(e),
                "Verifique os arquivos técnicos e tente novamente.",
                parent=self,
            )

    def preencher_ganhos_massa(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        DataStateManager = _l.DataStateManager
        LOGGER = _l.LOGGER
        show_user_error = _l.show_user_error
        GanhosMassaDialog = _l.GanhosMassaDialog
        _format_processing_summary = _l._format_processing_summary
        _row_has_any_key = _l._row_has_any_key
        _row_integrity_reasons = _l._row_integrity_reasons
        _selected_ids_from_view = _l._selected_ids_from_view
        get_row_value_by_key = _l.get_row_value_by_key
        sort_processing_rows = _l.sort_processing_rows
        carregar_arquivos = _l.carregar_arquivos
        pasta = self._ganhos_folder()  # [RB-RESTORE-OLD]
        if not self._path_exists(pasta):
            QtWidgets.QMessageBox.warning(
                self, "Aviso", "Selecione uma pasta válida para os arquivos."
            )  # [RB-RESTORE-OLD]
            return
        if not self.ensure_db_connected():  # [RB-RESTORE-OLD]
            return
        if not self._validate_ganhos_files(
            "Ganhos em massa",
            ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"],
        ):  # [RB-1.1]
            return

        indices = self.table_obras.selectedVisibleRows()
        if not indices:
            QtWidgets.QMessageBox.warning(self, "Aviso", "Selecione ao menos uma obra na tabela.")
            return

        targets, include_aprovadas, ignoradas_aprovadas = self._gate_aprovadas_for_action(
            "Ganhos em massa", self.table_obras
        )
        if not targets:
            return
        selected_ids = _selected_ids_from_view(self.table_obras)
        rows_sorted = sort_processing_rows(targets, selected_ids, include_aprovadas)


        dialog = GanhosMassaDialog(self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        calc_antes = dialog.check_antes.isChecked()
        calc_depois = dialog.check_depois.isChecked()
        calc_atuais = dialog.check_atuais.isChecked()

        if not any([calc_antes, calc_depois, calc_atuais]):
            QtWidgets.QMessageBox.information(self, "Aviso", "Nenhuma opção de ganho selecionada.")
            return

        # Desativa a seleção interativa de PI base durante o processamento em massa
        previous_prompt = self.calc_manager.prompt_pi_base
        self.calc_manager.prompt_pi_base = False

        for col in ("tensao_min_linha_inicial", "tensao_min_linha_final"):
            self.db_manager.add_column_if_missing(col)
        self.db_manager.update_columns()

        cols = self.db_manager.get_column_names()

        alimentadores_set = set()
        for row in rows_sorted:
            alim_principal = get_row_value_by_key(row, "alimentador_principal")
            benef = get_row_value_by_key(row, "alimentadores_beneficiados")
            for a in [alim_principal] + benef.split(';'):
                a = a.strip().lower()
                if a:
                    alimentadores_set.add(a)
        if alimentadores_set:
            try:
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, "Alimentadores Considerados.txt")
                with open(temp_path, "w", encoding="utf-8") as tmp:
                    tmp.write("\n".join(sorted(alimentadores_set)))
                if sys.platform.startswith("win"):
                    os.startfile(temp_path)
                else:
                    subprocess.run(["xdg-open", temp_path], check=False)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Aviso", f"Erro ao gerar o TXT: {str(e)}")

            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
            msg_box.setWindowTitle("Confirmar")
            msg_box.setText("Deseja prosseguir com a execução?")
            btn_atualizar = msg_box.addButton("Atualizar", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            btn_cancelar = msg_box.addButton("Cancelar", QtWidgets.QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()
            if msg_box.clickedButton() == btn_cancelar:
                self.calc_manager.prompt_pi_base = previous_prompt
                return



        try:
            dados = carregar_arquivos(pasta, ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"])
            data_flow = dados["FlowMT.TXT"]
            data_topo = dados["Topologia.TXT"]
            data_conf = dados["Confiabilidade.TXT"]
            if not self._update_tecnico_state(
                pasta,
                ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"],
                dados,
            ):  # [RB-1.1]
                show_user_error(
                    "Arquivos técnicos inválidos",
                    "Arquivos técnicos não puderam ser validados.",
                    "Verifique a pasta e tente novamente.",
                    parent=self,
                )
                self.calc_manager.prompt_pi_base = previous_prompt
                return
        except Exception as e:
            LOGGER.exception("Erro ao carregar arquivos técnicos.")
            self._set_data_state(
                "tecnico_txt",
                DataStateManager.INVALIDADO,
                path=pasta,
                error=str(e),
            )
            show_user_error(
                "Erro ao carregar arquivos",
                f"Erro ao carregar arquivos: {str(e)}",
                "Verifique a pasta e os arquivos técnicos.",
                parent=self,
            )
            self.calc_manager.prompt_pi_base = previous_prompt
            return



        processadas_ok = 0
        ignoradas_integridade = 0
        falhas: list[str] = []
        falhas_total = 0
        requires_municipio = any(
            _row_has_any_key(row, ["municipio", "município"]) for row in rows_sorted
        )

        for row in rows_sorted:
            integridade_reasons = _row_integrity_reasons(row, requires_municipio)
            if integridade_reasons:
                ignoradas_integridade += 1
                continue
            cod = get_row_value_by_key(row, "cod")
            alim_principal = get_row_value_by_key(row, "alimentador_principal")
            benef = get_row_value_by_key(row, "alimentadores_beneficiados")
            projeto_inv = get_row_value_by_key(row, "projeto_investimento")

            alimentadores = [
                a.strip().lower()
                for a in [alim_principal] + benef.split(";")
                if a.strip()
            ]


            try:
                tensao_min, tensao_media = self.calc_manager.calcular_tensoes(data_flow, alimentadores)
                tensao_min_linha = self.calc_manager.calcular_tensao_linha_minima(data_flow, alimentadores)
                tensao_max, _ = self.calc_manager.calcular_tensoes_max(data_flow, alimentadores)
                carregamento = self.calc_manager.calcular_carregamento(data_topo, alimentadores)
                _, maior_perda = self.calc_manager.calcular_perdas(data_flow, alimentadores)
                contas_antes, contas_depois = self.calc_manager.calcular_contas_contratos(data_conf, alimentadores)
                total_benef = self.calc_manager.calcular_contas_contratos_beneficiadas(
                    data_topo, data_conf, alimentadores, projeto_inv
                )
                chi_total, ci_total = self.calc_manager.calcular_chi_ci(data_conf, alimentadores)
                ganhos_antes_str = self.gerar_ganhos_totais(
                    alimentadores,
                    data_flow,
                    data_topo,
                    data_conf,
                    projeto_inv,
                    etapa="antes",
                )
                ganhos_depois_str = self.gerar_ganhos_totais(
                    alimentadores,
                    data_flow,
                    data_topo,
                    data_conf,
                    projeto_inv,
                    etapa="depois",
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Aviso", f"Erro ao calcular ganhos para a obra {cod}: {str(e)}")
                falhas_total += 1
                if len(falhas) < 5:
                    falhas.append(f"COD={cod or 'N/D'}: {e}")
                continue

            obra = list(self.db_manager.fetch_by_cod(cod) or [])
            if not obra:
                falhas_total += 1
                if len(falhas) < 5:
                    falhas.append(f"COD={cod or 'N/D'}: obra não encontrada")
                continue


            if calc_antes:
                obra[cols.index("contas_contratos_previos")] = str(contas_antes)
                obra[cols.index("contas_contratos_beneficiadas")] = str(total_benef)
                obra[cols.index("carregamento_inicial")] = str(round(carregamento or 0, 4))
                obra[cols.index("perdas_iniciais")] = str(round(maior_perda or 0, 4))
                obra[cols.index("tensao_media_inicial")] = str(round(tensao_media or 0, 4))
                obra[cols.index("tensao_min_inicial")] = str(round(tensao_min or 0, 4))
                obra[cols.index("tensao_min_linha_inicial")] = str(
                    round(tensao_min_linha or 0, 4)
                )
                obra[cols.index("chi_inicial")] = str(round(chi_total or 0, 4))
                obra[cols.index("ci_inicial")] = str(round(ci_total or 0, 4))
                obra[cols.index("tensao_max_inicial")] = str(round(tensao_max or 0, 4))
                obra[cols.index("ganhos_totais_antes")] = ganhos_antes_str

            if calc_depois:
                obra[cols.index("contas_contratos_posteriores")] = str(contas_depois)
                obra[cols.index("carregamento_final")] = str(round(carregamento or 0, 4))
                obra[cols.index("perdas_finais")] = str(round(maior_perda or 0, 4))
                obra[cols.index("tensao_media_final")] = str(round(tensao_media or 0, 4))
                obra[cols.index("tensao_min_final")] = str(round(tensao_min or 0, 4))
                obra[cols.index("tensao_min_linha_final")] = str(
                    round(tensao_min_linha or 0, 4)
                )
                obra[cols.index("tensao_max_final")] = str(round(tensao_max or 0, 4))
                obra[cols.index("chi_final")] = str(round(chi_total or 0, 4))
                obra[cols.index("ci_final")] = str(round(ci_total or 0, 4))
                obra[cols.index("ganhos_totais_depois")] = ganhos_depois_str

            if calc_atuais:
                obra[cols.index("tensao_min_registrada_atual")] = f"{round(tensao_min or 0, 4)}/{round(tensao_max or 0, 4)}"
                obra[cols.index("carregamento_max_registrado_atual")] = str(round(carregamento or 0, 4))
                ganhos_atual_str = self.gerar_ganhos_totais_atual(
                    alimentadores,
                    tensao_min,
                    tensao_min_linha,
                    tensao_max,
                    carregamento,
                )
                obra[cols.index("ganhos_totais_atual")] = ganhos_atual_str

            # Atualiza o registro no banco convertendo a lista modificada
            # em um dicionário alinhado às colunas, evitando deslocamentos
            dados_dict = {col: obra[i] for i, col in enumerate(cols)}
            try:
                self.db_manager.update_obra(dados_dict, cod, skip_blank=True)
            except PermissionError:
                falhas_total += 1
                if len(falhas) < 5:
                    falhas.append(f"COD={cod or 'N/D'}: permissão negada ao atualizar")
                continue
            processadas_ok += 1

        self.load_obras_into_table()
        resumo = _format_processing_summary(
            "Ganhos em massa",
            processadas_ok,
            ignoradas_aprovadas,
            ignoradas_integridade,
            falhas_total,
            falhas,
        )
        QtWidgets.QMessageBox.information(self, "Ganhos em massa", resumo)
        self.calc_manager.prompt_pi_base = previous_prompt

    def show_help_ganhos(self):
        QtWidgets.QMessageBox.information(
            self,
            "Ajuda - Ganhos",
            "- Informe os valores de antes e depois para calcular os ganhos.\n"
            "- Os botões permitem preencher automaticamente a partir dos arquivos.\n"
            "- A obra é 'suficiente' quando atende os critérios de planejamento no horizonte trienal.\n"
        )
