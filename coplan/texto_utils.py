"""Utilitarios de normalizacao de texto e mapas regionais.

Recuperado de ``partes/parte_02_texto_e_cod_pep.py``. Contem apenas a parte
livre de UI e de banco: as funcoes complexas (``cod_pep``, ``parse_cod_pep``,
``get_empresa_sigla_from_config``) permanecem no ``codigo5_coplan.py``
porque dependem de ``db``, ``ConfigManager``, ``LOGGER`` e outras
dependencias.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Sequence


def normalize_key(text: Any) -> str:
    """Normaliza texto removendo acentos e convertendo para maiusculas."""
    text = str(text or "")
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ASCII", "ignore").decode("ASCII").upper()


def _compact_key(text: Any) -> str:
    """Normaliza e remove separadores para comparacao tolerante."""
    return "".join(ch for ch in normalize_key(text) if ch.isalnum())


def normalize_text(s: Any) -> str:
    """Normaliza texto removendo acento, trim/upper e compactando espacos."""
    normalized = normalize_key(str(s or ""))
    return re.sub(r"\s+", " ", normalized).strip()


EMPRESA_SIGLAS_VALIDAS = {"MA", "PA", "PI", "AL", "RS", "AP", "GO"}

REGIONAL_TO_COD_RAW = {
    "NORTE": "NOR",
    "NORDESTE": "NDE",
    "NOROESTE": "NRO",
    "CENTRO": "CEN",
    "LESTE": "LES",
    "OESTE": "OES",
    "SUL": "SUL",
    "PARNAÍBA": "PAR",
    "PICOS": "PIC",
    "FLORIANO": "FLO",
    "METROPOLITANA": "MET",
    "INTERIOR": "INT",
    "FORMOSA": "FOR",
    "GOIÂNIA": "GOI",
    "ANÁPOLIS": "ANA",
    "IPORÁ": "IPO",
    "LUZIÂNIA": "LUZ",
    "MONTES BELOS": "MBL",
    "MORRINHOS": "MOR",
    "RIO VERDE": "RIV",
    "URUAÇU": "URU",
}
REGIONAL_TO_COD = {
    re.sub(r"\s+", " ", normalize_key(k)).strip(): v
    for k, v in REGIONAL_TO_COD_RAW.items()
}
