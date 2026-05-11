"""Funcoes puras de leitura/escrita de schema SQLite.

Migrado de varios metodos do ``DatabaseManager`` no ``codigo5_coplan.py``
(Passo 6a da separacao UI/Core). As funcoes aqui sao **stateless** e
recebem ``cursor`` ja aberto -- a UI continua gerenciando lifecycle de
conexao via ``DatabaseManager``.

Nenhum metodo eleva excecao por silenciar erros de leitura (decisao para
preservar paridade com o legado, que faz fallback para defaults). A UI
loga quando achar relevante.
"""
from __future__ import annotations

import sqlite3
from typing import Sequence


def escape_identifier(name: str) -> str:
    """Reproduz ``DatabaseManager._escape_identifier``.

    Envolve o nome em aspas duplas e duplica aspas internas, conforme a
    convencao SQLite para identificadores quotados.
    """
    return '"' + str(name).replace('"', '""') + '"'


def list_table_columns(cursor: sqlite3.Cursor, table_name: str = "obras") -> list[str]:
    """Retorna a lista de colunas de uma tabela na ordem em que aparecem.

    Usa ``PRAGMA table_info(<tabela>)``. Se a tabela nao existe, SQLite
    retorna lista vazia (e nao excecao) -- preservamos esse comportamento
    de retornar ``[]`` para alinhamento com o legado, que tambem caia em
    ``except Exception`` retornando lista vazia.
    """
    try:
        cursor.execute(f"PRAGMA table_info({escape_identifier(table_name)})")
        info = cursor.fetchall()
    except Exception:
        return []
    return [str(col[1]) for col in info]


def create_meta_table_if_needed(cursor: sqlite3.Cursor) -> None:
    """Cria a tabela ``meta`` (chave/valor) se nao existir.

    Schema identico ao legado:
    ``CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)``.
    """
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS meta ("
        "key TEXT PRIMARY KEY, "
        "value TEXT"
        ")"
    )


def read_schema_version(
    cursor: sqlite3.Cursor, key: str = "schema_version"
) -> int:
    """Le a versao do schema da tabela ``meta``.

    Retorna ``0`` em qualquer cenario problematico (chave ausente, valor
    nulo, valor nao numerico, erro de SQL). Preserva o fallback do legado
    que tambem garante 0 com try/except. A UI faz logging do erro real.
    """
    try:
        cursor.execute("SELECT value FROM meta WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row or row[0] is None:
            return 0
        return int(row[0])
    except Exception:
        return 0


def write_schema_version(
    cursor: sqlite3.Cursor, version: int, key: str = "schema_version"
) -> None:
    """Insere/atualiza versao na tabela ``meta`` via ``ON CONFLICT``.

    Reproduz literalmente:
    ``INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value``.
    """
    cursor.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(version)),
    )


def rename_column_if_needed(
    cursor: sqlite3.Cursor,
    table: str,
    old: str,
    new: str,
) -> bool:
    """Renomeia coluna ``old`` para ``new`` se ``old`` existe e ``new`` nao.

    Retorna ``True`` se mudou. ``False`` se ``old`` ausente ou ``new`` ja
    presente (no-op idempotente). Reproduz a logica de
    ``DatabaseManager.migrate_0_to_1``.
    """
    cols = list_table_columns(cursor, table)
    if old not in cols:
        return False
    if new in cols:
        return False
    cursor.execute(
        f"ALTER TABLE {escape_identifier(table)} "
        f"RENAME COLUMN {escape_identifier(old)} TO {escape_identifier(new)}"
    )
    return True


def compute_ordered_columns(
    existing: Sequence[str],
    ordered_template: Sequence[str],
) -> list[str]:
    """Reordena colunas: primeiro as do ``ordered_template`` (na ordem dele)
    e depois as colunas extras do ``existing`` (na ordem em que aparecem).

    Reproduz exatamente a logica de ``DatabaseManager.update_columns``:

        ordered = [c for c in ORDERED_COLUMNS if c in existing]
        for c in existing:
            if c not in ordered:
                ordered.append(c)
    """
    existing_set = set(existing)
    ordered: list[str] = [c for c in ordered_template if c in existing_set]
    seen = set(ordered)
    for c in existing:
        if c not in seen:
            ordered.append(c)
            seen.add(c)
    return ordered
