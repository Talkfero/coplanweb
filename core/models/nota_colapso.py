"""Resultado do calculo de Nota de Colapso de uma obra."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(frozen=True)
class NotaColapso:
    valor: Optional[float]
    criterio: str
    valores_considerados: Dict[str, float] = field(default_factory=dict)

    @property
    def tem_dados_suficientes(self) -> bool:
        return self.valor is not None
