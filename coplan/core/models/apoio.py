"""Modelos das linhas da planilha de Apoio (xlsx)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DadosAlimentador:
    """Linha da aba Apoio do xlsx (metadados de um alimentador)."""

    alimentador: str
    tensao: str = ""
    regional: str = ""
    superintendencia: str = ""
    se: str = ""

    @classmethod
    def from_apoio_row(cls, row: dict) -> "DadosAlimentador":
        return cls(
            alimentador=str(
                row.get("ALIMENTADOR") or row.get("Alimentador") or ""
            ).strip(),
            tensao=str(row.get("TENSAO") or "").strip(),
            regional=str(row.get("REGIONAL") or "").strip(),
            superintendencia=str(row.get("SUPERINTENDENCIA") or "").strip(),
            se=str(row.get("SE") or "").strip(),
        )


@dataclass(frozen=True)
class ModuloValor:
    """Linha da aba Modulo do xlsx (valor unitario por caracteristica+regional)."""

    caracteristica: str
    regional: str
    valor: float

    @property
    def chave_composta(self) -> str:
        return f"{self.caracteristica}_{self.regional}".replace("-", "_").upper()
