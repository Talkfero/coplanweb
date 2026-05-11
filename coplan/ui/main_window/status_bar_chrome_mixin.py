"""Mixin Status Bar / Chrome (toolbars + footer + status) -- 12 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 2).

Atributos esperados em ``self``:
- ``self.tabs``, ``self.tab_configuracoes``, ``self._config_tab_visibility_guard``
- ``self.act_*``, ``self.footer_*``, ``self.btn_*``, ``self.chk_incluir_aprovadas``
- ``self._statusbar_height_compact``, ``self._statusbar_height_expanded``
- ``self._loading_ui_state``, ``self.config``
- ``self.status_label``, ``self.table_obras``, ``self.db_manager``
- ``self.db_path_label``, ``self.support_path_label``, ``self._db_path_full_text``,
  ``self._support_path_full_text``, ``self.data_state``,
  ``self._footer_overflow_threshold``

Metodos esperados em ``self``:
- ``self.refresh_action_availability``, ``self._is_configuracoes_tab_visible``,
  ``self._hide_configuracoes_tab``, ``self.connect_database``, ``self.create_new_database``,
  ``self.save_data``, ``self.import_from_excel``, ``self.export_to_excel``,
  ``self.load_support_file``, ``self.open_configuracoes_tab``,
  ``self.on_gerar_cod_pep_clicked``, ``self.show_help_main``,
  ``self.atualizar_obras``, ``self.gerar_detalhamento``,
  ``self.exportar_relatorio_criterios_excel``, ``self.gerar_nota_colapso_excel``,
  ``self.abrir_dialogo_plano``, ``self.exportar_para_banco``, ``self.salvar_banco_dados``,
  ``self.marcar_obras_correcao``, ``self.delete_selected_obras``,
  ``self._warn_external_db_update``, ``self.update_reliability_labels``
"""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QSizePolicy, QStyle, QToolBar, QToolButton


class StatusBarChromeMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def _on_main_tab_changed(self, _index: int) -> None:
        self.refresh_action_availability()
        if self._config_tab_visibility_guard:
            return
        if self._is_configuracoes_tab_visible() and self.tabs.currentWidget() is not self.tab_configuracoes:
            self._config_tab_visibility_guard = True
            try:
                self._hide_configuracoes_tab()
            finally:
                self._config_tab_visibility_guard = False

    def _build_toolbar(self) -> None:
        # Faixa superior com identidade visual do aplicativo
        title_bar = QtWidgets.QWidget(self)
        title_bar.setObjectName("appTitleBar")
        title_bar.setFixedHeight(40)
        title_layout = QtWidgets.QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 16, 0)
        title_layout.setSpacing(12)

        title_label = QtWidgets.QLabel("COPLAN")
        title_label.setObjectName("appTitleLabel")
        subtitle_label = QtWidgets.QLabel("Cadastro e Visualização de Obras Elétricas")
        subtitle_label.setObjectName("appSubtitleLabel")

        title_layout.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)
        title_layout.addWidget(subtitle_label, 0, Qt.AlignmentFlag.AlignVCenter)
        title_layout.addStretch(1)

        title_toolbar = QToolBar("Identidade", self)
        title_toolbar.setMovable(False)
        title_toolbar.setFloatable(False)
        title_toolbar.addWidget(title_bar)
        title_toolbar.setObjectName("appTitleToolbar")
        title_toolbar.setContentsMargins(0, 0, 0, 0)
        title_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, title_toolbar)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

        toolbar = QToolBar("Menu Principal", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(22, 22))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        self.act_conectar = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton), "Conectar Banco", self)
        self.act_conectar.setToolTip("Conectar Banco")
        self.act_conectar.triggered.connect(self.connect_database)
        toolbar.addAction(self.act_conectar)

        self.act_novo = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder), "Criar Novo Banco", self)
        self.act_novo.setToolTip("Criar Novo Banco")
        self.act_novo.triggered.connect(self.create_new_database)
        toolbar.addAction(self.act_novo)

        toolbar.addSeparator()

        self.act_salvar = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Salvar Dados", self)
        self.act_salvar.setToolTip("Salvar Dados")
        self.act_salvar.triggered.connect(self.save_data)
        toolbar.addAction(self.act_salvar)

        self.act_importar = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown), "Importar Excel", self)
        self.act_importar.setToolTip("Importar Excel")
        self.act_importar.triggered.connect(self.import_from_excel)
        toolbar.addAction(self.act_importar)

        self.act_exportar = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp), "Exportar Excel", self)
        self.act_exportar.setToolTip("Exportar Excel")
        self.act_exportar.triggered.connect(self.export_to_excel)
        toolbar.addAction(self.act_exportar)

        toolbar.addSeparator()

        self.act_apoio = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon), "Carregar Apoio", self)
        self.act_apoio.setToolTip("Carregar Apoio")
        self.act_apoio.triggered.connect(self.load_support_file)
        toolbar.addAction(self.act_apoio)

        self.act_configuracoes = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView),
            "Configurações",
            self,
        )
        self.act_configuracoes.setToolTip("Abrir configurações gerais")
        self.act_configuracoes.triggered.connect(self.open_configuracoes_tab)
        toolbar.addAction(self.act_configuracoes)

        self.act_gerar_cod_pep = QAction(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton),
            "Gerar COD_PEP...",
            self,
        )
        self.act_gerar_cod_pep.setToolTip("Gerar COD_PEP...")
        self.act_gerar_cod_pep.triggered.connect(self.on_gerar_cod_pep_clicked)
        toolbar.addAction(self.act_gerar_cod_pep)

        toolbar.addSeparator()

        act_ajuda = QAction(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogHelpButton), "Ajuda", self)
        act_ajuda.setToolTip("Ajuda")
        act_ajuda.triggered.connect(self.show_help_main)
        toolbar.addAction(act_ajuda)

    def set_statusbar_height(self, compact: bool) -> None:
        h = (
            self._statusbar_height_compact
            if compact
            else self._statusbar_height_expanded
        )
        self.statusBar().setFixedHeight(h)

    def _persist_statusbar_compact(self, compact: bool) -> None:
        from ui.main_window import legacy_module
        ConfigManager = legacy_module().ConfigManager

        if not getattr(self, "_loading_ui_state", False):
            ui_state = self.config.setdefault("ui_state", {})
            ui_state["statusbar_compact"] = compact
            ConfigManager.save_config(self.config)

    def _setup_footer_icons(self):
        """Substitui os botões do rodapé por QToolButton, reordenando por fluxo de uso."""
        from ui.main_window import legacy_module
        legacy = legacy_module()
        _as_tool_button = legacy._as_tool_button
        iter_default_entries = legacy.iter_default_entries

        mapa = [
            ("btn_atualizar", "Atualizar", QStyle.StandardPixmap.SP_BrowserReload, self.atualizar_obras),
            ("btn_detalhamento", "Detalhamento", QStyle.StandardPixmap.SP_FileDialogDetailedView, self.gerar_detalhamento),
            (
                "btn_exportar_relatorio_criterios",
                "Relatório Critérios",
                QStyle.StandardPixmap.SP_FileDialogDetailedView,
                self.exportar_relatorio_criterios_excel,
            ),
            ("btn_gerar_nota", "Nota Colapso", QStyle.StandardPixmap.SP_FileIcon, self.gerar_nota_colapso_excel),
            ("btn_atualizar_plano", "Plano de Obras", QStyle.StandardPixmap.SP_DialogApplyButton, self.abrir_dialogo_plano),
            ("btn_exportar_banco", "Exportar Banco", QStyle.StandardPixmap.SP_DialogOpenButton, self.exportar_para_banco),
            ("btn_backup", "Backup Banco", QStyle.StandardPixmap.SP_DialogSaveButton, self.salvar_banco_dados),
            ("btn_marcar_correcao", "Marcar CORREÇÃO", QStyle.StandardPixmap.SP_DialogApplyButton, self.marcar_obras_correcao),
            ("btn_excluir", "Excluir", QStyle.StandardPixmap.SP_TrashIcon, self.delete_selected_obras),
        ]

        self.footer_actions_label = QtWidgets.QLabel("Ações rápidas:")
        self.footer_actions_label.setStyleSheet("font-weight: 700; color: #334155;")
        self.footer_layout.insertWidget(0, self.footer_actions_label)

        tool_buttons: list[QToolButton] = []
        for attr, texto, std_icon, slot in mapa:
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            tbtn = _as_tool_button(btn, self, texto, std_icon, slot, show_text=True)
            tbtn.setMinimumHeight(34)
            tbtn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            if attr == "btn_excluir":
                tbtn.setProperty("variant", "danger")
            elif attr in {"btn_backup", "btn_exportar_banco", "btn_exportar_relatorio_criterios"}:
                tbtn.setProperty("variant", "secondary")
            self.footer_layout.replaceWidget(btn, tbtn)
            btn.deleteLater()
            setattr(self, attr, tbtn)
            tool_buttons.append(tbtn)

        for button in tool_buttons:
            self.footer_layout.removeWidget(button)
        self.footer_layout.removeWidget(self.chk_incluir_aprovadas)

        self.footer_layout.addSpacing(6)
        for button in tool_buttons[:-2]:
            self.footer_layout.addWidget(button)
        self.footer_layout.addSpacing(14)
        self.footer_layout.addWidget(self.chk_incluir_aprovadas)
        self.footer_layout.addWidget(tool_buttons[-2])  # Marcar correção
        self.footer_layout.addWidget(tool_buttons[-1])  # Excluir
        self.btn_footer_more_actions = QtWidgets.QToolButton(self)
        self.btn_footer_more_actions.setText("Mais ações")
        self.btn_footer_more_actions.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.btn_footer_more_actions.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        )
        self.btn_footer_more_actions.setPopupMode(
            QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.footer_more_menu = QtWidgets.QMenu(self.btn_footer_more_actions)
        self.btn_footer_more_actions.setMenu(self.footer_more_menu)
        self.footer_layout.addWidget(self.btn_footer_more_actions)
        self.footer_layout.addStretch(1)

        self._footer_overflow_managed_buttons = [
            widget
            for entry in iter_default_entries()
            if isinstance(
                (widget := getattr(self, entry.attr_name, None)), QtWidgets.QWidget
            )
        ]
        self._footer_overflow_actions = [
            ("Relatório Critérios", self.exportar_relatorio_criterios_excel),
            ("Nota Colapso", self.gerar_nota_colapso_excel),
            ("Exportar Banco", self.exportar_para_banco),
            ("Backup Banco", self.salvar_banco_dados),
            ("Plano de Obras", self.abrir_dialogo_plano),
        ]
        self._refresh_footer_overflow_menu()
        self._refresh_footer_responsive_actions()

    def _refresh_footer_overflow_menu(self) -> None:
        menu = getattr(self, "footer_more_menu", None)
        if menu is None:
            return
        menu.clear()
        for label, slot in self._footer_overflow_actions:
            action = menu.addAction(label)
            action.triggered.connect(slot)

    def _refresh_footer_responsive_actions(self) -> None:
        from ui.main_window import legacy_module
        legacy = legacy_module()
        get_collapsed_action_keys = legacy.get_collapsed_action_keys
        iter_default_entries = legacy.iter_default_entries
        should_show_more_actions_button = legacy.should_show_more_actions_button

        collapsed_keys = get_collapsed_action_keys(
            self.width(), self._footer_overflow_threshold
        )
        for entry in iter_default_entries():
            button = getattr(self, entry.attr_name, None)
            if button is not None:
                button.setVisible(entry.attr_name not in collapsed_keys)
        if hasattr(self, "btn_footer_more_actions"):
            self.btn_footer_more_actions.setVisible(
                should_show_more_actions_button(
                    self.width(), self._footer_overflow_threshold
                )
            )

    def update_status_label(self):
        """Atualiza o rótulo de status com contagem e última modificação."""
        selected = len(self.table_obras.selectedVisibleRows())
        total = self.db_manager.count_obras()
        data, usuario = self.db_manager.get_last_modification_info()
        texto = f"{selected} de {total}"
        if data and usuario:
            texto += f" | Última modificação: {data} por {usuario}"
        self.status_label.setText(texto)
        self._warn_external_db_update(data)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._refresh_path_labels()
        self._refresh_footer_responsive_actions()

    def _apply_elided_status_text(self, label: QtWidgets.QLabel, text: str) -> None:
        """Aplica elide no meio e garante tooltip com o texto completo."""
        width = max(label.width(), label.minimumWidth())
        metrics = QtGui.QFontMetrics(label.font())
        label.setToolTip(text)
        label.setText(
            metrics.elidedText(
                text, QtCore.Qt.TextElideMode.ElideMiddle, width
            )
        )

    def _refresh_path_labels(self) -> None:
        """Reaplica o elide nos rótulos de caminho após resize."""
        db_text = getattr(self, "_db_path_full_text", "")
        apoio_text = getattr(self, "_support_path_full_text", "")
        if hasattr(self, "db_path_label"):
            self._apply_elided_status_text(self.db_path_label, db_text)
        if hasattr(self, "support_path_label"):
            self._apply_elided_status_text(self.support_path_label, apoio_text)

    def update_db_path_label(self):
        """Exibe os caminhos do banco de dados e da planilha de apoio."""
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        pac = self.db_manager.allowed_pacotes
        if pac:
            pac_str = ", ".join(pac)
        else:
            pac_str = "Todos"
        connected_path = self.db_manager.db_path or ""
        saved_db_path = self.data_state.get_state("db").path or ""
        if connected_path:
            path_text = f"Banco: {connected_path} [{pac_str}]"
        elif saved_db_path:
            path_text = f"Banco: {saved_db_path} [não conectado]"
        else:
            path_text = "Banco: não conectado"
        self._db_path_full_text = path_text

        apoio_state = self.data_state.get_state("apoio")
        if apoio_state.state == DataStateManager.CARREGADO_VALIDADO and apoio_state.path:
            display = f"Apoio: ✔ {apoio_state.path}"
        elif apoio_state.path:
            display = "Apoio: planilha configurada (não carregada)"
        else:
            display = "Apoio: planilha não carregada"

        self._support_path_full_text = display
        self._refresh_path_labels()
        self.update_reliability_labels()  # [RB-5]
