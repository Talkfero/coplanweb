# -*- coding: utf-8 -*-
"""Mixin de dominio "nota_colapso" da CoplanApi (extraido de main_web.py).

Nao instanciar diretamente: compoe backend.api.CoplanApi via heranca.
"""
from __future__ import annotations

import getpass  # noqa: F401
import hashlib  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import sys  # noqa: F401
import threading  # noqa: F401
from datetime import datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any, Callable  # noqa: F401

from backend._state import (  # noqa: F401
    APP_VERSION,
    HERE,
    _OP_LOCK,
    _OP_STATE,
    _op_check_cancel,
    _op_finish,
    _op_reset,
    _op_set_progress,
    _op_snapshot,
)


class NotaColapsoMixin:

    def calc_nota_carregamento(
        self, carreg_inicial: Any = 0, carreg_max: Any = 0,
    ) -> dict[str, Any]:
        """Nota de carregamento por faixa
        (CalculationManager.calcular_nota_carregamento)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "nota": None, "criterio": "",
                    "error": "calc indisponivel"}
        try:
            nota, crit = cm.calcular_nota_carregamento(
                float(carreg_inicial or 0), float(carreg_max or 0)
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "nota": None, "criterio": "",
                    "error": f"nota_carreg: {exc}"}
        return {"ok": True, "nota": nota, "criterio": str(crit or ""), "error": ""}

    def calc_nota_tensao_min(
        self, tensao_min_atual: Any = 0, tensao_min_inicial: Any = 0,
    ) -> dict[str, Any]:
        """Nota de tensao minima via tabela verdade 4x4
        (CalculationManager.calcular_nota_tensao_min)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "nota": None, "criterio": "",
                    "error": "calc indisponivel"}
        try:
            nota, crit = cm.calcular_nota_tensao_min(
                float(tensao_min_atual or 0), float(tensao_min_inicial or 0)
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "nota": None, "criterio": "",
                    "error": f"nota_tmin: {exc}"}
        return {"ok": True, "nota": nota, "criterio": str(crit or ""), "error": ""}

    def calc_nota_tensao_max(
        self, tensao_min_atual: Any = 0, tensao_max_inicial: Any = 0,
    ) -> dict[str, Any]:
        """Nota de tensao maxima por faixa
        (CalculationManager.calcular_nota_tensao_max)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "nota": None, "criterio": "",
                    "error": "calc indisponivel"}
        try:
            nota, crit = cm.calcular_nota_tensao_max(
                float(tensao_min_atual or 0), float(tensao_max_inicial or 0)
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "nota": None, "criterio": "",
                    "error": f"nota_tmax: {exc}"}
        return {"ok": True, "nota": nota, "criterio": str(crit or ""), "error": ""}

    def calc_nota_colapso_obra(self, cod: Any = "") -> dict[str, Any]:
        """Nota de colapso para UMA obra (CalculationManager.calcular_nota_colapso_obra).
        Versao por COD; o export_nota_colapso ja faz para varias."""
        cod_s = str(cod or "").strip()
        if not cod_s:
            return {"ok": False, "nota": None, "criterio": "",
                    "error": "cod vazio"}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "nota": None, "criterio": "",
                    "error": err or "db indisponivel"}
        try:
            row = db.fetch_by_cod(cod_s)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "nota": None, "criterio": "",
                    "error": f"fetch: {exc}"}
        if not row:
            return {"ok": False, "nota": None, "criterio": "",
                    "error": f"obra nao encontrada: {cod_s}"}
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "nota": None, "criterio": "",
                    "error": "calc indisponivel"}
        try:
            nota, crit = cm.calcular_nota_colapso_obra(row)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "nota": None, "criterio": "",
                    "error": f"nota_colapso: {exc}"}
        return {"ok": True, "nota": nota, "criterio": str(crit or ""), "error": ""}
