"""Mixin Estado de Fontes (data_state) -- 16 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 3).
"""
from __future__ import annotations

import os
import sqlite3
from typing import Optional

from PySide6 import QtWidgets


class EstadoFontesMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def _set_data_state(
        self,
        source: str,
        state: str,
        path: Optional[str] = None,
        error: Optional[str] = None,
        version_token: Optional[str] = None,
    ) -> None:
        """Atualiza o estado e refresca ações."""  # [RB-1.1]
        old_info = self.data_state.get_state(source)
        self.data_state.update_source(
            source, state, path=path, error=error, version_token=version_token
        )
        self._register_source_impact(source, old_info)  # [RB-5]
        self.refresh_action_availability()
        self.update_reliability_labels()  # [RB-5]

    def _register_source_impact(self, source: str, previous) -> None:
        """Registra impactos quando uma fonte é recarregada ou invalidada."""  # [RB-5]
        from ui.main_window import legacy_module
        legacy = legacy_module()
        DataStateManager = legacy.DataStateManager
        LOGGER = legacy.LOGGER

        impact_map = {
            "apoio": ["Cálculo de valores", "Despacho", "Relatórios"],
            "ganhos": ["Ganhos", "Relatórios", "VT"],
            "tecnico_txt": ["Ganhos", "Relatórios", "VT"],
        }
        if source not in impact_map:
            return
        current = self.data_state.get_state(source)
        if current.state == DataStateManager.NAO_CARREGADO:
            return
        changed = False
        if (
            previous.state == DataStateManager.NAO_CARREGADO
            and not previous.path
            and not previous.version_token
        ):
            changed = False
        if current.version_token and current.version_token != previous.version_token:
            changed = True
        if current.path and current.path != previous.path:
            changed = True
        if current.state == DataStateManager.INVALIDADO and previous.state != current.state:
            changed = True
        if not changed:
            return
        for modulo in impact_map[source]:
            self._impact_modules[modulo] = "INVALIDADO"
        source_label = {
            "apoio": "Apoio",
            "ganhos": "Ganhos",
            "tecnico_txt": "Arquivos técnicos",
        }.get(source, source)
        impacted = " / ".join(impact_map[source])
        self._impact_message = (
            f"Recarregar {source_label} invalidou: {impacted}"
        )
        LOGGER.info("Mapa de impacto atualizado (%s): %s", source, impacted)
        self._update_impact_label()

    def _update_impact_label(self) -> None:
        """Atualiza o texto do mapa de impacto na UI."""  # [RB-5]
        label = getattr(self, "impact_label", None)
        if label is None:
            return
        if self._impact_message:
            label.setText(self._impact_message)
            label.setStyleSheet("color: #b45309; font-weight: 600;")
        else:
            label.setText("Mapa de impacto: sem alterações recentes.")
            label.setStyleSheet("color: #64748b;")

    def _format_state_timestamp(self, info) -> str:
        if info.validated_at:
            return info.validated_at.strftime("%d/%m %H:%M")
        return "N/D"

    def update_reliability_labels(self) -> None:
        """Atualiza indicadores de confiabilidade no topo."""  # [RB-5]
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        db_label = getattr(self, "db_valid_label", None)
        apoio_label = getattr(self, "apoio_valid_label", None)
        tecnico_label = getattr(self, "tecnico_valid_label", None)
        if not (db_label and apoio_label and tecnico_label):
            return

        db_state = self.data_state.get_state("db")
        if db_state.state == DataStateManager.CARREGADO_VALIDADO:
            db_label.setText(f"DB: VALIDADO em {self._format_state_timestamp(db_state)}")
        elif db_state.state == DataStateManager.INVALIDADO:
            db_label.setText("DB: INVALIDADO")
        else:
            db_label.setText("DB: N/D")

        apoio_state = self.data_state.get_state("apoio")
        if apoio_state.state == DataStateManager.CARREGADO_VALIDADO:
            apoio_label.setText(
                f"Apoio: VALIDADO em {self._format_state_timestamp(apoio_state)}"
            )
        elif apoio_state.state == DataStateManager.INVALIDADO:
            apoio_label.setText("Apoio: INVALIDADO")
        else:
            apoio_label.setText("Apoio: N/D")

        if getattr(self.db_manager, "conn", None):
            dirty_count = self.db_manager.count_tecnico_dirty()
            if dirty_count > 0:
                tecnico_label.setText(f"Técnico: DIRTY ({dirty_count})")
            else:
                tecnico_label.setText("Técnico: OK")
        else:
            tecnico_label.setText("Técnico: N/D")

        self._update_impact_label()

    def _validate_db_minimum(self, db_path: str) -> bool:
        """Valida permissões, tabela e colunas essenciais do banco."""
        from ui.main_window import legacy_module
        legacy = legacy_module()
        log_connect_debug = legacy.log_connect_debug
        show_user_error = legacy.show_user_error
        open_sqlite_safe = legacy.open_sqlite_safe
        normalize_key = legacy.normalize_key
        LOGGER = legacy.LOGGER

        log_connect_debug("_validate_db_minimum.start", db_path)
        if not db_path:
            return False
        if not os.path.isfile(db_path):
            log_connect_debug("_validate_db_minimum.file_not_found", db_path)
            self._update_db_state(db_path, error="Arquivo de banco não encontrado.")
            show_user_error(
                "Banco inválido",
                f"Arquivo não encontrado: {db_path}",
                "Selecione ou crie um banco válido.",
                parent=self,
            )
            return False
        if not os.access(db_path, os.R_OK):
            log_connect_debug("_validate_db_minimum.no_read_permission", db_path)
            self._update_db_state(db_path, error="Sem permissão de leitura.")
            show_user_error(
                "Banco sem permissão",
                f"Sem permissão de leitura: {db_path}",
                "Verifique as permissões do arquivo.",
                parent=self,
            )
            return False
        if not os.access(db_path, os.W_OK):
            log_connect_debug("_validate_db_minimum.no_write_permission", db_path)
            self._update_db_state(db_path, error="Sem permissão de escrita.")
            show_user_error(
                "Banco sem permissão",
                f"Sem permissão de escrita: {db_path}",
                "Verifique as permissões do arquivo.",
                parent=self,
            )
            return False
        conn: sqlite3.Connection | None = None
        try:
            conn = open_sqlite_safe(db_path)
            log_connect_debug("_validate_db_minimum.open_ok", db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='obras'"
            )
            if cursor.fetchone() is None:
                log_connect_debug("_validate_db_minimum.table_obras_missing", db_path)
                conn.close()
                conn = None
                self._update_db_state(db_path, error="Tabela 'obras' inexistente.")
                show_user_error(
                    "Banco inválido",
                    "Tabela 'obras' não encontrada no banco.",
                    "Selecione um banco compatível com o sistema.",
                    parent=self,
                )
                return False
            cursor.execute("PRAGMA table_info(obras)")
            colunas = [str(row[1]).strip() for row in cursor.fetchall() if len(row) > 1]
            colunas_norm = {normalize_key(col) for col in colunas if col}
            required_min_columns = ["cod"]
            missing = [
                c for c in required_min_columns if normalize_key(c) not in colunas_norm
            ]
            conn.close()
            conn = None
            if missing:
                log_connect_debug(
                    "_validate_db_minimum.required_column_missing",
                    db_path,
                    extra={"missing": missing},
                )
                self._update_db_state(
                    db_path,
                    error="Banco sem coluna mínima obrigatória: " + ", ".join(missing),
                )
                show_user_error(
                    "Banco inválido",
                    "Coluna mínima obrigatória ausente: " + ", ".join(missing),
                    "Atualize o banco ou crie um novo banco pelo sistema.",
                    parent=self,
                )
                return False
            missing_full = sorted(
                c for c in self.db_manager.root_columns if normalize_key(c) not in colunas_norm
            )
            if missing_full:
                LOGGER.info(
                    "Banco com schema parcial detectado em validação inicial. "
                    "As colunas ausentes serão tratadas na conexão: %s",
                    ", ".join(missing_full[:12]) + ("..." if len(missing_full) > 12 else ""),
                )
                log_connect_debug(
                    "_validate_db_minimum.schema_partial",
                    db_path,
                    extra={"missing_count": len(missing_full)},
                )
        except Exception as exc:
            log_connect_debug("_validate_db_minimum.error", db_path, exc=exc)
            LOGGER.exception("Erro ao validar banco.")
            self._update_db_state(db_path, error=str(exc))
            show_user_error(
                "Erro ao validar banco",
                f"Falha na validação do banco: {exc}",
                "Verifique o arquivo do banco e tente novamente.",
                parent=self,
            )
            return False
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        log_connect_debug("_validate_db_minimum.success", db_path)
        return True

    def _update_db_state(self, db_path: str, error: Optional[str] = None) -> None:
        """Atualiza o estado do DB conforme colunas obrigatórias."""  # [RB-1.1]
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        columns = self.db_manager.get_column_names()
        missing = [c for c in self.db_manager.root_columns if c not in columns]
        if error:
            self._set_data_state(
                "db",
                DataStateManager.INVALIDADO,
                path=db_path,
                error=error,
                version_token=self._compute_file_token(db_path),
            )
        elif missing:
            self._set_data_state(
                "db",
                DataStateManager.INVALIDADO,
                path=db_path,
                error="Banco sem colunas obrigatórias: " + ", ".join(missing),
                version_token=self._compute_file_token(db_path),
            )
        else:
            self._set_data_state(
                "db",
                DataStateManager.CARREGADO_VALIDADO,
                path=db_path,
                version_token=self._compute_file_token(db_path),
            )

    def _update_apoio_state(self, filepath: str, sucesso: bool, error: str = "") -> None:
        """Atualiza o estado da planilha de apoio."""  # [RB-1.1]
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        if sucesso:
            token = self._compute_file_token(filepath)
            self._handle_tecnico_token_change("apoio", token)
            self._set_data_state(
                "apoio",
                DataStateManager.CARREGADO_VALIDADO,
                path=filepath,
                version_token=token,
            )
        else:
            self._set_data_state(
                "apoio",
                DataStateManager.INVALIDADO,
                path=filepath,
                error=error or "Falha ao validar planilha de apoio.",
                version_token=self._compute_file_token(filepath),
            )
        self.update_db_path_label()

    def _update_ganhos_path_state(self, pasta: str) -> None:
        """Marca a pasta de ganhos como carregada parcialmente."""  # [RB-1.1]
        from ui.main_window import legacy_module
        legacy = legacy_module()
        DataStateManager = legacy.DataStateManager
        TECNICO_REQUIRED_FILES = legacy.TECNICO_REQUIRED_FILES

        if pasta and os.path.isdir(pasta):
            token = self._compute_folder_token(pasta, TECNICO_REQUIRED_FILES)
            self._handle_tecnico_token_change("ganhos", token)
            self._set_data_state(
                "ganhos",
                DataStateManager.CARREGADO_PARCIAL,
                path=pasta,
                version_token=token,
            )
        else:
            self._set_data_state(
                "ganhos",
                DataStateManager.INVALIDADO,
                path=pasta,
                error="Pasta de ganhos inexistente ou inválida.",
            )

    def _update_tecnico_state(
        self, pasta: str, required_files: list[str], dados: dict[str, list[str]]
    ) -> bool:
        """Atualiza estado dos arquivos técnicos após leitura."""  # [RB-1.1]
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        missing = [name for name in required_files if not dados.get(name)]
        token = self._compute_folder_token(pasta, required_files)
        if missing:
            self._set_data_state(
                "tecnico_txt",
                DataStateManager.INVALIDADO,
                path=pasta,
                error="Arquivos técnicos vazios ou ausentes: " + ", ".join(missing),
                version_token=token,
            )
            return False
        self._handle_tecnico_token_change("tecnico_txt", token)
        self._set_data_state(
            "tecnico_txt",
            DataStateManager.CARREGADO_VALIDADO,
            path=pasta,
            version_token=token,
        )
        self._set_data_state(
            "ganhos",
            DataStateManager.CARREGADO_VALIDADO,
            path=pasta,
            version_token=token,
        )
        return True

    def require_state(self, action_name: str, required: dict[str, str]) -> bool:
        """Verifica pré-condições de estado antes de executar ações."""  # [RB-1.1]
        from ui.main_window import legacy_module
        LOGGER = legacy_module().LOGGER

        source_labels = {
            "db": ("Banco de dados", "Conecte ou crie um banco de dados."),
            "apoio": ("Planilha de apoio", "Carregue a planilha de apoio."),
            "ganhos": ("Pasta de ganhos", "Selecione a pasta dos arquivos de ganhos."),
            "tecnico_txt": ("Arquivos técnicos (TXT)", "Carregue os arquivos técnicos."),
        }

        pendencias: list[dict[str, str]] = []
        for source, min_state in required.items():
            if not self.data_state.meets_required(source, min_state):
                info = self.data_state.get_state(source)
                label, hint = source_labels.get(source, (source, ""))
                erro = f" Erro: {info.error_last}" if info.error_last else ""
                pendencias.append(
                    {
                        "source": source,
                        "label": label,
                        "detail": f"{label} ({info.state}).{erro} {hint}".strip(),
                    }
                )

        if pendencias:
            faltam = ", ".join(p["label"] for p in pendencias)
            detalhes = "\n".join(f"- {p['detail']}" for p in pendencias)
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg_box.setWindowTitle("Pré-requisitos não atendidos")
            msg_box.setText(f"Ação bloqueada: falta carregar {faltam}.")  # [RB-5]
            msg_box.setInformativeText(
                f"Ação '{action_name}' não pode ser iniciada.\n\n{detalhes}"
            )
            msg_box.setDetailedText(
                "Use os botões 'Ir para...' para resolver as pendências."
            )
            buttons = {}
            for pend in pendencias:
                btn = msg_box.addButton(
                    f"Ir para {pend['label']}",
                    QtWidgets.QMessageBox.ButtonRole.ActionRole,
                )
                buttons[btn] = pend["source"]
            msg_box.addButton(
                "Fechar", QtWidgets.QMessageBox.ButtonRole.RejectRole
            )
            msg_box.exec()
            clicked = msg_box.clickedButton()
            source = buttons.get(clicked)
            if source:
                LOGGER.info("Ação bloqueada (%s): redirecionando para %s.", action_name, source)
                self._go_to_required_source(source)
            return False
        return True

    def _go_to_required_source(self, source: str) -> None:
        """Atalho para guiar o usuário até a fonte necessária."""  # [RB-5]
        if source == "db":
            if hasattr(self, "tabs"):
                self.tabs.setCurrentWidget(self.tab_visualizar)
            self.connect_database()
            return
        if source == "apoio":
            if hasattr(self, "tabs"):
                self.tabs.setCurrentWidget(self.tab_cadastro)
            self.load_support_file()
            return
        if source in {"ganhos", "tecnico_txt"}:
            if hasattr(self, "tabs"):
                self.tabs.setCurrentWidget(self.tab_ganhos)
            self.selecionar_pasta_arquivos()
            return

    def _mark_db_refresh_point(self) -> None:
        data, usuario = self.db_manager.get_last_modification_info()
        self._last_db_refresh_timestamp = data
        self._last_db_refresh_user = usuario
        self._last_db_modification_warned = None

    def _warn_external_db_update(self, data: Optional[str]) -> None:
        if not data:
            return
        last_refresh = getattr(self, "_last_db_refresh_timestamp", None)
        if last_refresh and data != last_refresh:
            last_warned = getattr(self, "_last_db_modification_warned", None)
            if last_warned != data:
                QtWidgets.QMessageBox.information(
                    self,
                    "Banco atualizado",
                    "Banco atualizado por outro usuário; recarregue para ver mudanças.",
                )
                self._last_db_modification_warned = data

    def require_export_sources(self, action_name: str) -> bool:
        """Valida fontes técnicas e banco antes de exportar/relatar."""  # [RB-4]
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        return self.require_state(
            action_name,
            {
                "db": DataStateManager.CARREGADO_VALIDADO,
                "ganhos": DataStateManager.CARREGADO_VALIDADO,
                "tecnico_txt": DataStateManager.CARREGADO_VALIDADO,
            },
        )

    def refresh_action_availability(self) -> None:
        """Habilita/desabilita ações conforme o estado de dados."""  # [RB-1.1]
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        db_ready = self.data_state.meets_required(
            "db", DataStateManager.CARREGADO_VALIDADO
        )
        db_ok = bool(getattr(self.db_manager, "conn", None)) or db_ready  # [RB-RESTORE-OLD]
        ganhos_path = self._ganhos_folder()  # [RB-RESTORE-OLD]
        ganhos_path_ok = self._path_exists(ganhos_path)  # [RB-RESTORE-OLD]
        tecnico_ready = self.data_state.meets_required(
            "ganhos", DataStateManager.CARREGADO_VALIDADO
        ) and self.data_state.meets_required(
            "tecnico_txt", DataStateManager.CARREGADO_VALIDADO
        )
        export_ready = db_ready and tecnico_ready

        for action in (
            getattr(self, "act_salvar", None),
            getattr(self, "act_importar", None),
        ):
            if action is not None:
                action.setEnabled(db_ok)  # [RB-RESTORE-OLD]

        if getattr(self, "act_exportar", None) is not None:
            self.act_exportar.setEnabled(db_ok)
        if getattr(self, "act_gerar_cod_pep", None) is not None:
            self.act_gerar_cod_pep.setEnabled(db_ok)

        if hasattr(self, "btn_exportar_resumo"):
            self.btn_exportar_resumo.setEnabled(export_ready)
        if hasattr(self, "btn_exportar_banco"):
            self.btn_exportar_banco.setEnabled(db_ok)  # [RB-RESTORE-OLD]
        if hasattr(self, "btn_detalhamento"):
            self.btn_detalhamento.setEnabled(db_ok)  # [RB-RESTORE-OLD]
        if hasattr(self, "btn_gerar_nota"):
            self.btn_gerar_nota.setEnabled(db_ok)  # [RB-RESTORE-OLD]
        if hasattr(self, "btn_atualizar_snapshot_tecnico"):
            self.btn_atualizar_snapshot_tecnico.setEnabled(db_ok)  # [RB-RESTORE-OLD]

        for btn in (
            getattr(self, "btn_seta_antes", None),
            getattr(self, "btn_seta_depois", None),
            getattr(self, "btn_ganhos_massa", None),
            getattr(self, "btn_preencher_atuais", None),
        ):
            if btn is not None:
                btn.setEnabled(ganhos_path_ok)  # [RB-RESTORE-OLD]

        for btn in (
            getattr(self, "btn_atualizar", None),
            getattr(self, "btn_excluir", None),
            getattr(self, "btn_backup", None),
            getattr(self, "btn_atualizar_plano", None),
        ):
            if btn is not None:
                btn.setEnabled(db_ok)  # [RB-RESTORE-OLD]
