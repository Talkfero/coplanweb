"""Service de processamento da planilha de apoio.

Recebe os DataFrames validados pelo ``apoio_repo`` e produz um
``DadosApoio`` tipado (alimentadores, projetos, caracteristicas, nomes de
projeto, dados-por-alimentador e modulos por chave composta).

Reproduz a logica de ``SupportFileManager.load_support_file`` do legado:

- Listas extraidas via ``dropna() + strip()``.
- ``nomes_projetos`` filtra strings vazias.
- ``dados_alimentador`` itera **todas** as linhas (sem dropna), aplicando
  ``str(row[col]).strip()`` na chave -- mesmo comportamento do legado,
  inclusive eventuais chaves vazias ou ``"nan"`` resultantes de NaN.
- ``modulos`` constroi a chave_completa como ``f"{carac.upper().replace('-', '_')}_{regional.upper()}"``.
- ``valor_item`` invalido (texto nao numerico) vira 0.0, igual ao legado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List

import pandas as pd

from core.exceptions import ApoioFileError
from core.models import DadosAlimentador, ModuloValor
from core.repositories.apoio_repo import carregar_abas_apoio


@dataclass
class DadosApoio:
    """Dados normalizados extraidos da planilha de apoio."""

    alimentadores: List[str] = field(default_factory=list)
    projetos_investimento: List[str] = field(default_factory=list)
    caracteristicas: List[str] = field(default_factory=list)
    nomes_projetos: List[str] = field(default_factory=list)
    dados_alimentador: Dict[str, DadosAlimentador] = field(default_factory=dict)
    # Chave do dict ``modulos`` e a "chave_completa" (CARAC_REGIONAL,
    # uppercase, com hifens substituidos por underscore na carac).
    modulos: Dict[str, ModuloValor] = field(default_factory=dict)


def carregar_dados_apoio(
    filepath: str,
    *,
    read_excel: Callable[..., pd.DataFrame] = pd.read_excel,
) -> DadosApoio:
    """Le e processa a planilha de apoio (entrypoint legado/desktop).

    Args:
        filepath: caminho do xlsx.
        read_excel: callable usado para carregar uma aba; default
            ``pd.read_excel``. A UI legada passa ``read_excel_cached``.

    Returns:
        ``DadosApoio`` com listas e dicts populados.

    Raises:
        ApoioFileError: estrutura/colunas invalidas, ou nenhum alimentador
            encontrado (codigo ``DADOS_VAZIOS``).
    """
    abas = carregar_abas_apoio(filepath, read_excel=read_excel)
    return carregar_dados_apoio_from_dfs(abas.df_apoio, abas.df_modulo)


def carregar_dados_apoio_from_dfs(
    df_apoio: pd.DataFrame,
    df_modulo: pd.DataFrame,
) -> DadosApoio:
    """Mesma logica de ``carregar_dados_apoio`` mas recebe DataFrames
    diretamente. Usado pelo web quando o apoio vive como tabelas no
    proprio obras.db (sem precisar reler xlsx). Desktop continua
    usando ``carregar_dados_apoio(filepath)`` -- nao mexer.

    Args:
        df_apoio:  DataFrame da aba "Apoio" com nomes de coluna
            originais (Alimentador, Tensao, Regional, ...).
        df_modulo: DataFrame da aba "MODULO".

    Returns:
        ``DadosApoio`` populado.

    Raises:
        ApoioFileError(DADOS_VAZIOS): nenhum alimentador valido.
    """
    # ---------- aba Apoio ----------
    cols_apoio = {str(col).lower(): col for col in df_apoio.columns}
    alim_col = cols_apoio.get("alimentador")
    proj_col = cols_apoio.get("projeto de investimento")
    carac_col = (
        cols_apoio.get("características")
        or cols_apoio.get("caracteristicas")
        or cols_apoio.get("caracteristica")
    )
    regional_col = cols_apoio.get("regional")
    superint_col = cols_apoio.get("superintendência") or cols_apoio.get("superintendencia")
    tensao_col = cols_apoio.get("tensão") or cols_apoio.get("tensao")
    se_col = (
        cols_apoio.get("se")
        or cols_apoio.get("subestação_cod")
        or cols_apoio.get("subestacao_cod")
    )
    nome_proj_col = (
        cols_apoio.get("nome de projeto")
        or cols_apoio.get("nome do projeto")
        or cols_apoio.get("nome_projeto")
        or cols_apoio.get("nome projeto")
    )

    alimentadores: List[str] = []
    dados_alimentador: Dict[str, DadosAlimentador] = {}

    if alim_col:
        alimentadores = [str(x).strip() for x in df_apoio[alim_col].dropna().tolist()]
        # Itera TODAS as linhas (mesmo as com NaN no alim) para preservar
        # 100% o comportamento do legado, que tambem nao filtrava aqui.
        for _, row in df_apoio.iterrows():
            nome_alim = str(row[alim_col]).strip()
            dados_alimentador[nome_alim] = DadosAlimentador(
                alimentador=nome_alim,
                tensao=str(row[tensao_col]).strip() if tensao_col else "",
                regional=str(row[regional_col]).strip() if regional_col else "",
                superintendencia=str(row[superint_col]).strip() if superint_col else "",
                se=str(row[se_col]).strip() if se_col else "",
            )

    if not dados_alimentador:
        raise ApoioFileError(
            codigo="DADOS_VAZIOS",
            detalhes="Os dados dos alimentadores não foram carregados corretamente.",
            hint="Verifique se a aba 'Apoio' está preenchida corretamente.",
        )

    projetos_investimento = (
        [str(x).strip() for x in df_apoio[proj_col].dropna().tolist()]
        if proj_col
        else []
    )
    caracteristicas = (
        [str(x).strip() for x in df_apoio[carac_col].dropna().tolist()]
        if carac_col
        else []
    )
    nomes_projetos = (
        [
            str(x).strip()
            for x in df_apoio[nome_proj_col].dropna().tolist()
            if str(x).strip()
        ]
        if nome_proj_col
        else []
    )

    # ---------- aba MODULO ----------
    cols_modulo = {str(col).lower(): col for col in df_modulo.columns}
    chave_col = cols_modulo.get("carac+modulo")
    regional_mod_col = cols_modulo.get("regional")
    valor_item_col = cols_modulo.get("valor_item")

    modulos: Dict[str, ModuloValor] = {}
    if chave_col and regional_mod_col and valor_item_col:
        for _, row in df_modulo.iterrows():
            chave = str(row[chave_col]).strip().upper().replace("-", "_")
            regional_mod = str(row[regional_mod_col]).strip().upper()
            chave_completa = f"{chave}_{regional_mod}"
            try:
                valor = float(str(row[valor_item_col]).replace(",", "."))
            except Exception:
                valor = 0.0
            modulos[chave_completa] = ModuloValor(
                caracteristica=chave,
                regional=regional_mod,
                valor=valor,
            )

    return DadosApoio(
        alimentadores=alimentadores,
        projetos_investimento=projetos_investimento,
        caracteristicas=caracteristicas,
        nomes_projetos=nomes_projetos,
        dados_alimentador=dados_alimentador,
        modulos=modulos,
    )
