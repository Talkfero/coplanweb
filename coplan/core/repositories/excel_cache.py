"""Cache em pickle de DataFrames lidos de planilhas Excel.

Migrado do bloco ``# === EXCEL CACHE BEGIN ===`` (linhas 1431-1491) do
``codigo5_coplan.py``. Reproduz literalmente o comportamento do legado:

- Cache em arquivos ``.pkl`` (pickle) -- nao parquet, mantido por paridade.
- Chave SHA1 de ``abs_path|mtime|size`` para identificar arquivo de forma
  estavel; modificacao do arquivo invalida o cache automaticamente.
- Cache corrompido e apagado em vez de propagar excecao.
- Usa o ``logging`` padrao da stdlib (sem importar LOGGER global do codigo
  legado), com mensagens em PT-BR identicas ao legado para preservar logs.

O ``cache_dir`` e passado por parametro keyword-only em todas as funcoes
que tocam disco -- o module nao guarda estado proprio. A UI passa o
diretorio resolvido (``Path(APP_DIRS["cache"])`` no codigo5).
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

LOGGER = logging.getLogger(__name__)


def cache_key_for_file(path: str) -> str:
    """SHA1 de ``abs_path|mtime|size``.

    Identifica univocamente uma versao do arquivo: qualquer modificacao
    (renomear, mover, alterar conteudo) muda a chave.
    """
    abs_path = os.path.abspath(path)
    mtime = os.path.getmtime(abs_path)
    size = os.path.getsize(abs_path)
    raw_key = f"{abs_path}|{mtime}|{size}"
    return hashlib.sha1(raw_key.encode("utf-8")).hexdigest()


def cache_key_for_sheet(path: str, sheet_name: str | int) -> str:
    """SHA1 de ``cache_key_for_file(path)|sheet_name``.

    Cada aba de um xlsx tem chave de cache propria.
    """
    raw_key = f"{cache_key_for_file(path)}|{sheet_name}"
    return hashlib.sha1(raw_key.encode("utf-8")).hexdigest()


def _cache_path_for_key(key: str, *, cache_dir: Path) -> Path:
    """Caminho do arquivo .pkl associado a ``key`` dentro de ``cache_dir``."""
    return cache_dir / f"excel_{key}.pkl"


def cache_get_df(key: str, *, cache_dir: Path) -> Optional[pd.DataFrame]:
    """Le DataFrame do cache. Retorna ``None`` se nao existir.

    Em caso de arquivo corrompido (excecao em ``pd.read_pickle``), apaga e
    retorna ``None`` -- mesma semantica do legado.
    """
    cache_path = _cache_path_for_key(key, cache_dir=cache_dir)
    if not cache_path.exists():
        return None
    try:
        return pd.read_pickle(cache_path)
    except Exception:
        LOGGER.warning("Cache corrompido ou inv\u00e1lido. Recriando: %s", cache_path)
        try:
            cache_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def cache_set_df(key: str, df: pd.DataFrame, *, cache_dir: Path) -> None:
    """Persiste DataFrame em pickle no diretorio de cache.

    Cria o diretorio pai se nao existir.
    """
    cache_path = _cache_path_for_key(key, cache_dir=cache_dir)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(cache_path)


def read_excel_cached(
    filepath: str,
    sheet_name: str | int,
    *,
    cache_dir: Path,
    use_cache: bool = True,
    **read_excel_kwargs: Any,
) -> pd.DataFrame:
    """Le uma aba de excel, usando cache em pickle quando habilitado.

    Args:
        filepath: caminho do xlsx.
        sheet_name: nome ou indice da aba (passa para ``pd.read_excel``).
        cache_dir: diretorio onde o cache e armazenado.
        use_cache: se ``False``, ignora o cache (le e nao grava).
        **read_excel_kwargs: passados direto para ``pd.read_excel`` (dtype,
            converters, etc.).

    Mensagens de log preservadas literalmente do legado:
    "Cache HIT: %s (%s)" e "Cache MISS: %s (%s)".
    """
    if not use_cache:
        return pd.read_excel(filepath, sheet_name=sheet_name, **read_excel_kwargs)
    cache_key = cache_key_for_sheet(filepath, sheet_name)
    cached_df = cache_get_df(cache_key, cache_dir=cache_dir)
    if cached_df is not None:
        LOGGER.info("Cache HIT: %s (%s)", cache_key, filepath)
        return cached_df
    LOGGER.info("Cache MISS: %s (%s)", cache_key, filepath)
    df = pd.read_excel(filepath, sheet_name=sheet_name, **read_excel_kwargs)
    cache_set_df(cache_key, df, cache_dir=cache_dir)
    return df
