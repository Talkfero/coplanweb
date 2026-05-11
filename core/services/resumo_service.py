"""Servico de dominio para os blocos de **Resumo** (volumetria financeira,
quadro de resumo por alimentadores, resumo de ganhos por projeto e
montagem do DataFrame do Detalhamento de Obras).

Extraido de ``codigo5_coplan.py`` na Etapa B.3, agregando logica pura de:

- ``MainWindow.popular_volumetria_financeiro`` (L9391)
- ``MainWindow.popular_quadro_resumo_from_ganhos_depois`` (L9825)
- ``MainWindow.popular_resumo_ganhos_projeto`` (L9943)
- ``MainWindow._montar_resumo_detalhamento_excel`` (L13027)
- helpers ``_parse_ganhos_totais_resumo`` (L12979) e
  ``_formatar_decimal_resumo`` (L13010)

A UI continua responsavel por: ``QTableWidget``, ``QTableWidgetItem``,
``QColor`` (vermelho/verde para criterios), ``setForeground``,
``setFlags``, ``setRowCount``, ``resizeColumnsToContents``, leitura do
banco e dos campos de UI.

Convencoes:

- Funcoes nao mutam argumentos (operam sobre copias quando necessario).
- Mensagens em portugues sao identicas ao legado para manter paridade
  byte-a-byte.
- Pandas e dependencia liberada (verificada pelo ``test_core_purity``).
- Sem dependencia de PySide6.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import pandas as pd

from core.models.info_alim import InfoAlim


# ---------------------------------------------------------------------------
# 1. Helpers numericos e de formatacao
# ---------------------------------------------------------------------------
def parse_number_pt_br(valor: Any) -> float:
    """Converte texto/numero para float, aceitando notacao pt-BR e en-US.

    Reproduz exatamente ``parse_number`` (L9415-9444 e L9593-9622, ambas
    identicas no legado). Remove todos os caracteres exceto digitos,
    ``,`` ``.`` e ``-``; decide se ``,`` e separador decimal ou de milhar
    olhando a posicao relativa de ``,`` e ``.``. Devolve ``0.0`` em
    qualquer falha.
    """
    if isinstance(valor, (int, float)):
        return float(valor)
    if valor is None:
        return 0.0
    texto = str(valor).strip()
    if not texto:
        return 0.0
    texto = re.sub(r"[^0-9,.-]", "", texto)
    if not texto or texto in {"-", ",", "."}:
        return 0.0
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            decimal_sep = ","
            thousands_sep = "."
        else:
            decimal_sep = "."
            thousands_sep = ","
        texto = texto.replace(thousands_sep, "")
        texto = texto.replace(decimal_sep, ".")
    else:
        if "," in texto:
            texto = texto.replace(".", "")
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")
    try:
        return float(texto)
    except ValueError:
        return 0.0


def formatar_numero_pt_br(valor: Any, *, suprimir_centavos_zero: bool = True) -> str:
    """Formata numero em padrao pt-BR (``1.234,56``).

    Reproduz ``formatar_numero`` (L9499-9508). Quando
    ``suprimir_centavos_zero=True`` (default), remove ``,00`` no fim do
    texto. Devolve ``"-"`` em caso de erro de conversao.
    """
    try:
        valor_float = float(valor)
    except (TypeError, ValueError):
        return "-"
    texto = f"{valor_float:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    if suprimir_centavos_zero and texto.endswith(",00"):
        texto = texto[:-3]
    return texto


def formatar_quantidade_pt_br(valor: Any) -> str:
    """Formata quantidade. Mantem inteiro quando o valor e inteiro exato.

    Reproduz ``formatar_quantidade`` (L9634-9642). Diferente de
    ``formatar_numero_pt_br``: aqui a regra e inteiro -> str int sem
    formatacao de milhares; nao-inteiro -> ``1.234,56``.
    """
    try:
        valor_float = float(valor)
    except (TypeError, ValueError):
        return ""
    if math.isclose(valor_float, round(valor_float)):
        return str(int(round(valor_float)))
    texto = f"{valor_float:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_decimal_resumo(valor: Any) -> str:
    """Formata numero em pt-BR de forma simples, mantendo o que ja vier formatado.

    Reproduz ``MainWindow._formatar_decimal_resumo`` (L13010-13025):

    - ``None`` ou string vazia -> ``""``.
    - Texto que ja contem virgula -> mantem.
    - Texto que casa ``-?\\d+(\\.\\d+)?`` (numero com ponto decimal) ->
      troca ``.`` por ``,``.
    - Caso contrario, devolve o texto cru (apos strip).
    """
    if valor is None:
        return ""
    txt = str(valor).strip()
    if not txt:
        return ""
    if "," in txt:
        return txt
    if re.fullmatch(r"-?\d+(\.\d+)?", txt):
        return txt.replace(".", ",")
    return txt


def ordenar_ano(valor: Any) -> tuple:
    """Chave de sort para anos -- numericos primeiro, vazios e textos no fim.

    Reproduz ``ordenar_ano`` (L9460-9470 do legado).
    """
    texto = str(valor).strip()
    if not texto:
        return (1, "")
    try:
        return (0, int(texto))
    except ValueError:
        try:
            return (0, float(texto))
        except ValueError:
            return (1, texto)


# ---------------------------------------------------------------------------
# 2. Normalizacao de alimentadores (principal + beneficiados)
# ---------------------------------------------------------------------------
def normalizar_alimentadores(
    alimentador_principal: str,
    alimentadores_beneficiados_raw: str,
) -> list[str]:
    """Concatena principal + beneficiados, dedupe preservando ordem.

    Reproduz a logica replicada em L9834-9843, L9971-9981. Separadores
    aceitos para ``alimentadores_beneficiados_raw``: ``,``, ``\\n``,
    ``;``, ``|``. Cada alimentador recebe ``.strip().upper()``; vazios
    e duplicatas sao filtrados.
    """
    raw_list = [alimentador_principal or ""] + re.split(
        r"[,\n;|]+", alimentadores_beneficiados_raw or ""
    )
    seen: set[str] = set()
    alimentadores: list[str] = []
    for a in raw_list:
        a_u = (a or "").strip().upper()
        if a_u and a_u not in seen:
            alimentadores.append(a_u)
            seen.add(a_u)
    return alimentadores


# ---------------------------------------------------------------------------
# 3. Parsers de ``ganhos_totais_*``
# ---------------------------------------------------------------------------
def parse_ganhos_simples(
    ganhos_str: str | None,
) -> dict[str, dict[str, float | int]]:
    """Parser ``ganhos_totais_*`` -- versao "simples" (V1/V2).

    Reproduz L9847-9866 e L9985-10004 (identicas no legado).
    Estrategia: ``split(';')`` + ``split('_', 2)`` em 3 partes
    (``alim``, ``campo``, ``valor_str``). Tenta ``float()``, depois
    ``int()``; falha em qualquer um dos dois descarta o token.

    Limitacao conhecida: token como ``ALIM_Demand_MAX_42`` e descartado
    (``valor_str`` fica ``"MAX_42"``, falha em ``float``). Para esses
    casos use ``parse_ganhos_demand_max``.
    """
    dados: dict[str, dict[str, float | int]] = {}
    if not ganhos_str:
        return dados
    for part in str(ganhos_str).split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            alim, campo, valor_str = part.split("_", 2)
        except ValueError:
            continue
        alim = alim.strip().upper()
        campo = campo.strip().lower()
        try:
            valor: float | int = float(valor_str)
        except ValueError:
            try:
                valor = int(valor_str)
            except ValueError:
                continue
        if alim not in dados:
            dados[alim] = {}
        dados[alim][campo] = valor
    return dados


def parse_ganhos_demand_max(
    ganhos_str: str | None,
) -> dict[str, dict[str, str]]:
    """Parser ``ganhos_totais_*`` -- versao permissiva (V3).

    Reproduz ``MainWindow._parse_ganhos_totais_resumo`` (L12979-13007).
    Estrategia: ``split(';')`` + ``split('_')`` (sem limite) com
    ``alim = partes[0]``, ``valor = partes[-1]``,
    ``metrica = '_'.join(partes[1:-1])``. Captura metricas com ``_`` no
    nome como ``Demand_MAX``.

    Diferente de ``parse_ganhos_simples``: o valor e mantido como
    **string** (nao tenta converter para float). A conversao numerica
    fica a cargo do caller (ver ``formatar_decimal_resumo``).
    """
    resultado: dict[str, dict[str, str]] = {}
    if not ganhos_str:
        return resultado
    for token in str(ganhos_str).split(";"):
        token = token.strip()
        if not token:
            continue
        partes = token.split("_")
        if len(partes) < 3:
            continue
        alim = str(partes[0]).strip().upper()
        valor = partes[-1]
        metrica = "_".join(partes[1:-1])
        dados_alim = resultado.setdefault(alim, {})
        dados_alim[metrica] = valor
    return resultado


# ---------------------------------------------------------------------------
# 4. Avaliacao de criterios (carregamento, tensao, clientes)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CelulaCriterio:
    """Resultado da avaliacao de uma celula da tabela de Resumo.

    - ``text``: o que vai dentro do ``QTableWidgetItem`` (ex: ``"55%"``,
      ``"0.97 | 1.02"``, ``"-"``).
    - ``ok``: ``True`` (verde), ``False`` (vermelho), ``None`` (sem
      pintura -- caso "-").

    A UI usa ``ok`` para decidir entre ``QColor(0, 200, 0)`` e
    ``QColor(200, 0, 0)`` no ``setForeground``.
    """

    text: str
    ok: bool | None


def avaliar_carregamento(
    carreg_val: Any,
    *,
    carreg_limite_nao: float,
) -> CelulaCriterio:
    """Avalia carregamento de um alimentador.

    Reproduz L9892-9899, L10050-10057 (logica identica). Aceita um
    valor numerico finito ou descarta como ``"-"``. Compara com
    ``carreg_limite_nao`` (geralmente 100.0 do
    ``DEFAULT_CRITERIOS``).
    """
    if isinstance(carreg_val, (int, float)) and math.isfinite(float(carreg_val)):
        carreg_pct = int(round(float(carreg_val)))
        return CelulaCriterio(
            text=f"{carreg_pct}%",
            ok=float(carreg_val) <= carreg_limite_nao,
        )
    return CelulaCriterio(text="-", ok=None)


def avaliar_tensao(
    tmin_val: Any,
    tmax_val: Any,
    *,
    tensao_min_lim: float,
    tensao_max_lim: float,
) -> CelulaCriterio:
    """Avalia faixa (tensao_min, tensao_max) de um alimentador.

    Reproduz L9907-9921, L10065-10079 (logica identica). Ambos os
    valores precisam ser finitos para a celula ser pintada.
    """
    if (
        isinstance(tmin_val, (int, float))
        and isinstance(tmax_val, (int, float))
        and math.isfinite(float(tmin_val))
        and math.isfinite(float(tmax_val))
    ):
        tmin_f = float(tmin_val)
        tmax_f = float(tmax_val)
        return CelulaCriterio(
            text=f"{tmin_f:.2f} | {tmax_f:.2f}",
            ok=(tmin_f >= tensao_min_lim and tmax_f <= tensao_max_lim),
        )
    return CelulaCriterio(text="-", ok=None)


def formatar_clientes(clientes_val: Any) -> str:
    """Formata "contas/clientes" como inteiro ou ``"-"``.

    Reproduz L9929-9936, L10087-10094 (logica identica).
    """
    if clientes_val is None:
        return "-"
    try:
        return str(int(float(clientes_val)))
    except (TypeError, ValueError):
        return "-"


@dataclass(frozen=True)
class LinhaQuadroResumo:
    """Linha pronta para ``tabelaResumo`` ou ``tabelaResumoProjeto``.

    A UI itera essa lista e preenche 4 celulas: alimentador,
    carregamento (com cor), tensao (com cor), clientes (sem cor).
    """

    alimentador: str
    carregamento: CelulaCriterio
    tensao: CelulaCriterio
    clientes_text: str


def _le_criterios(criterios: Mapping[str, Any]) -> tuple[float, float, float]:
    """Le ``tensao_min``, ``tensao_max``, ``carregamento_limite_nao``.

    Reproduz L9868-9880, L10027-10039 (idem). O caller passa
    ``self.config.get("criterios_planejamento", DEFAULT_CRITERIOS)``;
    aqui aplicamos os mesmos defaults.
    """
    # defaults espelhados de DEFAULT_CRITERIOS no legado
    defaults = {
        "tensao_min": 0.95,
        "tensao_max": 1.03,
        "carregamento_limite_nao": 100.0,
    }
    return (
        float(criterios.get("tensao_min", defaults["tensao_min"])),
        float(criterios.get("tensao_max", defaults["tensao_max"])),
        float(
            criterios.get(
                "carregamento_limite_nao", defaults["carregamento_limite_nao"]
            )
        ),
    )


# ---------------------------------------------------------------------------
# 5. popular_volumetria_financeiro
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VolumetriaFinanceiro:
    """Saida de ``montar_volumetria_financeiro`` -- pronto para ``QTableWidget``.

    - ``cabecalhos``: lista com ``"PI"`` + 2*N entradas (Valor/Fisico
      por ano), com ``"\\n"`` no meio (ex: ``"2024\\nValor"``).
    - ``linhas``: cada item e uma lista com ``[pi, valor1, fisico1,
      valor2, fisico2, ...]``, todas strings ja formatadas em pt-BR.
    """

    cabecalhos: list[str]
    linhas: list[list[str]]


def montar_volumetria_financeiro(
    obras_visiveis: Sequence[Mapping[str, Any]],
) -> VolumetriaFinanceiro:
    """Pivota obras visiveis por (PI x ano), devolve cabecalhos+linhas.

    Reproduz L9391-9551 do legado, exceto a parte de UI (clear,
    setRowCount, QTableWidgetItem, alinhamento). Quando nao ha dados,
    devolve ``VolumetriaFinanceiro(["PI"], [])``.
    """
    vazio = VolumetriaFinanceiro(cabecalhos=["PI"], linhas=[])
    if not obras_visiveis:
        return vazio
    df = pd.DataFrame(list(obras_visiveis))
    if df.empty:
        return vazio

    df["projeto_investimento"] = (
        df["projeto_investimento"].fillna("").astype(str).str.strip()
    )
    df["ano_"] = df["ano_"].fillna("").astype(str).str.strip()
    df["valor_obra"] = df["valor_obra"].apply(parse_number_pt_br)
    df["quantidade_material"] = df["quantidade_material"].apply(parse_number_pt_br)

    agrupado = (
        df.groupby(["projeto_investimento", "ano_"], dropna=False)
        .agg({"valor_obra": "sum", "quantidade_material": "sum"})
        .reset_index()
    )
    if agrupado.empty:
        return vazio

    anos_unicos = agrupado["ano_"].unique().tolist()
    anos_ordenados = sorted(anos_unicos, key=ordenar_ano)

    pivot = df.pivot_table(
        index="projeto_investimento",
        columns="ano_",
        values=["valor_obra", "quantidade_material"],
        aggfunc="sum",
        fill_value=0.0,
    )
    if pivot.empty:
        return vazio

    pivot = pivot.swaplevel(0, 1, axis=1)
    col_tuplas = [
        (ano, campo)
        for ano in anos_ordenados
        for campo in ("valor_obra", "quantidade_material")
    ]
    pivot = pivot.reindex(
        columns=pd.MultiIndex.from_tuples(col_tuplas), fill_value=0.0
    )
    pivot = pivot.sort_index()

    cabecalhos = ["PI"]
    for ano in anos_ordenados:
        ano_texto = str(ano).strip()
        rotulo = ano_texto if ano_texto else "Sem Ano"
        cabecalhos.append(f"{rotulo}\nValor")
        cabecalhos.append(f"{rotulo}\nFísico")

    linhas: list[list[str]] = []
    for pi, dados in pivot.iterrows():
        linha: list[str] = [str(pi)]
        for ano in anos_ordenados:
            valor = dados.get((ano, "valor_obra"), 0.0)
            fisico = dados.get((ano, "quantidade_material"), 0.0)
            linha.append(formatar_numero_pt_br(valor))
            linha.append(formatar_numero_pt_br(fisico))
        linhas.append(linha)

    return VolumetriaFinanceiro(cabecalhos=cabecalhos, linhas=linhas)


# ---------------------------------------------------------------------------
# 6. popular_quadro_resumo_from_ganhos_depois
# ---------------------------------------------------------------------------
def montar_quadro_resumo_from_ganhos(
    *,
    alimentador_principal: str,
    alimentadores_beneficiados: str,
    ganhos_totais_depois: str,
    criterios: Mapping[str, Any],
) -> list[LinhaQuadroResumo]:
    """Monta linhas para ``tabelaResumo`` a partir do campo de ganhos.

    Reproduz L9825-9941 do legado, sem qualquer interacao com Qt. A UI
    itera as ``LinhaQuadroResumo`` e cria ``QTableWidgetItem`` com
    cores baseadas em ``CelulaCriterio.ok``.
    """
    alimentadores = normalizar_alimentadores(
        alimentador_principal, alimentadores_beneficiados
    )
    dados = parse_ganhos_simples(ganhos_totais_depois)

    tensao_min_lim, tensao_max_lim, carreg_limite = _le_criterios(criterios)

    linhas: list[LinhaQuadroResumo] = []
    for alim in alimentadores:
        info = dados.get(alim, {})
        carreg = avaliar_carregamento(
            info.get("carregamento"), carreg_limite_nao=carreg_limite,
        )
        tensao = avaliar_tensao(
            info.get("tensaominima"),
            info.get("tensaomax"),
            tensao_min_lim=tensao_min_lim,
            tensao_max_lim=tensao_max_lim,
        )
        clientes_text = formatar_clientes(info.get("contas"))
        linhas.append(
            LinhaQuadroResumo(
                alimentador=alim,
                carregamento=carreg,
                tensao=tensao,
                clientes_text=clientes_text,
            )
        )
    return linhas


# ---------------------------------------------------------------------------
# 7. popular_resumo_ganhos_projeto
# ---------------------------------------------------------------------------
def montar_resumo_ganhos_projeto(
    *,
    rows: Sequence[Sequence[Any]],
    cols: Sequence[str],
    criterios: Mapping[str, Any],
) -> list[LinhaQuadroResumo]:
    """Consolida ganhos de todas as obras de um projeto, retorna linhas.

    Reproduz L9943-10099 do legado (a parte logica). Para cada
    alimentador, escolhe o ``ganhos_totais_depois`` da obra de **maior
    codigo_item** em que ele aparece.

    Quando ``rows`` for vazio ou faltar alguma coluna obrigatoria,
    devolve lista vazia (a UI mostra a tabela vazia, mesmo do legado).
    """
    if not rows:
        return []
    cols_list = list(cols)
    try:
        idx_alim = cols_list.index("alimentador_principal")
        idx_benef = cols_list.index("alimentadores_beneficiados")
        idx_item = cols_list.index("codigo_item")
        idx_ganhos = cols_list.index("ganhos_totais_depois")
    except ValueError:
        return []

    ordem: list[str] = []
    vistos: set[str] = set()
    dados_alims: dict[str, tuple[int, dict[str, float | int]]] = {}

    for row in rows:
        alim_princ = row[idx_alim]
        alims_benef = row[idx_benef]
        cod_item = row[idx_item]
        ganhos = row[idx_ganhos]

        # Normaliza alimentadores -- mantem ordem global vs local
        raw_list = [alim_princ or ""] + re.split(
            r"[,\n;|]+", alims_benef or ""
        )
        normalizados: list[str] = []
        local_seen: set[str] = set()
        for a in raw_list:
            a_u = (a or "").strip().upper()
            if a_u and a_u not in local_seen:
                normalizados.append(a_u)
                local_seen.add(a_u)
            if a_u and a_u not in vistos:
                ordem.append(a_u)
                vistos.add(a_u)

        ganhos_dict = parse_ganhos_simples(ganhos)

        try:
            cod_int = int(str(cod_item).strip() or 0)
        except ValueError:
            cod_int = 0

        for alim in normalizados:
            info_alim = ganhos_dict.get(alim)
            atual = dados_alims.get(alim)
            # Se nao ha dado ainda nem nesta obra, registra vazio (mantem ordem)
            if atual is None and info_alim is None:
                dados_alims[alim] = (cod_int, {})
                continue
            # Atualiza so quando esta obra contribui e tem cod_item maior
            if info_alim is not None:
                if atual is None or cod_int > atual[0]:
                    dados_alims[alim] = (cod_int, info_alim)

    tensao_min_lim, tensao_max_lim, carreg_limite = _le_criterios(criterios)

    linhas: list[LinhaQuadroResumo] = []
    for alim in ordem:
        info = dados_alims.get(alim, (0, {}))[1]
        carreg = avaliar_carregamento(
            info.get("carregamento"), carreg_limite_nao=carreg_limite,
        )
        tensao = avaliar_tensao(
            info.get("tensaominima"),
            info.get("tensaomax"),
            tensao_min_lim=tensao_min_lim,
            tensao_max_lim=tensao_max_lim,
        )
        clientes_text = formatar_clientes(info.get("contas"))
        linhas.append(
            LinhaQuadroResumo(
                alimentador=alim,
                carregamento=carreg,
                tensao=tensao,
                clientes_text=clientes_text,
            )
        )
    return linhas


# ---------------------------------------------------------------------------
# 8. _montar_resumo_detalhamento_excel
# ---------------------------------------------------------------------------
def _codigo_num(valor: Any) -> int:
    """Extrai parte numerica de um ``codigo_item``. Reproduz ``codigo_num`` (L13054)."""
    try:
        return int(re.sub(r"\D", "", str(valor) or "") or "0")
    except Exception:
        return 0


def _split_alims_detalhamento(txt: Any) -> list[str]:
    """Divide string de alimentadores beneficiados (separadores ``;,|\\n``).

    Reproduz ``split_alims`` (L13060-13065).
    """
    if not txt:
        return []
    parts = re.split(r"[;\n,|]+", str(txt))
    return [p.strip().upper() for p in parts if p and p.strip()]


def montar_resumo_detalhamento(
    obras: Sequence[Sequence[Any]],
    cols: Sequence[str],
) -> pd.DataFrame | None:
    """Monta DataFrame de resumo do "Detalhamento de Obras".

    Reproduz ``MainWindow._montar_resumo_detalhamento_excel``
    (L13027-13203). Devolve ``None`` quando faltar coluna obrigatoria
    ou nao houver linhas (criterio do legado).

    Regras:

    - Agrupa obras por ``(nome_projeto, ano_, tipo_pacote)``. Quando
      ``nome_projeto`` for vazio, cada obra forma seu proprio grupo
      (chave ``__SEM_PROJETO__:{id(obra)}``).
    - Para cada grupo, monta lista de **todos** os alimentadores
      (principal + beneficiados + os que aparecerem em
      ``ganhos_totais_antes/depois``).
    - Para cada alimentador, ANTES = ganhos da obra de menor
      ``codigo_item`` em que ele aparece; DEPOIS = ganhos da obra de
      maior ``codigo_item``.
    - Ordem de saida: por menor ``codigo_item``, depois alfabetica.
    """
    cols_list = list(cols)
    try:
        idx_nome_proj = cols_list.index("nome_projeto")
        idx_ano = cols_list.index("ano_")
        idx_pacote = cols_list.index("tipo_pacote")
        idx_principal = cols_list.index("alimentador_principal")
        idx_benef = cols_list.index("alimentadores_beneficiados")
        idx_codigo = cols_list.index("codigo_item")
        idx_g_antes = cols_list.index("ganhos_totais_antes")
        idx_g_depois = cols_list.index("ganhos_totais_depois")
    except ValueError:
        return None

    # 1) agrupa por (nome_projeto, ano, pacote); obras sem projeto viram grupos solo
    grupos: dict[tuple[str, str, str], list[Sequence[Any]]] = {}
    for obra in obras:
        nome_proj = str(obra[idx_nome_proj] or "").strip()
        ano = str(obra[idx_ano] or "").strip()
        pacote = str(obra[idx_pacote] or "").strip()
        if not nome_proj:
            key = (f"__SEM_PROJETO__:{id(obra)}", ano, pacote)
        else:
            key = (nome_proj, ano, pacote)
        grupos.setdefault(key, []).append(obra)

    linhas: list[dict[str, Any]] = []

    # 2) processa cada projeto
    for (nome_proj, ano, pacote), lista in grupos.items():
        if not lista:
            continue
        ordenadas = sorted(lista, key=lambda o: _codigo_num(o[idx_codigo]))

        # principais = unique strip+upper de alimentador_principal
        principais = sorted(
            {
                str(o[idx_principal] or "").strip().upper()
                for o in ordenadas
                if str(o[idx_principal] or "").strip()
            }
        )
        if len(principais) == 1:
            principal_txt = principais[0]
        elif len(principais) > 1:
            principal_txt = "MÚLTIPLOS"
        else:
            principal_txt = ""

        # 2.1) alimentadores do projeto = principal + beneficiados + ganhos
        alims_projeto: set[str] = set()
        for obra in ordenadas:
            p = str(obra[idx_principal] or "").strip().upper()
            if p:
                alims_projeto.add(p)
            for b in _split_alims_detalhamento(obra[idx_benef]):
                alims_projeto.add(b)
            dados_antes = parse_ganhos_demand_max(str(obra[idx_g_antes] or ""))
            dados_depois = parse_ganhos_demand_max(str(obra[idx_g_depois] or ""))
            for a in set(dados_antes.keys()) | set(dados_depois.keys()):
                a_u = str(a).strip().upper()
                if a_u:
                    alims_projeto.add(a_u)
        if not alims_projeto:
            continue

        # 2.2) info_por_alim com first/last codigo_item
        info_por_alim: dict[str, InfoAlim] = {
            a: InfoAlim() for a in alims_projeto
        }
        for obra in ordenadas:
            cod_int = _codigo_num(obra[idx_codigo])

            alims_obra: set[str] = set()
            p = str(obra[idx_principal] or "").strip().upper()
            if p:
                alims_obra.add(p)
            for b in _split_alims_detalhamento(obra[idx_benef]):
                alims_obra.add(b)
            dados_antes = parse_ganhos_demand_max(str(obra[idx_g_antes] or ""))
            dados_depois = parse_ganhos_demand_max(str(obra[idx_g_depois] or ""))
            alims_obra |= {
                str(a).strip().upper()
                for a in (set(dados_antes.keys()) | set(dados_depois.keys()))
                if str(a).strip()
            }

            for alim in alims_obra:
                reg = info_por_alim.setdefault(alim, InfoAlim())
                if reg.first_codigo is None or cod_int < reg.first_codigo:
                    reg.first_codigo = cod_int
                    reg.first_antes = dados_antes.get(alim)
                if reg.last_codigo is None or cod_int > reg.last_codigo:
                    reg.last_codigo = cod_int
                    reg.last_depois = dados_depois.get(alim)

        # 2.3) ordem: por menor cod_item, depois alfabetica
        alimentadores_ordenados = sorted(
            info_por_alim.keys(),
            key=lambda a: (
                info_por_alim[a].first_codigo
                if info_por_alim[a].first_codigo is not None
                else 10**12,
                str(a),
            ),
        )

        for alim in alimentadores_ordenados:
            reg = info_por_alim.get(alim) or InfoAlim()
            m_antes = reg.first_antes or {}
            m_depois = reg.last_depois or {}

            linhas.append(
                {
                    "Projeto": "" if str(nome_proj).startswith("__SEM_PROJETO__:") else nome_proj,
                    "Ano": ano,
                    "Pacote": pacote,
                    "Alimentador Principal": principal_txt,
                    "Alimentador": alim,
                    "CCs Antes": m_antes.get("contas", ""),
                    "CCs Depois*": m_depois.get("contas", ""),
                    "Carregamento (%) Antes": formatar_decimal_resumo(
                        m_antes.get("carregamento")
                    ),
                    "Carregamento (%) Depois": formatar_decimal_resumo(
                        m_depois.get("carregamento")
                    ),
                    "Demanda (MW) Antes": formatar_decimal_resumo(
                        m_antes.get("Demand_MAX")
                    ),
                    "Demanda (MW) Depois*": formatar_decimal_resumo(
                        m_depois.get("Demand_MAX")
                    ),
                    "Tensão (pu) Antes": formatar_decimal_resumo(
                        m_antes.get("tensaominima")
                    ),
                    "Tensão (pu) Depois*": formatar_decimal_resumo(
                        m_depois.get("tensaominima")
                    ),
                }
            )

    if not linhas:
        return None
    return pd.DataFrame(linhas)
