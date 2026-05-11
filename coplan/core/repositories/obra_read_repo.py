"""Repositório de leitura da tabela ``obras`` com cache em memória.

Migrado da classe ``DataAccessLayer`` (codigo5_coplan.py linha 1148, Passo
6b da separação UI/Core). Mantém a forma de chamada idêntica ao legado
para que ``DatabaseManager.fetch_all`` etc. continuem delegando como antes
— a classe é re-exportada no codigo5 com o nome legado ``DataAccessLayer``.

Este repositório é estritamente READ-ONLY: leitura de obras com cache
em memória e filtros (por pacote, projeto, cod, etc.). Operações de
escrita (insert/update/delete) seguem no ``DatabaseManager`` legado e
serão migradas em passo futuro.

Sem Qt. Usa ``open_sqlite_safe`` e ``escape_identifier`` do core.
"""
from __future__ import annotations

import datetime
import logging
import sqlite3
import time
from typing import Any, Callable, Sequence

from core.repositories.sqlite_connection import open_sqlite_safe
from core.repositories.sqlite_schema import escape_identifier

LOGGER = logging.getLogger(__name__)


class ObraReadRepo:
    """Repositório de leitura da tabela ``obras`` com cache em memória.

    Carrega todas as linhas em uma chamada (``load_cache``) e atende
    consultas subsequentes em memória. Para invalidar o cache (ex: após
    insert/update do DatabaseManager), chame ``refresh_cache``.
    """

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
        """Atualiza a lista de colunas (ex: após ALTER TABLE ADD COLUMN).

        Não invalida o cache automaticamente — chame ``refresh_cache``
        se a estrutura mudou. Mantém a semântica do legado.
        """
        self.columns = list(columns)

    def _column_index(self, name: str) -> int:
        try:
            return self.columns.index(name)
        except ValueError:
            return -1

    def _open_connection(self) -> sqlite3.Connection:
        return open_sqlite_safe(self.db_path)

    def load_cache(self) -> None:
        """Lê todas as obras do banco e popula caches em memória."""
        if not self.db_path or not self.columns:
            self._cache_rows = []
            self._cache_by_cod = {}
            self._loaded = True
            return
        sql = None
        rows: list[tuple[Any, ...]] = []
        conn: sqlite3.Connection | None = None
        cur: sqlite3.Cursor | None = None
        try:
            conn = self._open_connection()
            cur = conn.cursor()
            cols_sql = ", ".join([escape_identifier(c) for c in self.columns])
            sql = (
                f"SELECT {cols_sql} FROM obras "
                "ORDER BY ano_, nome_projeto, codigo_item"
            )
            rows = cur.execute(sql).fetchall()
        except Exception as exc:
            LOGGER.warning("Falha ao carregar cache de obras: %s", exc)
            LOGGER.debug("CACHE_SQL_ON_ERROR: %s", sql)
            rows = []
        finally:
            if conn is not None:
                conn.close()
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
        """Força recarregar o cache do banco."""
        self._loaded = False
        self.load_cache()

    def ensure_loaded(self) -> None:
        """Carrega o cache se ainda não estiver carregado.

        Reproduz o ``ts_log`` do legado para fins de profiling em produção.
        """
        t_total = time.perf_counter()
        if self._loaded:
            logging.info("[TIMESTAMP] ensure_loaded() pulado (já carregado)")
            return
        t_load = time.perf_counter()
        self.load_cache()
        elapsed = time.perf_counter() - t_load
        logging.info(f"[TIMESTAMP] _load_all_tables() levou {elapsed:.3f}s")
        elapsed_total = time.perf_counter() - t_total
        logging.info(f"[TIMESTAMP] ensure_loaded TOTAL levou {elapsed_total:.3f}s")

    def get_rows(self) -> list[list[Any]]:
        """Retorna todas as linhas do cache (sem filtro)."""
        self.ensure_loaded()
        return list(self._cache_rows)

    def _filter_pacotes(
        self, rows: list[list[Any]], pacotes: list[str] | None
    ) -> list[list[Any]]:
        if not pacotes:
            return rows
        idx = self._column_index("tipo_pacote")
        if idx < 0:
            return []
        pacotes_set = {str(p) for p in pacotes}
        return [row for row in rows if str(row[idx]) in pacotes_set]

    def get_all(self, pacotes: list[str] | None = None) -> list[list[Any]]:
        """Retorna todas as linhas, opcionalmente filtradas por pacote."""
        self.ensure_loaded()
        return self._filter_pacotes(self._cache_rows, pacotes)

    def get_by_cod(self, cod: str) -> list[Any] | None:
        """Retorna a linha pelo ``cod`` (ou None se não existe)."""
        self.ensure_loaded()
        return self._cache_by_cod.get(str(cod))

    def get_rows_by_cods(
        self,
        cods: list[str],
        pacotes: list[str] | None = None,
    ) -> list[list[Any]]:
        """Retorna linhas cujo ``cod`` está na lista informada."""
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
        """Retorna linhas que pertencem ao mesmo nome_projeto.

        Filtros adicionais opcionais: ``ano`` (compara com ``ano_``) e
        ``pacote`` (compara com ``tipo_pacote``).
        """
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
            if (
                ano is not None
                and idx_ano >= 0
                and str(row[idx_ano]).strip() != str(ano).strip()
            ):
                continue
            if (
                pacote is not None
                and idx_pacote >= 0
                and str(row[idx_pacote]).strip() != str(pacote).strip()
            ):
                continue
            results.append(row)
        return results

    def count(self, pacotes: list[str] | None = None) -> int:
        """Total de obras (filtrado por pacote se informado)."""
        return len(self.get_all(pacotes))

    def count_tecnico_dirty(self, pacotes: list[str] | None = None) -> int:
        """Total de obras com ``tecnico_dirty == "SIM"``."""
        self.ensure_loaded()
        idx_dirty = self._column_index("tecnico_dirty")
        if idx_dirty < 0:
            return 0
        rows = self.get_all(pacotes)
        return sum(1 for row in rows if str(row[idx_dirty]).strip().upper() == "SIM")

    def get_last_modification_info(
        self, pacotes: list[str] | None = None
    ) -> tuple[str | None, str | None]:
        """Retorna ``(data, usuario)`` da última modificação.

        Formato da data preservado do legado: ``%d/%m/%y %H:%M``. Retorna
        ``(None, None)`` se as colunas não existem ou não há obra com data.
        """
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

    def get_distinct_values(
        self, column_name: str, pacotes: list[str] | None = None
    ) -> list[Any]:
        """Valores únicos não-vazios de uma coluna, ordenados."""
        self.ensure_loaded()
        idx = self._column_index(column_name)
        if idx < 0:
            return []
        values = {
            row[idx] for row in self.get_all(pacotes) if row[idx] not in (None, "")
        }
        return sorted(values)
