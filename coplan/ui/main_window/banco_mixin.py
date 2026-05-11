"""Mixin Banco -- 6 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 3).

**Excecao**: ``_exportar_para_banco_write_phase`` e ``_save_backup_db_file``
ficam no codigo5_coplan.py por terem decorator
``@run_write_in_qthread_if_ui_thread``.
"""
from __future__ import annotations

import os

from PySide6 import QtCore, QtWidgets


class BancoMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def ensure_db_connected(self) -> bool:
        """Garante que o banco de dados esteja disponível em cache."""
        from ui.main_window import legacy_module
        legacy = legacy_module()
        ts_now = legacy.ts_now
        ts_log = legacy.ts_log

        t_total = ts_now()
        dbm = getattr(self, "db_manager", None)
        if not dbm or not dbm.db_path:
            QtWidgets.QMessageBox.critical(self, "Erro", "Banco de dados não conectado.")
            return False

        t_cache = ts_now()
        dbm._ensure_cache_loaded()
        ts_log("_ensure_cache_loaded()", t_cache)
        ts_log("ensure_db_connected TOTAL", t_total)
        return True

    def _path_exists(self, p: str) -> bool:
        return bool(p and str(p).strip() and os.path.exists(str(p).strip()))  # [RB-RESTORE-OLD]

    def connect_database(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        log_connect_debug = legacy.log_connect_debug
        ConfigManager = legacy.ConfigManager
        LOGGER = legacy.LOGGER
        show_user_error = legacy.show_user_error

        db_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Selecionar Banco de Dados", "", "SQLite Database (*.db)")
        log_connect_debug("ui.connect_database.dialog_result", db_path)
        if db_path:
            with self._with_loading_indicator(action=getattr(self, "act_conectar", None)):
                try:
                    if not self._validate_db_minimum(db_path):
                        log_connect_debug("ui.connect_database.validation_failed", db_path)
                        return
                    log_connect_debug("ui.connect_database.connect_call", db_path)
                    self.db_manager.connect(db_path)
                    self.choose_packages()
                    self.config["obras"] = db_path
                    ConfigManager.save_config({"obras": db_path})
                    QtWidgets.QMessageBox.information(self, "Sucesso", "Conectado ao banco com sucesso!")
                    self._update_db_state(db_path)  # [RB-1.1]
                    self.load_obras_into_table()
                    self.update_db_path_label()
                    log_connect_debug("ui.connect_database.success", db_path)
                except Exception as e:
                    log_connect_debug("ui.connect_database.error", db_path, exc=e)
                    LOGGER.exception("Erro ao conectar ao banco.")
                    self._update_db_state(db_path, error=str(e))  # [RB-1.1]
                    show_user_error(
                        "Erro ao conectar ao banco",
                        f"Erro ao conectar ao banco: {str(e)}",
                        "Verifique o arquivo e as permissões e tente novamente.",
                        parent=self,
                    )

    def create_new_database(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        log_connect_debug = legacy.log_connect_debug
        ConfigManager = legacy.ConfigManager
        LOGGER = legacy.LOGGER
        show_user_error = legacy.show_user_error

        db_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Criar Novo Banco de Dados", "", "SQLite Database (*.db)")
        log_connect_debug("ui.create_new_database.dialog_result", db_path)
        if db_path:
            try:
                log_connect_debug("ui.create_new_database.connect_call", db_path)
                self.db_manager.connect(db_path)
                self.db_manager.set_allowed_pacotes(None)
                self.config["obras"] = db_path
                ConfigManager.save_config({"obras": db_path})
                QtWidgets.QMessageBox.information(self, "Sucesso", "Novo banco criado e conectado!")
                self._update_db_state(db_path)  # [RB-1.1]
                self.load_obras_into_table()
                self.update_db_path_label()
                log_connect_debug("ui.create_new_database.success", db_path)
            except Exception as e:
                log_connect_debug("ui.create_new_database.error", db_path, exc=e)
                LOGGER.exception("Erro ao criar banco.")
                self._update_db_state(db_path, error=str(e))  # [RB-1.1]
                show_user_error(
                    "Erro ao criar banco",
                    f"Erro ao criar banco: {str(e)}",
                    "Verifique o local de destino e permissões.",
                    parent=self,
                )

    def exportar_para_banco(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        DataStateManager = legacy.DataStateManager
        _selected_ids_from_view = legacy._selected_ids_from_view
        sort_processing_rows = legacy.sort_processing_rows
        _row_has_any_key = legacy._row_has_any_key
        _row_integrity_reasons = legacy._row_integrity_reasons
        get_row_value_by_key = legacy.get_row_value_by_key
        _row_id_value = legacy._row_id_value
        _format_processing_summary = legacy._format_processing_summary
        require_ganhos_ok_or_confirm = legacy.require_ganhos_ok_or_confirm
        is_database_busy_exception = legacy.is_database_busy_exception
        read_lock_info = legacy.read_lock_info
        get_lock_info_path = legacy.get_lock_info_path
        build_database_busy_message = legacy.build_database_busy_message

        if not self.require_state(
            "Exportar para banco", {"db": DataStateManager.CARREGADO_VALIDADO}
        ):  # [RB-RESTORE-OLD]
            return
        targets, include_aprovadas, ignoradas_aprovadas = self._gate_aprovadas_for_action(
            "Exportar para banco", self.table_obras
        )
        if not targets:
            return
        selected_ids = _selected_ids_from_view(self.table_obras)
        rows_sorted = sort_processing_rows(targets, selected_ids, include_aprovadas)
        requires_municipio = any(
            _row_has_any_key(row, ["municipio", "município"]) for row in rows_sorted
        )
        rows_valid = []
        ignoradas_integridade = 0
        integridade_counts: dict[str, int] = {}
        integridade_examples: list[str] = []
        for row in rows_sorted:
            reasons = _row_integrity_reasons(row, requires_municipio)
            if reasons:
                ignoradas_integridade += 1
                for reason in reasons:
                    integridade_counts[reason] = integridade_counts.get(reason, 0) + 1
                if len(integridade_examples) < 10:
                    cod = get_row_value_by_key(row, "cod") or _row_id_value(row)
                    integridade_examples.append(
                        f"{cod or 'N/D'}: {', '.join(reasons)}"
                    )
                continue
            rows_valid.append(row)
        if not rows_valid:
            detalhes = ""
            if integridade_counts:
                ordenadas = sorted(
                    integridade_counts.items(), key=lambda x: (-x[1], x[0])
                )
                detalhes = (
                    "\n\nMotivos (contagem):\n"
                    + "\n".join(f"- {r}: {c}" for r, c in ordenadas)
                )
            if integridade_examples:
                detalhes += "\n\nExemplos (COD: motivos):\n" + "\n".join(
                    f"- {ex}" for ex in integridade_examples
                )
            resumo = _format_processing_summary(
                "Exportar para Banco",
                0,
                ignoradas_aprovadas,
                ignoradas_integridade,
                0,
                [],
            )
            QtWidgets.QMessageBox.information(
                self, "Exportar para Banco", resumo + detalhes
            )
            return
        if not require_ganhos_ok_or_confirm(self, rows_valid, "Exportar para Banco"):
            return
        initial_dir = ""
        try:
            if self.db_manager and getattr(self.db_manager, "db_path", None):
                initial_dir = self.db_manager.get_db_dir()
        except Exception:
            initial_dir = ""
        # === FORCE DIALOG EVERY TIME (MODAL) BEGIN ===
        try:
            dlg = QtWidgets.QFileDialog(
                self, "Selecionar Banco de Dados para Exportação", initial_dir
            )
            dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptMode.AcceptSave)
            dlg.setFileMode(QtWidgets.QFileDialog.FileMode.AnyFile)
            dlg.setNameFilter("SQLite Database (*.db)")
            dlg.setDefaultSuffix("db")
            dlg.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
            dlg.setModal(True)
            dlg.raise_()
            dlg.activateWindow()

            if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
                return

            selected = dlg.selectedFiles()
            file_path = selected[0] if selected else ""
        except Exception:
            file_path = ""
        # === FORCE DIALOG EVERY TIME (MODAL) END ===

        if not file_path:
            return
        if os.path.splitext(file_path)[1].lower() != ".db":
            file_path = f"{file_path}.db"
        if not self.ensure_db_connected():
            return
        warning_schema_msg, info_msg, critical_msg = self._exportar_para_banco_write_phase(
            file_path,
            rows_valid,
            ignoradas_aprovadas,
            ignoradas_integridade,
        )

        if critical_msg:
            if is_database_busy_exception(critical_msg):
                lock_info = read_lock_info(get_lock_info_path(file_path))
                QtWidgets.QMessageBox.warning(
                    self,
                    "Banco em utilização",
                    build_database_busy_message(lock_info),
                )
            else:
                QtWidgets.QMessageBox.critical(self, "Erro", critical_msg)
            return
        if warning_schema_msg:
            QtWidgets.QMessageBox.warning(self, "Exportar para Banco", warning_schema_msg)
        if info_msg:
            titulo = "Nenhuma Obra" if info_msg.startswith("Nenhuma obra") else "Exportar para Banco"
            QtWidgets.QMessageBox.information(self, titulo, info_msg)

    def salvar_banco_dados(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        is_database_busy_exception = legacy.is_database_busy_exception
        read_lock_info = legacy.read_lock_info
        get_lock_info_path = legacy.get_lock_info_path
        build_database_busy_message = legacy.build_database_busy_message

        db_backup_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Salvar Banco de Dados", "", "SQLite Database (*.db)")
        if not db_backup_path:
            return
        if not self.ensure_db_connected():
            return
        try:
            self._save_backup_db_file(db_backup_path)
            QtWidgets.QMessageBox.information(self, "Sucesso", f"Banco de dados salvo com sucesso em: {db_backup_path}")
        except Exception as e:
            if is_database_busy_exception(e):
                lock_info = read_lock_info(get_lock_info_path(db_backup_path))
                QtWidgets.QMessageBox.warning(
                    self,
                    "Banco em utilização",
                    build_database_busy_message(lock_info),
                )
            else:
                QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao salvar banco de dados: {str(e)}")
