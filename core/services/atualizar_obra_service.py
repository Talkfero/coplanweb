"""Servico de dominio para a operacao de **Atualizar Obras**.

Extraido de ``codigo5_coplan.py::MainWindow.atualizar_obras`` na Etapa B.2.

Este modulo contem **apenas** a logica pura que estava emaranhada no
``atualizar_obras``: extracao de campos da tupla retornada pelo banco,
validacao de quantidade, montagem da chave de modulo, busca de valor na
planilha de apoio (``MODULO``) e agregacao do calculo final do valor da
obra (incluindo chaves extras por PI). A orquestracao -- QMessageBox,
QInputDialog, QDialog para selecionar PIs, leitura do Excel de apoio,
``db_manager.update_obra`` e geracao do TXT com chaves inexistentes --
**continua** em ``MainWindow.atualizar_obras``.

Convencoes:

- Funcoes nao mutam argumentos -- sempre devolvem dataclass/tupla.
- Mensagens de falha (``motivo_falha``) reproduzem char-a-char os textos
  que iam ao ``falhas`` no legado, exceto o prefixo ``"COD=... :"`` que
  permanece responsabilidade do agregador.
- Sem dependencia de PySide6 (verificado pelo ``test_core_purity``).
- Pandas e dependencia liberada (ja consumido por ``apoio_service``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

import pandas as pd


# ---------------------------------------------------------------------------
# 1. Dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class AtualizarObraInput:
    """Snapshot puro dos campos de uma obra extraidos do banco.

    Todos os campos chegam **ja normalizados** (ver ``extrair_obra_input``):
    ``.strip()``, ``.upper()`` e ``.replace(",", ".")`` quando aplicavel.
    Valor de ``quantidade_material`` e mantido como string crua para que
    ``validar_quantidade`` reproduza o ``ValueError`` do legado.

    ``obra_data_map`` espelha o mapping ``{col: valor}`` montado na linha
    14657 do legado, usado pelo ``gerar_descricao_obra``. Fica no Input
    para a UI consumir apos sucesso (o service nao chama ``calc_manager``).
    """

    cod: str
    projeto_investimento: str
    pi_base: str
    nivel_tensao: str
    tensao_op: str
    caracteristicas_material: str
    nome_regional: str
    quantidade_material: str
    obra_data_map: Mapping[str, Any]


@dataclass(frozen=True)
class AtualizarObraResult:
    """Resultado da avaliacao de UMA obra.

    Campos:

    - ``cod``: cod da obra (para a UI compor a mensagem de falha).
    - ``sucesso_base``: ``True`` se a parte base (qtd, regional, chave,
      valor base) foi calculada com sucesso. Mesmo com sucesso_base, pode
      haver falhas em chaves extras (ver ``motivos_falha``).
    - ``valor_obra_formatado``: ``"1234,56"`` pronto para o UPDATE quando
      ``sucesso_base`` e ``True``; ``None`` caso contrario.
    - ``chave_completa``: chave de modulo computada (``None`` apenas nos
      casos em que a regional nao foi resolvida).
    - ``motivos_falha``: lista de mensagens de falha (sem o prefixo
      ``"COD=..."``). Pode conter falhas da base **e/ou** das extras.
    - ``chaves_inexistentes``: chaves de modulo nao encontradas (base e/ou
      extras), para o agregador acumular no relatorio TXT.
    """

    cod: str
    sucesso_base: bool
    valor_obra_formatado: str | None
    chave_completa: str | None
    motivos_falha: list[str] = field(default_factory=list)
    chaves_inexistentes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProcessamentoResult:
    """Agregado de uma rodada de ``processar_atualizacao``.

    Espelha 1:1 os contadores do loop legado (linhas 14528-14676):

    - ``processadas_ok`` = obras com ``sucesso_base``.
    - ``falhas_total`` = soma de ``len(r.motivos_falha)`` por result.
    - ``falhas`` = ate ``falhas_max`` mensagens completas com prefixo
      ``"COD=<cod ou N/D>: <motivo>"``.
    - ``chaves_inexistentes`` = uniao de todas as ``chaves_inexistentes``.

    O caller (UI) ainda precisa iterar ``results`` para chamar
    ``update_obra`` e (opcionalmente) ``gerar_descricao_obra``.
    """

    results: list[AtualizarObraResult]
    processadas_ok: int
    falhas_total: int
    falhas: list[str]
    chaves_inexistentes: set[str]


# ---------------------------------------------------------------------------
# 2. Extracao de campos da tupla obra[cols]
# ---------------------------------------------------------------------------
def extrair_obra_input(
    obra: Sequence[Any],
    cols: Sequence[str],
    *,
    pi_base_fallback_fn: Callable[[str], str],
) -> AtualizarObraInput:
    """Reproduz as linhas 14545-14557 do legado.

    Faz o ``.strip()``/``.upper()`` (e ``.replace(",", ".")`` onde
    aplicavel) **identico** ao legado. Quando a coluna ``pi_base`` nao
    existe na tabela, delega ao ``pi_base_fallback_fn`` (a UI passa
    ``lambda pi: get_pi_base(pi, prompt_user=False)``, que e puro nessa
    chamada).

    Quando ``pi_base`` existe mas vem vazia, RESOLVE via
    ``pi_base_fallback_fn`` (mesma rota usada quando a coluna nao
    existe). Antes, caia em ``projeto_investimento`` cru -- texto
    longo tipo "INSTALACAO DE BANCOS DE CAPACITORES" -- que nao
    casava com chave nenhuma na planilha MODULO, fazendo o calculo
    falhar com "chave inexistente". O cadastro (calcular_valor_obra
    RPC) sempre fez essa resolucao, criando uma divergencia entre
    os dois caminhos.
    """

    def _at(col: str) -> str:
        return str(obra[cols.index(col)])

    projeto_investimento = _at("projeto_investimento").strip().upper()
    if "pi_base" in cols:
        pi_base_raw = _at("pi_base").strip().upper()
    else:
        pi_base_raw = ""
    if pi_base_raw:
        pi_base = pi_base_raw
    else:
        pi_base = (
            pi_base_fallback_fn(projeto_investimento).strip().upper()
            or projeto_investimento
        )

    nivel_tensao = _at("nivel_tensao_obra").strip().replace(",", ".").upper()

    if "tensao_operacao" in cols:
        tensao_op = _at("tensao_operacao").strip()
    else:
        tensao_op = _at("nivel_tensao_obra").strip()

    caracteristicas_material = _at("caracteristicas_material").strip().upper()
    nome_regional = _at("nome_regional").strip().upper()
    quantidade_material = _at("quantidade_material").strip().replace(",", ".")

    obra_data_map = {col: obra[i] for i, col in enumerate(cols)}
    cod = ""
    if "cod" in cols:
        cod = str(obra[cols.index("cod")])

    return AtualizarObraInput(
        cod=cod,
        projeto_investimento=projeto_investimento,
        pi_base=pi_base,
        nivel_tensao=nivel_tensao,
        tensao_op=tensao_op,
        caracteristicas_material=caracteristicas_material,
        nome_regional=nome_regional,
        quantidade_material=quantidade_material,
        obra_data_map=obra_data_map,
    )


# ---------------------------------------------------------------------------
# 3. Validacao de quantidade
# ---------------------------------------------------------------------------
def validar_quantidade(qtd_str: str) -> tuple[float | None, str | None]:
    """Reproduz linhas 14559-14566 do legado.

    Devolve ``(valor_float, motivo_falha)``: exatamente um dos dois e
    ``None``. Nao tenta normalizar virgula -- isso ja foi feito em
    ``extrair_obra_input``.
    """
    try:
        return float(qtd_str), None
    except (ValueError, TypeError):
        return None, "quantidade inválida"


# ---------------------------------------------------------------------------
# 4. Montagem da chave de modulo (incluindo regional)
# ---------------------------------------------------------------------------
def montar_chave_completa(
    inp: AtualizarObraInput,
    regional_map: Mapping[str, str],
) -> tuple[str | None, str | None, str | None]:
    """Reproduz linhas 14569-14580 do legado.

    Devolve ``(chave_completa, codigo_regional, motivo_falha)``:

    - Sucesso: ``("PI-NIV-CARAC_REG-XXXX", "REG-XXXX", None)``.
    - Regional ausente do ``regional_map``: ``(None, None, "regional nao
      encontrada")``. Note que a chave-sem-regional (que vai pra
      ``chaves_inexistentes``) e calculada por ``calcular_valor_obra``,
      nao aqui (precisa de ``projeto_investimento``).
    """
    codigo_regional = regional_map.get(inp.nome_regional)
    if not codigo_regional:
        return None, None, "regional não encontrada"
    chave_completa = (
        f"{inp.pi_base}-{inp.nivel_tensao}-{inp.caracteristicas_material}_{codigo_regional}"
    )
    return chave_completa, codigo_regional, None


# ---------------------------------------------------------------------------
# 5. Busca do valor base na planilha de modulo
# ---------------------------------------------------------------------------
def buscar_valor_modulo(
    df_modulo: pd.DataFrame,
    *,
    col_chave: str,
    col_valor: str,
    chave: str,
) -> tuple[float | None, bool, str | None]:
    """Reproduz linhas 14582-14609 do legado.

    Aplica mascara case-insensitive (``.astype(str).str.strip().str.upper()
    == chave``), soma todos os ``valor_item`` correspondentes e devolve:

    - ``(total, True, None)`` em sucesso.
    - ``(None, False, "chave de modulo nao encontrada")`` se mask vazia.
    - ``(None, False, f"valor invalido para {chave}")`` se ``to_numeric``
      falhar.

    O parametro ``chave`` e comparado **literalmente** (a UI passa a chave
    ja em UPPER); aqui o ``.upper()`` da coluna casa com isso.
    """
    serie_chaves = (
        df_modulo[col_chave]
        .astype(str)
        .str.strip()
        .str.upper()
    )
    mask = serie_chaves == chave
    valores = df_modulo.loc[mask, col_valor]
    if valores.empty:
        return None, False, "chave de módulo não encontrada"
    try:
        valores_float = pd.to_numeric(
            valores.astype(str).str.replace(",", "."), errors="raise"
        )
    except Exception:
        return None, False, f"valor inválido para {chave}"
    return float(valores_float.sum()), True, None


# ---------------------------------------------------------------------------
# 6. Calculo completo de uma obra
# ---------------------------------------------------------------------------
def calcular_valor_obra(
    inp: AtualizarObraInput,
    df_modulo: pd.DataFrame,
    *,
    col_chave: str,
    col_valor: str,
    regional_map: Mapping[str, str],
    extra_keys_for_pi: Sequence[str],
) -> AtualizarObraResult:
    """Orquestra as etapas 3-5 + chaves extras para uma obra.

    Reproduz linhas 14559-14653 do legado. O caller (a UI ou
    ``processar_atualizacao``) e responsavel por resolver
    ``extra_keys_for_pi`` (i.e., a uniao de
    ``get_pi_extra_module_keys(pi_base)`` com as entradas do
    ``extra_key_map`` cuja lista de PIs contem ``inp.pi_base``).

    Quando ``sucesso_base`` for ``False``, ``valor_obra_formatado`` e
    ``None`` e a UI deve **pular** o ``update_obra``. Quando
    ``sucesso_base`` for ``True`` mas ``motivos_falha`` nao-vazio, a UI
    procede com o ``update_obra`` mas tambem reporta as falhas das
    chaves extras (mesmo comportamento do legado, ver linha 14671).
    """
    motivos: list[str] = []
    chaves_inex: list[str] = []

    # 1. Quantidade
    qtd_val, motivo = validar_quantidade(inp.quantidade_material)
    if motivo is not None:
        return AtualizarObraResult(
            cod=inp.cod,
            sucesso_base=False,
            valor_obra_formatado=None,
            chave_completa=None,
            motivos_falha=[motivo],
            chaves_inexistentes=[],
        )

    # 2. Regional / chave base
    chave, codigo_regional, motivo = montar_chave_completa(inp, regional_map)
    if motivo is not None:
        chave_sem_regional = (
            f"{inp.projeto_investimento}-{inp.nivel_tensao}-{inp.caracteristicas_material}"
        )
        return AtualizarObraResult(
            cod=inp.cod,
            sucesso_base=False,
            valor_obra_formatado=None,
            chave_completa=None,
            motivos_falha=[motivo],
            chaves_inexistentes=[chave_sem_regional],
        )

    # 3. Valor base
    assert chave is not None and codigo_regional is not None
    valor_base, ok, motivo = buscar_valor_modulo(
        df_modulo,
        col_chave=col_chave,
        col_valor=col_valor,
        chave=chave,
    )
    if not ok:
        if motivo == "chave de módulo não encontrada":
            chaves_inex.append(
                f"{inp.pi_base}-{inp.nivel_tensao}-{inp.caracteristicas_material}"
            )
        return AtualizarObraResult(
            cod=inp.cod,
            sucesso_base=False,
            valor_obra_formatado=None,
            chave_completa=chave,
            motivos_falha=[motivo or ""],
            chaves_inexistentes=chaves_inex,
        )

    # 4. Chaves extras (nao-bloqueantes)
    valor_unitario_total = valor_base or 0.0
    extras_seen: set[str] = set()
    for key in extra_keys_for_pi:
        kn = str(key or "").strip().upper()
        if not kn or kn in extras_seen:
            continue
        extras_seen.add(kn)
        chave_extra = f"{kn}_{codigo_regional}"
        valor_extra, ok_e, motivo_e = buscar_valor_modulo(
            df_modulo,
            col_chave=col_chave,
            col_valor=col_valor,
            chave=chave_extra,
        )
        if not ok_e:
            if motivo_e == "chave de módulo não encontrada":
                chaves_inex.append(chave_extra)
                motivos.append(f"chave extra ausente {chave_extra}")
            else:
                motivos.append(motivo_e or f"valor inválido para {chave_extra}")
            continue
        valor_unitario_total += float(valor_extra or 0.0)

    # 5. Sucesso base (mesmo com extras com falha)
    valor_total = round(valor_unitario_total * qtd_val, 2)
    valor_formatado = str(valor_total).replace(".", ",")
    return AtualizarObraResult(
        cod=inp.cod,
        sucesso_base=True,
        valor_obra_formatado=valor_formatado,
        chave_completa=chave,
        motivos_falha=motivos,
        chaves_inexistentes=chaves_inex,
    )


# ---------------------------------------------------------------------------
# 7. Loop agregador
# ---------------------------------------------------------------------------
def _resolver_extra_keys(
    pi_base: str,
    *,
    extra_key_map: Mapping[str, Sequence[str]],
    pi_extra_module_keys_fn: Callable[[str], Sequence[str]],
) -> list[str]:
    """Reproduz linhas 14612-14615 do legado (resolucao de extras).

    Junta ``get_pi_extra_module_keys(pi_base)`` (vindo da config) com as
    entradas do ``extra_key_map`` (vindo dos dialogos do usuario) cuja
    lista de PIs contem ``pi_base``. Mantem ordem e duplicatas; a
    deduplicacao acontece dentro de ``calcular_valor_obra``.
    """
    extras = list(pi_extra_module_keys_fn(pi_base))
    for key, pi_list in extra_key_map.items():
        if pi_base in pi_list:
            extras.append(key)
    return extras


def processar_atualizacao(
    inputs: Sequence[AtualizarObraInput],
    df_modulo: pd.DataFrame,
    *,
    col_chave: str,
    col_valor: str,
    regional_map: Mapping[str, str],
    extra_key_map: Mapping[str, Sequence[str]],
    pi_extra_module_keys_fn: Callable[[str], Sequence[str]],
    falhas_max: int = 5,
) -> ProcessamentoResult:
    """Loop agregador puro -- itera ``inputs`` e devolve relatorio.

    Reproduz a contabilidade do loop legado (linhas 14535-14676) mas sem
    ``QMessageBox``, sem ``self.db_manager.update_obra`` e sem
    ``calc_manager.gerar_descricao_obra``. A UI pega ``result.results``,
    pega cada result com ``sucesso_base==True`` e chama:

    1. ``calc_manager.gerar_descricao_obra(input.pi_base, input.obra_data_map)``
       quando ``atualizar_descricao`` for True.
    2. ``db_manager.update_obra({"valor_obra": result.valor_obra_formatado,
       ["descricao_obra": descricao]}, cod, skip_blank=True)``.

    O ``falhas_max`` (5 por default) reproduz o ``if len(falhas) < 5:`` do
    legado. O contador ``falhas_total`` continua incrementando alem desse
    limite (so a lista visivel e capada).
    """
    results: list[AtualizarObraResult] = []
    processadas_ok = 0
    falhas_total = 0
    falhas: list[str] = []
    chaves_inex: set[str] = set()

    for inp in inputs:
        extras = _resolver_extra_keys(
            inp.pi_base,
            extra_key_map=extra_key_map,
            pi_extra_module_keys_fn=pi_extra_module_keys_fn,
        )
        result = calcular_valor_obra(
            inp,
            df_modulo,
            col_chave=col_chave,
            col_valor=col_valor,
            regional_map=regional_map,
            extra_keys_for_pi=extras,
        )
        results.append(result)
        if result.sucesso_base:
            processadas_ok += 1
        for motivo in result.motivos_falha:
            falhas_total += 1
            if len(falhas) < falhas_max:
                falhas.append(f"COD={result.cod or 'N/D'}: {motivo}")
        for ch in result.chaves_inexistentes:
            chaves_inex.add(ch)

    return ProcessamentoResult(
        results=results,
        processadas_ok=processadas_ok,
        falhas_total=falhas_total,
        falhas=falhas,
        chaves_inexistentes=chaves_inex,
    )
