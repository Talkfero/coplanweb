"""Servico puro de metadata de PI (Projeto de Investimento).

Reproduz literalmente a logica das 8 funcoes ``get_pi_*`` e
``_normalize_pi_metadata_entry`` do ``codigo5_coplan.py`` (linhas
1580-1740). Migra tambem a constante ``DEFAULT_PI_METADATA`` (linhas
1511-1612), que e dado de dominio.

Sem I/O, sem Qt, sem ConfigManager: a UI le o config.json e passa o dict
``config`` como parametro. Para o estado mutavel ``PI_BASE_CUSTOM`` (lista
de bases adicionadas pelo usuario na sessao), a UI passa ``custom_bases``
como parametro de ``listar_todas_bases``.

Funcoes publicas:

- ``listar_pi_metadata(config)``       -> ``list[PIMetadata]``
- ``buscar_pi_metadata(pi, config)``   -> ``PIMetadata | None``
- ``obter_tipo_base(pi, config)``      -> ``str``
- ``obter_abreviacao(pi, config)``     -> ``str``
- ``obter_descricao_template(...)``    -> ``str``
- ``obter_modulos_extras(pi, config)`` -> ``list[str]``
- ``listar_todas_bases(config, custom_bases=())`` -> ``list[str]``
"""
from __future__ import annotations

from typing import Optional, Sequence

from core.models import PIMetadata
from shared.texto_utils import normalize_key


# ---------------------------------------------------------------------------
# DEFAULT_PI_METADATA (migrada literal do codigo5_coplan.py linhas 1511-1612)
# ---------------------------------------------------------------------------
DEFAULT_PI_METADATA: list[dict] = [
    {
        "nome": "DISTRIBUIÇÃO",
        "abreviacao": "DIS",
        "tipo_base": "DISTRIBUIÇÃO",
        "descricao_template": (
            "- CONSTRUÇÃO DE APROXIMADAMENTE {quantidade_material} KM DE RD "
            "{nivel_tensao_obra} KV EM CABOS DO TIPO {caracteristicas_material}, "
            "DESDE AS COORDENADAS {coordenada_inicio} ATÉ AS COORDENADAS "
            "{coordenada_fim}"
        ),
        "calculo": {"modulo_extra": []},
        "flags": {"exige_aterramento": False},
    },
    {
        "nome": "MELHORAMENTOS",
        "abreviacao": "MEL",
        "tipo_base": "MELHORAMENTOS",
        "descricao_template": (
            "- RECONDUTORAMENTO DE APROXIMADAMENTE {quantidade_material} KM DE RD "
            "{nivel_tensao_obra} KV PARA CABOS DO TIPO {caracteristicas_material}, "
            "DESDE AS COORDENADAS {coordenada_inicio} ATÉ AS COORDENADAS "
            "{coordenada_fim}"
        ),
        "calculo": {"modulo_extra": []},
        "flags": {"exige_aterramento": False},
    },
    {
        "nome": "TRIFASEAMENTO",
        "abreviacao": "TRF",
        "tipo_base": "TRIFASEAMENTO",
        "descricao_template": (
            "- TRIFASEAMENTO DE APROXIMADAMENTE {quantidade_material} KM DE RD "
            "{nivel_tensao_obra} KV EM CABOS DO TIPO {caracteristicas_material}, "
            "DESDE AS COORDENADAS {coordenada_inicio} ATÉ AS COORDENADAS "
            "{coordenada_fim}"
        ),
        "calculo": {"modulo_extra": []},
        "flags": {"exige_aterramento": False},
    },
    {
        "nome": "INSTALAÇÃO DE BANCOS DE REGULADORES DE TENSÃO EM RD",
        "abreviacao": "BRT",
        "tipo_base": "INSTALAÇÃO DE BANCOS DE REGULADORES DE TENSÃO EM RD",
        "descricao_template": (
            "- INSTALAÇÃO DE {quantidade_material} BANCO(S) DE REGULADORES DE "
            "TENSÃO DE {caracteristicas_material} {tensao_operacao} KV NAS "
            "COORDENADAS {coordenada_fim}"
        ),
        "calculo": {"modulo_extra": ["ATERRAMENTO"], "criterio_colapso": "tensao"},
        "flags": {"exige_aterramento": True},
    },
    {
        "nome": "INSTALAÇÃO DE BANCOS DE CAPACITORES EM RD",
        "abreviacao": "BC",
        "tipo_base": "INSTALAÇÃO DE BANCOS DE CAPACITORES EM RD",
        "descricao_template": (
            "- INSTALAÇÃO DE {quantidade_material} BANCO(S) DE CAPACITORES DE "
            "{caracteristicas_material} KVAR {tensao_operacao} KV NAS "
            "COORDENADAS {coordenada_fim}"
        ),
        "calculo": {"modulo_extra": [], "criterio_colapso": "tensao"},
        "flags": {"exige_aterramento": False},
    },
    {
        "nome": "INSTALAÇÃO DE BANCOS DE REATORES EM RD",
        "abreviacao": "RTO",
        "tipo_base": "INSTALAÇÃO DE BANCOS DE REATORES EM RD",
        "descricao_template": (
            "- INSTALAÇÃO DE {quantidade_material} BANCO(S) DE REATORES DE "
            "{caracteristicas_material} KVAR {tensao_operacao} KV NAS "
            "COORDENADAS {coordenada_fim}"
        ),
        "calculo": {"modulo_extra": [], "criterio_colapso": "tensao"},
        "flags": {"exige_aterramento": False},
    },
    {
        "nome": "DISTRIBUIÇÃO LD 34,5 KV",
        "abreviacao": "DLD",
        "tipo_base": "DISTRIBUIÇÃO LD 34,5 KV",
        "descricao_template": (
            "- CONSTRUÇÃO DE APROXIMADAMENTE {quantidade_material} KM DE RD "
            "{nivel_tensao_obra} KV EM CABOS DO TIPO {caracteristicas_material}, "
            "DESDE AS COORDENADAS {coordenada_inicio} ATÉ AS COORDENADAS "
            "{coordenada_fim}"
        ),
        "calculo": {"modulo_extra": []},
        "flags": {"exige_aterramento": False},
    },
    {
        "nome": "INSTALAÇÃO DE TRAFO RD",
        "abreviacao": "",
        "tipo_base": "INSTALAÇÃO DE TRAFO RD",
        "descricao_template": (
            "- INSTALAÇÃO DE {quantidade_material} TRANSFORMADOR(ES) DE "
            "{caracteristicas_material} KVA EM RD {tensao_operacao} KV NAS "
            "COORDENADAS {coordenada_fim}"
        ),
        "calculo": {"modulo_extra": []},
        "flags": {"exige_aterramento": False},
    },
]


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------
def _entries_normalizadas(config: Optional[dict]) -> list[dict]:
    """Reproduz ``get_pi_metadata_entries`` do legado, mas como helper interno
    que retorna list[dict] em formato plano (como a UI legada espera)."""
    if not isinstance(config, dict):
        config = {}
    raw_entries = config.get("pi_metadata", [])
    if not isinstance(raw_entries, list):
        raw_entries = []

    entries: list[dict] = []
    index: dict[str, int] = {}
    for entry in DEFAULT_PI_METADATA:
        normalized = normalize_key(entry["nome"])
        index[normalized] = len(entries)
        entries.append(entry)

    for entry in raw_entries:
        normalized_entry = _normalizar_entry_dict(entry)
        if not normalized_entry:
            continue
        normalized_key = normalize_key(normalized_entry["nome"])
        if normalized_key in index:
            entries[index[normalized_key]] = normalized_entry
        else:
            index[normalized_key] = len(entries)
            entries.append(normalized_entry)
    return entries


def _normalizar_entry_dict(entry: dict) -> Optional[dict]:
    """Reproduz ``_normalize_pi_metadata_entry`` do legado."""
    if not isinstance(entry, dict):
        return None
    nome = str(entry.get("nome", "")).strip()
    if not nome:
        return None
    tipo_base = str(entry.get("tipo_base") or nome).strip()
    descricao_template = str(entry.get("descricao_template") or "").strip()
    calculo = entry.get("calculo") if isinstance(entry.get("calculo"), dict) else {}
    flags = entry.get("flags") if isinstance(entry.get("flags"), dict) else {}
    return {
        "nome": nome,
        "abreviacao": str(entry.get("abreviacao") or "").strip(),
        "tipo_base": tipo_base,
        "descricao_template": descricao_template,
        "calculo": calculo,
        "flags": flags,
    }


def _entries_dict_para_pi_metadata(entries: list[dict]) -> list[PIMetadata]:
    """Converte entries dict legado para lista de PIMetadata, ignorando os invalidos."""
    result: list[PIMetadata] = []
    for entry in entries:
        m = PIMetadata.from_config_entry(entry)
        if m is not None:
            result.append(m)
    return result


def _mapa_normalizado(entries: list[dict]) -> dict[str, dict]:
    """Reproduz ``get_pi_metadata_map``: mapa por nome normalizado e tipo_base."""
    mapping: dict[str, dict] = {}
    for entry in entries:
        nome_key = normalize_key(str(entry.get("nome") or ""))
        if nome_key:
            mapping[nome_key] = entry
        tipo_base = entry.get("tipo_base") or entry.get("nome") or ""
        base_key = normalize_key(str(tipo_base))
        if base_key:
            mapping.setdefault(base_key, entry)
    return mapping


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------
def listar_pi_metadata(config: Optional[dict] = None) -> list[PIMetadata]:
    """Defaults + entries do config, deduplicadas por nome normalizado.

    Retorna PIMetadata tipado. Para wrappers de compatibilidade que precisam
    do formato dict legado, use ``[m.to_dict() for m in listar_pi_metadata(config)]``.
    """
    return _entries_dict_para_pi_metadata(_entries_normalizadas(config))


def buscar_pi_metadata(
    pi: str, config: Optional[dict] = None
) -> Optional[PIMetadata]:
    """Procura PI por nome (normalizado) ou por tipo_base. Case-insensitive."""
    key = normalize_key(pi)
    if not key:
        return None
    entries = _entries_normalizadas(config)
    mapa = _mapa_normalizado(entries)
    entry = mapa.get(key)
    if entry is None:
        return None
    return PIMetadata.from_config_entry(entry)


def obter_tipo_base(pi: str, config: Optional[dict] = None) -> str:
    """``tipo_base.upper()`` do PI; cai em ``pi.upper()`` se nao houver metadata.

    Reproduz ``get_pi_tipo_base`` do legado.
    """
    metadata = buscar_pi_metadata(pi, config)
    if metadata:
        base = metadata.tipo_base or metadata.nome or pi
        return str(base).strip().upper()
    return str(pi or "").strip().upper()


def obter_abreviacao(pi: str, config: Optional[dict] = None) -> str:
    """Abreviacao do PI em UPPER; cai em ``"ERRO"`` se nao houver.

    Reproduz ``get_pi_abreviacao`` do legado.
    """
    metadata = buscar_pi_metadata(pi, config)
    if metadata:
        abrev = str(metadata.abreviacao or "").strip().upper()
        if abrev:
            return abrev
    return "ERRO"


def obter_descricao_template(
    pi: str, config: Optional[dict] = None
) -> str:
    """Template de descricao do PI; ``""`` se nao houver."""
    metadata = buscar_pi_metadata(pi, config)
    if not metadata:
        return ""
    return str(metadata.descricao_template or "").strip()


def obter_modulos_extras(
    pi_base: str, config: Optional[dict] = None
) -> list[str]:
    """Chaves extras de modulo para o PI base.

    Considera, nesta ordem:

    1. ``calculo.modulo_extra`` da metadata.
    2. ``"ATERRAMENTO"`` se ``flags.exige_aterramento``.
    3. ``config.last_pi_extra_map[pi_base]`` (estado salvo da UI).

    Deduplica preservando a ordem de aparicao.
    """
    if not isinstance(config, dict):
        config = {}

    extras: list[str] = []
    metadata = buscar_pi_metadata(pi_base, config)
    if metadata is not None:
        for chave in metadata.calculo.modulos_extras:
            chave_str = str(chave or "").strip().upper()
            if chave_str:
                extras.append(chave_str)
        if metadata.flags.get("exige_aterramento"):
            extras.append("ATERRAMENTO")

    extra_map = config.get("last_pi_extra_map", {})
    if isinstance(extra_map, dict):
        chaves_config = extra_map.get(str(pi_base or "").strip().upper(), [])
        if isinstance(chaves_config, list):
            for chave in chaves_config:
                chave_str = str(chave or "").strip().upper()
                if chave_str:
                    extras.append(chave_str)

    seen: set[str] = set()
    unicos: list[str] = []
    for chave in extras:
        if chave in seen:
            continue
        unicos.append(chave)
        seen.add(chave)
    return unicos


def listar_todas_bases(
    config: Optional[dict] = None,
    *,
    custom_bases: Sequence[str] = (),
    hidden_defaults: Sequence[str] = (),
) -> list[str]:
    """Lista de bases de PI: defaults + config + custom_bases.

    ``custom_bases`` e o estado mutavel de sessao (``PI_BASE_CUSTOM`` no
    legado), passado pela UI. Service e stateless e nao toca nele.
    Deduplica case-insensitive (sem acento).

    ``hidden_defaults`` lista nomes de bases default que o usuario removeu
    via UI (config.pi_base_hidden_defaults). Filtra qualquer base default
    cujo tipo_base normalizado bata com algum nome em hidden_defaults --
    permite "desligar" defaults sem editar a constante DEFAULT_PI_METADATA.
    """
    hidden_keys = {
        normalize_key(str(h or "")).strip()
        for h in hidden_defaults
        if str(h or "").strip()
    }
    bases: list[str] = []
    seen: set[str] = set()

    for entry in _entries_normalizadas(config):
        base = str(entry.get("tipo_base") or entry.get("nome") or "").strip()
        key = normalize_key(base).strip()
        if not key or key in seen:
            continue
        if key in hidden_keys:
            continue
        bases.append(base)
        seen.add(key)

    for custom in custom_bases:
        raw = str(custom or "").strip()
        key = normalize_key(raw).strip()
        if not key or key in seen:
            continue
        bases.append(custom)
        seen.add(key)

    return bases


# ---------------------------------------------------------------------------
# Variante que levanta PIDesconhecidoError (Passo 7)
# ---------------------------------------------------------------------------
from core.exceptions import PIDesconhecidoError


def buscar_pi_metadata_strict(
    pi: str, config: Optional[dict] = None
) -> PIMetadata:
    """Variante de ``buscar_pi_metadata`` que levanta excecao se PI desconhecido.

    Raises:
        PIDesconhecidoError: ``pi`` nao tem entrada em DEFAULT_PI_METADATA
            nem em ``config["pi_metadata"]``.
    """
    metadata = buscar_pi_metadata(pi, config)
    if metadata is None:
        raise PIDesconhecidoError(pi)
    return metadata

