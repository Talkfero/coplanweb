"""Servico de dominio para a operacao de **salvar obra**.

Extraido de ``codigo5_coplan.py::MainWindow.save_data`` na Etapa B.1.

Este modulo contem **apenas** a logica pura que estava emaranhada no
``save_data``: montagem do dict canonico de dados da obra, deteccao de
diff, montagem da mensagem de historico e validacoes simples de
alimentador. A orquestracao (QMessageBox, QInputDialog, branching de
``self.obra_em_edicao`` / ``self.projeto_obras``) **continua** em
``MainWindow.save_data``.

Convencoes:

- Funcoes nao mutam argumentos -- sempre devolvem novo ``dict``.
- ``datetime.datetime`` injetavel via ``when`` para testes deterministicos.
- Mensagens em portugues sao identicas ao legado para manter paridade.
- Sem dependencia de PySide6 (verificado pelo ``test_core_purity``).
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from core.services.obra_rules import CAMPOS_CRITICOS_MUDANCA, diff_fields


# ---------------------------------------------------------------------------
# 1. Validacoes simples de alimentador
# ---------------------------------------------------------------------------
def aplicar_alimentador_validations(
    alimentador: str,
    beneficiados: Sequence[str],
) -> list[str]:
    """Retorna lista de mensagens de erro para alimentador / beneficiados.

    Reproduz as duas regras do legado (linhas 13252-13263 do codigo5):

    - Se o ``alimentador`` contem ``_``, devolve a mensagem "Nao use
      sublinhado (_) no campo Alimentador Obra.".
    - Se algum dos ``beneficiados`` contem ``_``, devolve a mensagem
      "Nao use sublinhado (_) nos alimentadores beneficiados.".

    Lista vazia significa "tudo ok". Permite que a UI itere e mostre
    QMessageBox individualmente, mantendo os textos PT-BR exatos.
    """
    erros: list[str] = []
    if "_" in (alimentador or ""):
        erros.append("Não use sublinhado (_) no campo Alimentador Obra.")
    if any("_" in (b or "") for b in beneficiados):
        erros.append("Não use sublinhado (_) nos alimentadores beneficiados.")
    return erros


# ---------------------------------------------------------------------------
# 2. Construcao do dict canonico de dados da obra
# ---------------------------------------------------------------------------
@dataclass(frozen=True, kw_only=True)
class SalvarObraInput:
    """Entrada estruturada para ``build_obra_dados``.

    Espelha 1:1 os campos lidos pela UI no ``save_data`` legado, exceto:

    - ``alimentadores_beneficiados`` chega como ``list[str]`` (a funcao
      faz o ``";".join``).
    - ``tensao_operacao_explicita`` e o conteudo do campo dedicado; se
      vazio, ``build_obra_dados`` aplica o fallback para
      ``nivel_tensao_obra`` (mesma regra do legado).
    - ``snapshot_*`` ja vem calculado pela UI (envolve I/O de arquivos).
    - ``descricao_obra`` ja vem resolvida (manual, existente ou auto).
    """

    # Identificacao
    cod: str
    ano: str
    projeto_investimento: str
    pi_base: str
    nome_projeto: str
    codigo_item: str

    # Alimentadores
    alimentador_principal: str
    beneficiados_list: list[str]

    # Localizacao
    coordenada_inicio: str
    coordenada_fim: str
    nome_regional: str
    nome_superintendencia: str
    subestacao: str

    # Material
    quantidade_material: str
    caracteristicas_material: str
    novo_bay: str

    # Atributos da obra
    nivel_criticidade: str
    observacoes_gerais: str
    nivel_tensao_obra: str
    tensao_operacao_explicita: str

    # Ganhos antes
    contas_contratos_previos: str
    carregamento_inicial: str
    perdas_iniciais: str
    tensao_media_inicial: str
    tensao_min_inicial: str
    tensao_min_linha_inicial: str
    chi_inicial: str
    ci_inicial: str
    tensao_max_inicial: str

    # Ganhos depois
    contas_contratos_posteriores: str
    carregamento_final: str
    perdas_finais: str
    tensao_media_final: str
    tensao_min_final: str
    tensao_min_linha_final: str
    chi_final: str
    ci_final: str
    tensao_max_final: str

    # Ganhos atuais (medicao real)
    tensao_min_registrada_atual: str
    carregamento_max_registrado_atual: str
    ganhos_totais_atual: str

    # Beneficiados
    contas_contratos_beneficiadas: str
    cc_benef_chi_ci: str

    # Totais
    valor_obra: str
    ganhos_totais_antes: str
    ganhos_totais_depois: str

    # Estado
    tipo_pacote: str
    obra_aprovada: str
    descricao_obra: str
    manobra: str

    # Snapshot tecnico (computado pela UI)
    snapshot_token: str
    snapshot_at: str
    snapshot_src: str


def build_obra_dados(inp: SalvarObraInput) -> dict[str, Any]:
    """Constroi o dict canonico para persistencia da obra.

    Aplica duas transformacoes ao que a UI passa:

    1. ``alimentadores_beneficiados = ";".join(beneficiados_list)``
    2. ``tensao_operacao = tensao_operacao_explicita or nivel_tensao_obra``

    E adiciona a constante ``tecnico_dirty = "NÃO"`` (toda obra recem-salva
    parte limpa).

    A ordem de chaves reproduz a ordem do dict do legado (L13381-13438).
    """
    return {
        "cod": inp.cod,
        "ano_": inp.ano,
        "projeto_investimento": inp.projeto_investimento,
        "pi_base": inp.pi_base,
        "nome_projeto": inp.nome_projeto,
        "codigo_item": inp.codigo_item,
        "alimentador_principal": inp.alimentador_principal,
        "alimentadores_beneficiados": ";".join(inp.beneficiados_list),
        "coordenada_inicio": inp.coordenada_inicio,
        "coordenada_fim": inp.coordenada_fim,
        "quantidade_material": inp.quantidade_material,
        "caracteristicas_material": inp.caracteristicas_material,
        "novo_bay": inp.novo_bay,
        "nivel_criticidade": inp.nivel_criticidade,
        "observacoes_gerais": inp.observacoes_gerais,
        "nome_regional": inp.nome_regional,
        "nome_superintendencia": inp.nome_superintendencia,
        "nivel_tensao_obra": inp.nivel_tensao_obra,
        "tensao_operacao": inp.tensao_operacao_explicita or inp.nivel_tensao_obra,
        "subestacao": inp.subestacao,
        "contas_contratos_previos": inp.contas_contratos_previos,
        "contas_contratos_posteriores": inp.contas_contratos_posteriores,
        "contas_contratos_beneficiadas": inp.contas_contratos_beneficiadas,
        "carregamento_inicial": inp.carregamento_inicial,
        "carregamento_final": inp.carregamento_final,
        "perdas_iniciais": inp.perdas_iniciais,
        "perdas_finais": inp.perdas_finais,
        "tensao_media_inicial": inp.tensao_media_inicial,
        "tensao_media_final": inp.tensao_media_final,
        "tensao_min_inicial": inp.tensao_min_inicial,
        "tensao_min_final": inp.tensao_min_final,
        "tensao_min_linha_inicial": inp.tensao_min_linha_inicial,
        "tensao_min_linha_final": inp.tensao_min_linha_final,
        "chi_inicial": inp.chi_inicial,
        "ci_inicial": inp.ci_inicial,
        "tensao_max_inicial": inp.tensao_max_inicial,
        "tensao_max_final": inp.tensao_max_final,
        "tensao_min_registrada_atual": inp.tensao_min_registrada_atual,
        "carregamento_max_registrado_atual": inp.carregamento_max_registrado_atual,
        "tipo_pacote": inp.tipo_pacote,
        "obra_aprovada": inp.obra_aprovada,
        "valor_obra": inp.valor_obra,
        "cc_benef_chi_ci": inp.cc_benef_chi_ci,
        "chi_final": inp.chi_final,
        "ci_final": inp.ci_final,
        "descricao_obra": inp.descricao_obra,
        "manobra": inp.manobra,
        "ganhos_totais_antes": inp.ganhos_totais_antes,
        "ganhos_totais_depois": inp.ganhos_totais_depois,
        "ganhos_totais_atual": inp.ganhos_totais_atual,
        "tecnico_snapshot_token": inp.snapshot_token,
        "tecnico_snapshot_at": inp.snapshot_at,
        "tecnico_snapshot_src": inp.snapshot_src,
        "tecnico_dirty": "NÃO",
    }


# ---------------------------------------------------------------------------
# 3. Avaliacao de diff e historico
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DiffResult:
    """Resultado puro da analise de diferencas para um save.

    A UI usa estes campos para decidir:

    - ``bloqueado_por_despachada(decision)`` -> bloqueia salvamento.
    - ``decision.campos_criticos_alterados`` nao-vazio -> pedir motivo.
    - ``aplicar_historico_ao_dict(dados, decision, motivo=...)`` -> anexa
      historico se houver mudancas.
    """

    campos_alterados: list[str]
    campos_criticos_alterados: list[str]
    despacho_status: str
    historico_col: str | None
    historico_base: str


def avaliar_diff(
    dados: Mapping[str, Any],
    old_map: Mapping[str, Any] | None,
    *,
    db_columns: Sequence[str],
) -> DiffResult:
    """Calcula o ``DiffResult`` para um save.

    ``old_map`` pode ser ``None`` ou ``{}`` em insercoes (nao ha estado
    anterior); nesse caso ``campos_alterados`` fica vazio.

    Reproduz as linhas 13443-13486 do codigo5:

    - Conjunto de campos comparados = ``CAMPOS_CRITICOS_MUDANCA + dados.keys()``
      sem duplicar (mantendo ordem de insercao).
    - ``despacho_status`` lido de ``old_map`` em maiusculas.
    - ``historico_col`` = primeira coluna em ``("historico", "observacoes")``
      presente em ``db_columns`` (ou ``None``).
    - ``historico_base`` = valor atual da ``historico_col`` em ``old_map``.
    """
    old_dict = dict(old_map or {})
    campos_relevantes = list(
        dict.fromkeys(list(CAMPOS_CRITICOS_MUDANCA) + list(dados.keys()))
    )
    if not old_dict:
        changed: list[str] = []
    else:
        changed = diff_fields(old_dict, dict(dados), campos_relevantes)

    critical = [c for c in changed if c in CAMPOS_CRITICOS_MUDANCA]

    despacho = ""
    if old_dict:
        despacho = str(old_dict.get("despacho_status") or "").strip().upper()

    historico_col: str | None = None
    for col in ("historico", "observacoes"):
        if col in db_columns:
            historico_col = col
            break

    historico_base = ""
    if historico_col:
        historico_base = str(old_dict.get(historico_col) or "").strip()

    return DiffResult(
        campos_alterados=list(changed),
        campos_criticos_alterados=list(critical),
        despacho_status=despacho,
        historico_col=historico_col,
        historico_base=historico_base,
    )


def montar_historico_msg(
    *,
    campos_alterados: Sequence[str],
    campos_criticos_alterados: Sequence[str],
    motivo: str = "",
    when: datetime.datetime | None = None,
) -> str:
    """Monta a string de historico anexada ao save.

    Formato (identico ao legado, L13472-13475):

        ``[YYYY-MM-DD HH:MM] Campos: a, b, c``

    Se houver ``campos_criticos_alterados``, anexa ``" | Motivo: <texto>"``.

    O parametro ``when`` permite injetar timestamp em testes; por default
    usa ``datetime.now()``.
    """
    if when is None:
        when = datetime.datetime.now()
    timestamp = when.strftime("%Y-%m-%d %H:%M")
    msg = f"[{timestamp}] Campos: {', '.join(campos_alterados)}"
    if campos_criticos_alterados:
        msg += f" | Motivo: {(motivo or '').strip()}"
    return msg


def aplicar_historico_ao_dict(
    dados: Mapping[str, Any],
    decision: DiffResult,
    *,
    motivo: str = "",
    when: datetime.datetime | None = None,
) -> dict[str, Any]:
    """Devolve ``dict(dados)`` com ``decision.historico_col`` atualizada.

    Comportamento (reproduz L13471-13488 do codigo5):

    - Se ``decision.campos_alterados`` for vazio, devolve copia de
      ``dados`` inalterada.
    - Se ``decision.historico_col`` for ``None`` (banco nao tem coluna
      "historico" nem "observacoes"), devolve copia inalterada -- a UI
      e responsavel por escrever no log.
    - Caso contrario, anexa a mensagem ao texto base com ``"\\n"``
      separador, ou usa a mensagem direta se base estava vazia.
    """
    out = dict(dados)
    if not decision.campos_alterados:
        return out
    if decision.historico_col is None:
        return out
    msg = montar_historico_msg(
        campos_alterados=decision.campos_alterados,
        campos_criticos_alterados=decision.campos_criticos_alterados,
        motivo=motivo,
        when=when,
    )
    if decision.historico_base:
        out[decision.historico_col] = f"{decision.historico_base}\n{msg}"
    else:
        out[decision.historico_col] = msg
    return out


def bloqueado_por_despachada(decision: DiffResult) -> bool:
    """``True`` se a obra esta DESPACHADA e teve campo critico alterado.

    A UI usa para mostrar a mensagem
    ``"Obra ja DESPACHADA. Para alterar, marque como CORREÇÃO primeiro."``
    e abortar o save (linhas 13453-13459 do codigo5).
    """
    return (
        decision.despacho_status == "DESPACHADA"
        and bool(decision.campos_criticos_alterados)
    )
