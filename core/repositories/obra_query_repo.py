"""Queries de leitura sobre a tabela ``obras`` (Passo 6e).

Funcoes que precisam de cursor SQLite (em contraste com
``obra_read_repo.py`` que usa cache em memoria).

Atualmente expoe ``find_duplicate``: localiza uma obra duplicada usando a
``build_dup_key`` -- por COD_OBRA quando presente, ou por
(alimentador, pi_base, ano, municipio) com tie-break por descricao
normalizada.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Optional, Sequence

from core.repositories.obra_sql_helpers import build_select_sql
from core.services.obra_rules import build_dup_key
from core.services.row_helpers import (
    find_column_name,
    first_non_empty_value,
    normalize_description,
)


def find_duplicate(
    cursor: sqlite3.Cursor,
    columns: Sequence[str],
    row: dict,
) -> Optional[dict]:
    """Localiza obra duplicada em ``obras`` baseada em ``row``.

    Reproduz literalmente ``find_duplicate_in_db`` do codigo5 (linha 782+),
    agora puro: recebe cursor e lista de colunas em vez de objeto db.

    Args:
        cursor: cursor SQLite ja aberto (transacao ativa ou nao).
        columns: lista de colunas em ordem (geralmente ``db.get_column_names()``).
        row: dict da obra candidata (vindo da UI/Excel/widget).

    Returns:
        ``dict`` com a obra duplicada (mapeando ``columns -> valores``)
        ou ``None`` se nao houver duplicata.

    Algoritmo:

    1. Calcula ``build_dup_key(row)``.
    2. Se a chave comeca com ``COD_OBRA:``, faz SELECT por ``cod``.
    3. Caso contrario, exige (alim, pi, ano) -- todos presentes em
       ``columns`` e em ``row``. Adiciona filtro por ``municipio`` se
       presente. Se houver descricao no ``row``, faz tie-break por
       descricao normalizada (case+espacos+upper).
    """
    if not columns:
        return None

    key = build_dup_key(row)
    cod_col = find_column_name(columns, ["cod"])
    if key.startswith("COD_OBRA:") and cod_col:
        cod_val = key.split(":", 1)[1]
        cursor.execute(
            build_select_sql("obras", columns, where_columns=[cod_col]),
            (cod_val,),
        )
        result = cursor.fetchone()
        return dict(zip(columns, result)) if result else None

    alim_col = find_column_name(columns, ["alimentador_principal", "alimentador"])
    pi_col = find_column_name(columns, ["pi_base", "projeto_investimento"])
    ano_col = find_column_name(columns, ["ano_", "ano"])
    if not alim_col or not pi_col or not ano_col:
        return None

    alim_val = first_non_empty_value(
        row, ["alimentador", "alimentador_principal", "circuito"]
    )
    pi_val = first_non_empty_value(
        row, ["pi_base", "pi base", "pi", "projeto_investimento"]
    )
    ano_val = first_non_empty_value(row, ["ano", "ano_", "plano"])
    if not alim_val or not pi_val or not ano_val:
        return None

    filters: list[tuple[str, Any]] = [
        (alim_col, alim_val),
        (pi_col, pi_val),
        (ano_col, ano_val),
    ]
    mun_col = find_column_name(columns, ["municipio", "munic\u00edpio"])
    municipio_val = first_non_empty_value(row, ["municipio", "munic\u00edpio"])
    if mun_col and municipio_val:
        filters.append((mun_col, municipio_val))

    where_cols = [col for col, _ in filters]
    values = [val for _, val in filters]
    cursor.execute(
        build_select_sql("obras", columns, where_columns=where_cols),
        values,
    )
    candidates = cursor.fetchall()
    if not candidates:
        return None

    desc_col = find_column_name(columns, ["descricao_obra", "descricao", "descri\u00e7\u00e3o"])
    desc_norm = normalize_description(
        first_non_empty_value(row, ["descricao_obra", "descricao", "descri\u00e7\u00e3o"])
    )
    for candidate in candidates:
        candidate_map = dict(zip(columns, candidate))
        if not desc_col:
            return candidate_map
        existing_desc = normalize_description(candidate_map.get(desc_col, ""))
        if existing_desc == desc_norm:
            return candidate_map
    return None


# ---------------------------------------------------------------------------
# Indice em memoria para deteccao de duplicidade em LOTE (import).
# ---------------------------------------------------------------------------
class DuplicateIndex:
    """Indice em memoria que espelha ``find_duplicate``, mas carrega as
    obras uma unica vez e consulta em O(1)/O(k) por linha -- em vez de 1
    SELECT por linha (O(linhas x obras)) na importacao de planilhas.

    Mesma semantica: COD_OBRA (match exato por ``cod``) ou composto
    (alim, pi, ano [+ municipio]) com tie-break por descricao normalizada.
    """

    def __init__(
        self, columns: Sequence[str], cod_col, alim_col, pi_col, ano_col,
        mun_col, desc_col,
    ) -> None:
        self._cod_col = cod_col
        self._alim_col = alim_col
        self._pi_col = pi_col
        self._ano_col = ano_col
        self._mun_col = mun_col
        self._desc_col = desc_col
        self._by_cod: dict[str, dict] = {}
        self._by_comp: dict[tuple, list[dict]] = {}

    def add(self, row_map: dict) -> None:
        if self._cod_col:
            cv = row_map.get(self._cod_col)
            if cv is not None and str(cv) != "":
                self._by_cod[str(cv)] = row_map
        if self._alim_col and self._pi_col and self._ano_col:
            key = (
                str(row_map.get(self._alim_col) or ""),
                str(row_map.get(self._pi_col) or ""),
                str(row_map.get(self._ano_col) or ""),
            )
            self._by_comp.setdefault(key, []).append(row_map)

    def find(self, row: dict) -> Optional[dict]:
        key = build_dup_key(row)
        if key.startswith("COD_OBRA:") and self._cod_col:
            cod_val = key.split(":", 1)[1]
            return self._by_cod.get(str(cod_val))
        if not (self._alim_col and self._pi_col and self._ano_col):
            return None
        alim_val = first_non_empty_value(
            row, ["alimentador", "alimentador_principal", "circuito"])
        pi_val = first_non_empty_value(
            row, ["pi_base", "pi base", "pi", "projeto_investimento"])
        ano_val = first_non_empty_value(row, ["ano", "ano_", "plano"])
        if not alim_val or not pi_val or not ano_val:
            return None
        candidates = self._by_comp.get(
            (str(alim_val), str(pi_val), str(ano_val)))
        if not candidates:
            return None
        mun_val = first_non_empty_value(row, ["municipio", "município"])
        if self._mun_col and mun_val:
            candidates = [
                c for c in candidates
                if str(c.get(self._mun_col) or "") == str(mun_val)
            ]
            if not candidates:
                return None
        if not self._desc_col:
            return candidates[0]
        desc_norm = normalize_description(first_non_empty_value(
            row, ["descricao_obra", "descricao", "descrição"]))
        for c in candidates:
            if normalize_description(c.get(self._desc_col, "")) == desc_norm:
                return c
        return None


def build_duplicate_index(
    cursor: sqlite3.Cursor, columns: Sequence[str],
) -> DuplicateIndex:
    """Carrega todas as obras 1x e devolve um ``DuplicateIndex`` pronto
    para consultas em lote. Use no lugar de chamar ``find_duplicate`` por
    linha quando ha muitas linhas (ex.: importacao de planilha)."""
    cols = list(columns or [])
    idx = DuplicateIndex(
        cols,
        find_column_name(cols, ["cod"]),
        find_column_name(cols, ["alimentador_principal", "alimentador"]),
        find_column_name(cols, ["pi_base", "projeto_investimento"]),
        find_column_name(cols, ["ano_", "ano"]),
        find_column_name(cols, ["municipio", "município"]),
        find_column_name(cols, ["descricao_obra", "descricao", "descrição"]),
    )
    if not cols:
        return idx
    cursor.execute(build_select_sql("obras", cols))
    for row in cursor.fetchall():
        idx.add(dict(zip(cols, row)))
    return idx


# ---------------------------------------------------------------------------
# Variante que levanta ObraDuplicadaError (Passo 7)
# ---------------------------------------------------------------------------
from core.exceptions import ObraDuplicadaError
from core.services.obra_rules import build_dup_key as _build_dup_key


def find_duplicate_or_raise(
    cursor: sqlite3.Cursor,
    columns: Sequence[str],
    row: dict,
) -> None:
    """Variante de ``find_duplicate`` que levanta excecao em caso de match.

    Raises:
        ObraDuplicadaError: com ``duplicate`` (dict da obra ja existente)
            e ``chave`` (``"COD_OBRA:X"`` ou ``"COMP:..."``).

    Retorna ``None`` (silencioso) quando NAO ha duplicata.
    """
    duplicate = find_duplicate(cursor, columns, row)
    if duplicate is None:
        return
    chave = _build_dup_key(row)
    raise ObraDuplicadaError(duplicate, chave)

