"""Metadata de Projeto de Investimento (PI)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class CalculoPI:
    criterio_colapso: str = ""
    modulos_extras: List[str] = field(default_factory=list)

    @classmethod
    def from_calculo_dict(cls, raw: Optional[dict]) -> "CalculoPI":
        if not isinstance(raw, dict):
            return cls()
        criterio = str(raw.get("criterio_colapso") or "").strip().lower()
        modulos = raw.get("modulo_extra") or raw.get("modulos_extras") or []
        if not isinstance(modulos, list):
            modulos = []
        return cls(
            criterio_colapso=criterio,
            modulos_extras=[
                str(item).strip().upper() for item in modulos if str(item).strip()
            ],
        )


@dataclass(frozen=True)
class PIMetadata:
    nome: str
    abreviacao: str = ""
    tipo_base: str = ""
    descricao_template: str = ""
    calculo: CalculoPI = field(default_factory=CalculoPI)
    flags: Dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_config_entry(cls, entry: dict) -> Optional["PIMetadata"]:
        if not isinstance(entry, dict):
            return None
        nome = str(entry.get("nome", "")).strip()
        if not nome:
            return None
        tipo_base = str(entry.get("tipo_base") or nome).strip()
        flags_raw = entry.get("flags")
        flags: Dict[str, bool] = {}
        if isinstance(flags_raw, dict):
            flags = {str(k): bool(v) for k, v in flags_raw.items()}
        return cls(
            nome=nome,
            abreviacao=str(entry.get("abreviacao") or "").strip(),
            tipo_base=tipo_base,
            descricao_template=str(entry.get("descricao_template") or "").strip(),
            calculo=CalculoPI.from_calculo_dict(entry.get("calculo")),
            flags=flags,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nome": self.nome,
            "abreviacao": self.abreviacao,
            "tipo_base": self.tipo_base,
            "descricao_template": self.descricao_template,
            "calculo": {
                "criterio_colapso": self.calculo.criterio_colapso,
                "modulo_extra": list(self.calculo.modulos_extras),
            },
            "flags": dict(self.flags),
        }
