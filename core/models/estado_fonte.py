"""Estado de carregamento de uma fonte de dados (migrado do codigo5)."""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class DataSourceState:
    """Estado de uma fonte de dados (banco, planilha, etc.)."""

    state: str = "NAO_CARREGADO"
    path: str = ""
    loaded_at: Optional[datetime.datetime] = None
    validated_at: Optional[datetime.datetime] = None
    error_last: str = ""
    version_token: str = ""
