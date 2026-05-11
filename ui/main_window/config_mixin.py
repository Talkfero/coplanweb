"""Mixin Configuracoes -- 10 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 2).

Atributos esperados em ``self`` (vindos da MainWindow base):
- ``self.tab_configuracoes``, ``self.tabs``, ``self.cfg_*`` (combo/spin/field),
  ``self.config``, ``self.db_manager``, ``self.field_caminho_pasta``,
  ``self._config_tab_visibility_guard``

Metodos esperados em ``self``:
- ``self._setup_template_settings_tab``, ``self._save_criterios_config``,
  ``self._restore_criterios_config``, ``self._save_piora_config``,
  ``self._restore_piora_config``, ``self._set_data_state``,
  ``self.refresh_action_availability``, ``self.update_db_path_label``,
  ``self.load_obras_into_table``
"""
from __future__ import annotations

from contextlib import contextmanager

from PySide6 import QtCore, QtWidgets
from PySide6.QtGui import QAction


class ConfigMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def setup_tab_configuracoes(self) -> None:
        layout = QtWidgets.QVBoxLayout(self.tab_configuracoes)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        empresa_group = QtWidgets.QGroupBox("Configurações Gerais")
        empresa_form = QtWidgets.QFormLayout(empresa_group)
        empresa_row = QtWidgets.QHBoxLayout()
        self.cfg_combo_empresa = QtWidgets.QComboBox(empresa_group)
        self.cfg_combo_empresa.addItems(["MA", "PA", "PI", "AL", "RS", "AP", "GO"])
        self.cfg_btn_salvar_empresa = QtWidgets.QPushButton("Salvar Empresa")
        empresa_row.addWidget(self.cfg_combo_empresa)
        empresa_row.addWidget(self.cfg_btn_salvar_empresa)
        empresa_row.addStretch(1)
        empresa_form.addRow("Empresa (sigla)", empresa_row)
        layout.addWidget(empresa_group)

        self.cfg_tabs = QtWidgets.QTabWidget(self.tab_configuracoes)
        layout.addWidget(self.cfg_tabs, 1)

        tab_criterios = QtWidgets.QWidget()
        criterios_form = QtWidgets.QFormLayout(tab_criterios)
        self.cfg_spin_tmin = QtWidgets.QDoubleSpinBox(tab_criterios)
        self.cfg_spin_tmin.setRange(0, 2)
        self.cfg_spin_tmin.setDecimals(3)
        self.cfg_spin_tmax = QtWidgets.QDoubleSpinBox(tab_criterios)
        self.cfg_spin_tmax.setRange(0, 2)
        self.cfg_spin_tmax.setDecimals(3)
        self.cfg_spin_carreg_sim = QtWidgets.QDoubleSpinBox(tab_criterios)
        self.cfg_spin_carreg_sim.setRange(0, 1000)
        self.cfg_spin_carreg_nao = QtWidgets.QDoubleSpinBox(tab_criterios)
        self.cfg_spin_carreg_nao.setRange(0, 1000)
        self.cfg_spin_clientes = QtWidgets.QSpinBox(tab_criterios)
        self.cfg_spin_clientes.setRange(0, 1000000)
        criterios_form.addRow("Tensão mínima >", self.cfg_spin_tmin)
        criterios_form.addRow("Tensão máxima <", self.cfg_spin_tmax)
        criterios_form.addRow("Carregamento manobra SIM/vazio <", self.cfg_spin_carreg_sim)
        criterios_form.addRow("Carregamento manobra NÃO <", self.cfg_spin_carreg_nao)
        criterios_form.addRow("Contas Contratos posteriores <", self.cfg_spin_clientes)
        criterios_btns = QtWidgets.QHBoxLayout()
        criterios_btns.addStretch(1)
        self.cfg_btn_criterios_restaurar = QtWidgets.QPushButton("Restaurar Padrão")
        self.cfg_btn_criterios_salvar = QtWidgets.QPushButton("Salvar")
        criterios_btns.addWidget(self.cfg_btn_criterios_restaurar)
        criterios_btns.addWidget(self.cfg_btn_criterios_salvar)
        criterios_form.addRow(criterios_btns)
        self.cfg_tabs.addTab(tab_criterios, "Critérios de Planejamento")

        tab_piora = QtWidgets.QWidget()
        piora_form = QtWidgets.QFormLayout(tab_piora)
        self.cfg_field_piora_carreg = QtWidgets.QLineEdit(tab_piora)
        self.cfg_field_piora_tensao = QtWidgets.QLineEdit(tab_piora)
        self.cfg_field_piora_anos = QtWidgets.QLineEdit(tab_piora)
        piora_form.addRow("Aumento de Carregamento (%)", self.cfg_field_piora_carreg)
        piora_form.addRow("Redução de Tensão (pu)", self.cfg_field_piora_tensao)
        piora_form.addRow("Horizonte (anos)", self.cfg_field_piora_anos)
        piora_btns = QtWidgets.QHBoxLayout()
        piora_btns.addStretch(1)
        self.cfg_btn_piora_restaurar = QtWidgets.QPushButton("Restaurar Padrão")
        self.cfg_btn_piora_salvar = QtWidgets.QPushButton("Salvar")
        piora_btns.addWidget(self.cfg_btn_piora_restaurar)
        piora_btns.addWidget(self.cfg_btn_piora_salvar)
        piora_form.addRow(piora_btns)
        self.cfg_tabs.addTab(tab_piora, "Piora de Mercado")

        tab_template = QtWidgets.QWidget()
        self._setup_template_settings_tab(tab_template)
        self.cfg_tabs.addTab(tab_template, "Template de Descrição")

        self.cfg_btn_salvar_empresa.clicked.connect(self._save_empresa_config)
        self.cfg_btn_criterios_salvar.clicked.connect(self._save_criterios_config)
        self.cfg_btn_criterios_restaurar.clicked.connect(self._restore_criterios_config)
        self.cfg_btn_piora_salvar.clicked.connect(self._save_piora_config)
        self.cfg_btn_piora_restaurar.clicked.connect(self._restore_piora_config)

        self._refresh_configuracoes_ui()

    def _refresh_configuracoes_ui(self) -> None:
        from ui.main_window import legacy_module
        legacy = legacy_module()
        ConfigManager = legacy.ConfigManager
        get_empresa_sigla_from_config = legacy.get_empresa_sigla_from_config
        DEFAULT_CRITERIOS = legacy.DEFAULT_CRITERIOS
        DEFAULT_PIORA_MERCADO = legacy.DEFAULT_PIORA_MERCADO

        self.config = ConfigManager.load_config()

        try:
            empresa = get_empresa_sigla_from_config(self.config)
        except Exception:
            empresa = "MA"
        if hasattr(self, "cfg_combo_empresa"):
            self.cfg_combo_empresa.blockSignals(True)
            idx_empresa = self.cfg_combo_empresa.findText(empresa)
            if idx_empresa >= 0:
                self.cfg_combo_empresa.setCurrentIndex(idx_empresa)
            self.cfg_combo_empresa.blockSignals(False)

        crit = self.config.get("criterios_planejamento", DEFAULT_CRITERIOS)
        if hasattr(self, "cfg_spin_tmin"):
            self.cfg_spin_tmin.setValue(crit.get("tensao_min", DEFAULT_CRITERIOS["tensao_min"]))
            self.cfg_spin_tmax.setValue(crit.get("tensao_max", DEFAULT_CRITERIOS["tensao_max"]))
            self.cfg_spin_carreg_sim.setValue(
                crit.get(
                    "carregamento_limite_sim_ou_vazio",
                    DEFAULT_CRITERIOS["carregamento_limite_sim_ou_vazio"],
                )
            )
            self.cfg_spin_carreg_nao.setValue(
                crit.get("carregamento_limite_nao", DEFAULT_CRITERIOS["carregamento_limite_nao"])
            )
            self.cfg_spin_clientes.setValue(
                crit.get("clientes_maximo", DEFAULT_CRITERIOS["clientes_maximo"])
            )

        piora = self.config.get("piora_mercado", DEFAULT_PIORA_MERCADO)
        if hasattr(self, "cfg_field_piora_carreg"):
            self.cfg_field_piora_carreg.setText(str(piora.get("carregamento_percentual", "")))
            self.cfg_field_piora_tensao.setText(str(piora.get("tensao_delta", "")))
            self.cfg_field_piora_anos.setText(str(piora.get("anos_horizonte", "")))

        reload_bases = getattr(self, "_cfg_template_reload_pi_bases", None)
        if callable(reload_bases):
            reload_bases()
        load_template = getattr(self, "_cfg_template_load_template", None)
        combo_pi = getattr(self, "cfg_template_combo_pi", None)
        if callable(load_template) and combo_pi is not None:
            load_template(combo_pi.currentText())

    def _save_empresa_config(self) -> None:
        from ui.main_window import legacy_module
        legacy = legacy_module()
        normalize_text = legacy.normalize_text
        EMPRESA_SIGLAS_VALIDAS = legacy.EMPRESA_SIGLAS_VALIDAS
        ConfigManager = legacy.ConfigManager
        LOGGER = legacy.LOGGER

        empresa = normalize_text(self.cfg_combo_empresa.currentText())
        if empresa not in EMPRESA_SIGLAS_VALIDAS:
            QtWidgets.QMessageBox.warning(
                self,
                "Configurações",
                f"Empresa inválida. Use: {', '.join(sorted(EMPRESA_SIGLAS_VALIDAS))}.",
            )
            return
        ConfigManager.save_config({"empresa_sigla": empresa})
        self.config["empresa_sigla"] = empresa
        preenchidos = 0
        if getattr(self.db_manager, "conn", None):
            try:
                preenchidos = self.db_manager.preencher_cod_pep_pendentes()
                if preenchidos > 0:
                    self.load_obras_into_table()
            except Exception as exc:
                LOGGER.warning("Falha ao preencher COD_PEP após salvar empresa: %s", exc)
        msg = f"Empresa padrão salva: {empresa}."
        if preenchidos > 0:
            msg += f" COD_PEP preenchido em {preenchidos} obra(s) pendente(s)."
        QtWidgets.QMessageBox.information(self, "Configurações", msg)

    def open_configuracoes_tab(self, *_args) -> None:
        self._open_configuracoes_tab()

    def _is_configuracoes_tab_visible(self) -> bool:
        tabs = getattr(self, "tabs", None)
        tab_cfg = getattr(self, "tab_configuracoes", None)
        return bool(tabs is not None and tab_cfg is not None and tabs.indexOf(tab_cfg) >= 0)

    def _show_configuracoes_tab(self) -> None:
        if not self._is_configuracoes_tab_visible():
            self.tabs.insertTab(self.tabs.count(), self.tab_configuracoes, "Configurações")

    def _hide_configuracoes_tab(self) -> None:
        if self._is_configuracoes_tab_visible():
            idx = self.tabs.indexOf(self.tab_configuracoes)
            if idx >= 0:
                self.tabs.removeTab(idx)

    def _open_configuracoes_tab(self, initial_tab: str | None = None) -> None:
        if hasattr(self, "tabs") and hasattr(self, "tab_configuracoes"):
            self._config_tab_visibility_guard = True
            try:
                self._show_configuracoes_tab()
                self.tabs.setCurrentWidget(self.tab_configuracoes)
            finally:
                self._config_tab_visibility_guard = False
        tabs = getattr(self, "cfg_tabs", None)
        if tabs is not None:
            target = {"criterios": 0, "piora": 1, "template": 2}.get(
                str(initial_tab or "").strip().lower(),
                0,
            )
            tabs.setCurrentIndex(target)
        self._refresh_configuracoes_ui()

    def _initialize_saved_paths(self) -> None:
        """Inicializa caminhos salvos sem disparar cargas pesadas."""
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        db_path = self.config.get("obras", "")
        apoio_path = self.config.get("apoio", "")
        ganhos_path = self.config.get("caminho_pasta_ganhos", "")

        self._set_data_state("db", DataStateManager.NAO_CARREGADO, path=db_path)
        self._set_data_state("apoio", DataStateManager.NAO_CARREGADO, path=apoio_path)
        self._set_data_state("ganhos", DataStateManager.NAO_CARREGADO, path=ganhos_path)
        self._set_data_state("tecnico_txt", DataStateManager.NAO_CARREGADO, path="")

        if ganhos_path and hasattr(self, "field_caminho_pasta"):
            self.field_caminho_pasta.setText(ganhos_path)
            self.refresh_action_availability()  # [RB-RESTORE-OLD]
        self.update_db_path_label()

    @contextmanager
    def _with_loading_indicator(
        self,
        *,
        button: QtWidgets.QPushButton | None = None,
        action: QAction | None = None,
        loading_text: str = "Carregando...",
    ):
        button_text = button.text() if button is not None else ""
        button_enabled = button.isEnabled() if button is not None else False
        action_text = action.text() if action is not None else ""
        action_tooltip = action.toolTip() if action is not None else ""
        action_enabled = action.isEnabled() if action is not None else False

        if button is not None:
            button.setText(loading_text)
            button.setEnabled(False)
        if action is not None:
            action.setText(loading_text)
            action.setToolTip(loading_text)
            action.setEnabled(False)

        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
        )
        try:
            yield
        finally:
            if action is not None:
                action.setText(action_text)
                action.setToolTip(action_tooltip)
                action.setEnabled(action_enabled)
            if button is not None:
                button.setText(button_text)
                button.setEnabled(button_enabled)
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
            )
