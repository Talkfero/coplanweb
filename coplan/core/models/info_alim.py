"""Info consolidada de alimentador durante calculos (migrado de TypedDict)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class InfoAlim:
    first_codigo: Optional[int] = None
    first_antes: Optional[Dict[str, Any]] = None
    last_codigo: Optional[int] = None
    last_depois: Optional[Dict[str, Any]] = None
