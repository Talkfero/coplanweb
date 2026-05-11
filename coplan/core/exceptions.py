"""Excecoes de dominio do core.

O core lanca excecoes tipadas com dados estruturados; a UI as traduz em
mensagens ao usuario (QMessageBox/show_user_error). Nao colocar aqui textos
em portugues destinados ao usuario final NAS DOCSTRINGS -- mas as
mensagens carregadas pelas excecoes (campos ``detalhes`` e ``hint``) SAO
em portugues, porque preservam literalmente os textos do legado para
manter paridade.

Hierarquia:

    CoreError
    |-- ApoioFileError              (xlsx de apoio)
    |-- RowIntegrityError           (validate_min_integrity_strict)
    |-- GanhosInconsistentesError   (validate_ganhos_consistency_strict)
    |-- ObraDuplicadaError          (find_duplicate_or_raise)
    |-- PIDesconhecidoError         (buscar_pi_metadata_strict)
    `-- ConfiguracaoInvalidaError   (config.json com problema)
"""
from __future__ import annotations

from typing import Any, Optional


class CoreError(Exception):
    """Raiz de todas as excecoes de dominio do Coplan."""


class ApoioFileError(CoreError):
    """Erro de leitura ou validacao da planilha de apoio (xlsx).

    Carrega o codigo da falha (estavel para teste/comparacao), os
    detalhes (mensagem tecnica em PT-BR identica ao legado) e o hint
    (sugestao de correcao para o usuario, tambem em PT-BR identico ao
    legado). A UI captura essa excecao e chama
    ``show_user_error(titulo, exc.detalhes, exc.hint)`` para preservar
    100% o comportamento atual.

    Codigos previstos:

    - ``ARQUIVO_NAO_ENCONTRADO``    : caminho nao existe
    - ``ERRO_LEITURA``              : pandas falhou ao abrir/ler
    - ``ABA_AUSENTE_APOIO``         : nao tem aba "Apoio"
    - ``ABA_AUSENTE_MODULO``        : nao tem aba "MODULO"
    - ``COLUNAS_FALTANTES_APOIO``   : aba Apoio sem colunas minimas
    - ``COLUNAS_FALTANTES_MODULO``  : aba MODULO sem colunas minimas
    - ``DADOS_VAZIOS``              : aba Apoio nao produziu nenhum alim
    """

    def __init__(self, codigo: str, detalhes: str, hint: str = "") -> None:
        super().__init__(detalhes)
        self.codigo = codigo
        self.detalhes = detalhes
        self.hint = hint


class RowIntegrityError(CoreError):
    """Row de obra nao atende a integridade minima exigida.

    Levantada por ``obra_rules.validate_min_integrity_strict``. Carrega a
    lista de motivos (``reasons``) -- ex: ``["Sem PI_BASE", "Sem Ano"]`` --
    e contadores agregados quando aplicavel.
    """

    def __init__(
        self,
        reasons: list[str],
        *,
        counters: Optional[dict[str, int]] = None,
        samples: Optional[list[str]] = None,
    ) -> None:
        super().__init__(f"Integridade minima nao atendida: {', '.join(reasons)}")
        self.reasons = list(reasons)
        self.counters = dict(counters) if counters else {}
        self.samples = list(samples) if samples else []


class GanhosInconsistentesError(CoreError):
    """Campos de ganhos da obra estao inconsistentes.

    Levantada por ``obra_rules.validate_ganhos_consistency_strict``. Carrega
    a lista de erros encontrados (``errors``) -- ex: ``["Antes vazio",
    "Ganho total inconsistente"]``.
    """

    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"Ganhos inconsistentes: {', '.join(errors)}")
        self.errors = list(errors)


class ObraDuplicadaError(CoreError):
    """Detectou obra duplicada via ``find_duplicate_or_raise``.

    Carrega o ``duplicate`` (dict da obra ja existente) e a ``chave`` que
    levou ao match (``"COD_OBRA:X"`` ou ``"COMP:..."``).
    """

    def __init__(self, duplicate: dict, chave: str) -> None:
        super().__init__(f"Obra duplicada detectada: {chave}")
        self.duplicate = dict(duplicate)
        self.chave = chave


class PIDesconhecidoError(CoreError):
    """Tentativa de obter metadata de PI nao mapeado em DEFAULT nem config.

    Levantada por ``pi_metadata_service.buscar_pi_metadata_strict``.
    """

    def __init__(self, pi: str) -> None:
        super().__init__(f"PI desconhecido: {pi!r}")
        self.pi = str(pi or "")


class ConfiguracaoInvalidaError(CoreError):
    """Config.json com chave faltante ou tipo invalido.

    Carrega ``chave`` afetada e ``detalhes`` da inconsistencia.
    """

    def __init__(self, chave: str, detalhes: str) -> None:
        super().__init__(f"Configuracao invalida em {chave!r}: {detalhes}")
        self.chave = chave
        self.detalhes = detalhes
