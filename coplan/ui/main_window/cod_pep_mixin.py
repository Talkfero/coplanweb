"""Mixin COD_PEP -- 4 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 3).
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class CodPepMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def _build_template_data(
        self,
        cod: str = "",
        pi_base: str | None = None,
        projeto_investimento: str | None = None,
    ) -> dict:
        from ui.main_window import legacy_module
        get_pi_base = legacy_module().get_pi_base

        projeto_investimento = (
            projeto_investimento or self.field_projeto_investimento.currentText().strip()
        )
        if pi_base is None:
            pi_base = get_pi_base(projeto_investimento, prompt_user=False)
        tensao_operacao = (
            self.field_tensao_operacao.text().strip()
            or self.field_tensao.text().strip()
        )
        beneficiados_lista = [
            self.list_alimentadores_benef.item(i).text()
            for i in range(self.list_alimentadores_benef.count())
        ]
        return {
            "cod": cod,
            "ano_": self.field_ano.currentText().strip(),
            "projeto_investimento": projeto_investimento,
            "pi_base": pi_base,
            "nome_projeto": self.field_projeto.text().strip(),
            "codigo_item": self.field_item.text().strip(),
            "alimentador_principal": self.field_alimentador.currentText().strip(),
            "alimentadores_beneficiados": ";".join(beneficiados_lista),
            "coordenada_inicio": self.field_coord_inicio.text().strip(),
            "coordenada_fim": self.field_coord_fim.text().strip(),
            "quantidade_material": self.field_quantidade.text().strip(),
            "caracteristicas_material": self.field_caracteristicas.currentText().strip(),
            "novo_bay": self.field_novo_bay.currentText().strip(),
            "nivel_criticidade": self.field_criticidade.currentText().strip(),
            "observacoes_gerais": self.field_observacoes.toPlainText().strip(),
            "nome_regional": self.field_regional.text().strip(),
            "nome_superintendencia": self.field_superintendencia.text().strip(),
            "nivel_tensao_obra": self.field_tensao.text().strip(),
            "tensao_operacao": tensao_operacao,
            "subestacao": self.field_se.text().strip(),
            "contas_contratos_previos": self.field_contas_antes.text().strip(),
            "contas_contratos_posteriores": self.field_contas_depois.text().strip(),
            "contas_contratos_beneficiadas": self.field_contas_benef.text().strip(),
            "carregamento_inicial": self.field_carregamento_antes.text().strip(),
            "carregamento_final": self.field_carregamento_depois.text().strip(),
            "perdas_iniciais": self.field_perdas_antes.text().strip(),
            "perdas_finais": self.field_perdas_depois.text().strip(),
            "tensao_media_inicial": self.field_tensao_media_antes.text().strip(),
            "tensao_media_final": self.field_tensao_media_depois.text().strip(),
            "tensao_min_inicial": self.field_tensao_min_antes.text().strip(),
            "tensao_min_final": self.field_tensao_min_depois.text().strip(),
            "tensao_min_linha_inicial": self.field_tensao_min_linha_antes.text().strip(),
            "tensao_min_linha_final": self.field_tensao_min_linha_depois.text().strip(),
            "chi_inicial": self.field_chi_antes.text().strip(),
            "ci_inicial": self.field_ci_antes.text().strip(),
            "tensao_max_inicial": self.field_tensao_max_antes.text().strip(),
            "tensao_max_final": self.field_tensao_max_depois.text().strip(),
            "tensao_min_registrada_atual": self.edit_tensao_reg_atual.text().strip(),
            "carregamento_max_registrado_atual": self.edit_carreg_reg_atual.text().strip(),
            "tipo_pacote": self.field_pacote.currentText().strip(),
            "obra_aprovada": self.field_obra_aprovada.currentText().strip(),
            "valor_obra": self.field_valor_obra.text().strip(),
            "cc_benef_chi_ci": self.field_cc_benef_chi_ci.text().strip(),
            "chi_final": self.field_chi_depois.text().strip(),
            "ci_final": self.field_ci_depois.text().strip(),
            "manobra": self.field_manobra.currentText().strip(),
            "ganhos_totais_antes": self.field_ganhos_totais_antes.text().strip(),
            "ganhos_totais_depois": self.field_ganhos_totais_depois.text().strip(),
            "ganhos_totais_atual": self.edit_ganhos_totais_atual.text().strip(),
        }

    def _setup_template_settings_tab(self, container: QtWidgets.QWidget) -> None:
        from ui.main_window import legacy_module
        legacy = legacy_module()
        ConfigManager = legacy.ConfigManager
        get_all_pi_bases = legacy.get_all_pi_bases
        _normalize_pi_base_name = legacy._normalize_pi_base_name
        PI_BASE_MAP = legacy.PI_BASE_MAP
        TemplatePlainTextEdit = legacy.TemplatePlainTextEdit
        get_pi_default_description_template = legacy.get_pi_default_description_template
        render_template = legacy.render_template

        layout = QtWidgets.QVBoxLayout(container)

        config = ConfigManager.load_config()
        templates = config.get("descricao_obra_templates", {})
        template_keys = set(templates.keys()) if isinstance(templates, dict) else set()
        bases = get_all_pi_bases()
        seen = {_normalize_pi_base_name(b) for b in bases}
        extras = list(PI_BASE_MAP.values()) + list(template_keys)
        for base in extras:
            key = _normalize_pi_base_name(base)
            if key and key not in seen:
                bases.append(base)
                seen.add(key)
        columns = self._get_visualizar_columns_candidates()

        combo_pi = QtWidgets.QComboBox(container)
        combo_pi.addItems(bases)
        self.cfg_template_combo_pi = combo_pi
        btn_manage_pi = QtWidgets.QPushButton("+ PI_BASE")

        editor = TemplatePlainTextEdit(columns, container)
        editor.setPlaceholderText(
            "Digite o template. Use {nome_coluna} para inserir valores."
        )

        preview_output = QtWidgets.QPlainTextEdit(container)
        preview_output.setReadOnly(True)
        preview_output.setPlaceholderText("Pré-visualização do template renderizado.")
        preview_output.setFixedHeight(80)

        left_layout = QtWidgets.QVBoxLayout()
        form = QtWidgets.QFormLayout()
        combo_layout = QtWidgets.QHBoxLayout()
        combo_layout.addWidget(combo_pi)
        combo_layout.addWidget(btn_manage_pi)
        form.addRow("PI Base", combo_layout)
        form.addRow("Template", editor)
        left_layout.addLayout(form)

        hint = QtWidgets.QLabel(
            "Digite “{” para ver as colunas disponíveis no autocomplete."
        )
        hint.setWordWrap(True)
        left_layout.addWidget(hint)

        btn_preview = QtWidgets.QPushButton("Pré-visualizar")
        left_layout.addWidget(btn_preview)
        left_layout.addWidget(preview_output)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(QtWidgets.QLabel("Campos disponíveis"))
        list_fields = QtWidgets.QListWidget(container)
        list_fields.addItems(columns)
        list_fields.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        right_layout.addWidget(list_fields)

        main_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(left_layout, 3)
        main_layout.addLayout(right_layout, 1)
        layout.addLayout(main_layout)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        btn_save = QtWidgets.QPushButton("Salvar")
        btn_restore_pi = QtWidgets.QPushButton("Restaurar padrão do PI")
        btn_restore_all = QtWidgets.QPushButton("Restaurar todos")
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_restore_pi)
        btn_layout.addWidget(btn_restore_all)
        layout.addLayout(btn_layout)

        def _load_template(pi_base: str) -> None:
            cfg = ConfigManager.load_config()
            templates_cfg = cfg.get("descricao_obra_templates", {})
            template = ""
            if isinstance(templates_cfg, dict):
                template = templates_cfg.get(pi_base.strip().upper(), "") or ""
            if not template:
                template = get_pi_default_description_template(pi_base, cfg)
            editor.setPlainText(template)
            preview_output.clear()

        def _save_template() -> None:
            pi_base = combo_pi.currentText().strip().upper()
            template = editor.toPlainText()
            try:
                cfg = ConfigManager.load_config()
                templates_cfg = dict(cfg.get("descricao_obra_templates", {}))
                templates_cfg[pi_base] = template
                ConfigManager.save_config({"descricao_obra_templates": templates_cfg})
                cfg2 = ConfigManager.load_config()
                tpl2 = (cfg2.get("descricao_obra_templates", {}) or {}).get(pi_base, None)
                if tpl2 == template:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Salvo",
                        f"Template salvo com sucesso para o PI Base: {pi_base}.",
                    )
                else:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Atenção",
                        "O template foi gravado, mas não foi possível confirmar a persistência ao reler o config.",
                    )
            except Exception as exc:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Erro ao salvar",
                    f"Não foi possível salvar o template.\n\nDetalhes: {exc}",
                )

        def _restore_template() -> None:
            pi_base = combo_pi.currentText().strip().upper()
            cfg = ConfigManager.load_config()
            templates_cfg = dict(cfg.get("descricao_obra_templates", {}))
            templates_cfg.pop(pi_base, None)
            ConfigManager.save_config({"descricao_obra_templates": templates_cfg})
            _load_template(pi_base)

        def _restore_all() -> None:
            ConfigManager.save_config({"descricao_obra_templates": {}})
            _load_template(combo_pi.currentText())

        def _preview() -> None:
            template = editor.toPlainText()
            data_map = self._build_template_data(
                pi_base=combo_pi.currentText().strip().upper()
            )
            preview_output.setPlainText(render_template(template, data_map))

        def _insert_field(item: QtWidgets.QListWidgetItem) -> None:
            if item:
                editor.insert_placeholder(item.text())

        def _reload_pi_bases(keep: str | None = None) -> None:
            current = keep or combo_pi.currentText()
            updated_bases = get_all_pi_bases()
            seen_local = {_normalize_pi_base_name(b) for b in updated_bases}
            cfg = ConfigManager.load_config()
            templates_now = cfg.get("descricao_obra_templates", {})
            template_keys_now = (
                set(templates_now.keys()) if isinstance(templates_now, dict) else set()
            )
            extras_now = list(PI_BASE_MAP.values()) + list(template_keys_now)
            for base in extras_now:
                key = _normalize_pi_base_name(base)
                if key and key not in seen_local:
                    updated_bases.append(base)
                    seen_local.add(key)
            combo_pi.blockSignals(True)
            combo_pi.clear()
            combo_pi.addItems(updated_bases)
            if current:
                idx = combo_pi.findText(current)
                if idx >= 0:
                    combo_pi.setCurrentIndex(idx)
            combo_pi.blockSignals(False)

        def _open_manage_pi_base() -> None:
            self.open_manage_pi_base_dialog(self)
            _reload_pi_bases()

        combo_pi.currentTextChanged.connect(_load_template)
        list_fields.itemDoubleClicked.connect(_insert_field)
        btn_save.clicked.connect(_save_template)
        btn_restore_pi.clicked.connect(_restore_template)
        btn_restore_all.clicked.connect(_restore_all)
        btn_preview.clicked.connect(_preview)
        btn_manage_pi.clicked.connect(_open_manage_pi_base)

        self._cfg_template_reload_pi_bases = _reload_pi_bases
        self._cfg_template_load_template = _load_template
        _load_template(combo_pi.currentText())

    def open_descricao_template_dialog(self, *_args) -> None:
        self._open_configuracoes_tab("template")

    def on_gerar_cod_pep_clicked(self) -> None:
        from ui.main_window import legacy_module
        legacy = legacy_module()
        DataStateManager = legacy.DataStateManager
        CodPepBatchDialog = legacy.CodPepBatchDialog
        get_empresa_sigla_from_config = legacy.get_empresa_sigla_from_config
        ProgressRelay = legacy.ProgressRelay

        if not self.require_state(
            "Gerar COD_PEP", {"db": DataStateManager.CARREGADO_VALIDADO}
        ):
            return
        if not self.ensure_db_connected():
            return

        tabela = getattr(self, "table_obras", None)
        if tabela is None or tabela.rowCount() == 0:
            QtWidgets.QMessageBox.information(
                self,
                "Gerar COD_PEP",
                "Não há obras carregadas para processar.",
            )
            return

        selecionadas = self._get_visualizar_scope_rows("selected")
        dialog = CodPepBatchDialog(
            self.db_manager,
            self,
            has_selection=bool(selecionadas),
        )
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        scope = dialog.selected_scope()
        somente_vazios = dialog.somente_vazios()
        incluir_aprovadas = dialog.incluir_aprovadas()
        ids: list[str] = []
        scope_years: list[str] = []
        if scope == CodPepBatchDialog.SCOPE_SELECTED:
            ids = self._get_visualizar_scope_ids("selected")
            scope_years = self._get_visualizar_scope_years("selected")
        elif scope == CodPepBatchDialog.SCOPE_VISIBLE:
            ids = self._get_visualizar_scope_ids("visible")
            scope_years = self._get_visualizar_scope_years("visible")
        else:
            ids = self._buscar_ids_por_pacotes(dialog.selected_pacotes(), somente_vazios)
            scope_years = self._get_visualizar_scope_years("visible")
        ids, ignoradas_aprovadas = self._filtrar_ids_por_aprovacao(
            ids,
            incluir_aprovadas,
        )
        if scope == CodPepBatchDialog.SCOPE_PACKAGES and scope_years:
            ids = self._filtrar_ids_por_anos(ids, scope_years)
        anos_por_ids = self._buscar_anos_por_ids(ids)
        if anos_por_ids:
            scope_years = anos_por_ids

        if not ids:
            mensagem = "Nenhuma obra encontrada no escopo informado."
            if ignoradas_aprovadas > 0 and not incluir_aprovadas:
                mensagem = (
                    "Nenhuma obra NÃO aprovada para processar no escopo informado. "
                    "Marque 'Incluir obras aprovadas' para incluir."
                )
            QtWidgets.QMessageBox.information(
                self,
                "Gerar COD_PEP",
                mensagem,
            )
            return

        try:
            empresa_sigla = get_empresa_sigla_from_config(self.config)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Gerar COD_PEP",
                f"Falha ao obter a empresa configurada: {exc}",
            )
            return

        total_ids = max(len(ids), 1)
        progress = QtWidgets.QProgressDialog(
            "Preparando geração de COD_PEP...",
            "Cancelar",
            0,
            total_ids,
            self,
        )
        progress.setWindowTitle("Geração de COD_PEP em andamento")
        progress.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        progress.show()
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents
        )

        cancel_state = {"cancelado": False}
        progress.canceled.connect(lambda: cancel_state.__setitem__("cancelado", True))

        relay = ProgressRelay(self)

        def apply_progress(processados: int, total: int, label: str) -> None:
            max_total = max(int(total), 1)
            progress.setRange(0, max_total)
            progress.setValue(max(0, min(int(processados), max_total)))
            if label:
                progress.setLabelText(str(label))
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents
            )

        relay.progress_changed.connect(
            apply_progress,
            QtCore.Qt.ConnectionType.QueuedConnection,
        )

        try:
            atualizados, ignorados, erros = self.db_manager.gerar_cod_pep_para_cods(
                ids,
                empresa_sigla,
                somente_vazios=somente_vazios,
                scope_years=scope_years,
                reiniciar_numeracao=not somente_vazios,
                progress_callback=lambda v, t, txt: relay.progress_changed.emit(v, t, txt),
                cancel_callback=lambda: bool(cancel_state["cancelado"]),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(
                self,
                "Gerar COD_PEP",
                f"Erro ao gerar COD_PEP em lote: {exc}",
            )
            self.load_obras_into_table()
            return
        finally:
            if progress is not None:
                progress.setValue(progress.maximum())
                progress.close()

        resumo = [
            f"Atualizados: {atualizados}",
            f"Ignorados: {ignorados}",
        ]
        if cancel_state["cancelado"]:
            resumo.append("Processo cancelado pelo usuário.")
        if ignoradas_aprovadas > 0 and not incluir_aprovadas:
            resumo.append(f"Ignoradas (aprovadas): {ignoradas_aprovadas}")
        resumo.append(f"Erros: {len(erros)}")
        if erros:
            resumo.append("")
            resumo.append("Exemplos:")
            resumo.extend(f"- {msg}" for msg in erros[:10])
            if len(erros) > 10:
                resumo.append(f"... e mais {len(erros) - 10} erro(s).")

        QtWidgets.QMessageBox.information(
            self,
            "Gerar COD_PEP",
            "\n".join(resumo),
        )
        self.load_obras_into_table()
