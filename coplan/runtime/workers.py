"""Workers Qt assincronos para escrita SQL, importacao/exportacao Excel.

Extraidos de codigo5_coplan.py:
- DBWriteWorker: roda run_sql_write_safe em thread
- ProgressRelay: pequeno relay de Signal
- ExportExcelWorker: exporta selecao para .xlsx em background
- ImportExcelWorker: importa .xlsx para o banco em background
- LongProcessWorker: stub de processo demorado (usado em demo/menu)
"""
from __future__ import annotations

import logging
import re
import sqlite3
from typing import Any, Sequence

import pandas as pd
from openpyxl import Workbook
from PySide6 import QtCore
from PySide6.QtCore import QObject, Signal, Slot

from runtime.apoio import _clean_excel_columns, read_excel_cached
from runtime.config import ORDERED_COLUMNS
from runtime.database import DatabaseManager, open_sqlite_safe, run_sql_write_safe
from runtime.dialogs import open_file

LOGGER = logging.getLogger("codigo5_coplan")


# ---------------------------------------------------------------------------
# DBWriteWorker -- escrita SQL em background
# ---------------------------------------------------------------------------
class DBWriteWorker(QObject):
    finished = Signal(bool, str)

    def __init__(
        self,
        db_path: str,
        sql: str,
        params: Sequence[Any] = (),
        *,
        action: str = "Escrita em banco",
        retries: int = 0,
    ) -> None:
        super().__init__()
        self.db_path = db_path
        self.sql = sql
        self.params = tuple(params)
        self.action = action
        self.retries = retries

    @Slot()
    def run(self) -> None:
        ok, err = run_sql_write_safe(
            self.db_path,
            self.sql,
            self.params,
            action=self.action,
            retries=self.retries,
            retry_delay_ms=500,
        )
        self.finished.emit(ok, "" if err is None else str(err))


# ---------------------------------------------------------------------------
# ProgressRelay -- relay de signal para passar progress entre threads
# ---------------------------------------------------------------------------
class ProgressRelay(QtCore.QObject):
    progress_changed = Signal(int, int, str)


# ---------------------------------------------------------------------------
# ExportExcelWorker -- exporta selecao para .xlsx em background
# ---------------------------------------------------------------------------
class ExportExcelWorker(QtCore.QObject, QtCore.QRunnable):
    export_success = Signal(str)
    export_error = Signal(str)
    export_progress = Signal(int, int, str)

    def __init__(
        self,
        db_path: str,
        file_path: str,
        selected_ids: list,
        selected_columns: list[str] | None = None,
    ):
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)
        self.db_path = db_path
        self.file_path = file_path
        self.selected_ids = selected_ids
        self.selected_columns = selected_columns

    @Slot()
    def run(self):
        conn: sqlite3.Connection | None = None
        try:
            if not self.selected_ids:
                self.export_error.emit("Nenhuma obra selecionada para exportação.")
                return
            self.export_progress.emit(0, 0, "Consultando registros para exportação...")
            conn = open_sqlite_safe(self.db_path)
            cursor = conn.cursor()

            placeholders = ", ".join(["?"] * len(self.selected_ids))
            if self.selected_columns is not None:
                cursor.execute("PRAGMA table_info(obras)")
                cols_db = [row[1] for row in cursor.fetchall()]
                valid_cols = set(cols_db)
                cols = [c for c in self.selected_columns if c in valid_cols]
                if not cols:
                    cols = cols_db
                select_cols = ", ".join(
                    ['"' + str(c).replace('"', '""') + '"' for c in cols]
                )
            else:
                cols = ORDERED_COLUMNS
                select_cols = ", ".join(
                    ['"' + str(c).replace('"', '""') + '"' for c in cols]
                )
            query = f"SELECT {select_cols} FROM obras WHERE cod IN ({placeholders})"
            cursor.execute(query, self.selected_ids)

            rows = cursor.fetchall()

            def norm(v):
                if isinstance(v, str):
                    s = v.strip()
                    if re.fullmatch(r"-?\d+\.\d+", s):
                        return s.replace(".", ",")
                return v

            cols = [desc[0] for desc in cursor.description]
            total_rows = len(rows)
            total_steps = max(total_rows + 2, 1)
            self.export_progress.emit(
                1,
                total_steps,
                f"Gerando planilha... (0/{total_rows})",
            )

            wb = Workbook()
            ws = wb.active
            if ws is None:
                ws = wb.create_sheet(title="obras")
            else:
                ws.title = "obras"
            ws.append(cols)
            for idx, row in enumerate(rows, start=1):
                ws.append([norm(v) for v in row])
                if idx == total_rows or idx % 100 == 0:
                    self.export_progress.emit(
                        idx + 1,
                        total_steps,
                        f"Gerando planilha... ({idx}/{total_rows})",
                    )

            self.export_progress.emit(total_steps, total_steps, "Salvando arquivo...")
            wb.save(self.file_path)
            self.export_progress.emit(total_steps, total_steps, "Finalizando exportação...")
            open_file(self.file_path)

            self.export_success.emit(self.file_path)
        except Exception as e:
            LOGGER.exception("Erro ao exportar Excel.")
            self.export_error.emit(str(e))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# ImportExcelWorker -- importa .xlsx para o banco em background
# ---------------------------------------------------------------------------
class ImportExcelWorker(QtCore.QObject, QtCore.QRunnable):
    import_success = Signal(str)
    import_error = Signal(str)

    def __init__(self, db_manager: DatabaseManager, file_path: str, use_cache: bool = False):
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)
        self.db_manager = db_manager
        self.file_path = file_path
        self.use_cache = use_cache

    @Slot()
    def run(self):
        try:
            if self.use_cache:
                df = read_excel_cached(self.file_path, 0, use_cache=True, dtype=str)
            else:
                df = pd.read_excel(self.file_path, dtype=str)
            df.fillna("", inplace=True)
            df, _clean_cols = _clean_excel_columns(df)

            self.db_manager.add_column_if_missing("empresa")
            self.db_manager.add_column_if_missing("cod_pep")
            self.db_manager.update_columns()

            required_cols = self.db_manager.get_column_names()
            if not set(self.db_manager.root_columns).issubset(set(df.columns)):
                raise ValueError("O arquivo Excel não possui as colunas corretas.")
            for col in df.columns:
                if col not in required_cols:
                    self.db_manager.add_column_if_missing(col)
            self.db_manager.update_columns()
            try:
                self.db_manager.backup_database(label="pre_import", min_interval_minutes=10)
            except Exception:
                LOGGER.exception("Falha ao criar backup pré-importação.")

            def import_rows():
                inserted = 0
                updated = 0
                skipped_permission = 0
                for _, row in df.iterrows():
                    dados_row = {col: row[col] for col in df.columns}
                    cod = dados_row.get("cod")
                    try:
                        if self.db_manager.fetch_by_cod(cod):
                            self.db_manager.update_obra(dados_row, cod, skip_blank=True)
                            updated += 1
                        else:
                            self.db_manager.insert_obra(dados_row)
                            inserted += 1
                    except PermissionError:
                        skipped_permission += 1
                        continue
                return inserted, updated, skipped_permission

            inserted, updated, skipped_permission = self.db_manager.run_write_transaction(import_rows)
            LOGGER.info(
                "Importação concluída. Inseridos=%s, atualizados=%s, ignorados_por_permissao=%s.",
                inserted,
                updated,
                skipped_permission,
            )
            self.db_manager.update_columns()
            refresh_cache = getattr(self.db_manager, "_refresh_cache", None)
            if callable(refresh_cache):
                refresh_cache()
            self.import_success.emit(self.file_path)
        except PermissionError as e:
            LOGGER.exception("Erro de permissão ao importar Excel.")
            self.import_error.emit(str(e))
        except Exception as e:
            LOGGER.exception("Erro ao importar Excel.")
            self.import_error.emit(str(e))


# ---------------------------------------------------------------------------
# LongProcessWorker -- stub de processo demorado (demo/menu)
# ---------------------------------------------------------------------------
class LongProcessWorker(QtCore.QObject, QtCore.QRunnable):
    """Worker de exemplo para um processo demorado em segundo plano.

    Usado em demos / menu para mostrar o fluxo de progresso. Pode ser
    adaptado para cálculos avançados, leituras de arquivos grandes, etc.
    """
    progress_signal = Signal(int)
    long_process_finished = Signal(str)

    def __init__(self, param):
        QtCore.QObject.__init__(self)
        QtCore.QRunnable.__init__(self)
        self.param = param

    @Slot()
    def run(self):
        try:
            for i in range(101):
                QtCore.QThread.msleep(20)
            self.long_process_finished.emit("Processamento concluído com sucesso!")
        except Exception as e:
            LOGGER.exception("Erro no processamento em LongProcessWorker.")
            self.long_process_finished.emit(f"Erro no processamento: {str(e)}")
