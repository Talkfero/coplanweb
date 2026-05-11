"""Repositorio de leitura da planilha de apoio (xlsx).

Le o arquivo, identifica nomes de abas case-insensitively e valida que
existem as abas e colunas minimas requeridas. Retorna ``AbasApoio`` com
DataFrames brutos para o service processar.

A funcao ``read_excel`` e injetada como dependencia para permitir que a
UI legada passe ``read_excel_cached`` (com cache em parquet) em producao
e que os testes passem mocks/stubs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from core.exceptions import ApoioFileError


# Aliases aceitos para colunas da aba Apoio (coluna canonica -> aliases lower).
ALIASES_APOIO = {
    "alimentador": ["alimentador"],
    "projeto de investimento": ["projeto de investimento"],
    "regional": ["regional"],
    "superintendência": ["superintendência", "superintendencia"],
    "tensão": ["tensão", "tensao"],
    "se": ["se", "subestação_cod", "subestacao_cod"],
}

# Colunas obrigatorias da aba MODULO (lower-case, sem aliases).
COLUNAS_OBRIGATORIAS_MODULO = ["carac+modulo", "regional", "valor_item"]


@dataclass(frozen=True)
class AbasApoio:
    """DataFrames das abas Apoio e Modulo, ja validadas."""

    df_apoio: pd.DataFrame
    df_modulo: pd.DataFrame


def carregar_abas_apoio(
    filepath: str,
    *,
    read_excel: Callable[..., pd.DataFrame] = pd.read_excel,
) -> AbasApoio:
    """Le e valida estrutura minima do xlsx de apoio.

    Args:
        filepath: caminho do arquivo xlsx.
        read_excel: callable usado para carregar uma aba. Permite injetar
            uma versao com cache (``read_excel_cached`` do legado) ou um
            stub em testes. Default ``pd.read_excel``.

    Returns:
        ``AbasApoio`` com DataFrames das duas abas.

    Raises:
        ApoioFileError: ``codigo`` identifica o tipo de problema. Os
        textos em ``detalhes`` e ``hint`` sao identicos aos que o
        ``SupportFileManager._validate_minimum_support`` produzia.
    """
    if not os.path.isfile(filepath):
        raise ApoioFileError(
            codigo="ARQUIVO_NAO_ENCONTRADO",
            detalhes=f"Arquivo não encontrado: {filepath}",
            hint="Selecione uma planilha de apoio válida.",
        )

    try:
        xls = pd.ExcelFile(filepath)
    except Exception as exc:
        raise ApoioFileError(
            codigo="ERRO_LEITURA",
            detalhes=f"Erro ao abrir planilha: {exc}",
            hint="Verifique se o arquivo está acessível e não está corrompido.",
        ) from exc

    abas = {str(aba).lower(): aba for aba in xls.sheet_names}
    if "apoio" not in abas:
        raise ApoioFileError(
            codigo="ABA_AUSENTE_APOIO",
            detalhes="Abas ausentes: apoio.",
            hint="Inclua as abas 'Apoio' e 'MODULO' na planilha.",
        )
    if "modulo" not in abas:
        raise ApoioFileError(
            codigo="ABA_AUSENTE_MODULO",
            detalhes="Abas ausentes: modulo.",
            hint="Inclua as abas 'Apoio' e 'MODULO' na planilha.",
        )

    try:
        df_apoio = read_excel(filepath, abas["apoio"])
    except Exception as exc:
        raise ApoioFileError(
            codigo="ERRO_LEITURA",
            detalhes=f"Erro ao ler aba Apoio: {exc}",
            hint="Verifique o formato e a codificação da planilha.",
        ) from exc

    cols_apoio_lower = {str(col).lower(): col for col in df_apoio.columns}
    missing_apoio = [
        rotulo
        for rotulo, aliases in ALIASES_APOIO.items()
        if not any(alias in cols_apoio_lower for alias in aliases)
    ]
    if missing_apoio:
        raise ApoioFileError(
            codigo="COLUNAS_FALTANTES_APOIO",
            detalhes="Colunas ausentes na aba 'Apoio': " + ", ".join(missing_apoio),
            hint="Ajuste a planilha para conter as colunas mínimas exigidas.",
        )

    try:
        df_modulo = read_excel(filepath, abas["modulo"])
    except Exception as exc:
        raise ApoioFileError(
            codigo="ERRO_LEITURA",
            detalhes=f"Erro ao ler aba MODULO: {exc}",
            hint="Verifique o formato da aba MODULO e tente novamente.",
        ) from exc

    cols_modulo_lower = {str(col).lower(): col for col in df_modulo.columns}
    missing_modulo = [c for c in COLUNAS_OBRIGATORIAS_MODULO if c not in cols_modulo_lower]
    if missing_modulo:
        raise ApoioFileError(
            codigo="COLUNAS_FALTANTES_MODULO",
            detalhes="Colunas ausentes na aba 'MODULO': " + ", ".join(missing_modulo),
            hint="Ajuste a aba MODULO para conter as colunas mínimas exigidas.",
        )

    return AbasApoio(df_apoio=df_apoio, df_modulo=df_modulo)
