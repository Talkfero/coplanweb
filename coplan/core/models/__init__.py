"""Modelos de dominio do Coplan.

Somente dataclasses e metodos puros. Re-exporta as classes mais usadas.
"""
from __future__ import annotations

from .apoio import DadosAlimentador, ModuloValor
from .criterios import CriteriosPlanejamento, PioraMercado
from .estado_fonte import DataSourceState
from .info_alim import InfoAlim
from .nota_colapso import NotaColapso
from .obra import (
    AuditoriaRegistro,
    AuditoriaTecnica,
    DadosObra,
    Ganhos,
    GanhosAntes,
    GanhosAtual,
    GanhosDepois,
    Identificacao,
    Localizacao,
    MaterialObra,
    Obra,
)
from .pi_metadata import CalculoPI, PIMetadata

__all__ = [
    "AuditoriaRegistro",
    "AuditoriaTecnica",
    "CalculoPI",
    "CriteriosPlanejamento",
    "DadosAlimentador",
    "DadosObra",
    "DataSourceState",
    "Ganhos",
    "GanhosAntes",
    "GanhosAtual",
    "GanhosDepois",
    "Identificacao",
    "InfoAlim",
    "Localizacao",
    "MaterialObra",
    "ModuloValor",
    "NotaColapso",
    "Obra",
    "PIMetadata",
    "PioraMercado",
]
