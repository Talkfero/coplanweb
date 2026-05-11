"""Servico de dominio para os relatorios de criterios de planejamento.

Extraido de ``codigo5_coplan.py`` na Etapa B.4, agregando logica pura de:

- ``MainWindow.verificar_criterios_planejamento_v2`` (L10795)
- ``MainWindow._avaliar_criterios_persistencia`` (L10923)
- ``MainWindow._build_criterios_persistencia_updates`` (L11009)
- ``MainWindow.montar_relatorio_criterios_por_projeto`` (L11398)
- ``MainWindow.verificar_criterios_planejamento`` (L11795, V1 -- DEPRECATED)
- 7 helpers (``_norm_alim``, ``_split_alimentadores_benef``,
  ``_is_missing_value``, ``_parse_ganhos_totais_depois``,
  ``_parse_ganhos_totais_metricas``, ``_obra_atende``,
  ``_avaliar_alim_por_ganhos``).

Convencoes:

- Funcoes nao mutam argumentos.
- Mensagens em portugues sao identicas ao legado para manter paridade
  byte-a-byte (incluindo acentos: "tensao_min", "tensão", "NÃO", etc.).
- Pandas e dependencia liberada (verificada pelo ``test_core_purity``).
- Sem dependencia de PySide6.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from core.services.resumo_service import parse_ganhos_demand_max


# ---------------------------------------------------------------------------
# 1. Helpers basicos
# ---------------------------------------------------------------------------
def norm_alim(s: Any) -> str:
    """Normaliza nome de alimentador: ``str(s or '').strip().upper()``.

    Reproduz ``MainWindow._norm_alim`` (L10700-10701).
    """
    return str(s or "").strip().upper()


def split_alimentadores_benef(s: Any) -> list[str]:
    """Divide string de alimentadores beneficiados.

    Reproduz ``MainWindow._split_alimentadores_benef`` (L10743-10750).
    Separadores aceitos: ``,``, ``;``, ``|``, ``/``, ``\\``, ``\\n``.
    Cada item e normalizado com ``norm_alim``; vazios sao filtrados.
    """
    itens = re.split(r"[,;|/\\\n]+", str(s or ""))
    alimentadores: list[str] = []
    for item in itens:
        alim = norm_alim(item)
        if alim:
            alimentadores.append(alim)
    return alimentadores


def is_missing_value(value: Any) -> bool:
    """Detecta valores 'faltantes' em rows do banco.

    Reproduz ``MainWindow._is_missing_value`` (staticmethod, L10752-10761):

    - ``None`` -> True.
    - ``float NaN`` -> True.
    - String vazia (apos strip) -> True.
    - String ``"nan"`` ou ``"none"`` (case-insensitive) -> True.
    """
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    texto = str(value).strip()
    if texto == "":
        return True
    return texto.lower() in ("nan", "none")


# ---------------------------------------------------------------------------
# 2. Parsers de ganhos (V4 e V5 do legado)
# ---------------------------------------------------------------------------
def parse_ganhos_rsplit(txt: Any) -> dict[str, dict[str, float]]:
    """Parser V4 -- usa ``rsplit('_', 2)``, valores em float.

    Reproduz ``MainWindow._parse_ganhos_totais_depois`` (L10703-10728).
    Diferente do parser V3 (``parse_ganhos_demand_max`` em
    ``resumo_service``): aqui o valor e convertido para float, e o
    split usa ``rsplit('_', 2)`` -- o que tem implicacoes:

    - ``ALIM01_carregamento_55.48`` casa: alim=ALIM01, metrica=carregamento.
    - ``ALIM_Demand_MAX_42`` -> rsplit em 3: ``["ALIM_Demand", "MAX", "42"]``
      -> alim=ALIM_DEMAND, metrica=max. Diferente do V3 que daria
      alim=ALIM, metrica=Demand_MAX. **Cuidado** ao comparar.

    Devolve ``{}`` em qualquer falha (nunca levanta excecao).
    """
    try:
        if not txt:
            return {}
        resultado: dict[str, dict[str, float]] = {}
        for raw in str(txt).split(";"):
            token = raw.strip()
            if not token:
                continue
            parts = token.rsplit("_", 2)
            if len(parts) != 3:
                continue
            alim_raw, metrica_raw, valor_raw = parts
            alim = norm_alim(alim_raw)
            metrica = str(metrica_raw or "").strip().lower()
            if not alim or not metrica:
                continue
            try:
                valor = float(str(valor_raw).replace(",", "."))
            except Exception:
                continue
            resultado.setdefault(alim, {})[metrica] = valor
        return resultado
    except Exception:
        return {}


def parse_ganhos_metricas_float(txt: Any) -> dict[str, dict[str, float]]:
    """Parser V5 -- chama V3 (``parse_ganhos_demand_max``) + converte float.

    Reproduz ``MainWindow._parse_ganhos_totais_metricas`` (L10730-10741).
    Comeca pelo V3 (que captura ``Demand_MAX`` e similares) e depois
    converte cada valor de string para float, descartando os que falham.
    Metricas sao normalizadas para lowercase.
    """
    resultado: dict[str, dict[str, float]] = {}
    parsed_raw = parse_ganhos_demand_max(txt)
    for alim, metrics in parsed_raw.items():
        for metrica, valor in metrics.items():
            try:
                valor_num = float(str(valor).replace(",", "."))
            except Exception:
                continue
            resultado.setdefault(alim, {})[str(metrica).strip().lower()] = valor_num
    return resultado


# ---------------------------------------------------------------------------
# 3. Avaliacao de criterios por obra
# ---------------------------------------------------------------------------
def obra_atende(
    row: Sequence[Any],
    idx: Mapping[str, int],
    criterios: Mapping[str, Any],
    conv_float: Callable[[Any], float],
    conv_int: Callable[[Any], int],
) -> tuple[bool | None, list[str]]:
    """Avalia se uma obra atende aos criterios de planejamento.

    Reproduz ``MainWindow._obra_atende`` (L11915-11953). A assinatura e
    preservada byte-a-byte (mesmos parametros nomeados/posicionais) para
    manter compatibilidade com os 9 callers existentes no legado.

    Retornos:

    - ``(None, ["dados_insuficientes"])`` se algum dos 4 campos
      criticos (tmin/tmax/carreg/clientes) for missing.
    - ``(True, [])`` se atende todos os 3 criterios (tensao,
      carregamento, clientes).
    - ``(False, [<motivos>])`` caso contrario; motivos podem conter
      ``"tensão"``, ``"carregamento"``, ``"clientes"``.

    Nota tecnica: ``manobra`` em ``""`` ou ``"SIM"`` usa
    ``carregamento_limite_sim_ou_vazio``; ``"NÃO"`` (e qualquer outro
    valor) usa ``carregamento_limite_nao``.
    """
    raw_tmin = row[idx["tmin"]]
    raw_tmax = row[idx["tmax"]]
    raw_carreg = row[idx["carreg"]]
    raw_clientes = row[idx["clientes"]]
    if any(
        is_missing_value(valor)
        for valor in (raw_tmin, raw_tmax, raw_carreg, raw_clientes)
    ):
        return None, ["dados_insuficientes"]

    tmin = conv_float(raw_tmin)
    tmax = conv_float(raw_tmax)
    carreg = conv_float(raw_carreg)
    manobra = str(row[idx["manobra"]]).strip().upper()
    clientes = conv_int(raw_clientes)

    motivos: list[str] = []
    if not (tmin > criterios["tensao_min"] and tmax < criterios["tensao_max"]):
        motivos.append("tensão")

    if manobra in ("", "SIM"):
        if carreg >= criterios["carregamento_limite_sim_ou_vazio"]:
            motivos.append("carregamento")
    else:
        if carreg >= criterios["carregamento_limite_nao"]:
            motivos.append("carregamento")

    if clientes >= criterios["clientes_maximo"]:
        motivos.append("clientes")

    return len(motivos) == 0, motivos


def avaliar_alim_por_ganhos(
    metrics: Mapping[str, float],
    manobra: Any,
    criterios: Mapping[str, Any],
) -> tuple[bool | None, list[str]]:
    """Avalia um alimentador a partir de seu dict ``metrics``.

    Reproduz ``MainWindow._avaliar_alim_por_ganhos`` (L10763-10793).
    Espera as 4 chaves obrigatorias: ``tensaominima``, ``tensaomax``,
    ``carregamento``, ``contas``. Se faltar qualquer uma OU se for
    missing, devolve ``(None, ["dados_incompletos"])``.

    Mesma logica de carregamento do ``obra_atende``: ``""`` ou ``"SIM"``
    usa o limite "sim_ou_vazio"; demais usam o "nao".
    """
    required = ("tensaominima", "tensaomax", "carregamento", "contas")
    if not metrics or any(key not in metrics for key in required):
        return None, ["dados_incompletos"]

    if any(is_missing_value(metrics.get(key)) for key in required):
        return None, ["dados_incompletos"]

    tmin = metrics["tensaominima"]
    tmax = metrics["tensaomax"]
    carreg = metrics["carregamento"]
    clientes = metrics["contas"]

    motivos: list[str] = []
    if not (tmin > criterios["tensao_min"] and tmax < criterios["tensao_max"]):
        motivos.append("tensão")

    manobra_norm = str(manobra).strip().upper()
    if manobra_norm in ("", "SIM"):
        if carreg >= criterios["carregamento_limite_sim_ou_vazio"]:
            motivos.append("carregamento")
    else:
        if carreg >= criterios["carregamento_limite_nao"]:
            motivos.append("carregamento")

    if clientes >= criterios["clientes_maximo"]:
        motivos.append("clientes")

    return len(motivos) == 0, motivos


# ---------------------------------------------------------------------------
# 4. Helpers internos comuns para conversao
# ---------------------------------------------------------------------------
def _conv_float(v: Any) -> float:
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return 0.0


def _conv_int(v: Any) -> int:
    try:
        return int(str(v))
    except Exception:
        return 0


def _conv_float_opt(valor: Any) -> float | None:
    if is_missing_value(valor):
        return None
    texto = str(valor).strip()
    try:
        retorno = float(texto.replace(",", "."))
    except Exception:
        return None
    if isinstance(retorno, float) and math.isnan(retorno):
        return None
    return retorno


def _conv_int_opt(valor: Any) -> int | None:
    if is_missing_value(valor):
        return None
    texto = str(valor).strip()
    try:
        return int(float(texto.replace(",", ".")))
    except Exception:
        return None


def _col_idx_map(columns: Sequence[str], names: Sequence[str]) -> dict[str, int]:
    """Helper -- monta dict {nome: idx ou -1 se ausente}."""
    cols = list(columns)
    return {n: (cols.index(n) if n in cols else -1) for n in names}


# ---------------------------------------------------------------------------
# 5. verificar_criterios_v2
# ---------------------------------------------------------------------------
def verificar_criterios_v2(
    obras: Sequence[Sequence[Any]],
    columns: Sequence[str],
    *,
    criterios: Mapping[str, Any],
) -> list[bool | None]:
    """Avalia criterios com regra V2 (cor unica por projeto).

    Reproduz ``MainWindow.verificar_criterios_planejamento_v2``
    (L10795-10921).

    Regra V2:
    - Nao permite mistura de cores dentro do mesmo ``nome_projeto``.
    - Conjunto de alimentadores = principal + beneficiados.
    - Usa ``ganhos_totais_depois`` (parser V4) por alimentador, do
      maior ``codigo_item`` para o menor, ate encontrar o primeiro com
      avaliacao definida.
    - Fallback: avaliacao da ultima obra do projeto (maior cod) via
      ``obra_atende``.

    Quando faltam colunas obrigatorias, devolve ``[True for _ in obras]``
    (legado se comporta como "tudo ok" nesse caso).
    """
    idx = _col_idx_map(
        columns,
        ["tensao_min_final", "tensao_max_final", "carregamento_final",
         "manobra", "contas_contratos_posteriores", "nome_projeto",
         "codigo_item", "alimentador_principal",
         "alimentadores_beneficiados", "ganhos_totais_depois"],
    )
    # rebatiza para os nomes curtos do legado
    idx = {
        "tmin": idx["tensao_min_final"],
        "tmax": idx["tensao_max_final"],
        "carreg": idx["carregamento_final"],
        "manobra": idx["manobra"],
        "clientes": idx["contas_contratos_posteriores"],
        "projeto": idx["nome_projeto"],
        "item": idx["codigo_item"],
        "alim": idx["alimentador_principal"],
        "benef": idx["alimentadores_beneficiados"],
        "ganhos": idx["ganhos_totais_depois"],
    }

    if any(idx[k] < 0 for k in ("tmin", "tmax", "carreg", "manobra", "clientes")):
        return [True for _ in obras]

    parsed_cache: dict[str, dict[str, dict[str, float]]] = {}

    def _get_parsed(txt: Any) -> dict[str, dict[str, float]]:
        chave = str(txt or "")
        if chave in parsed_cache:
            return parsed_cache[chave]
        parsed_cache[chave] = parse_ganhos_rsplit(chave)
        return parsed_cache[chave]

    resultados: list[bool | None] = [True for _ in obras]
    projetos: dict[str, list[tuple[int, Sequence[Any]]]] = {}

    for i, row in enumerate(obras):
        nome = str(row[idx["projeto"]]).strip() if idx["projeto"] >= 0 else ""
        if not nome:
            atende, _ = obra_atende(row, idx, criterios, _conv_float, _conv_int)
            resultados[i] = atende
            continue
        projetos.setdefault(nome, []).append((i, row))

    for _nome, rows in projetos.items():
        alim_set: set[str] = set()
        for _i, row in rows:
            if idx["alim"] >= 0:
                principal = norm_alim(row[idx["alim"]])
                if principal:
                    alim_set.add(principal)
            if idx["benef"] >= 0:
                alim_set.update(split_alimentadores_benef(row[idx["benef"]]))

        if not alim_set:
            for i, row in rows:
                atende, _ = obra_atende(row, idx, criterios, _conv_float, _conv_int)
                resultados[i] = atende
            continue

        rows_sorted = sorted(
            rows,
            key=lambda item: _conv_int(item[1][idx["item"]]) if idx["item"] >= 0 else 0,
        )
        last_row = rows_sorted[-1][1]
        rows_desc = list(reversed(rows_sorted))

        projeto_atende: bool | None = True
        for alim in sorted(alim_set):
            status_final: bool | None = None
            if idx["ganhos"] >= 0:
                for _i, row in rows_desc:
                    parsed = _get_parsed(row[idx["ganhos"]])
                    metrics = parsed.get(alim)
                    if not metrics:
                        continue
                    avalia, _motivos = avaliar_alim_por_ganhos(
                        metrics, row[idx["manobra"]], criterios,
                    )
                    if avalia is None:
                        continue
                    status_final = avalia
                    break

            if status_final is None:
                status_final, _ = obra_atende(
                    last_row, idx, criterios, _conv_float, _conv_int,
                )

            if status_final is None:
                projeto_atende = None
                break
            if status_final is False:
                projeto_atende = False
                break

        for i, _row in rows:
            resultados[i] = projeto_atende

    return resultados


# ---------------------------------------------------------------------------
# 6. avaliar_criterios_persistencia
# ---------------------------------------------------------------------------
def avaliar_criterios_persistencia(
    row: Sequence[Any],
    idx: Mapping[str, int],
    criterios: Mapping[str, Any],
) -> tuple[str, str, str]:
    """Avalia criterios para persistencia (status textual).

    Reproduz ``MainWindow._avaliar_criterios_persistencia``
    (L10923-11007). Devolve tupla ``(status, motivos_str, limite_txt)``:

    - ``status`` em ``{"OK", "FAIL", "DADOS_INSUFICIENTES"}``.
    - ``motivos_str`` -- texto pronto para gravar (ex:
      ``"tensão<limite; carreg>limite"`` para FAIL,
      ``"faltam: tensao_min_final"`` para DADOS_INSUFICIENTES).
    - ``limite_txt`` -- string com o ``carregamento_limite_*`` aplicado.
    """
    manobra = row[idx["manobra"]] if idx["manobra"] >= 0 else ""
    manobra_norm = str(manobra or "").strip().upper()
    limite_carreg = (
        criterios["carregamento_limite_sim_ou_vazio"]
        if manobra_norm in ("", "SIM")
        else criterios["carregamento_limite_nao"]
    )
    limite_txt = str(limite_carreg)

    missing: list[str] = []

    raw_tmin = row[idx["tmin"]]
    raw_tmax = row[idx["tmax"]]
    raw_carreg = row[idx["carreg"]]
    raw_clientes = row[idx["clientes"]]

    if _conv_float_opt(raw_tmin) is None:
        missing.append("tensao_min_final")
    if _conv_float_opt(raw_tmax) is None:
        missing.append("tensao_max_final")
    if _conv_float_opt(raw_carreg) is None:
        missing.append("carregamento_final")
    if _conv_int_opt(raw_clientes) is None:
        missing.append("contas_contratos_posteriores")

    if missing:
        motivos = "faltam: " + "; ".join(missing)
        return "DADOS_INSUFICIENTES", motivos, limite_txt

    atende, motivos_list = obra_atende(row, idx, criterios, _conv_float, _conv_int)
    if atende is None:
        return "DADOS_INSUFICIENTES", "dados_insuficientes", limite_txt
    if atende:
        return "OK", "", limite_txt

    motivos_map = {
        "tensão": "tensão<limite",
        "carregamento": "carreg>limite",
        "clientes": "clientes>limite",
    }
    motivos_traduzidos = [motivos_map.get(m, m) for m in motivos_list]
    return "FAIL", "; ".join(motivos_traduzidos), limite_txt


# ---------------------------------------------------------------------------
# 7. build_criterios_persistencia_updates
# ---------------------------------------------------------------------------
def build_criterios_persistencia_updates(
    obras: Sequence[Sequence[Any]],
    columns: Sequence[str],
    *,
    criterios: Mapping[str, Any],
) -> list[tuple[str, str, str, str]]:
    """Monta lista de updates ``(status, motivos, limite, cod)`` por obra.

    Reproduz ``MainWindow._build_criterios_persistencia_updates``
    (L11009-11049). Quando faltarem colunas obrigatorias, o status fica
    ``DADOS_INSUFICIENTES`` com motivo ``"colunas_ausentes: ..."``.
    Obras sem ``cod`` sao ignoradas (mesma regra do legado).
    """
    nomes = [
        "tensao_min_final", "tensao_max_final", "carregamento_final",
        "manobra", "contas_contratos_posteriores", "cod",
    ]
    idx_full = _col_idx_map(columns, nomes)
    idx = {
        "tmin": idx_full["tensao_min_final"],
        "tmax": idx_full["tensao_max_final"],
        "carreg": idx_full["carregamento_final"],
        "manobra": idx_full["manobra"],
        "clientes": idx_full["contas_contratos_posteriores"],
        "cod": idx_full["cod"],
    }

    required_cols = {
        "tensao_min_final": idx["tmin"],
        "tensao_max_final": idx["tmax"],
        "carregamento_final": idx["carreg"],
        "manobra": idx["manobra"],
        "contas_contratos_posteriores": idx["clientes"],
    }
    missing_cols = [c for c, p in required_cols.items() if p < 0]

    updates: list[tuple[str, str, str, str]] = []
    for row in obras:
        cod = str(row[idx["cod"]] or "").strip() if idx["cod"] >= 0 else ""
        if not cod:
            continue
        if missing_cols:
            motivo = "colunas_ausentes: " + "; ".join(sorted(missing_cols))
            updates.append(("DADOS_INSUFICIENTES", motivo, "", cod))
            continue
        status, motivos, limite_txt = avaliar_criterios_persistencia(
            row, idx, criterios,
        )
        updates.append((status, motivos, limite_txt, cod))
    return updates


# ---------------------------------------------------------------------------
# 8. montar_relatorio_criterios_por_projeto
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RelatorioCriterios:
    """Saida de ``montar_relatorio_criterios_por_projeto``.

    A UI consome ``df_projetos`` e ``df_alimentadores`` para exportar
    para Excel (1 sheet cada).
    """

    df_projetos: pd.DataFrame
    df_alimentadores: pd.DataFrame


def _conv_int_relatorio(v: Any) -> int:
    """Conversao de codigo_item para o relatorio (legado L11447-11451)."""
    try:
        return int(str(v).strip())
    except Exception:
        return int(re.sub(r"\D", "", str(v)) or 0)


def _avaliar_relatorio(
    tmin: float | None,
    tmax: float | None,
    carreg: float | None,
    clientes: int | None,
    manobra: Any,
    criterios: Mapping[str, Any],
) -> tuple[bool | None, list[str], dict[str, bool | None], float]:
    """Avaliacao usada por ``montar_relatorio_criterios_por_projeto``.

    Reproduz a closure ``avaliar`` (L11474-11527 do legado). Diferente
    de ``obra_atende``: usa **estritamente maior/menor** vs criterios e
    devolve um dict ``passes`` com cada flag individual.
    """
    manobra_norm = str(manobra or "").strip().upper()
    limite_carreg = (
        criterios["carregamento_limite_sim_ou_vazio"]
        if manobra_norm in ("", "SIM")
        else criterios["carregamento_limite_nao"]
    )
    pass_tmin = None if tmin is None else tmin > criterios["tensao_min"]
    pass_tmax = None if tmax is None else tmax < criterios["tensao_max"]
    pass_carreg = None if carreg is None else carreg < limite_carreg
    pass_clientes = None if clientes is None else clientes < criterios["clientes_maximo"]

    motivos: list[str] = []
    if pass_tmin is False:
        motivos.append("tensão_min")
    if pass_tmax is False:
        motivos.append("tensão_max")
    if pass_carreg is False:
        motivos.append("carregamento")
    if pass_clientes is False:
        motivos.append("clientes")

    passes = {
        "tmin": pass_tmin, "tmax": pass_tmax,
        "carreg": pass_carreg, "clientes": pass_clientes,
    }
    if any(v is None for v in (pass_tmin, pass_tmax, pass_carreg, pass_clientes)):
        return None, ["dados_insuficientes"], passes, limite_carreg

    status_ok = all(v is True for v in (pass_tmin, pass_tmax, pass_carreg, pass_clientes))
    return status_ok, motivos, passes, limite_carreg


def _fmt_flag(valor: bool | None) -> str:
    """``True`` -> ``"SIM"``, ``False`` -> ``"NÃO"``, ``None`` -> ``"NA"``."""
    if valor is None:
        return "NA"
    return "SIM" if valor else "NÃO"


def montar_relatorio_criterios_por_projeto(
    obras: Sequence[Sequence[Any]],
    columns: Sequence[str],
    *,
    criterios: Mapping[str, Any],
) -> RelatorioCriterios:
    """Monta os 2 DataFrames do relatorio de criterios por projeto.

    Reproduz a parte logica de
    ``MainWindow.montar_relatorio_criterios_por_projeto`` (L11398-11692).
    A UI continua responsavel por ``db_manager.fetch_all/fetch_by_cods``
    e ``get_column_names()``.

    Levanta ``ValueError`` quando alguma coluna obrigatoria esta
    ausente -- mesma mensagem do legado.
    """
    obrigatorias = [
        "nome_projeto", "codigo_item", "alimentador_principal",
        "alimentadores_beneficiados", "ganhos_totais_depois",
        "tensao_min_final", "tensao_max_final", "carregamento_final",
        "contas_contratos_posteriores", "manobra",
    ]
    cols_list = list(columns)
    faltantes = [c for c in obrigatorias if c not in cols_list]
    if faltantes:
        raise ValueError(f"Colunas ausentes para relatório: {', '.join(faltantes)}")

    nomes = [
        "nome_projeto", "pi_base", "projeto_investimento", "codigo_item",
        "cod", "alimentador_principal", "alimentadores_beneficiados",
        "ganhos_totais_depois", "tensao_min_final", "tensao_max_final",
        "carregamento_final", "contas_contratos_posteriores", "manobra",
    ]
    idx_full = _col_idx_map(columns, nomes)
    idx = {
        "projeto": idx_full["nome_projeto"],
        "pi_base": idx_full["pi_base"],
        "pi": idx_full["projeto_investimento"],
        "item": idx_full["codigo_item"],
        "cod": idx_full["cod"],
        "alim": idx_full["alimentador_principal"],
        "benef": idx_full["alimentadores_beneficiados"],
        "ganhos": idx_full["ganhos_totais_depois"],
        "tmin": idx_full["tensao_min_final"],
        "tmax": idx_full["tensao_max_final"],
        "carreg": idx_full["carregamento_final"],
        "clientes": idx_full["contas_contratos_posteriores"],
        "manobra": idx_full["manobra"],
    }

    parsed_cache: dict[str, dict[str, dict[str, float]]] = {}

    def _get_parsed(txt: Any) -> dict[str, dict[str, float]]:
        chave = str(txt or "")
        if chave in parsed_cache:
            return parsed_cache[chave]
        parsed_cache[chave] = parse_ganhos_metricas_float(chave)
        return parsed_cache[chave]

    # 1) Agrupa obras por nome_projeto (com fallback __SEM_PROJETO__)
    projetos: dict[str, list[Sequence[Any]]] = {}
    for row in obras:
        nome = str(row[idx["projeto"]]).strip() if idx["projeto"] >= 0 else ""
        if not nome:
            cod = str(row[idx["cod"]]).strip() if idx["cod"] >= 0 else ""
            nome = f"SEM_PROJETO:{cod or len(projetos) + 1}"
        projetos.setdefault(nome, []).append(row)

    linhas_projeto: list[dict[str, str]] = []
    linhas_alim: list[dict[str, str]] = []

    for nome_projeto, rows in projetos.items():
        # 2) Conjunto de alimentadores do projeto
        alim_set: set[str] = set()
        for row in rows:
            principal = norm_alim(row[idx["alim"]])
            if principal:
                alim_set.add(principal)
            alim_set.update(split_alimentadores_benef(row[idx["benef"]]))

        rows_sorted = sorted(rows, key=lambda r: _conv_int_relatorio(r[idx["item"]]))
        rows_desc = list(reversed(rows_sorted))
        last_row = rows_sorted[-1]

        def _first_non_empty(col: int, _rows=rows_sorted) -> str:
            if col < 0:
                return ""
            for row in _rows:
                valor = str(row[col]).strip()
                if valor:
                    return valor
            return ""

        projeto_falha = False
        projeto_insuficiente = False
        alimentadores_falha: list[str] = []
        motivos_falha_set: set[str] = set()
        resumo_origem: list[str] = []

        for alim in sorted(alim_set):
            origem = "FALLBACK_ULTIMA_OBRA"
            codigo_item_origem = str(last_row[idx["item"]]).strip()
            manobra_usada = last_row[idx["manobra"]]
            token_ganhos_bruto = ""
            metrics: dict[str, float] | None = None
            origem_ganhos_row: Sequence[Any] | None = None

            for row in rows_desc:
                ganhos_text = str(row[idx["ganhos"]] or "").strip()
                if not ganhos_text:
                    continue
                parsed = _get_parsed(ganhos_text)
                metrics_row = parsed.get(alim)
                if not metrics_row:
                    continue
                metrics = metrics_row
                origem_ganhos_row = row
                token_ganhos_bruto = ganhos_text if len(ganhos_text) <= 500 else ""
                break

            required = ("tensaominima", "tensaomax", "carregamento", "contas")
            use_fallback = True
            if metrics is not None and origem_ganhos_row is not None:
                if all(k in metrics for k in required):
                    origem = "GANHOS_DEPOIS"
                    use_fallback = False
                    codigo_item_origem = str(origem_ganhos_row[idx["item"]]).strip()
                    manobra_usada = origem_ganhos_row[idx["manobra"]]
                else:
                    origem = "GANHOS_INCOMPLETOS_FALLBACK"

            if use_fallback:
                tmin = _conv_float_opt(last_row[idx["tmin"]])
                tmax = _conv_float_opt(last_row[idx["tmax"]])
                carreg = _conv_float_opt(last_row[idx["carreg"]])
                clientes = _conv_int_opt(last_row[idx["clientes"]])
            else:
                assert metrics is not None
                tmin = metrics.get("tensaominima")
                tmax = metrics.get("tensaomax")
                carreg = metrics.get("carregamento")
                clientes = _conv_int_opt(metrics.get("contas"))

            status_ok, motivos, passes, limite_carreg = _avaliar_relatorio(
                tmin, tmax, carreg, clientes, manobra_usada, criterios,
            )
            if status_ok is None:
                status_txt = "DADOS INSUFICIENTES"
                projeto_insuficiente = True
            else:
                status_txt = "OK" if status_ok else "FAIL"

            resumo_origem.append(
                f"{alim}:{'ganhos' if origem == 'GANHOS_DEPOIS' else 'fallback'}"
                if origem != "GANHOS_INCOMPLETOS_FALLBACK"
                else f"{alim}:ganhos_incompletos"
            )

            if status_ok is False:
                projeto_falha = True
                alimentadores_falha.append(alim)
                motivos_falha_set.update(motivos)

            linhas_alim.append({
                "nome_projeto": nome_projeto,
                "alimentador": alim,
                "status": status_txt,
                "origem": origem,
                "codigo_item_origem": str(codigo_item_origem),
                "manobra_usada": str(manobra_usada or ""),
                "contas_usado": "" if clientes is None else str(clientes),
                "carregamento_usado": "" if carreg is None else str(carreg),
                "tensaominima_usado": "" if tmin is None else str(tmin),
                "tensaomax_usado": "" if tmax is None else str(tmax),
                "criterio_tmin": str(criterios["tensao_min"]),
                "criterio_tmax": str(criterios["tensao_max"]),
                "criterio_carregamento_limite": str(limite_carreg),
                "criterio_clientes_max": str(criterios["clientes_maximo"]),
                "passou_tmin": _fmt_flag(passes["tmin"]),
                "passou_tmax": _fmt_flag(passes["tmax"]),
                "passou_carreg": _fmt_flag(passes["carreg"]),
                "passou_clientes": _fmt_flag(passes["clientes"]),
                "token_ganhos_bruto": token_ganhos_bruto,
            })

        linhas_projeto.append({
            "nome_projeto": nome_projeto,
            "pi_base": _first_non_empty(idx["pi_base"]),
            "projeto_investimento": _first_non_empty(idx["pi"]),
            "qtde_obras": str(len(rows_sorted)),
            "codigo_item_min": str(rows_sorted[0][idx["item"]]).strip(),
            "codigo_item_max": str(rows_sorted[-1][idx["item"]]).strip(),
            "alimentadores_projeto": ";".join(sorted(alim_set)),
            "projeto_atende": "DADOS INSUFICIENTES" if projeto_insuficiente
                              else ("NÃO" if projeto_falha else "SIM"),
            "alimentadores_falha": ";".join(alimentadores_falha),
            "motivos_falha": ";".join(sorted(motivos_falha_set)),
            "resumo_origem_dados": ";".join(resumo_origem),
        })

    df_projetos = pd.DataFrame(linhas_projeto).fillna("").astype(str)
    df_alims = pd.DataFrame(linhas_alim).fillna("").astype(str)
    return RelatorioCriterios(df_projetos=df_projetos, df_alimentadores=df_alims)


# ---------------------------------------------------------------------------
# 9. verificar_criterios_v1 (DEPRECATED -- sem callers no codigo5)
# ---------------------------------------------------------------------------
def verificar_criterios_v1(
    obras: Sequence[Sequence[Any]],
    columns: Sequence[str],
    *,
    criterios: Mapping[str, Any],
) -> list[bool | None]:
    """Avaliacao V1 (DEPRECATED -- sem callers no codigo5 desde V2).

    Reproduz ``MainWindow.verificar_criterios_planejamento``
    (L11795-11912). Mantida para nao apagar codigo legado; pode ser
    removida quando nao houver mais callers em nenhuma camada.

    Regra V1 (diferente da V2):
    - Agrupa por ``(nome_projeto, alimentador_principal)``.
    - Se algum item do par atende, status=OK.
    - Caso contrario, usa o ultimo item com ganhos preenchidos.
    """
    cols_list = list(columns)
    idx = {
        "tmin": cols_list.index("tensao_min_final"),
        "tmax": cols_list.index("tensao_max_final"),
        "carreg": cols_list.index("carregamento_final"),
        "manobra": cols_list.index("manobra"),
        "clientes": cols_list.index("contas_contratos_posteriores"),
        "projeto": cols_list.index("nome_projeto"),
        "item": cols_list.index("codigo_item"),
        "alim": cols_list.index("alimentador_principal"),
    }

    def _has_ganhos(row: Sequence[Any]) -> bool:
        campos = [
            row[idx["tmin"]], row[idx["tmax"]],
            row[idx["carreg"]], row[idx["clientes"]],
        ]
        return any(str(c).strip() != "" for c in campos)

    grupos: dict[tuple[str, str], list[Sequence[Any]]] = {}
    for row in obras:
        nome = str(row[idx["projeto"]]).strip()
        alim = str(row[idx["alim"]]).strip()
        if not nome or not alim:
            continue
        grupos.setdefault((nome, alim), []).append(row)

    projeto_alim_result: dict[tuple[str, str], bool | None] = {}
    for chave, rows in grupos.items():
        tmp: list[tuple[Sequence[Any], int]] = []
        for r in rows:
            tmp.append((r, _conv_int(r[idx["item"]])))
        tmp.sort(key=lambda x: x[1], reverse=True)

        status_ok = False
        ultima_com_ganhos: Sequence[Any] | None = None
        for r, _cod_int in tmp:
            if not _has_ganhos(r):
                continue
            if ultima_com_ganhos is None:
                ultima_com_ganhos = r
            atende, _ = obra_atende(r, idx, criterios, _conv_float, _conv_int)
            if atende is True:
                status_ok = True
                break

        if status_ok:
            projeto_alim_result[chave] = True
        elif ultima_com_ganhos is not None:
            atende, _ = obra_atende(
                ultima_com_ganhos, idx, criterios, _conv_float, _conv_int,
            )
            projeto_alim_result[chave] = atende

    resultados: list[bool | None] = []
    for row in obras:
        nome = str(row[idx["projeto"]]).strip()
        alim = str(row[idx["alim"]]).strip()
        if nome and alim:
            chave = (nome, alim)
            if chave in projeto_alim_result:
                resultados.append(projeto_alim_result[chave])
            else:
                atende, _ = obra_atende(row, idx, criterios, _conv_float, _conv_int)
                resultados.append(atende)
        else:
            atende, _ = obra_atende(row, idx, criterios, _conv_float, _conv_int)
            resultados.append(atende)
    return resultados
