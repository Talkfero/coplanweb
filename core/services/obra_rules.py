"""Regras de negocio puras sobre rows de obra (dicts).

Migrado das funcoes top-level de ``codigo5_coplan.py``/``parte_03``
(Passo 6d). Reproduz literalmente o comportamento legado.

Estas funcoes operam sobre ``row: dict`` (sem tipagem estatica) -- contrato
diferente da dataclass ``Obra`` em ``core.models.obra``, que usa atributos
canonicos. As duas formas convivem:

- ``Obra.is_aprovada()``     -- consulta ``dados.obra_aprovada`` (snake_case);
- ``obra_rules.is_aprovada(row)`` -- consulta ``row["Obra Aprovada"]``
  (formato legado da UI/Excel/widget de tabela).

A logica de validacao e identica nos dois caminhos.
"""
from __future__ import annotations

from typing import Any, Sequence

from core.services.row_helpers import (
    expand_key_variants,
    first_non_empty_value,
    get_row_value_by_key,
    has_any_value,
    normalize_description,
    row_has_any_key,
    parse_float_brl,
)
from shared.texto_utils import normalize_key


# ---------------------------------------------------------------------------
# Constantes migradas do codigo5_coplan.py (linhas ~1885-2020)
# ---------------------------------------------------------------------------
CAMPOS_CRITICOS_MUDANCA = [
    "pi_base",
    "ano_",
    "tipo_pacote",
    "alimentador_principal",
    "municipio",
    "ganhos_totais_antes",
    "ganhos_totais_depois",
    "ganhos_totais_atual",
    "criterios_status",
    "descricao_obra",
]

GANHOS_NUMERIC_FIELDS = {
    "quantidade_material",
    "contas_contratos_previos",
    "contas_contratos_posteriores",
    "contas_contratos_beneficiadas",
    "carregamento_inicial",
    "carregamento_final",
    "perdas_iniciais",
    "perdas_finais",
    "tensao_media_inicial",
    "tensao_media_final",
    "tensao_min_inicial",
    "tensao_min_final",
    "tensao_min_linha_inicial",
    "tensao_min_linha_final",
    "chi_inicial",
    "ci_inicial",
    "tensao_max_inicial",
    "tensao_max_final",
    "tensao_min_registrada_atual",
    "carregamento_max_registrado_atual",
    "valor_obra",
    "cc_benef_chi_ci",
    "chi_final",
    "ci_final",
    "ganhos_totais_antes",
    "ganhos_totais_depois",
    "ganhos_totais_atual",
}

GANHOS_ANTES_FIELDS = [
    "contas_contratos_previos",
    "carregamento_inicial",
    "perdas_iniciais",
    "tensao_media_inicial",
    "tensao_min_inicial",
    "tensao_min_linha_inicial",
    "chi_inicial",
    "ci_inicial",
    "tensao_max_inicial",
    "ganhos_totais_antes",
]

GANHOS_DEPOIS_FIELDS = [
    "contas_contratos_posteriores",
    "carregamento_final",
    "perdas_finais",
    "tensao_media_final",
    "tensao_min_final",
    "tensao_min_linha_final",
    "chi_final",
    "ci_final",
    "tensao_max_final",
    "ganhos_totais_depois",
]

GANHO_TOTAL_FIELDS = [
    "ganho_total",
    "ganhos_total",
    "ganhos_totais_atual",
]

GANHO_ANTES_TOTAL_FIELDS = [
    "ganho_antes",
    "ganhos_antes",
    "ganho_total_antes",
    "ganhos_totais_antes",
]

GANHO_DEPOIS_TOTAL_FIELDS = [
    "ganho_depois",
    "ganhos_depois",
    "ganho_total_depois",
    "ganhos_totais_depois",
]


# ---------------------------------------------------------------------------
# Predicados / chaves de identificacao
# ---------------------------------------------------------------------------
def is_aprovada(row: dict) -> bool:
    """``True`` se row indica obra aprovada (chave ``"Obra Aprovada"``)."""
    valor = row.get("Obra Aprovada", "")
    return str(valor or "").strip().upper() == "SIM"


def is_tecnico_dirty_value(value: Any) -> bool:
    """``True`` se ``value`` representa estado "tecnico_dirty" (SIM/1/TRUE/S)."""
    return str(value or "").strip().upper() in {"SIM", "1", "TRUE", "S"}


def build_scope_key(row: dict) -> str:
    """Chave de escopo: ``pacote|alimentador|ano``."""
    pacote = (
        row.get("pacote")
        or row.get("pasta_tecnica")
        or row.get("pasta t\u00e9cnica")
        or row.get("tipo_pacote")
        or ""
    )
    alimentador = (
        row.get("alimentador")
        or row.get("alimentador_principal")
        or row.get("circuito")
        or ""
    )
    ano = row.get("ano") or row.get("ano_") or ""
    pacote = str(pacote or "").strip()
    alimentador = str(alimentador or "").strip()
    ano = str(ano or "").strip()
    if not (pacote or alimentador or ano):
        return ""
    return f"{pacote}|{alimentador}|{ano}"


def build_dup_key(row: dict) -> str:
    """Chave para detectar duplicidade de obra.

    ``"COD_OBRA:<cod>"`` se cod presente, senao ``"COMP:<alim>|<municipio>|<descr>|<pi>|<ano>"``.
    """
    cod_obra = first_non_empty_value(
        row, ["cod_obra", "cod obra", "codigo_obra", "codigo obra", "cod", "id"]
    )
    if cod_obra:
        return f"COD_OBRA:{cod_obra}"

    alim = first_non_empty_value(
        row, ["alimentador", "alimentador_principal", "circuito"]
    )
    municipio = first_non_empty_value(row, ["municipio", "munic\u00edpio"])
    descricao = normalize_description(
        first_non_empty_value(row, ["descricao_obra", "descricao", "descri\u00e7\u00e3o"])
    )
    pi_base = first_non_empty_value(
        row, ["pi_base", "pi base", "pi", "projeto_investimento"]
    )
    ano = first_non_empty_value(row, ["ano", "ano_", "plano"])
    return f"COMP:{alim}|{municipio}|{descricao}|{pi_base}|{ano}"


def row_id_value(row: dict) -> str:
    """Retorna o id efetivo de uma row (cod, codigo, codigo_item, id)."""
    return first_non_empty_value(
        row, ["id", "cod", "codigo", "codigo_item", "cod_obra", "codigo obra"]
    )


def sort_row_id(value: Any) -> tuple[int, Any]:
    """Chave de ordenacao para ids: numericos antes, depois alfabeticos."""
    text = str(value or "").strip()
    if not text:
        return (1, "")
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)


# ---------------------------------------------------------------------------
# Validacoes
# ---------------------------------------------------------------------------
def row_integrity_reasons(row: dict, requires_municipio: bool = False) -> list[str]:
    """Lista motivos pelos quais ``row`` nao atende integridade minima."""
    reasons: list[str] = []
    pi_base = first_non_empty_value(
        row, ["pi_base", "pi base", "pi", "projeto_investimento"]
    )
    ano = first_non_empty_value(row, ["ano", "ano_", "plano"])
    cod = first_non_empty_value(row, ["cod", "codigo", "codigo_item", "id"])
    alimentador = first_non_empty_value(
        row, ["alimentador", "alimentador_principal", "circuito"]
    )
    pacote = first_non_empty_value(
        row, ["pacote", "pasta_tecnica", "pasta t\u00e9cnica", "tipo_pacote"]
    )
    municipio = (
        first_non_empty_value(row, ["municipio", "munic\u00edpio"])
        if requires_municipio
        else ""
    )
    if not pi_base:
        reasons.append("Sem PI_BASE")
    if not ano:
        reasons.append("Sem Ano")
    if not cod:
        reasons.append("Sem COD/ID")
    if not alimentador:
        reasons.append("Sem Alimentador")
    if not pacote:
        reasons.append("Sem Pacote")
    if requires_municipio and not municipio:
        reasons.append("Sem Munic\u00edpio")
    return reasons


def validate_min_integrity(
    rows: list[dict],
) -> tuple[bool, dict[str, int], list[str]]:
    """Conta motivos de falha em uma lista de rows."""
    counters = {
        "Sem PI_BASE": 0,
        "Sem Ano": 0,
        "Sem COD/ID": 0,
        "Sem Alimentador": 0,
        "Sem Pacote": 0,
        "Sem Munic\u00edpio": 0,
    }
    samples: list[str] = []
    requires_municipio = any(
        row_has_any_key(row, ["municipio", "munic\u00edpio"]) for row in rows
    )

    for row in rows:
        reasons: list[str] = []
        pi_base = first_non_empty_value(
            row, ["pi_base", "pi base", "pi", "projeto_investimento"]
        )
        ano = first_non_empty_value(row, ["ano", "ano_", "plano"])
        cod = first_non_empty_value(row, ["cod", "codigo", "codigo_item", "id"])
        alimentador = first_non_empty_value(
            row, ["alimentador", "alimentador_principal", "circuito"]
        )
        pacote = first_non_empty_value(
            row, ["pacote", "pasta_tecnica", "pasta t\u00e9cnica", "tipo_pacote"]
        )
        municipio = (
            first_non_empty_value(row, ["municipio", "munic\u00edpio"])
            if requires_municipio
            else ""
        )
        if not pi_base:
            reasons.append("Sem PI_BASE")
        if not ano:
            reasons.append("Sem Ano")
        if not cod:
            reasons.append("Sem COD/ID")
        if not alimentador:
            reasons.append("Sem Alimentador")
        if not pacote:
            reasons.append("Sem Pacote")
        if requires_municipio and not municipio:
            reasons.append("Sem Munic\u00edpio")

        for reason in reasons:
            counters[reason] += 1
        if reasons and len(samples) < 5:
            samples.append(f"COD={cod or 'N/D'}, motivo={reasons[0]}")

    ok = all(count == 0 for count in counters.values())
    return ok, counters, samples


def validate_ganhos_consistency(
    row: dict, tolerancia: float
) -> tuple[bool, list[str]]:
    """Valida consistencia dos campos de ganhos em ``row``."""
    errors: list[str] = []
    has_antes = has_any_value(row, GANHOS_ANTES_FIELDS)
    has_depois = has_any_value(row, GANHOS_DEPOIS_FIELDS)

    if has_antes and not has_depois:
        errors.append("Depois vazio")
    if has_depois and not has_antes:
        errors.append("Antes vazio")

    ganho_total_raw = first_non_empty_value(row, expand_key_variants(GANHO_TOTAL_FIELDS))
    ganho_antes_raw = first_non_empty_value(
        row, expand_key_variants(GANHO_ANTES_TOTAL_FIELDS)
    )
    ganho_depois_raw = first_non_empty_value(
        row, expand_key_variants(GANHO_DEPOIS_TOTAL_FIELDS)
    )
    ganho_total = parse_float_brl(ganho_total_raw)
    ganho_antes = parse_float_brl(ganho_antes_raw)
    ganho_depois = parse_float_brl(ganho_depois_raw)
    if (
        ganho_total is not None
        and ganho_antes is not None
        and ganho_depois is not None
        and abs(ganho_total - (ganho_depois - ganho_antes)) > tolerancia
    ):
        errors.append("Ganho total inconsistente")

    criterios_status = get_row_value_by_key(row, "criterios_status")
    if normalize_key(criterios_status) == "DADOS_INSUFICIENTES":
        errors.append(
            "Crit\u00e9rios insuficientes para exporta\u00e7\u00e3o dependente de ganhos"
        )
    return len(errors) == 0, errors


# ---------------------------------------------------------------------------
# Filtros / ordenacao / formatacao
# ---------------------------------------------------------------------------
def filter_targets_by_aprovacao(
    rows: list[dict], include_aprovadas: bool
) -> tuple[list[dict], int]:
    """Filtra rows: se ``include_aprovadas=False``, ignora rows aprovadas.

    Retorna ``(filtradas, ignoradas)``.
    """
    if include_aprovadas:
        return rows, 0
    filtradas = []
    ignoradas = 0
    for row in rows:
        if is_aprovada(row):
            ignoradas += 1
        else:
            filtradas.append(row)
    return filtradas, ignoradas


def sort_processing_rows(
    rows: list[dict],
    selected_ids: set[str],
    include_aprovadas: bool,
) -> list[dict]:
    """Ordena rows para processamento: selecionadas primeiro, nao aprovadas
    antes das aprovadas, dirty antes de clean, depois por id.

    Reproduz ``sort_processing_rows`` do codigo5.
    """
    del include_aprovadas  # legado nao usa internamente

    def _sort_key(row: dict) -> tuple[int, int, int, int, Any]:
        rid = row_id_value(row)
        is_selected = 0 if rid and rid in selected_ids else 1
        is_row_aprovada = 1 if is_aprovada(row) else 0
        dirty_raw = get_row_value_by_key(row, "tecnico_dirty")
        is_dirty = 0 if is_tecnico_dirty_value(dirty_raw) else 1
        id_rank, id_value = sort_row_id(rid)
        return (is_selected, is_row_aprovada, is_dirty, id_rank, id_value)

    return sorted(rows, key=_sort_key)


def format_processing_summary(
    action_label: str,
    processadas_ok: int,
    ignoradas_aprovadas: int,
    ignoradas_integridade: int,
    falhas_total: int,
    falhas: list[str],
) -> str:
    """Formata mensagem de resumo de processamento em PT-BR.

    Reproduz ``_format_processing_summary`` do codigo5 (textos preservados).
    """
    resumo = [
        f"Processadas com sucesso: {processadas_ok}",
        f"Ignoradas (aprovadas): {ignoradas_aprovadas}",
        f"Ignoradas (integridade): {ignoradas_integridade}",
        f"Falhas: {falhas_total}",
    ]
    message = (
        f"{action_label} conclu\u00eddo.\n\nResumo:\n" + "\n".join(resumo)
    )
    if falhas:
        message += "\n\nPrimeiros erros:\n" + "\n".join(
            f"- {err}" for err in falhas
        )
    return message


def diff_fields(old: dict, new: dict, fields: list[str]) -> list[str]:
    """Lista campos cujo valor em ``new`` difere de ``old``.

    Reproduz ``diff_fields`` do codigo5: comparacao via ``str().strip()``.
    """
    changed = []
    for field in fields:
        if field in old or field in new:
            old_val = "" if old.get(field) is None else str(old.get(field)).strip()
            new_val = "" if new.get(field) is None else str(new.get(field)).strip()
            if old_val != new_val:
                changed.append(field)
    return changed


# ---------------------------------------------------------------------------
# Variantes _strict (Passo 7) -- levantam excecoes em vez de retornar tupla
# ---------------------------------------------------------------------------
from core.exceptions import GanhosInconsistentesError, RowIntegrityError


def validate_min_integrity_strict(rows: list[dict]) -> None:
    """Variante de ``validate_min_integrity`` que levanta excecao.

    Raises:
        RowIntegrityError: com ``reasons`` (lista de motivos unicos),
            ``counters`` (contadores agregados) e ``samples`` (5 primeiros
            exemplos COD/motivo).

    Util quando o caller prefere try/except a verificar tupla. A versao
    nao-strict (``validate_min_integrity``) continua existindo.
    """
    ok, counters, samples = validate_min_integrity(rows)
    if ok:
        return
    reasons = [label for label, count in counters.items() if count > 0]
    raise RowIntegrityError(reasons, counters=counters, samples=samples)


def validate_ganhos_consistency_strict(row: dict, tolerancia: float) -> None:
    """Variante de ``validate_ganhos_consistency`` que levanta excecao.

    Raises:
        GanhosInconsistentesError: com lista de erros encontrados.
    """
    ok, errors = validate_ganhos_consistency(row, tolerancia)
    if ok:
        return
    raise GanhosInconsistentesError(errors)

