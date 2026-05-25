"""Mixin Cadastro -- 16 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 4).
"""
from __future__ import annotations

from typing import Any

import datetime

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QStyle


class CadastroMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def open_manage_pi_base_dialog(self, parent: QtWidgets.QWidget | None = None) -> None:
        from ui.main_window import legacy_module
        _l = legacy_module()
        ConfigManager = _l.ConfigManager
        PI_BASE_CUSTOM = _l.PI_BASE_CUSTOM
        PI_BASE_MAP = _l.PI_BASE_MAP
        _normalize_pi_base_name = _l._normalize_pi_base_name
        get_all_pi_bases = _l.get_all_pi_bases
        get_pi_metadata = _l.get_pi_metadata
        dialog = QtWidgets.QDialog(parent or self)
        dialog.setWindowTitle("Gerenciar PI_BASE")
        dialog.setMinimumWidth(420)
        layout = QtWidgets.QVBoxLayout(dialog)

        list_widget = QtWidgets.QListWidget(dialog)
        layout.addWidget(list_widget)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("Adicionar")
        btn_rename = QtWidgets.QPushButton("Renomear")
        btn_remove = QtWidgets.QPushButton("Remover")
        btn_restore = QtWidgets.QPushButton("Restaurar padrões")
        btn_close = QtWidgets.QPushButton("Fechar")
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_rename)
        btn_layout.addWidget(btn_remove)
        btn_layout.addWidget(btn_restore)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

        def _refresh_list(select_value: str | None = None) -> None:
            list_widget.clear()
            list_widget.addItems(self.pi_base_custom)
            if select_value:
                matches = list_widget.findItems(
                    select_value, QtCore.Qt.MatchFlag.MatchExactly
                )
                if matches:
                    list_widget.setCurrentItem(matches[0])

        def _save_custom_list(extra_updates: dict | None = None) -> None:
            PI_BASE_CUSTOM[:] = list(self.pi_base_custom)
            payload = {"pi_base_custom": list(self.pi_base_custom)}
            if extra_updates:
                payload.update(extra_updates)
            ConfigManager.save_config(payload)

        def _validate_new_name(name: str, ignore_value: str | None = None) -> str | None:
            normalized = _normalize_pi_base_name(name)
            if not normalized:
                QtWidgets.QMessageBox.warning(
                    dialog, "Entrada inválida", "O nome do PI_BASE não pode ficar vazio."
                )
                return None
            if get_pi_metadata(normalized) is not None:
                QtWidgets.QMessageBox.warning(
                    dialog,
                    "PI_BASE duplicado",
                    "Esse PI_BASE já existe na lista padrão.",
                )
                return None
            for custom in self.pi_base_custom:
                if ignore_value and _normalize_pi_base_name(ignore_value) == _normalize_pi_base_name(custom):
                    continue
                if _normalize_pi_base_name(custom) == normalized:
                    QtWidgets.QMessageBox.warning(
                        dialog,
                        "PI_BASE duplicado",
                        "Esse PI_BASE já existe na lista customizada.",
                    )
                    return None
            return normalized

        def _add_pi_base() -> None:
            nome, ok = QtWidgets.QInputDialog.getText(
                dialog, "Adicionar PI_BASE", "Digite o nome do novo PI_BASE:"
            )
            if not ok:
                return
            novo = _validate_new_name(nome)
            if not novo:
                return
            self.pi_base_custom.append(novo)
            _save_custom_list()
            _refresh_list(novo)

        def _rename_pi_base() -> None:
            item = list_widget.currentItem()
            if not item:
                QtWidgets.QMessageBox.information(
                    dialog, "Seleção necessária", "Selecione um PI_BASE para renomear."
                )
                return
            atual = item.text()
            novo_nome, ok = QtWidgets.QInputDialog.getText(
                dialog,
                "Renomear PI_BASE",
                "Digite o novo nome do PI_BASE:",
                text=atual,
            )
            if not ok:
                return
            novo = _validate_new_name(novo_nome, ignore_value=atual)
            if not novo or novo == atual:
                return

            templates = dict(ConfigManager.load_config().get("descricao_obra_templates", {}))
            updates: dict[str, Any] = {}

            if atual in templates:
                templates[novo] = templates.pop(atual)
                updates["descricao_obra_templates"] = templates

            remapped = False
            for pi_key, base in list(PI_BASE_MAP.items()):
                if _normalize_pi_base_name(base) == _normalize_pi_base_name(atual):
                    PI_BASE_MAP[pi_key] = novo
                    remapped = True
            if remapped:
                updates["pi_base_map"] = dict(PI_BASE_MAP)

            self.pi_base_custom = [novo if b == atual else b for b in self.pi_base_custom]
            _save_custom_list(updates)
            _refresh_list(novo)

        def _remove_pi_base() -> None:
            item = list_widget.currentItem()
            if not item:
                QtWidgets.QMessageBox.information(
                    dialog, "Seleção necessária", "Selecione um PI_BASE para remover."
                )
                return
            alvo = item.text()
            alvo_key = _normalize_pi_base_name(alvo)

            config = ConfigManager.load_config()
            templates = dict(config.get("descricao_obra_templates", {}))
            used_in_templates = alvo in templates
            used_in_map = any(
                _normalize_pi_base_name(v) == alvo_key for v in PI_BASE_MAP.values()
            )

            replacement = None
            if used_in_templates or used_in_map:
                choices = [
                    base
                    for base in get_all_pi_bases()
                    if _normalize_pi_base_name(base) != alvo_key
                ]
                replacement, ok = QtWidgets.QInputDialog.getItem(
                    dialog,
                    "Substituir PI_BASE",
                    "Escolha o PI_BASE substituto para os registros existentes:",
                    choices,
                    0,
                    False,
                )
                if not ok:
                    return

            if used_in_templates:
                templates.pop(alvo, None)

            if used_in_map and replacement:
                for pi_key, base in list(PI_BASE_MAP.items()):
                    if _normalize_pi_base_name(base) == alvo_key:
                        PI_BASE_MAP[pi_key] = replacement

            self.pi_base_custom = [b for b in self.pi_base_custom if b != alvo]
            updates = {"descricao_obra_templates": templates}
            if used_in_map and replacement:
                updates["pi_base_map"] = dict(PI_BASE_MAP)
            _save_custom_list(updates)
            _refresh_list()

        def _restore_defaults() -> None:
            reply = QtWidgets.QMessageBox.question(
                dialog,
                "Restaurar padrões",
                "Deseja restaurar os PI_BASE padrão? Isso removerá os PI_BASE customizados e o mapeamento atual.",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            self.pi_base_custom = []
            PI_BASE_CUSTOM.clear()
            PI_BASE_MAP.clear()
            ConfigManager.save_config({"pi_base_custom": [], "pi_base_map": {}})
            _refresh_list()

        btn_add.clicked.connect(_add_pi_base)
        btn_rename.clicked.connect(_rename_pi_base)
        btn_remove.clicked.connect(_remove_pi_base)
        btn_restore.clicked.connect(_restore_defaults)
        btn_close.clicked.connect(dialog.accept)

        _refresh_list()
        dialog.exec()

    def setup_tab_cadastro(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        CopyListWidget = _l.CopyListWidget
        _as_tool_button = _l._as_tool_button
        scroll = QtWidgets.QScrollArea(self.tab_cadastro)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        container = QtWidgets.QWidget()
        self.cadastro_layout = QtWidgets.QVBoxLayout(container)
        scroll.setWidget(container)
        outer_layout = QtWidgets.QVBoxLayout(self.tab_cadastro)
        outer_layout.addWidget(scroll)

        # Container para habilitar/desabilitar todos os widgets da aba
        self.group_dados = QtWidgets.QGroupBox()
        dados_layout = QtWidgets.QVBoxLayout(self.group_dados)
        dados_layout.setContentsMargins(10, 10, 10, 10)

        # ------------------------------------------------------------------
        # Dados Básicos da Obra
        group_basicos = QtWidgets.QGroupBox("Dados Básicos da Obra")
        form_basicos = QtWidgets.QFormLayout(group_basicos)

        self.field_ano = QtWidgets.QComboBox()
        current_year = datetime.datetime.now().year
        self.field_ano.addItems([str(year) for year in range(current_year, current_year + 11)])
        ano_width = self.field_ano.fontMetrics().averageCharWidth() * 18
        self.field_ano.setFixedWidth(ano_width)
        form_basicos.addRow("Ano", self.field_ano)

        self.field_projeto_investimento = QtWidgets.QComboBox()
        self.field_projeto_investimento.addItems([
            "DISTRIBUIÇÃO",
            "MELHORAMENTOS",
            "TRIFASEAMENTO",
            "INSTALAÇÃO DE BANCOS DE REGULADORES DE TENSÃO EM RD",
            "INSTALAÇÃO DE BANCOS DE CAPACITORES EM RD",
            "INSTALAÇÃO DE BANCOS DE REATORES EM RD",
            "DISTRIBUIÇÃO LD 34,5 KV",
        ])
        pi_layout = QtWidgets.QHBoxLayout()
        pi_layout.addWidget(self.field_projeto_investimento)
        self.field_item = QtWidgets.QLineEdit()
        self.field_item.setFixedWidth(self.field_item.sizeHint().width() // 2)
        pi_layout.addWidget(QtWidgets.QLabel("Item"))
        pi_layout.addWidget(self.field_item)
        pi_layout.addStretch(1)
        form_basicos.addRow("Projeto de Investimento", pi_layout)
        self.field_projeto_investimento.currentTextChanged.connect(self.verificar_pi_padrao)

        h_layout_projeto = QtWidgets.QHBoxLayout()
        self.combo_nome_projeto = QtWidgets.QComboBox()
        self.combo_nome_projeto.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.combo_nome_projeto.setFixedWidth(200)
        self.combo_nome_projeto.currentTextChanged.connect(self._preencher_nome_projeto_auto)
        h_layout_projeto.addWidget(self.combo_nome_projeto)

        self.field_projeto = QtWidgets.QLineEdit()
        self.field_projeto.setFixedWidth(200)
        instruction_label = QtWidgets.QLabel('Não pode iniciar com "Obra"')
        btn_nome_projetos = QtWidgets.QPushButton("Nome de projetos")
        menu_nome_projetos = QtWidgets.QMenu(btn_nome_projetos)
        menu_nome_projetos.addAction("Nova SE", self.nova_se)
        menu_nome_projetos.addAction("Novo AL", self.novo_al)
        menu_nome_projetos.addAction("Reconfiguração", self.reconfiguracao)
        menu_nome_projetos.addAction("Alívio SE", self.alivio_se)
        menu_nome_projetos.addAction("Flexibilização", self.flexibilizacao)
        btn_nome_projetos.setMenu(menu_nome_projetos)

        h_layout_projeto.addWidget(self.field_projeto)
        h_layout_projeto.addWidget(instruction_label)
        h_layout_projeto.addWidget(btn_nome_projetos)

        btn_buscar_projeto = QtWidgets.QPushButton("Escolher Projeto")
        btn_buscar_projeto.clicked.connect(self.buscar_projetos)
        h_layout_projeto.addWidget(btn_buscar_projeto)
        form_basicos.addRow("Projeto", h_layout_projeto)

        self.field_observacoes = QtWidgets.QPlainTextEdit()
        self.field_observacoes.setFixedHeight(60)
        form_basicos.addRow("Observações", self.field_observacoes)

        dados_layout.addWidget(group_basicos)
        dados_layout.addSpacing(10)

        # ------------------------------------------------------------------
        # Informações Técnicas
        group_tecnicas = QtWidgets.QGroupBox("Informações Técnicas")
        form_tecnicas = QtWidgets.QFormLayout(group_tecnicas)

        self.field_alimentador = QtWidgets.QComboBox()
        self.field_alimentador.setEditable(True)
        self.field_alimentador.currentIndexChanged.connect(self.alimentador_selecionado)
        self.field_alimentador.setFixedWidth(self.field_alimentador.sizeHint().width() * 2)
        _val_alim = QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(r'^[^_]+$'), self)
        _line_edit_alim = self.field_alimentador.lineEdit()
        if _line_edit_alim is not None:
            _line_edit_alim.setValidator(_val_alim)
        self.field_alimentador.setToolTip("Não use sublinhado (_) neste campo")
        self.field_tensao = QtWidgets.QLineEdit()
        self.field_tensao.setMaxLength(5)
        self.field_tensao_operacao = QtWidgets.QLineEdit()
        self.field_tensao_operacao.setMaxLength(5)
        self.field_regional = QtWidgets.QLineEdit()
        self.field_regional.setMaxLength(15)
        self.field_superintendencia = QtWidgets.QLineEdit()
        self.field_superintendencia.setMaxLength(12)
        self.field_se = QtWidgets.QLineEdit()

        alimentador_layout = QtWidgets.QHBoxLayout()
        alimentador_layout.addWidget(self.field_alimentador)
        alimentador_layout.addWidget(QtWidgets.QLabel("Tensão Obra"))
        alimentador_layout.addWidget(self.field_tensao)
        alimentador_layout.addWidget(QtWidgets.QLabel("Tensão Oper."))
        alimentador_layout.addWidget(self.field_tensao_operacao)
        alimentador_layout.addWidget(QtWidgets.QLabel("Regional"))
        alimentador_layout.addWidget(self.field_regional)
        alimentador_layout.addWidget(QtWidgets.QLabel("Superintendência"))
        alimentador_layout.addWidget(self.field_superintendencia)
        alimentador_layout.addWidget(QtWidgets.QLabel("SE"))
        alimentador_layout.addWidget(self.field_se)
        alimentador_layout.addStretch(1)
        form_tecnicas.addRow("Alimentador Obra", alimentador_layout)

        self.field_coord_inicio = QtWidgets.QLineEdit()
        self.field_coord_fim = QtWidgets.QLineEdit()
        self.field_quantidade = QtWidgets.QLineEdit()
        self.field_quantidade.setFixedWidth(self.field_quantidade.sizeHint().width() // 2)
        self.field_caracteristicas = QtWidgets.QComboBox()
        self.field_caracteristicas.setEditable(True)
        self.field_caracteristicas.setFixedWidth(self.field_caracteristicas.sizeHint().width() * 3)
        self.field_manobra = QtWidgets.QComboBox()
        self.field_manobra.setEditable(False)
        self.field_manobra.addItems(["SIM", "NÃO"])

        coord_layout = QtWidgets.QHBoxLayout()
        coord_layout.addWidget(self.field_coord_inicio)
        coord_layout.addWidget(QtWidgets.QLabel("Coordenadas Para"))
        coord_layout.addWidget(self.field_coord_fim)
        coord_layout.addWidget(QtWidgets.QLabel("Quantidade"))
        coord_layout.addWidget(self.field_quantidade)
        coord_layout.addWidget(QtWidgets.QLabel("Características"))
        coord_layout.addWidget(self.field_caracteristicas)
        coord_layout.addWidget(QtWidgets.QLabel("Manobra"))
        coord_layout.addWidget(self.field_manobra)
        coord_layout.addStretch(1)
        form_tecnicas.addRow("Coordenadas De", coord_layout)

        self.field_novo_bay = QtWidgets.QComboBox()
        self.field_novo_bay.addItems(["NÃO", "SIM"])
        self.field_manobra.setFixedWidth(self.field_novo_bay.sizeHint().width())
        self.field_criticidade = QtWidgets.QComboBox()
        self.field_criticidade.addItems(["Baixa", "Média", "Alta"])

        bay_crit_layout = QtWidgets.QHBoxLayout()
        bay_crit_layout.addWidget(QtWidgets.QLabel("Novo Bay?"))
        bay_crit_layout.addWidget(self.field_novo_bay)
        bay_crit_layout.addWidget(QtWidgets.QLabel("Criticidade"))
        bay_crit_layout.addWidget(self.field_criticidade)
        bay_crit_layout.addStretch(1)
        form_tecnicas.addRow("", bay_crit_layout)

        dados_layout.addWidget(group_tecnicas)
        dados_layout.addSpacing(10)

        # ------------------------------------------------------------------
        # Dados Financeiros
        group_fin = QtWidgets.QGroupBox("Dados Financeiros")
        form_fin = QtWidgets.QFormLayout(group_fin)

        self.field_pacote = QtWidgets.QComboBox()
        self.field_pacote.addItems([
            "Mercado",
            "Confiabilidade",
            "Interligação de UDE",
            "Solicitação Regional",
            "Orçamento de Conexao",
            "PLPT",
        ])
        form_fin.addRow("Pacote", self.field_pacote)

        self.field_obra_aprovada = QtWidgets.QComboBox()
        self.field_obra_aprovada.addItems(["NÃO", "SIM"])
        form_fin.addRow("Obra Aprovada", self.field_obra_aprovada)

        self.field_valor_obra = QtWidgets.QLineEdit()
        btn_calcular_valor = QtWidgets.QPushButton("Calcular Valor da Obra")
        btn_calcular_valor.clicked.connect(self.calcular_valor_obra_handler)

        valor_obra_layout = QtWidgets.QHBoxLayout()
        valor_obra_layout.addWidget(self.field_valor_obra)
        valor_obra_layout.addWidget(btn_calcular_valor)
        valor_obra_layout.addStretch(1)
        form_fin.addRow("Valor da Obra", valor_obra_layout)

        dados_layout.addWidget(group_fin)
        dados_layout.addSpacing(10)

        # ------------------------------------------------------------------
        # Ações
        group_acoes = QtWidgets.QGroupBox("Ações")
        acoes_layout = QtWidgets.QHBoxLayout(group_acoes)
        btn_salvar_obra = _as_tool_button(
            None,
            self,
            "Salvar Obra",
            QStyle.StandardPixmap.SP_DialogSaveButton,
            self.save_data,
        )
        btn_salvar_obra.setShortcut(QtGui.QKeySequence("Ctrl+B"))
        btn_limpar_campos = _as_tool_button(
            None,
            self,
            "Limpar Campos",
            QStyle.StandardPixmap.SP_DialogResetButton,
            self.limpar_campos_cadastro,
        )
        broom_icon = QtGui.QIcon.fromTheme("edit-clear")
        if not broom_icon.isNull():
            btn_limpar_campos.setIcon(broom_icon)
        btn_template_descricao = QtWidgets.QPushButton("⚙ Configurações")
        btn_template_descricao.setAutoDefault(False)
        btn_template_descricao.clicked.connect(self.open_descricao_template_dialog)
        acoes_layout.addWidget(btn_salvar_obra)
        acoes_layout.addWidget(btn_limpar_campos)
        acoes_layout.addWidget(btn_template_descricao)
        acoes_layout.addStretch(1)

        dados_layout.addWidget(group_acoes)
        dados_layout.addSpacing(10)

        # ------------------------------------------------------------------
        # Alimentadores e Subestações
        group_aliment = QtWidgets.QGroupBox("Alimentadores e Subestações")
        aliment_layout = QtWidgets.QVBoxLayout(group_aliment)
        self.field_alimentador_benef = QtWidgets.QComboBox()
        self.field_alimentador_benef.setEditable(True)
        _val_benef = QtGui.QRegularExpressionValidator(QtCore.QRegularExpression(r'^[^_]+$'), self)
        _line_edit_benef = self.field_alimentador_benef.lineEdit()
        if _line_edit_benef is not None:
            _line_edit_benef.setValidator(_val_benef)
        self.field_alimentador_benef.setToolTip("Não use sublinhado (_) neste campo")
        btn_add_benef = _as_tool_button(
            None,
            self,
            "Adicionar à Lista",
            QStyle.StandardPixmap.SP_ArrowDown,
            self.adicionar_alimentador_benef,
        )
        top_benef_layout = QtWidgets.QHBoxLayout()
        top_benef_layout.addWidget(self.field_alimentador_benef)
        top_benef_layout.addWidget(btn_add_benef)
        top_benef_layout.addStretch(1)
        aliment_layout.addLayout(top_benef_layout)
        self.list_alimentadores_benef = CopyListWidget()
        self.list_alimentadores_benef.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_alimentadores_benef.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        # Mostrar alimentadores em colunas de quatro itens para reduzir a altura
        self.list_alimentadores_benef.setWrapping(True)
        self.list_alimentadores_benef.setFlow(QtWidgets.QListView.Flow.TopToBottom)
        self.list_alimentadores_benef.setFixedHeight(120)
        self.list_subestacoes = CopyListWidget()
        self.list_subestacoes.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_subestacoes.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.list_subestacoes.setFixedHeight(100)
        lists_layout = QtWidgets.QHBoxLayout()
        lists_layout.addWidget(self.list_alimentadores_benef)
        sub_layout = QtWidgets.QVBoxLayout()
        sub_layout.addWidget(QtWidgets.QLabel("Subestações Consideradas"))
        sub_layout.addWidget(self.list_subestacoes)
        lists_layout.addLayout(sub_layout)
        aliment_layout.addLayout(lists_layout)

        dados_layout.addWidget(group_aliment)
        dados_layout.addStretch(1)

        self.cadastro_layout.addWidget(self.group_dados)

        self.list_alimentadores_benef.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_alimentadores_benef.customContextMenuRequested.connect(self.mostrar_menu_contexto_alimentadores)
        self.list_subestacoes.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_subestacoes.customContextMenuRequested.connect(self.mostrar_menu_contexto_subestacoes)

        self.update_subestacoes_list()

        self.populate_combo_nome_projeto()

        # Todos os combo boxes (exceto ano) devem iniciar sem seleção
        for cb in [
            self.field_projeto_investimento,
            self.field_alimentador,
            self.field_caracteristicas,
            self.field_manobra,
            self.field_novo_bay,
            self.field_criticidade,
            self.field_pacote,
            self.field_alimentador_benef,
            self.combo_nome_projeto,
        ]:
            cb.setCurrentIndex(-1)

        # Obra Aprovada deve iniciar como "NÃO"
        self.field_obra_aprovada.setCurrentIndex(0)

        self.cadastro_layout.addStretch(1)

        self.nav_layout = QtWidgets.QHBoxLayout()
        self.btn_prev_proj = QtWidgets.QPushButton("\u25C0")
        self.btn_prev_proj.clicked.connect(self.prev_projeto_obra)
        self.label_nav_proj = QtWidgets.QLabel()
        self.btn_next_proj = QtWidgets.QPushButton("\u25B6")
        self.btn_next_proj.clicked.connect(self.next_projeto_obra)
        self.btn_cancelar_proj = QtWidgets.QPushButton("Cancelar")
        self.btn_cancelar_proj.clicked.connect(self.cancelar_atualizacao_projeto)
        self.label_msg_proj = QtWidgets.QLabel()
        self.btn_finalizar_proj = QtWidgets.QPushButton("Salvar no banco de dados")
        self.btn_finalizar_proj.clicked.connect(self.finalizar_atualizacao_projeto)
        self.nav_layout.addWidget(self.btn_prev_proj)
        self.nav_layout.addWidget(self.label_nav_proj)
        self.nav_layout.addWidget(self.btn_next_proj)
        self.nav_layout.addWidget(self.btn_cancelar_proj)
        self.nav_layout.addWidget(self.label_msg_proj)
        self.nav_layout.addWidget(self.btn_finalizar_proj)
        self.cadastro_layout.addLayout(self.nav_layout)
        for w in [self.btn_prev_proj, self.btn_next_proj, self.btn_cancelar_proj, self.label_nav_proj, self.label_msg_proj, self.btn_finalizar_proj]:
            w.hide()

    def calcular_valor_obra_handler(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        DataStateManager = _l.DataStateManager
        get_pi_base = _l.get_pi_base
        if not self.require_state(
            "Calcular valor da obra", {"apoio": DataStateManager.CARREGADO_VALIDADO}
        ):  # [RB-5]
            return
        try:
            projeto_investimento = self.field_projeto_investimento.currentText().strip()
            # Evita qualquer interação com o usuário ao calcular o valor da obra,
            # reaproveitando apenas os mapeamentos de PI já existentes.
            pi_base = get_pi_base(projeto_investimento, prompt_user=False)
            quantidade = self.field_quantidade.text().strip()
            caracteristica = self.field_caracteristicas.currentText().strip()
            valor = self.calc_manager.calcular_valor_obra(
                pi_base,
                self.field_tensao.text().strip(),
                caracteristica,
                self.field_regional.text().strip(),
                quantidade
            )
            if valor is not None:
                self.field_valor_obra.setText(str(valor))
            else:
                QtWidgets.QMessageBox.warning(self, "Aviso", 
                    "Nenhum valor unitário encontrado para os parâmetros selecionados.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro no cálculo do valor da obra: {str(e)}")

    def validar_campos_obrigatorios(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        get_pi_base = _l.get_pi_base
        normalize_key = _l.normalize_key
        campos = {
            "Ano": self.field_ano.currentText().strip(),
            "Projeto de Investimentos": self.field_projeto_investimento.currentText().strip(),
            "Alimentador Obra": self.field_alimentador.currentText().strip(),
            "Quantidade": self.field_quantidade.text().strip(),
            "Coordenadas Para": self.field_coord_fim.text().strip(),
            "Pacote": self.field_pacote.currentText().strip(),
            "Características": self.field_caracteristicas.currentText().strip(),
            "Manobra": self.field_manobra.currentText().strip(),
        }

        pi = self.field_projeto_investimento.currentText().strip()
        pi_base = get_pi_base(pi, prompt_user=False)
        valores_distribuicao = {
            "DISTRIBUICAO",
            "DISTRIBUICAO LD 34,5 KV",
        }
        if (
            normalize_key(pi) in valores_distribuicao
            or normalize_key(pi_base) in valores_distribuicao
        ):
            campos["Projeto"] = self.field_projeto.text().strip()

        campos_vazios = [nome for nome, valor in campos.items() if not valor]
        return campos_vazios

    def limpar_campos_cadastro(self):
        self.field_ano.setCurrentIndex(0)
        self.field_ano.setEnabled(True)
        self.projeto_novo_ano = None
        self.field_projeto_investimento.setCurrentIndex(-1)
        self.combo_nome_projeto.setCurrentIndex(-1)
        self.field_projeto.clear()
        self.field_item.clear()
        self.field_alimentador.setCurrentIndex(-1)
        self.field_regional.clear()
        self.field_superintendencia.clear()
        self.field_tensao.clear()
        self.field_tensao_operacao.clear()
        self.field_se.clear()
        self.field_coord_inicio.clear()
        self.field_coord_fim.clear()
        self.field_quantidade.clear()
        self.field_caracteristicas.setCurrentIndex(-1)
        self.field_manobra.setCurrentIndex(-1)  # Limpa o campo Manobra
        self.field_novo_bay.setCurrentIndex(-1)
        self.field_criticidade.setCurrentIndex(-1)
        self.field_observacoes.clear()
        self.field_pacote.setCurrentIndex(-1)
        self.field_obra_aprovada.setCurrentIndex(0)
        self.field_valor_obra.clear()
        self.list_alimentadores_benef.clear()
        self.update_subestacoes_list()
        
        # Novos campos a serem limpos:
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
        self.field_contas_benef.clear()         # Para "Contas Contratos Beneficiadas"
        self.field_cc_benef_chi_ci.clear()        # Para "CC_benef_CHI_CI"
        self.edit_tensao_reg_atual.clear()
        self.edit_carreg_reg_atual.clear()
        self.field_ganhos_totais_antes.clear()
        self.field_ganhos_totais_depois.clear()
        self.edit_ganhos_totais_atual.clear()

        self.obra_em_edicao = None

    def selecionar_pasta_arquivos(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        ConfigManager = _l.ConfigManager
        """Permite ao usuário selecionar a pasta e salva no config.json"""
        pasta = QtWidgets.QFileDialog.getExistingDirectory(self, "Selecionar Pasta")
        if pasta:
            self.field_caminho_pasta.setText(pasta)

            # Atualiza e salva o novo caminho no config.json
            self.config["caminho_pasta_ganhos"] = pasta
            ConfigManager.save_config(self.config)
            self._update_ganhos_path_state(pasta)  # [RB-1.1]

    def nova_se(self):
        """Define o nome do projeto para Nova SE."""
        self.field_projeto.setText("Nova_SE_")

    def novo_al(self):
        """Atalho para preencher dados de novo AL."""
        self.preencher_novo_al()

    def reconfiguracao(self):
        """Define o nome do projeto para Reconfiguração."""
        self.field_projeto.setText("Reconfiguração_")

    def alivio_se(self):
        """Define o nome do projeto para Alívio SE."""
        self.field_projeto.setText("Alívio_SE_")

    def flexibilizacao(self):
        """Define o nome do projeto para Flexibilização."""
        self.field_projeto.setText("Flexibilização_AL_")

    def verificar_pi_padrao(self, pi):
        from ui.main_window import legacy_module
        _l = legacy_module()
        PI_BASE_MAP = _l.PI_BASE_MAP
        _is_pi_base_known = _l._is_pi_base_known
        get_pi_base = _l.get_pi_base
        """Verifica se o PI está na lista padrão e solicita a base caso não esteja."""
        pi = pi.strip()
        # === PI_BASE CUSTOM BEGIN ===
        if self.calc_manager.prompt_pi_base and pi and not _is_pi_base_known(pi):
        # === PI_BASE CUSTOM END ===
            PI_BASE_MAP.pop(pi, None)
            get_pi_base(pi, prompt_user=True)

    def selecionar_pis(self):
        from ui.main_window import legacy_module
        _l = legacy_module()
        get_pi_base = _l.get_pi_base
        """Exibe diálogo para seleção múltipla de PIs disponíveis."""
        if self.support_manager.projetos_investimento_pre_definidos:
            itens = self.support_manager.projetos_investimento_pre_definidos
        else:
            itens = [self.field_projeto_investimento.itemText(i) for i in range(self.field_projeto_investimento.count())]

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Selecionar PIs")
        layout = QtWidgets.QVBoxLayout(dialog)

        lista = QtWidgets.QListWidget()
        lista.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.MultiSelection)
        lista.addItems(itens)
        layout.addWidget(lista)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(btn_box)

        selecionados = []

        def accept():
            for item in lista.selectedItems():
                pi = item.text()
                get_pi_base(pi)
                selecionados.append(pi)
            dialog.accept()

        btn_box.accepted.connect(accept)
        btn_box.rejected.connect(dialog.reject)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            self.selected_pis = selecionados

    def calcular_numero_item(self, nome_projeto):
        if not self.ensure_db_connected():
            return 1
        try:
            return self.db_manager.get_next_codigo_item(nome_projeto)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao calcular número do item: {str(e)}")
            return 1

    def enable_cadastro_fields(self, enabled):
        self.group_dados.setEnabled(enabled)
        self.group_param.setEnabled(enabled)

    def preencher_campos_obra(self, obra):
        from ui.main_window import legacy_module
        _l = legacy_module()
        DEFAULT_CRITERIOS = _l.DEFAULT_CRITERIOS
        DEFAULT_PIORA_MERCADO = _l.DEFAULT_PIORA_MERCADO
        PI_BASE_MAP = _l.PI_BASE_MAP
        cols = self.db_manager.get_column_names()

        # Preenche Projeto de Investimento sem disparar a verificação de PI Base
        try:
            pi = str(obra[cols.index("projeto_investimento")]).strip()
        except (IndexError, ValueError):
            pi = ""
        try:
            pi_base = str(obra[cols.index("pi_base")]).strip()
        except (IndexError, ValueError):
            pi_base = ""

        if pi and pi_base:
            PI_BASE_MAP[pi] = pi_base

        if isinstance(self.field_projeto_investimento, QtWidgets.QComboBox):
            self.field_projeto_investimento.blockSignals(True)
            self.field_projeto_investimento.setCurrentText(pi)
            self.field_projeto_investimento.blockSignals(False)
        elif isinstance(self.field_projeto_investimento, QtWidgets.QPlainTextEdit):
            self.field_projeto_investimento.setPlainText(pi)
        else:
            self.field_projeto_investimento.setText(pi)

        mapping = {
            "ano_": self.field_ano,
            "nome_projeto": self.field_projeto,
            "codigo_item": self.field_item,
            "alimentador_principal": self.field_alimentador,
            "nome_regional": self.field_regional,
            "nome_superintendencia": self.field_superintendencia,
            "nivel_tensao_obra": self.field_tensao,
            "tensao_operacao": self.field_tensao_operacao,
            "subestacao": self.field_se,
            "coordenada_inicio": self.field_coord_inicio,
            "coordenada_fim": self.field_coord_fim,
            "quantidade_material": self.field_quantidade,
            "caracteristicas_material": self.field_caracteristicas,
            "manobra": self.field_manobra,
            "novo_bay": self.field_novo_bay,
            "nivel_criticidade": self.field_criticidade,
            "observacoes_gerais": self.field_observacoes,
            "tipo_pacote": self.field_pacote,
            "obra_aprovada": self.field_obra_aprovada,
            "valor_obra": self.field_valor_obra,
        }
        for col_name, widget in mapping.items():
            try:
                value = obra[cols.index(col_name)]
            except (IndexError, ValueError):
                value = ""
            if isinstance(widget, QtWidgets.QComboBox):
                widget.setCurrentText(str(value))
            elif isinstance(widget, QtWidgets.QPlainTextEdit):
                widget.setPlainText(str(value))
            else:
                widget.setText(str(value))

        beneficiados = obra[cols.index("alimentadores_beneficiados")]
        self.list_alimentadores_benef.clear()
        if beneficiados:
            for b in beneficiados.split(";"):
                item_text = b.strip()
                if item_text:
                    self.list_alimentadores_benef.addItem(item_text)
        self.update_subestacoes_list()

        ganhos_mapping = {
            "contas_contratos_previos": self.field_contas_antes,
            "contas_contratos_posteriores": self.field_contas_depois,
            "contas_contratos_beneficiadas": self.field_contas_benef,
            "carregamento_inicial": self.field_carregamento_antes,
            "carregamento_final": self.field_carregamento_depois,
            "perdas_iniciais": self.field_perdas_antes,
            "perdas_finais": self.field_perdas_depois,
            "tensao_media_inicial": self.field_tensao_media_antes,
            "tensao_media_final": self.field_tensao_media_depois,
            "tensao_min_inicial": self.field_tensao_min_antes,
            "tensao_min_final": self.field_tensao_min_depois,
            "tensao_min_linha_inicial": self.field_tensao_min_linha_antes,
            "tensao_min_linha_final": self.field_tensao_min_linha_depois,
            "chi_inicial": self.field_chi_antes,
            "chi_final": self.field_chi_depois,
            "ci_inicial": self.field_ci_antes,
            "ci_final": self.field_ci_depois,
            "tensao_max_inicial": self.field_tensao_max_antes,
            "tensao_max_final": self.field_tensao_max_depois,
            "tensao_min_registrada_atual": self.edit_tensao_reg_atual,
            "carregamento_max_registrado_atual": self.edit_carreg_reg_atual,
            "cc_benef_chi_ci": self.field_cc_benef_chi_ci,
            "ganhos_totais_antes": self.field_ganhos_totais_antes,
            "ganhos_totais_depois": self.field_ganhos_totais_depois,
            "ganhos_totais_atual": self.edit_ganhos_totais_atual,
        }
        for col_name, widget in ganhos_mapping.items():
            try:
                value = obra[cols.index(col_name)]
                if isinstance(widget, QtWidgets.QPlainTextEdit):
                    widget.setPlainText(str(value))
                else:
                    widget.setText(str(value))
            except (IndexError, ValueError):
                if isinstance(widget, QtWidgets.QPlainTextEdit):
                    widget.setPlainText("")
                else:
                    widget.clear()
        self.obra_em_edicao = obra[cols.index("cod")]

        criterios = self.config.get("criterios_planejamento", DEFAULT_CRITERIOS)
        piora_mercado = self.config.get("piora_mercado", DEFAULT_PIORA_MERCADO)

        def _parse_float(v: str) -> float:
            return float(str(v).replace(",", ".")) if str(v).strip() else 0.0

        def _parse_int(v: str) -> int:
            return int(str(v)) if str(v).strip() else 0

        def atualizar_labels_planejamento_desde_tela() -> None:
            """
            Recalcula os textos de:
            - label_planejamento (atendeu / não atendeu critérios)
            - label_posterga (obra suficiente / insuficiente)
            usando os valores que estão NA TELA na aba Ganhos (campos 'Depois').
            """

            # Começa com os dados salvos em banco
            obra_avaliada = list(obra)

            try:
                idx_tmin = cols.index("tensao_min_final")
                idx_tmax = cols.index("tensao_max_final")
                idx_carreg = cols.index("carregamento_final")
                idx_clientes = cols.index("contas_contratos_posteriores")
                idx_manobra = cols.index("manobra")
            except ValueError:
                # Se alguma coluna não existir, não faz nada
                return

            # Sobrescreve com o que está digitado na aba Ganhos (campos DEPOIS)
            obra_avaliada[idx_tmin] = self.field_tensao_min_depois.text().strip()
            obra_avaliada[idx_tmax] = self.field_tensao_max_depois.text().strip()
            obra_avaliada[idx_carreg] = self.field_carregamento_depois.text().strip()
            obra_avaliada[idx_clientes] = self.field_contas_depois.text().strip()
            # manobra permanece o valor que já está em 'obra' (não é editado na aba Ganhos)

            # --- 1) Critérios de planejamento ---
            atende_, motivos_planej = self._obra_atende(
                obra_avaliada,
                {
                    "tmin": idx_tmin,
                    "tmax": idx_tmax,
                    "carreg": idx_carreg,
                    "manobra": idx_manobra,
                    "clientes": idx_clientes,
                },
                criterios,
                _parse_float,
                _parse_int,
            )

            if atende_ is None:
                texto_ = "⚠️ Dados insuficientes para avaliar Planejamento"
            elif atende_:
                texto_ = "✅ Atendeu aos critérios de Planejamento"
            else:
                detalhes_ = ", ".join(motivos_planej)
                if detalhes_:
                    texto_ = f"❌ Não atendeu aos critérios de Planejamento ({detalhes_})"
                else:
                    texto_ = "❌ Não atendeu aos critérios de Planejamento"
            self.label_planejamento.setText(texto_)

            # --- 2) Suficiência da obra (postergação) ---
            suficiente_, motivos_posterga = self._obra_suficiente(
                obra_avaliada,
                {
                    "tmin": idx_tmin,
                    "tmax": idx_tmax,
                    "carreg": idx_carreg,
                    "manobra": idx_manobra,
                    "clientes": idx_clientes,
                },
                criterios,
                piora_mercado,
                _parse_float,
                _parse_int,
            )

            if suficiente_ is None:
                texto_p_ = "⚠️ Dados insuficientes para avaliar suficiência da obra"
            elif suficiente_:
                texto_p_ = "✅ Obra planejada suficiente"
            else:
                detalhes_p = ", ".join(motivos_posterga)
                if detalhes_p:
                    texto_p_ = f"❌ Obra planejada insuficiente ({detalhes_p})"
                else:
                    texto_p_ = "❌ Obra planejada insuficiente"

            self.label_posterga.setText(texto_p_)


        # Calcula uma vez ao carregar a obra na aba Ganhos
        atualizar_labels_planejamento_desde_tela()

        # Sempre que o usuário mexer nos campos 'depois', recalcula os textos
        for widget in (
            self.field_tensao_min_depois,
            self.field_tensao_max_depois,
            self.field_carregamento_depois,
            self.field_contas_depois,
        ):
            widget.textChanged.connect(atualizar_labels_planejamento_desde_tela)

        try:
            alim_principal = str(
                obra[cols.index("alimentador_principal")]
            )
        except (IndexError, ValueError):
            alim_principal = ""
        try:
            alim_benef = str(
                obra[cols.index("alimentadores_beneficiados")]
            )
        except (IndexError, ValueError):
            alim_benef = ""
        self.popular_quadro_resumo_from_ganhos_depois(
            alim_principal,
            alim_benef,
        )
        try:
            nome_proj = str(obra[cols.index("nome_projeto")])
        except (IndexError, ValueError):
            nome_proj = ""
        self.popular_resumo_ganhos_projeto(nome_proj)
