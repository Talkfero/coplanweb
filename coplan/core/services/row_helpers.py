"""Utilitarios genericos de leitura/normalizacao de linhas (dicts) e strings.

Migrado de funcoes top-level do ``codigo5_coplan.py`` (Passo 6d). Sem
dominio especifico de obra -- apenas helpers reutilizaveis para fazer
leituras tolerantes em dicts vindos de widgets/Excel/banco.

Nenhuma das funcoes consulta UI, banco ou config. Sao puras.
"""
from __future__ import annotations

from typing import Any, Sequence

from texto_utils import _compact_key, normalize_key


def normalize_description(text: Any) -> str:
    """Normaliza descricao: upper + colapso de espacos.

    Reproduz ``_normalize_description`` do codigo5.
    """
    return " ".join(str(text or "").strip().upper().split())


def find_column_name(
    columns: Sequence[str], candidates: Sequence[str]
) -> str | None:
    """Procura a primeira coluna em ``columns`` cujo nome normalizado
    coincida com algum dos ``candidates``. Tolerante a case e acento.

    Reproduz ``_find_column_name`` do codigo5.
    """
    normalized_cols = {normalize_key(col): col for col in columns}
    for candidate in candidates:
        match = normalized_cols.get(normalize_key(candidate))
        if match:
            return match
    return None


def get_row_value_by_key(row: dict, key: str) -> str:
    """Busca o valor de ``key`` em ``row`` ignorando case/separador.

    Reproduz ``get_row_value_by_key`` do codigo5: compara chaves via
    ``normalize_key`` e ``_compact_key`` (remove separadores).
    """
    key_norm = normalize_key(key)
    key_compact = _compact_key(key)
    for col, value in row.items():
        col_norm = normalize_key(col)
        if col_norm == key_norm or _compact_key(col) == key_compact:
            return str(value or "").strip()
    return ""


def row_has_any_key(row: dict, keys: Sequence[str]) -> bool:
    """``True`` se ``row`` tem alguma das ``keys`` (tolerante a case/separador).

    Reproduz ``_row_has_any_key`` do codigo5.
    """
    normalized = {normalize_key(key) for key in keys}
    compacted = {_compact_key(key) for key in keys}
    for col in row.keys():
        col_norm = normalize_key(col)
        if col_norm in normalized:
            return True
        if _compact_key(col) in compacted:
            return True
    return False


def first_non_empty_value(row: dict, keys: Sequence[str]) -> str:
    """Retorna o primeiro valor nao vazio em ``row`` para qualquer das ``keys``.

    Reproduz ``_first_non_empty_value`` do codigo5.
    """
    for key in keys:
        value = get_row_value_by_key(row, key)
        if str(value).strip():
            return str(value).strip()
    return ""


def expand_key_variants(keys: Sequence[str]) -> list[str]:
    """Expande variantes de chave: cada chave + versao com ``_`` -> ``" "``.

    Reproduz ``_expand_key_variants`` do codigo5. Util para tolerar formato
    em snake_case e em "human form".
    """
    variants: list[str] = []
    for key in keys:
        key_str = str(key)
        variants.append(key_str)
        variants.append(key_str.replace("_", " "))
    return list(dict.fromkeys(variants))


def has_any_value(row: dict, keys: Sequence[str]) -> bool:
    """``True`` se alguma chave de ``keys`` (ou suas variantes) tem valor nao vazio.

    Reproduz ``_has_any_value`` do codigo5.
    """
    for key in expand_key_variants(keys):
        if str(get_row_value_by_key(row, key)).strip():
            return True
    return False


def parse_float_brl(value: Any) -> float | None:
    """Converte string para float aceitando virgula decimal pt-BR.

    Retorna ``None`` se vazio ou nao parseavel. Reproduz ``_parse_float`` do
    codigo5 (versao top-level).
    """
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None
