"""Mixin Importar Excel -- 6 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 3).
"""
from __future__ import annotations

import datetime
import os
import re

import pandas as pd
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Slot


class ImportarExcelMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    @Slot(str)
    def on_import_success(self, file_path: str):
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        QtWidgets.QMessageBox.information(
            self,
            "Sucesso",
            f"Dados importados com sucesso do arquivo: {file_path}",
        )
        self.db_manager.update_columns()
        self._set_data_state(
            "db",
            DataStateManager.CARREGADO_VALIDADO,
            path=self.db_manager.db_path or "",
            version_token=self._compute_file_token(self.db_manager.db_path or ""),
        )
        self.load_obras_into_table()

    @Slot(str)
    def on_import_error(self, error_msg: str):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        LOGGER = legacy.LOGGER
        show_user_error = legacy.show_user_error
        DataStateManager = legacy.DataStateManager

        LOGGER.error("Erro na importação: %s", error_msg)
        show_user_error(
            "Erro na importação",
            error_msg,
            "Revise o arquivo e tente novamente.",
            parent=self,
        )
        self._set_data_state(
            "db",
            DataStateManager.CARREGADO_VALIDADO,
            path=self.db_manager.db_path or "",
            version_token=self._compute_file_token(self.db_manager.db_path or ""),
        )

    @Slot(str)
    def on_long_process_finished(self, message: str):
        QtWidgets.QMessageBox.information(self, "Processo", message)

    def _prompt_duplicate_action(self, duplicate: dict, row: dict) -> str:
        from ui.main_window import legacy_module
        build_dup_key = legacy_module().build_dup_key

        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Possível duplicidade")
        msg_box.setText("Já existe um registro semelhante no banco de dados.")
        info_lines = []
        dup_cod = duplicate.get("cod") if duplicate else None
        if dup_cod:
            info_lines.append(f"COD existente: {dup_cod}")
        dup_key = build_dup_key(row)
        if dup_key:
            info_lines.append(f"Chave detectada: {dup_key}")
        if info_lines:
            msg_box.setInformativeText("\n".join(info_lines))

        merge_btn = msg_box.addButton(
            "Mesclar/Atualizar existente",
            QtWidgets.QMessageBox.ButtonRole.AcceptRole,
        )
        create_btn = msg_box.addButton(
            "Criar nova mesmo assim",
            QtWidgets.QMessageBox.ButtonRole.ActionRole,
        )
        cancel_btn = msg_box.addButton(
            "Cancelar",
            QtWidgets.QMessageBox.ButtonRole.RejectRole,
        )
        msg_box.setDefaultButton(merge_btn)
        msg_box.setEscapeButton(cancel_btn)
        msg_box.exec()
        clicked = msg_box.clickedButton()
        if clicked == merge_btn:
            return "merge"
        if clicked == create_btn:
            return "create"
        return "cancel"

    def _merge_duplicate_record(self, duplicate: dict, row: dict) -> bool:
        from ui.main_window import legacy_module
        legacy = legacy_module()
        normalize_text = legacy.normalize_text
        cod_pep = legacy.cod_pep

        if not duplicate:
            return False
        cod = str(duplicate.get("cod") or "").strip()
        if not cod:
            return False

        updates = self.db_manager.build_merge_updates(duplicate, row) or {}
        row_data = row if isinstance(row, dict) else {}

        # EMPRESA: prioriza valor do Excel; se não vier, usa configuração atual.
        empresa_excel = row_data.get("empresa")
        empresa_nova = normalize_text(empresa_excel)
        if not empresa_nova:
            empresa_nova = self.db_manager.get_empresa_sigla_from_config()

        if empresa_nova:
            empresa_atual = normalize_text(duplicate.get("empresa"))
            if empresa_atual != empresa_nova:
                updates["empresa"] = empresa_nova

        # COD_PEP: prioriza Excel; se não vier, recalcula com as regras atuais.
        cod_pep_excel = row_data.get("cod_pep")
        cod_pep_novo = str(cod_pep_excel or "").strip()
        if not cod_pep_novo and empresa_nova:
            obra_calc = dict(duplicate)
            for key, value in row_data.items():
                if not self.db_manager._is_missing(value):
                    obra_calc[key] = value
            obra_calc["empresa"] = empresa_nova
            cod_pep_novo = str(cod_pep(self.db_manager, obra_calc, empresa_nova) or "").strip()

        if cod_pep_novo:
            cod_pep_atual = str(duplicate.get("cod_pep") or "").strip()
            if cod_pep_atual != cod_pep_novo:
                updates["cod_pep"] = cod_pep_novo

        if not updates:
            return False
        self.db_manager.update_obra(updates, cod, skip_blank=True)
        return True

    def import_from_excel(self):
        from ui.main_window import legacy_module
        legacy = legacy_module()
        DataStateManager = legacy.DataStateManager
        _clean_excel_columns = legacy._clean_excel_columns
        show_user_error = legacy.show_user_error
        find_duplicate_in_db = legacy.find_duplicate_in_db
        LOGGER = legacy.LOGGER

        if not self.require_state(
            "Importar Excel", {"db": DataStateManager.CARREGADO_VALIDADO}
        ):  # [RB-1.1]
            return
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Importar do Excel", "", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        progress: QtWidgets.QProgressDialog | None = QtWidgets.QProgressDialog(
            "Lendo arquivo Excel...",
            "Cancelar",
            0,
            0,
            self,
        )
        progress.setWindowTitle("Importação em andamento")
        progress.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        progress.show()
        QtWidgets.QApplication.processEvents(
            QtCore.QEventLoop.ProcessEventsFlag.AllEvents
        )
        try:
            df = pd.read_excel(file_path, dtype=str)
            df.fillna("", inplace=True)
            df, _clean_cols = _clean_excel_columns(df)

            # Garante as colunas PEP no schema mesmo quando o Excel não as traz.
            self.db_manager.add_column_if_missing("empresa")
            self.db_manager.add_column_if_missing("cod_pep")
            self.db_manager.update_columns()

            required_cols = self.db_manager.get_column_names()
            # Verifica se todas as colunas "raiz" estão presentes
            if not set(self.db_manager.root_columns).issubset(set(df.columns)):
                show_user_error(
                    "Erro na importação",
                    "O arquivo Excel não possui as colunas corretas.",
                    "Verifique se o arquivo foi exportado pelo sistema.",
                    parent=self,
                )
                return

            # Inclui automaticamente novas colunas presentes no Excel
            for col in df.columns:
                if col not in required_cols:
                    self.db_manager.add_column_if_missing(col)
            self.db_manager.update_columns()

            ignorados = 0
            error_log: list[str] = []
            total_linhas = len(df.index)
            cancelado = False

            progress.setRange(0, max(total_linhas, 1))
            progress.setLabelText(
                f"Importando registros... (0/{total_linhas})"
            )
            progress.setValue(0)
            QtWidgets.QApplication.processEvents(
                QtCore.QEventLoop.ProcessEventsFlag.AllEvents
            )

            for linha_excel, (_idx, row) in enumerate(df.iterrows(), start=2):
                if progress.wasCanceled():
                    cancelado = True
                    break
                processadas = min(linha_excel - 2, total_linhas)
                progress.setValue(processadas)
                progress.setLabelText(
                    f"Importando registros... ({processadas}/{total_linhas})"
                )
                QtWidgets.QApplication.processEvents(
                    QtCore.QEventLoop.ProcessEventsFlag.AllEvents
                )
                dados_row = {col: row[col] for col in df.columns}
                alim = str(dados_row.get("alimentador_principal", "") or "")
                benef = str(dados_row.get("alimentadores_beneficiados", "") or "")
                cod = dados_row.get("cod", "")

                # Regra de sublinhado (mesma ideia do salvar individual)
                if "_" in alim or any("_" in b for b in re.split(r'[,;|\n]+', benef)):
                    ignorados += 1
                    error_log.append(
                        f"Linha {linha_excel} (cod={cod}): "
                        f"Ignorado — alimentador_principal/beneficiados contém sublinhado (_)."
                    )
                    continue

                try:
                    # Aqui entram todas as regras internas de insert/update:
                    # - _apply_novo_bay_rules
                    # - allowed_pacotes / PermissionError
                    # - normalização de decimais, etc.
                    duplicate = find_duplicate_in_db(self.db_manager, dados_row)
                    if duplicate:
                        merged = self._merge_duplicate_record(duplicate, dados_row)
                        if not merged:
                            ignorados += 1
                            error_log.append(
                                f"Linha {linha_excel} (cod={cod}): "
                                "Duplicidade detectada, mas sem atualizações aplicáveis."
                            )
                        continue
                    self.db_manager.insert_obra(dados_row)

                except PermissionError as e:
                    ignorados += 1
                    error_log.append(
                        f"Linha {linha_excel} (cod={cod}): "
                        f"Permissão negada (pacote não permitido ou regra de acesso). Detalhes: {e}"
                    )
                    continue

                except Exception as e:
                    ignorados += 1
                    error_log.append(
                        f"Linha {linha_excel} (cod={cod}): "
                        f"Erro ao importar registro. Detalhes: {repr(e)}"
                    )
                    continue

            # Gera arquivo de log se houver erros
            log_path = None
            if error_log:
                base, _ext = os.path.splitext(file_path)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                log_path = f"{base}_log_importacao_{timestamp}.txt"
                try:
                    with open(log_path, "w", encoding="utf-8") as f:
                        f.write("LOG DE ERROS DE IMPORTAÇÃO\n")
                        f.write(f"Arquivo de origem: {file_path}\n")
                        f.write(
                            "Data/Hora: "
                            f"{datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                        )
                        for line in error_log:
                            f.write(line + "\n")
                except Exception as e:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Aviso",
                        "Ocorreram erros na importação e o log não pôde ser salvo.\n"
                        f"Detalhes: {e}",
                    )

            self.db_manager.update_columns()
            refresh_cache = getattr(self.db_manager, "_refresh_cache", None)
            if callable(refresh_cache):
                refresh_cache()

            if progress is not None:
                progress.setValue(max(total_linhas, 1))
                progress.close()

            msg = "Dados importados e atualizados com sucesso!"
            if cancelado:
                msg = "Importação cancelada pelo usuário."
            if ignorados:
                msg += f" {ignorados} registros ignorados (ver log)."
            if log_path:
                msg += f"\nUm log de erros foi salvo em:\n{log_path}"

            QtWidgets.QMessageBox.information(self, "Sucesso", msg)
            self.load_obras_into_table()

        except PermissionError as e:
            if progress is not None:
                progress.close()
            LOGGER.exception("Erro de permissão na importação.")
            show_user_error(
                "Erro de permissão",
                str(e),
                "Verifique os pacotes permitidos e tente novamente.",
                parent=self,
            )
        except Exception as e:
            if progress is not None:
                progress.close()
            LOGGER.exception("Erro na importação.")
            show_user_error(
                "Erro na importação",
                f"Erro na importação: {str(e)}",
                "Verifique o arquivo e tente novamente.",
                parent=self,
            )
