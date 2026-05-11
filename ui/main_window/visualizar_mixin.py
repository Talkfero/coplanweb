"""Mixin Visualizar -- 16 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 4).
"""
from __future__ import annotations

import math
import os
from typing import Any, Callable, Sequence

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QSizePolicy


class VisualizarMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def col_index(self, name: str) -> int:
        """Retorna o índice da coluna com base no nome."""
        try:
            return self.db_manager.get_column_names().index(name)
        except ValueError:
            return -1

    def setup_tab_visualizar(self):
        from ui.main_window import legacy_module
        VisibleRowTableWidget = legacy_module().VisibleRowTableWidget

        layout = QtWidgets.QVBoxLayout(self.tab_visualizar)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        top_actions = QtWidgets.QHBoxLayout()
        top_actions.setContentsMargins(0, 0, 0, 0)
        top_actions.setSpacing(4)
        self.btn_load_db_apoio = QtWidgets.QPushButton("Carregar Banco e Apoio")
        self.btn_load_db_apoio.setFixedHeight(30)
        self.btn_load_db_apoio.clicked.connect(self._on_load_db_and_apoio_clicked)
        top_actions.addWidget(self.btn_load_db_apoio)

        top_actions.addStretch(1)
        self.btn_colunas_visualizar = QtWidgets.QPushButton("⚙ Colunas")
        self.btn_colunas_visualizar.setFixedHeight(30)
        self.btn_colunas_visualizar.setAutoDefault(False)
        self.btn_colunas_visualizar.clicked.connect(self.show_visualizar_columns_dialog)
        top_actions.addWidget(self.btn_colunas_visualizar)
        layout.addLayout(top_actions)

        filter_layout = QtWidgets.QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(4)

        self.filter_cod = QtWidgets.QLineEdit()
        self.filter_cod.setPlaceholderText("Filtrar COD (';' para múltiplos)")

        self.filter_ano = QtWidgets.QLineEdit()
        self.filter_ano.setPlaceholderText("Filtrar Ano (';' para múltiplos)")

        self.filter_pi = QtWidgets.QLineEdit()
        self.filter_pi.setPlaceholderText("Filtrar PI (';' para múltiplos)")

        self.filter_nome_projeto = QtWidgets.QLineEdit()
        self.filter_nome_projeto.setPlaceholderText("Filtrar Projeto (';' para múltiplos)")

        self.filter_alimentador = QtWidgets.QLineEdit()
        self.filter_alimentador.setPlaceholderText("Filtrar Alimentador Principal (';' para múltiplos)")

        self.filter_alimentadores_benef = QtWidgets.QLineEdit()
        self.filter_alimentadores_benef.setPlaceholderText("Filtrar Alimentadores Beneficiados (';' para múltiplos)")

        self.filter_regional = QtWidgets.QLineEdit()
        self.filter_regional.setPlaceholderText("Filtrar Regional (';' para múltiplos)")

        self.filter_superintendencia = QtWidgets.QLineEdit()
        self.filter_superintendencia.setPlaceholderText("Filtrar Superintendência (';' para múltiplos)")

        self.filter_subestacao = QtWidgets.QLineEdit()
        self.filter_subestacao.setPlaceholderText("Filtrar Subestação (';' para múltiplos)")

        self.filter_pacote = QtWidgets.QLineEdit()
        self.filter_pacote.setPlaceholderText("Filtrar Pacote (';' para múltiplos)")

        self.filter_tecnico_dirty = QtWidgets.QLineEdit()
        self.filter_tecnico_dirty.setPlaceholderText(
            "Filtrar Técnico Atualizado (SIM/NÃO)"
        )

        btn_filtros = QtWidgets.QPushButton("Filtros…")
        btn_filtros.setFixedHeight(30)
        btn_filtros.clicked.connect(self.show_filter_dialog)
        filter_layout.addWidget(btn_filtros)

        self.filter_global = QtWidgets.QLineEdit()
        self.filter_global.setFixedHeight(30)
        self.filter_global.setPlaceholderText("Busca inteligente em todos os campos (';' para múltiplos)")
        self.filter_global.setClearButtonEnabled(True)
        self.filter_global.setToolTip(
            "Atalhos: Ctrl+L/Ctrl+F para focar, Esc para limpar o campo."
        )
        filter_layout.addWidget(self.filter_global)

        self.btn_limpar_filtros = QtWidgets.QPushButton("Limpar filtros")
        self.btn_limpar_filtros.setFixedHeight(30)
        self.btn_limpar_filtros.setProperty("variant", "secondary")
        self.btn_limpar_filtros.setToolTip("Limpa todos os filtros e exibe novamente todas as obras.")
        self.btn_limpar_filtros.clicked.connect(self.clear_all_filters)
        filter_layout.addWidget(self.btn_limpar_filtros)

        self.filter_feedback = QtWidgets.QLabel("Sem filtros ativos")
        self.filter_feedback.setObjectName("filterFeedbackLabel")
        self.filter_feedback.setStyleSheet(
            "color:#475569; font-weight:600; padding:2px 6px; background:#eef2ff; border-radius:6px;"
        )
        filter_layout.addWidget(self.filter_feedback)

        self.filter_timer = QtCore.QTimer(self)
        self.filter_timer.setSingleShot(True)
        self.filter_timer.setInterval(180)
        self.filter_timer.timeout.connect(self.filter_table)
        self.shortcut_focus_filter_global = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+L"), self
        )
        self.shortcut_focus_filter_global.activated.connect(self.focus_global_filter)
        self.shortcut_find_filter_global = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+F"), self
        )
        self.shortcut_find_filter_global.activated.connect(self.focus_global_filter)

        self.shortcut_clear_filter_global = QtGui.QShortcut(
            QtGui.QKeySequence("Escape"), self.filter_global
        )
        self.shortcut_clear_filter_global.activated.connect(
            self.filter_global.clear
        )

        layout.addLayout(filter_layout)

        self.filter_cod.textChanged.connect(self.schedule_filter_table)
        self.filter_pi.textChanged.connect(self.schedule_filter_table)
        self.filter_nome_projeto.textChanged.connect(self.schedule_filter_table)
        self.filter_alimentador.textChanged.connect(self.schedule_filter_table)
        self.filter_alimentadores_benef.textChanged.connect(self.schedule_filter_table)
        self.filter_regional.textChanged.connect(self.schedule_filter_table)
        self.filter_superintendencia.textChanged.connect(self.schedule_filter_table)
        self.filter_tecnico_dirty.textChanged.connect(self.schedule_filter_table)
        self.filter_global.textChanged.connect(self.schedule_filter_table)
        self.filter_global.returnPressed.connect(self.filter_table)

        self.table_obras = VisibleRowTableWidget()
        self.table_obras.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.table_obras, 1)
        # === VISUALIZAR: READONLY + COPY BEGIN ===
        self._visualizar_readonly = True
        self.table_obras.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_obras.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems)
        self.table_obras.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_obras.setDragEnabled(False)
        self.table_obras.setAcceptDrops(False)
        self.table_obras.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.NoDragDrop)
        self.table_obras.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_obras.customContextMenuRequested.connect(self.mostrar_menu_linha)
        try:
            self.table_obras.doubleClicked.disconnect()
        except Exception:
            pass
        self.table_obras.doubleClicked.connect(self._on_visualizar_double_click)
        self._visualizar_copy_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Copy),
            self.table_obras,
        )
        self._visualizar_copy_shortcut.activated.connect(
            lambda: self._copy_visualizar_selection_to_clipboard(self.table_obras)
        )
        # === VISUALIZAR: READONLY + COPY END ===

        self.status_label = QtWidgets.QLabel()
        layout.addWidget(self.status_label)

        self.legend_label = QtWidgets.QLabel(
            "🔴 Texto vermelho: Não atendeu aos critérios de planejamento\n"
            "⚫ Texto preto: Atendeu aos critérios de planejamento"
        )
        layout.addWidget(self.legend_label)

        self.pagination_layout = QtWidgets.QHBoxLayout()
        self.btn_prev_page = QtWidgets.QToolButton()
        self.btn_prev_page.setText("◀ Anterior")
        self.btn_prev_page.clicked.connect(self._go_to_previous_page)
        self.pagination_layout.addWidget(self.btn_prev_page)

        self.pagination_label = QtWidgets.QLabel("Página 1/1")
        self.pagination_layout.addWidget(self.pagination_label)

        self.btn_next_page = QtWidgets.QToolButton()
        self.btn_next_page.setText("Próxima ▶")
        self.btn_next_page.clicked.connect(self._go_to_next_page)
        self.pagination_layout.addWidget(self.btn_next_page)

        self.pagination_layout.addSpacing(10)
        self.pagination_layout.addWidget(QtWidgets.QLabel("Itens por página:"))
        self.page_size_combo = QtWidgets.QComboBox()
        self.page_size_combo.addItems(["100", "300", "500", "1000"])
        self.page_size_combo.setCurrentText(str(self._visualizar_page_size))
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        self.pagination_layout.addWidget(self.page_size_combo)
        self.pagination_layout.addStretch(1)
        layout.addLayout(self.pagination_layout)

        if self.table_obras.selectionModel():
            self.table_obras.selectionModel().selectionChanged.connect(self.update_status_label)

        header = self.table_obras.horizontalHeader()
        header.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.mostrar_menu_cabecalho)
        # === VISUALIZAR: COLUMN WIDTH PERSIST BEGIN ===
        header.sectionResized.connect(self._on_visualizar_section_resized)
        # === VISUALIZAR: COLUMN WIDTH PERSIST END ===
        self.apply_visualizar_columns_config()

        self.filter_ano.textChanged.connect(self.schedule_filter_table)
        self.filter_subestacao.textChanged.connect(self.schedule_filter_table)
        self.filter_pacote.textChanged.connect(self.schedule_filter_table)
        self.filter_tecnico_dirty.textChanged.connect(self.schedule_filter_table)

        # Botões de ação (atualizar, excluir, etc.)
        self.footer_layout = QtWidgets.QHBoxLayout()
        self.btn_atualizar = QtWidgets.QPushButton("Atualizar Obras")
        self.btn_atualizar.clicked.connect(self.atualizar_obras)
        self.footer_layout.addWidget(self.btn_atualizar)

        self.btn_excluir = QtWidgets.QPushButton("Excluir Obras Selecionadas")
        self.btn_excluir.clicked.connect(self.delete_selected_obras)
        self.footer_layout.addWidget(self.btn_excluir)

        self.btn_detalhamento = QtWidgets.QPushButton("Detalhamento de obras")
        self.btn_detalhamento.clicked.connect(self.gerar_detalhamento)
        self.footer_layout.addWidget(self.btn_detalhamento)

        self.btn_marcar_correcao = QtWidgets.QPushButton("Marcar como CORREÇÃO")
        self.btn_marcar_correcao.clicked.connect(self.marcar_obras_correcao)
        self.footer_layout.addWidget(self.btn_marcar_correcao)

        self.btn_backup = QtWidgets.QPushButton("Salvar Banco de Dados")
        self.btn_backup.clicked.connect(self.salvar_banco_dados)
        self.footer_layout.addWidget(self.btn_backup)

        self.btn_exportar_banco = QtWidgets.QPushButton("Exportar para Banco")
        self.btn_exportar_banco.clicked.connect(self.exportar_para_banco)
        self.footer_layout.addWidget(self.btn_exportar_banco)

        self.btn_atualizar_plano = QtWidgets.QPushButton("Atualizar Plano de Obras")
        self.btn_atualizar_plano.clicked.connect(self.abrir_dialogo_plano)
        self.footer_layout.addWidget(self.btn_atualizar_plano)

        self.btn_gerar_nota = QtWidgets.QPushButton("Gerar nota de Colapso")
        self.btn_gerar_nota.clicked.connect(self.gerar_nota_colapso_excel)
        self.footer_layout.addWidget(self.btn_gerar_nota)

        self.btn_exportar_relatorio_criterios = QtWidgets.QPushButton(
            "Exportar Relatório de Critérios"
        )
        self.btn_exportar_relatorio_criterios.clicked.connect(
            self.exportar_relatorio_criterios_excel
        )
        self.footer_layout.addWidget(self.btn_exportar_relatorio_criterios)

        self.btn_cancelar_plano = QtWidgets.QPushButton("Cancelar Atualização do Plano de Obras")
        self.btn_cancelar_plano.clicked.connect(self.cancelar_atualizacao_plano_obras)
        self.btn_cancelar_plano.hide()
        self.footer_layout.addWidget(self.btn_cancelar_plano)

        self.chk_incluir_aprovadas = QtWidgets.QCheckBox("Incluir aprovadas")
        self.chk_incluir_aprovadas.setChecked(False)
        self.footer_layout.addWidget(self.chk_incluir_aprovadas)

        layout.addLayout(self.footer_layout)
        self._setup_footer_icons()

    def mostrar_menu_contexto_alimentadores(self, pos):
        """Exibe o menu de contexto para remover alimentadores beneficiados."""
        menu = QtWidgets.QMenu(self)
        copiar_acao = QtGui.QAction("Copiar", self)
        copiar_acao.triggered.connect(self.copiar_alimentadores_benef)
        menu.addAction(copiar_acao)
        remover_acao = QtGui.QAction("Remover", self)
        remover_acao.triggered.connect(self.remover_alimentador_beneficiado)
        menu.addAction(remover_acao)

        menu.exec(self.list_alimentadores_benef.viewport().mapToGlobal(pos))

    def copiar_textos_lista(self, lista):
        itens = lista.selectedItems()
        if not itens:
            return
        texto = "\n".join(i.text() for i in itens)
        QtWidgets.QApplication.clipboard().setText(texto)

    def mostrar_menu_contexto_subestacoes(self, pos):
        menu = QtWidgets.QMenu(self)
        copiar_acao = QtGui.QAction("Copiar", self)
        copiar_acao.triggered.connect(lambda: self.copiar_textos_lista(self.list_subestacoes))
        menu.addAction(copiar_acao)
        menu.exec(self.list_subestacoes.viewport().mapToGlobal(pos))

        self.update_subestacoes_list()

    def mostrar_menu_cabecalho(self, pos):
        """Exibe menu de contexto para recolher colunas da tabela."""
        header = self.table_obras.horizontalHeader()
        coluna = header.logicalIndexAt(pos)
        if coluna < 0:
            return

        menu = QtWidgets.QMenu(self)
        acao_recolher = QtGui.QAction("Recolher", self)
        acao_recolher.triggered.connect(lambda: self.recolher_coluna(coluna))
        menu.addAction(acao_recolher)

        menu.exec(header.mapToGlobal(pos))

    def mostrar_menu_linha(self, pos):
        row = self.table_obras.rowAt(pos.y())
        if row < 0:
            return
        menu = QtWidgets.QMenu(self)

        try:
            col_nome = self.db_manager.get_column_names().index("nome_projeto")
            item = self.table_obras.item(row, col_nome) if col_nome >= 0 else None
            nome_projeto = item.text().strip() if item else ""
        except Exception:
            nome_projeto = ""

        if nome_projeto:
            acao_atualizar = QtGui.QAction("Atualizar Projeto", self)
            acao_atualizar.triggered.connect(lambda: self.iniciar_atualizacao_projeto(row))
            if getattr(self, "plano_update_active", False) and row in getattr(self, "blocked_rows", set()):
                acao_atualizar.setEnabled(False)
            menu.addAction(acao_atualizar)
        else:
            acao_editar = QtGui.QAction("Editar Obra", self)
            col_cod = self.col_index("cod")
            acao_editar.triggered.connect(
                lambda: self.abrir_editar_obra(self.table_obras.model().index(row, col_cod))
            )
            menu.addAction(acao_editar)

        menu.exec(self.table_obras.viewport().mapToGlobal(pos))

    def recolher_coluna(self, coluna):
        """Ajusta a largura da coluna para cerca de 15 caracteres."""
        metrics = QtGui.QFontMetrics(self.table_obras.font())
        largura = metrics.horizontalAdvance("X" * 15)
        self.table_obras.setColumnWidth(coluna, largura)

    def load_last_obras(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        log_connect_debug = legacy.log_connect_debug
        DataStateManager = legacy.DataStateManager
        LOGGER = legacy.LOGGER
        show_user_error = legacy.show_user_error

        db_path = self.config.get("obras", "")
        log_connect_debug("ui.load_last_obras.start", db_path)
        if db_path and os.path.exists(db_path):
            try:
                if not self._validate_db_minimum(db_path):
                    log_connect_debug("ui.load_last_obras.validation_failed", db_path)
                    return
                log_connect_debug("ui.load_last_obras.connect_call", db_path)
                self.db_manager.connect(db_path)
                self.choose_packages()
                self._update_db_state(db_path)  # [RB-1.1]
                self.load_obras_into_table()
                self.update_db_path_label()
                log_connect_debug("ui.load_last_obras.success", db_path)
            except Exception as e:
                log_connect_debug("ui.load_last_obras.error", db_path, exc=e)
                LOGGER.exception("Falha ao conectar ao último banco.")
                self._update_db_state(db_path, error=str(e))  # [RB-1.1]
                show_user_error(
                    "Falha ao conectar ao banco",
                    f"Não foi possível conectar ao último banco: {str(e)}",
                    "Verifique o arquivo do banco e tente novamente.",
                    parent=self,
                )
        else:
            log_connect_debug("ui.load_last_obras.path_missing", db_path)
            self._set_data_state("db", DataStateManager.NAO_CARREGADO, path=db_path)  # [RB-1.1]

    def choose_packages(self):
        """Solicita ao usuário que selecione um ou mais pacotes para trabalhar."""
        from ui.main_window import legacy_module
        legacy = legacy_module()
        ts_now = legacy.ts_now
        ts_log = legacy.ts_log

        t_dist = ts_now()
        pacotes = self.db_manager.get_distinct_values("tipo_pacote")
        ts_log('get_distinct_values("tipo_pacote")', t_dist)
        if not pacotes:
            self.db_manager.set_allowed_pacotes(None)
            return

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Selecionar Pacotes")
        layout = QtWidgets.QVBoxLayout(dialog)

        check_all = QtWidgets.QCheckBox("Habilitar todos")
        layout.addWidget(check_all)

        list_widget = QtWidgets.QListWidget()
        list_widget.addItems(pacotes)
        list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
        layout.addWidget(list_widget)

        def toggle_list():
            list_widget.setEnabled(not check_all.isChecked())

        check_all.stateChanged.connect(toggle_list)
        toggle_list()

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(btns)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)

        t_dialog = ts_now()
        dialog_result = dialog.exec()
        ts_log("Abrir dialog Pacote", t_dialog)

        if dialog_result == QtWidgets.QDialog.DialogCode.Accepted:
            if check_all.isChecked():
                self.db_manager.set_allowed_pacotes(None)
            else:
                selecionados = [list_widget.item(i).text() for i in range(list_widget.count()) if list_widget.item(i).isSelected()]
                if selecionados:
                    self.db_manager.set_allowed_pacotes(selecionados)
                else:
                    self.db_manager.set_allowed_pacotes(None)
        else:
            self.db_manager.set_allowed_pacotes(None)

        if hasattr(self, "field_pacote"):
            self.field_pacote.clear()
            pac_sel = self.db_manager.allowed_pacotes
            if pac_sel:
                self.field_pacote.addItems(pac_sel)
            else:
                self.field_pacote.addItems(pacotes)

    def load_obras_into_table(self):
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        if not self.require_state(
            "Carregar obras", {"db": DataStateManager.CARREGADO_VALIDADO}
        ):  # [RB-1.1]
            return
        try:
            previous_widths: list[int] = []
            if self.table_obras.columnCount() > 0:
                previous_widths = [
                    self.table_obras.columnWidth(i)
                    for i in range(self.table_obras.columnCount())
                ]
            obras = self.db_manager.fetch_all(self.db_manager.allowed_pacotes)
            columns = self.db_manager.get_column_names()
            self.table_obras.setRowCount(0)
            self.table_obras.setColumnCount(len(columns))
            self.table_obras.setHorizontalHeaderLabels([col.replace("_", " ").title() for col in columns])

            avaliacoes = self.verificar_criterios_planejamento_v2(obras, columns)
            criterios_updates = self._build_criterios_persistencia_updates(obras, columns)
            if criterios_updates:
                self.db_manager.update_criterios_por_cod(criterios_updates)

            self._visualizar_source_rows = [
                (tuple(row_data), atende) for row_data, atende in zip(obras, avaliacoes)
            ]
            self._visualizar_filtered_rows = list(self._visualizar_source_rows)
            self._visualizar_current_page = 1
            self._visualizar_column_names = columns
            self.populate_combo_nome_projeto()
            self._render_visualizar_page()
            metrics = QtGui.QFontMetrics(self.table_obras.font())
            base_width = metrics.horizontalAdvance("X" * 10)

            idx_cod = self.col_index("cod")
            if idx_cod >= 0 and "cod" not in self._visualizar_col_widths:
                self.table_obras.setColumnWidth(idx_cod, base_width)
                self.table_obras.horizontalHeader().setSectionResizeMode(
                    idx_cod, QtWidgets.QHeaderView.ResizeMode.Interactive
                )

            idx_obs = self.col_index("observacoes_gerais")
            if idx_obs >= 0 and "observacoes_gerais" not in self._visualizar_col_widths:
                self.table_obras.setColumnWidth(idx_obs, base_width)
                self.table_obras.horizontalHeader().setSectionResizeMode(
                    idx_obs, QtWidgets.QHeaderView.ResizeMode.Interactive
                )
            self._mark_db_refresh_point()
            self.update_status_label()
            self.filter_table()
            self.update_tecnico_dirty_indicator()
            if getattr(self, "plano_update_active", False):
                params = getattr(self, "plano_update_params", None) or ()
                if len(params) == 3:
                    pacote, ini, fim = params
                    self.aplicar_atualizacao_plano(pacote, ini, fim)
            if previous_widths and not self._visualizar_col_widths:
                max_cols = min(len(previous_widths), self.table_obras.columnCount())
                for i in range(max_cols):
                    self.table_obras.setColumnWidth(i, previous_widths[i])
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao carregar obras: {str(e)}")

    @staticmethod
    def _is_missing_value(value: Any) -> bool:
        """Wrapper -- delega ao core/services/relatorio_criterios_service."""
        from core.services.relatorio_criterios_service import is_missing_value as _impl
        return _impl(value)

    def _fetch_obras_by_cods(self, cods: list[str]) -> list[list[Any]]:
        return self.db_manager.fetch_by_cods(cods)

    def _obra_atende(
        self,
        row: Sequence[Any],
        idx: dict[str, int],
        criterios: dict,
        conv_float: Callable[[Any], float],
        conv_int: Callable[[Any], int],
    ) -> tuple[bool | None, list[str]]:
        """Wrapper -- delega ao core/services/relatorio_criterios_service."""
        from core.services.relatorio_criterios_service import obra_atende as _impl
        return _impl(row, idx, criterios, conv_float, conv_int)

    def _obra_suficiente(self, row, idx, criterios, pioras, conv_float, conv_int, anos=None):
        """Avalia se a obra suporta a piora de mercado por ``anos``.
        Retorna (suficiente: bool, motivos: list[str]).
        """
        from ui.main_window import legacy_module
        DEFAULT_PIORA_MERCADO = legacy_module().DEFAULT_PIORA_MERCADO

        raw_tmin = row[idx["tmin"]]
        raw_tmax = row[idx["tmax"]]
        raw_carreg = row[idx["carreg"]]
        raw_clientes = row[idx["clientes"]]
        if any(
            self._is_missing_value(valor)
            for valor in (raw_tmin, raw_tmax, raw_carreg, raw_clientes)
        ):
            return None, ["dados_insuficientes"]

        def conv_float_opt(valor: Any) -> float | None:
            if self._is_missing_value(valor):
                return None
            texto = str(valor).strip()
            try:
                retorno = float(texto.replace(",", "."))
            except Exception:
                return None
            if isinstance(retorno, float) and math.isnan(retorno):
                return None
            return retorno

        def conv_int_opt(valor: Any) -> int | None:
            if self._is_missing_value(valor):
                return None
            texto = str(valor).strip()
            try:
                return int(float(texto.replace(",", ".")))
            except Exception:
                return None

        tmin = conv_float_opt(raw_tmin)
        tmax = conv_float_opt(raw_tmax)
        carreg = conv_float_opt(raw_carreg)
        manobra = str(row[idx["manobra"]]).strip().upper()
        clientes = conv_int_opt(raw_clientes)
        if any(valor is None for valor in (tmin, tmax, carreg, clientes)):
            return None, ["dados_insuficientes"]

        if anos is None:
            anos = int(pioras.get("anos_horizonte", DEFAULT_PIORA_MERCADO["anos_horizonte"]))

        delta_tensao = pioras.get("tensao_delta", DEFAULT_PIORA_MERCADO["tensao_delta"])
        perc_carreg = pioras.get("carregamento_percentual", DEFAULT_PIORA_MERCADO["carregamento_percentual"])

        for _ in range(anos):
            if any(valor is None for valor in (tmin, tmax, carreg, clientes)):
                return None, ["dados_insuficientes"]
            carreg *= 1 + (perc_carreg / 100.0)
            tmin -= delta_tensao
            tmax -= delta_tensao

            atende, motivos = self._obra_atende(
                (
                    tmin,
                    tmax,
                    carreg,
                    manobra,
                    clientes,
                ),
                {"tmin": 0, "tmax": 1, "carreg": 2, "manobra": 3, "clientes": 4},
                criterios,
                float,
                int,
            )
            if atende is None:
                return None, ["dados_insuficientes"]
            if not atende:
                return False, motivos

        return True, []

    def _on_visualizar_double_click(self, index):
        if index is None or not index.isValid():
            return

        # Mapeia para source row ANTES de qualquer logica -- importante
        # porque blocked_rows e self.table_obras.item(row, col) usam o row
        # do source model (nao do proxy).
        model = self.table_obras.model()
        src_index = index
        try:
            if isinstance(model, QtCore.QSortFilterProxyModel):
                src_index = model.mapToSource(index)
                src_model = model.sourceModel()
            else:
                src_model = model
        except Exception:
            src_model = model
            src_index = index

        row = src_index.row()
        if row < 0:
            return

        # Modo "Atualizar Plano de Obras" ativo: replica logica de
        # abrir_editar_obra (que tem o desvio para iniciar_atualizacao_projeto).
        # Inline aqui em vez de delegar -- evita problemas de proxy row.
        if getattr(self, "plano_update_active", False):
            if row in getattr(self, "blocked_rows", set()):
                return
            try:
                cols_db = self.db_manager.get_column_names()
                col_nome = cols_db.index("nome_projeto") if "nome_projeto" in cols_db else -1
                item_nome = self.table_obras.item(row, col_nome) if col_nome >= 0 else None
                nome_projeto = item_nome.text().strip() if item_nome else ""
            except Exception:
                nome_projeto = ""
            if nome_projeto:
                self.iniciar_atualizacao_projeto(row)
                return

        cod = None
        try:
            cols = src_model.columnCount()
            cod_col = None
            for c in range(cols):
                h = src_model.headerData(c, QtCore.Qt.Orientation.Horizontal)
                if isinstance(h, str) and h.strip().lower() == "cod":
                    cod_col = c
                    break
            if cod_col is None:
                cod_col = 0

            cod_idx = src_model.index(row, cod_col)
            cod = cod_idx.data()
        except Exception:
            cod = None

        if not cod:
            QtWidgets.QMessageBox.warning(
                self,
                "Aviso",
                "Não foi possível identificar o COD da obra para edição.",
            )
            return

        self._open_editar_obra_by_cod(str(cod))
