"""Config de dominio: criterios de planejamento e piora de mercado."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CriteriosPlanejamento:
    tensao_min: float = 0.95
    tensao_max: float = 1.03
    carregamento_limite_sim_ou_vazio: float = 67.0
    carregamento_limite_nao: float = 100.0
    clientes_maximo: int = 6000

    @classmethod
    def default(cls) -> "CriteriosPlanejamento":
        return cls()


@dataclass(frozen=True)
class PioraMercado:
    carregamento_percentual: float = 3.0
    tensao_delta: float = 0.005
    anos_horizonte: int = 3

    @classmethod
    def default(cls) -> "PioraMercado":
        return cls()
