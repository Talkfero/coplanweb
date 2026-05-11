"""Servico puro de calculo de Nota de Colapso de uma obra.

Reproduz literalmente as 4 funcoes hoje implementadas em
``CalculationManager`` no ``codigo5_coplan.py`` (linhas 5788-6050):

- ``_calcular_nota_carregamento``
- ``_calcular_nota_tensao_min``  (tabela verdade 4x4)
- ``_calcular_nota_tensao_max``
- ``calcular_nota_colapso``      (orquestracao + fallbacks de campo + escolha)

A logica e mantida 100% identica ao legado para garantir paridade
funcional. Os limites das faixas (67/80/90/100 para carregamento;
0,95/1,03/1,05/1,07 para tensao) sao **constantes do dominio do calculo
de nota de colapso** -- distintos dos ``CriteriosPlanejamento`` (que
governam a avaliacao atende/nao-atende). NAO MISTURAR.

Sem I/O, sem Qt, sem ConfigManager: a UI deve resolver e passar o
``PIMetadata`` do projeto pronto.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

from core.models import NotaColapso, Obra, PIMetadata


# ---------------------------------------------------------------------------
# Helper de parsing (reproduz o ``conv`` lambda do codigo5)
# ---------------------------------------------------------------------------
def _parse_valor(valor: Any) -> float:
    """Converte string para float aceitando os formatos brasileiros.

    Reproduz o ``conv`` inline em ``calcular_nota_colapso_obra``:

    - vazio   -> 0.0
    - "1,03"  -> 1.03
    - "1.03"  -> 1.03
    - "1.234,56" (mil/decimal pt-BR) -> 1234.56
    - "1,234.56" (mil/decimal en)    -> 1.234.56? -- nao tratado, mas o
      legado tambem nao trata.

    A regra "se contem ',' E '.', e a virgula esta DEPOIS do ponto, entao
    o ponto e separador de milhar e a virgula e decimal" reproduz fielmente
    a logica do legado (linhas 5975-5979).
    """
    s = str(valor).strip()
    if s == "":
        return 0.0
    if "," in s and "." in s and s.rfind(",") > s.rfind("."):
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    return float(s)


# ---------------------------------------------------------------------------
# Sub-funcoes de calculo (constantes hardcoded, identicas ao codigo legado)
# ---------------------------------------------------------------------------
def _calcular_nota_carregamento(
    carreg_inicial: float, carreg_max: float
) -> Tuple[Optional[int], str]:
    """Reproduz ``calcular_nota_carregamento`` (linhas 5788-5813)."""
    try:
        if carreg_inicial == 0 or carreg_max == 0:
            return 0, "Carregamento: Dados insuficientes"
        if carreg_max < 67 and carreg_inicial < 67:
            return 1, "Carregamento: <67"
        elif 67 <= carreg_max < 80 and 67 <= carreg_inicial < 80:
            return 3, "Carregamento: 67-80"
        elif 67 <= carreg_max < 80 and 80 <= carreg_inicial < 90:
            return 4, "Carregamento: 67-80 e 80-90"
        elif 80 <= carreg_max < 90 and 80 <= carreg_inicial < 90:
            return 5, "Carregamento: 80-90"
        elif 80 <= carreg_max < 90 and 95 <= carreg_inicial <= 100:
            return 6, "Carregamento: 80-90 e 95-100"
        elif 90 <= carreg_max < 100 and 90 <= carreg_inicial < 100:
            return 7, "Carregamento: 90-100"
        elif 90 <= carreg_max < 100 and carreg_inicial >= 100:
            return 8, "Carregamento: 90-100 e >=100"
        elif carreg_max >= 100 and carreg_inicial >= 100:
            return 9, "Carregamento: >=100"
        else:
            return 0, "Carregamento: Nao definido"
    except Exception:
        return None, "Erro no carregamento"


def _faixa_tensao_min(valor: float) -> int:
    """Faixa indexada para a tabela verdade de tensao minima.

    1 = [0,95-1,03], 2 = [0,93-0,95), 3 = [0,90-0,93), 4 = <0,90, 0 = >1,03.
    """
    if valor < 0.90:
        return 4
    elif valor < 0.93:
        return 3
    elif valor < 0.95:
        return 2
    elif valor <= 1.03:
        return 1
    else:
        return 0


_TABELA_VERDADE_TMIN = {
    (1, 1): (1, "0,95-1,03 / 0,95-1,03"),
    (2, 1): (1, "0,93-0,95 / 0,95-1,03"),
    (3, 1): (1, "0,90-0,93 / 0,95-1,03"),
    (4, 1): (1, "<0,90 / 0,95-1,03"),
    (1, 2): (4, "0,95-1,03 / 0,93-0,95"),
    (1, 3): (5, "0,95-1,03 / 0,90-0,93"),
    (2, 2): (5, "0,93-0,95 / 0,93-0,95"),
    (3, 2): (5, "0,90-0,93 / 0,93-0,95"),
    (4, 2): (5, "<0,90 / 0,93-0,95"),
    (2, 3): (6, "0,93-0,95 / 0,90-0,93"),
    (3, 3): (7, "0,90-0,93 / 0,90-0,93"),
    (4, 3): (7, "<0,90 / 0,90-0,93"),
    (3, 4): (8, "0,90-0,93 / <0,90"),
    (4, 4): (9, "<0,90 / <0,90"),
}


def _calcular_nota_tensao_min(
    tensao_min_atual: float, tensao_min_inicial: float
) -> Tuple[Optional[int], str]:
    """Reproduz ``calcular_nota_tensao_min`` (linhas 5816-5929) com tabela verdade."""
    try:
        if tensao_min_atual == 0 or tensao_min_inicial == 0:
            return 0, "Tensao Minima: Dados insuficientes"
        faixa_atual = _faixa_tensao_min(tensao_min_atual)
        faixa_inicial = _faixa_tensao_min(tensao_min_inicial)
        chave = (faixa_atual, faixa_inicial)
        if chave in _TABELA_VERDADE_TMIN:
            nota, descricao = _TABELA_VERDADE_TMIN[chave]
            return nota, f"Tensao Minima: {descricao}"
        return 0, "Tensao Minima: Nao definido"
    except Exception:
        return None, "Erro na tensao minima"


def _calcular_nota_tensao_max(
    tensao_min_atual: float, tensao_max_inicial: float
) -> Tuple[Optional[int], str]:
    """Reproduz ``calcular_nota_tensao_max`` (linhas 5932-5950)."""
    try:
        if tensao_min_atual == 0 or tensao_max_inicial == 0:
            return 0, "Tensao Maxima: Dados insuficientes"
        if 0.95 <= tensao_min_atual <= 1.03 and 0.95 <= tensao_max_inicial <= 1.03:
            return 1, "Tensao Maxima: 0.95-1.03"
        elif 1.03 < tensao_min_atual <= 1.05 and 1.05 <= tensao_max_inicial <= 1.07:
            return 6, "Tensao Maxima: 1.03-1.05 e 1.05-1.07"
        elif 1.05 < tensao_min_atual <= 1.07 and 1.05 <= tensao_max_inicial <= 1.07:
            return 7, "Tensao Maxima: 1.05-1.07"
        elif 1.05 < tensao_min_atual <= 1.07 and tensao_max_inicial > 1.07:
            return 8, "Tensao Maxima: 1.05-1.07 e >1.07"
        elif tensao_min_atual > 1.07 and tensao_max_inicial > 1.07:
            return 9, "Tensao Maxima: >1.07"
        else:
            return 0, "Tensao Maxima: Nao definido"
    except Exception:
        return None, "Erro na tensao maxima"


# ---------------------------------------------------------------------------
# Funcao publica
# ---------------------------------------------------------------------------
def calcular_nota_colapso(
    obra: Obra,
    pi_metadata: Optional[PIMetadata] = None,
) -> NotaColapso:
    """Calcula a Nota de Colapso de uma obra.

    Reproduz literalmente ``CalculationManager.calcular_nota_colapso_obra``
    do ``codigo5_coplan.py`` (linhas 5963-6050).

    Args:
        obra: a entidade ``Obra`` (do ``core.models``).
        pi_metadata: metadata do PI da obra. Quando ``None`` ou quando o
            criterio do PI nao for ``"tensao"``, escolhe a maior nota
            entre carregamento, tensao_min e tensao_max. Quando o PI tem
            ``criterio_colapso == "tensao"``, considera somente tmin/tmax.

    Returns:
        ``NotaColapso`` com:

        - ``valor``: a nota escolhida (``None`` se houve erro de conversao);
        - ``criterio``: a string descritiva da regra aplicada;
        - ``valores_considerados``: dict com os 5 valores numericos usados
          (carreg_inicial, carreg_max, tensao_min_inicial, tensao_max_inicial,
          tmin_registrada, tmax_registrada). Util para auditoria/relatorio.
    """
    try:
        # 1) Carregamento -- usa carregamento_inicial; se vazio, cai pra final.
        carreg_inicial_str = str(obra.ganhos.antes.carregamento_inicial or "").strip()
        if carreg_inicial_str == "":
            carreg_inicial_str = str(obra.ganhos.depois.carregamento_final or "").strip()
        carreg_inicial = _parse_valor(carreg_inicial_str)

        carreg_max = _parse_valor(obra.ganhos.atual.carregamento_max_registrado_atual)

        # 2) Tensao min inicial -- usa inicial; se vazio, cai pra final.
        tmin_ini_str = str(obra.ganhos.antes.tensao_min_inicial or "").strip()
        if tmin_ini_str == "":
            tmin_ini_str = str(obra.ganhos.depois.tensao_min_final or "").strip()
        tensao_min_inicial = _parse_valor(tmin_ini_str)

        # 3) Tensao max inicial -- usa inicial; se vazio, cai pra final.
        tmax_ini_str = str(obra.ganhos.antes.tensao_max_inicial or "").strip()
        if tmax_ini_str == "":
            tmax_ini_str = str(obra.ganhos.depois.tensao_max_final or "").strip()
        tensao_max_inicial = _parse_valor(tmax_ini_str)

        # 4) Tensao registrada (atual) -- pode vir como "x/y"; senao usa
        # como min e copia para max. Se vazio, cai pra tensao_min_inicial.
        treg_str = str(
            obra.ganhos.atual.tensao_min_registrada_atual or ""
        ).strip()
        if treg_str == "":
            treg_str = str(obra.ganhos.antes.tensao_min_inicial or "").strip()

        if "/" in treg_str:
            partes = treg_str.split("/")
            if len(partes) != 2:
                tmin_registrada = _parse_valor(partes[0])
                tmax_registrada = _parse_valor(partes[0])
            else:
                tmin_registrada = _parse_valor(partes[0])
                tmax_registrada = _parse_valor(partes[1])
        else:
            tmin_registrada = _parse_valor(treg_str)
            tmax_registrada = tmin_registrada

    except Exception as exc:
        return NotaColapso(
            valor=None,
            criterio=f"Erro na conversao dos valores: {exc}",
        )

    # 5) Calcula as 3 sub-notas
    nota_carreg, crit_carreg = _calcular_nota_carregamento(carreg_inicial, carreg_max)
    nota_tmin, crit_tmin = _calcular_nota_tensao_min(tmin_registrada, tensao_min_inicial)
    nota_tmax, crit_tmax = _calcular_nota_tensao_max(tmax_registrada, tensao_max_inicial)

    valores_considerados = {
        "carreg_inicial": carreg_inicial,
        "carreg_max": carreg_max,
        "tensao_min_inicial": tensao_min_inicial,
        "tensao_max_inicial": tensao_max_inicial,
        "tmin_registrada": tmin_registrada,
        "tmax_registrada": tmax_registrada,
    }

    # 6) Escolha do criterio dependendo do PI
    criterio_pi = ""
    if pi_metadata is not None:
        criterio_pi = (pi_metadata.calculo.criterio_colapso or "").strip().lower()

    if criterio_pi == "tensao":
        # PIs de criterio "tensao": ignora carregamento. Usa o maior entre
        # tmin e tmax. Trata None como -1 (mesma logica do legado).
        val_tmin = -1 if nota_tmin is None else float(nota_tmin)
        val_tmax = -1 if nota_tmax is None else float(nota_tmax)
        if val_tmin >= val_tmax:
            return NotaColapso(
                valor=nota_tmin,
                criterio=crit_tmin,
                valores_considerados=valores_considerados,
            )
        return NotaColapso(
            valor=nota_tmax,
            criterio=crit_tmax,
            valores_considerados=valores_considerados,
        )

    # Demais PIs: maior das 3 notas.
    candidatos = [
        (nota_carreg, crit_carreg),
        (nota_tmin, crit_tmin),
        (nota_tmax, crit_tmax),
    ]
    melhor_nota, melhor_crit = max(
        candidatos, key=lambda x: x[0] if x[0] is not None else -1
    )
    return NotaColapso(
        valor=melhor_nota,
        criterio=melhor_crit,
        valores_considerados=valores_considerados,
    )
