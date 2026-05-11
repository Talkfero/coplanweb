# -*- coding: utf-8 -*-
import datetime
import logging
import sqlite3
from typing import Any, Callable, Sequence

LOGGER = logging.getLogger(__name__)


class DataAccessLayer:
    def __init__(
        self,
        db_path: str,
        columns: list[str],
        normalize_row: Callable[[Sequence[Any]], list[Any]],
    ) -> None:
        self.db_path = db_path
        self.columns = list(columns)
        self._normalize_row = normalize_row
        self._cache_rows: list[list[Any]] = []
        self._cache_by_cod: dict[str, list[Any]] = {}
        self._loaded = False

    def set_columns(self, columns: list[str]) -> None:
        self.columns = list(columns)

    def _column_index(self, name: str) -> int:
        try:
            return self.columns.index(name)
        except ValueError:
            return -1

    def _open_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(
            self.db_path,
            timeout=15,
            check_same_thread=False,
            isolation_level=None,
        )

    def load_cache(self) -> None:
        if not self.db_path or not self.columns:
            self._cache_rows = []
            self._cache_by_cod = {}
            self._loaded = True
            return
        cols = ", ".join(self.columns)
        sql = f"SELECT {cols} FROM obras ORDER BY ano_, nome_projeto, codigo_item"
        try:
            conn = self._open_connection()
            try:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()
            finally:
                conn.close()
        except Exception as exc:
            LOGGER.warning("Falha ao carregar cache de obras: %s", exc)
            rows = []
        normalized = [self._normalize_row(row) for row in rows]
        self._cache_rows = normalized
        cod_idx = self._column_index("cod")
        if cod_idx >= 0:
            self._cache_by_cod = {
                str(row[cod_idx]): row
                for row in normalized
                if row[cod_idx] is not None
            }
        else:
            self._cache_by_cod = {}
        self._loaded = True

    def refresh_cache(self) -> None:
        self._loaded = False
        self.load_cache()

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load_cache()

    def get_rows(self) -> list[list[Any]]:
        self.ensure_loaded()
        return list(self._cache_rows)

    def _filter_pacotes(self, rows: list[list[Any]], pacotes: list[str] | None) -> list[list[Any]]:
        if not pacotes:
            return rows
        idx = self._column_index("tipo_pacote")
        if idx < 0:
            return []
        pacotes_set = {str(p) for p in pacotes}
        return [row for row in rows if str(row[idx]) in pacotes_set]

    def get_all(self, pacotes: list[str] | None = None) -> list[list[Any]]:
        self.ensure_loaded()
        return self._filter_pacotes(self._cache_rows, pacotes)

    def get_by_cod(self, cod: str) -> list[Any] | None:
        self.ensure_loaded()
        return self._cache_by_cod.get(str(cod))

    def get_rows_by_cods(
        self,
        cods: list[str],
        pacotes: list[str] | None = None,
    ) -> list[list[Any]]:
        if not cods:
            return []
        self.ensure_loaded()
        idx_cod = self._column_index("cod")
        if idx_cod < 0:
            return []
        cods_set = {str(cod) for cod in cods}
        rows = [row for row in self._cache_rows if str(row[idx_cod]) in cods_set]
        return self._filter_pacotes(rows, pacotes)

    def get_rows_by_project(
        self,
        nome_projeto: str,
        ano: str | None = None,
        pacote: str | None = None,
    ) -> list[list[Any]]:
        self.ensure_loaded()
        idx_nome = self._column_index("nome_projeto")
        if idx_nome < 0:
            return []
        idx_ano = self._column_index("ano_")
        idx_pacote = self._column_index("tipo_pacote")
        nome_norm = str(nome_projeto).strip()
        results = []
        for row in self._cache_rows:
            if str(row[idx_nome]).strip() != nome_norm:
                continue
            if ano is not None and idx_ano >= 0 and str(row[idx_ano]).strip() != str(ano).strip():
                continue
            if pacote is not None and idx_pacote >= 0 and str(row[idx_pacote]).strip() != str(pacote).strip():
                continue
            results.append(row)
        return results

    def count(self, pacotes: list[str] | None = None) -> int:
        return len(self.get_all(pacotes))

    def count_tecnico_dirty(self, pacotes: list[str] | None = None) -> int:
        self.ensure_loaded()
        idx_dirty = self._column_index("tecnico_dirty")
        if idx_dirty < 0:
            return 0
        rows = self.get_all(pacotes)
        return sum(1 for row in rows if str(row[idx_dirty]).strip().upper() == "SIM")

    def get_last_modification_info(self, pacotes: list[str] | None = None) -> tuple[str | None, str | None]:
        self.ensure_loaded()
        idx_data = self._column_index("data_modificacao")
        idx_user = self._column_index("modificado_por")
        if idx_data < 0 or idx_user < 0:
            return None, None
        last_dt = None
        last_user = ""
        for row in self.get_all(pacotes):
            data_str = row[idx_data]
            if not data_str:
                continue
            try:
                dt = datetime.datetime.strptime(data_str, "%d/%m/%y %H:%M")
            except Exception:
                continue
            if not last_dt or dt > last_dt:
                last_dt = dt
                last_user = row[idx_user]
        if last_dt:
            return last_dt.strftime("%d/%m/%y %H:%M"), last_user
        return None, None

    def get_distinct_values(self, column_name: str, pacotes: list[str] | None = None) -> list[Any]:
        self.ensure_loaded()
        idx = self._column_index(column_name)
        if idx < 0:
            return []
        values = {row[idx] for row in self.get_all(pacotes) if row[idx] not in (None, "")}
        return sorted(values)
