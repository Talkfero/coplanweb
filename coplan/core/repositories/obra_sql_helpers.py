"""Builders de SQL para a tabela ``obras`` (Passo 6c).

Funcoes puras que constroem strings SQL com placeholders ``?``. Sem
cursor, sem state, sem Qt. Os identificadores de colunas/tabela sao
escapados via ``escape_identifier`` do core para suportar nomes com
espacos, acentos, hifens, etc.

Reproduz literalmente os patterns construidos inline em
``DatabaseManager.insert_obra``, ``update_obra``, ``delete_obra`` e
``find_duplicate_in_db`` do ``codigo5_coplan.py``.
"""
from __future__ import annotations

from typing import Sequence

from core.repositories.sqlite_schema import escape_identifier


def build_insert_sql(table: str, columns: Sequence[str]) -> str:
    """``INSERT INTO {table} ({cols escaped}) VALUES (?, ?, ...)``.

    Args:
        table: nome da tabela (sera escapado).
        columns: lista de colunas (cada uma escapada).

    Raises:
        ValueError: se ``columns`` estiver vazia (INSERT sem colunas e
            invalido em SQLite).
    """
    if not columns:
        raise ValueError("INSERT exige ao menos uma coluna.")
    cols_sql = ", ".join(escape_identifier(c) for c in columns)
    placeholders = ", ".join(["?"] * len(columns))
    return f"INSERT INTO {escape_identifier(table)} ({cols_sql}) VALUES ({placeholders})"


def build_update_sql(
    table: str,
    set_columns: Sequence[str],
    where_columns: Sequence[str],
) -> str:
    """``UPDATE {table} SET col1=?, col2=?, ... WHERE col=? AND ...``.

    Args:
        table: nome da tabela.
        set_columns: colunas a atualizar (cada uma vira ``col=?``).
        where_columns: colunas usadas no WHERE (combinadas via AND).

    Raises:
        ValueError: se ``set_columns`` ou ``where_columns`` estiverem
            vazias. UPDATE sem WHERE e perigoso (atualiza todas as linhas)
            -- preferimos travar.
    """
    if not set_columns:
        raise ValueError("UPDATE exige ao menos uma coluna em SET.")
    if not where_columns:
        raise ValueError(
            "UPDATE exige ao menos uma coluna no WHERE para evitar "
            "atualizacoes em massa acidentais."
        )
    set_sql = ", ".join(f"{escape_identifier(c)} = ?" for c in set_columns)
    where_sql = " AND ".join(f"{escape_identifier(c)} = ?" for c in where_columns)
    return f"UPDATE {escape_identifier(table)} SET {set_sql} WHERE {where_sql}"


def build_delete_sql(table: str, where_columns: Sequence[str]) -> str:
    """``DELETE FROM {table} WHERE col=? AND ...``.

    Raises:
        ValueError: se ``where_columns`` estiver vazia (DELETE sem WHERE
            apaga toda a tabela; preferimos travar).
    """
    if not where_columns:
        raise ValueError(
            "DELETE exige ao menos uma coluna no WHERE para evitar "
            "apagar toda a tabela."
        )
    where_sql = " AND ".join(f"{escape_identifier(c)} = ?" for c in where_columns)
    return f"DELETE FROM {escape_identifier(table)} WHERE {where_sql}"


def build_select_sql(
    table: str,
    columns: Sequence[str],
    where_columns: Sequence[str] = (),
    order_by: Sequence[str] = (),
) -> str:
    """``SELECT cols FROM {table} [WHERE ...] [ORDER BY ...]``.

    Args:
        table: nome da tabela.
        columns: colunas a retornar (escapadas). Se vazia, usa ``*``.
        where_columns: colunas de filtro (vira ``col=? AND ...``). Vazia
            -> sem WHERE.
        order_by: colunas para ORDER BY na ordem fornecida. Vazia -> sem
            ORDER BY.

    Reproduz o padrao usado em ``find_duplicate_in_db`` (codigo5 linhas
    893-927) e ``ObraReadRepo.load_cache``.
    """
    if columns:
        cols_sql = ", ".join(escape_identifier(c) for c in columns)
    else:
        cols_sql = "*"
    sql = f"SELECT {cols_sql} FROM {escape_identifier(table)}"
    if where_columns:
        where_sql = " AND ".join(
            f"{escape_identifier(c)} = ?" for c in where_columns
        )
        sql += f" WHERE {where_sql}"
    if order_by:
        order_sql = ", ".join(escape_identifier(c) for c in order_by)
        sql += f" ORDER BY {order_sql}"
    return sql
