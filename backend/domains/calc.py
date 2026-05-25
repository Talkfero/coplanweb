# -*- coding: utf-8 -*-
"""Mixin de dominio "calc" da CoplanApi (extraido de main_web.py).

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


class CalcMixin:

    # --- Fase 3: CalculationManager (calculos finos) ------------------

    def _ensure_calc_manager(self):
        """Cria/retorna singleton de CalculationManager."""
        cm = getattr(self, "_calc_manager", None)
        if cm is not None:
            return cm
        try:
            self._ensure_managers()
            from runtime.calc import CalculationManager
            cm = CalculationManager(
                self._support_manager, prompt_pi_base=False
            )
            self._calc_manager = cm
            return cm
        except Exception:  # noqa: BLE001
            return None

    def calc_gerar_cod(
        self, pacote: Any = "", alimentador: Any = "",
        projeto_investimento: Any = "", quantidade: Any = "",
        caracteristica: Any = "", coord_final: Any = "", pi_base: Any = "",
    ) -> dict[str, Any]:
        """Gera o codigo da obra (CalculationManager.gerar_cod).
        Formato: PCT|ALIM|TIPO|QTDxCARAC|COORD."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "cod": "", "error": "calc indisponivel"}
        try:
            cod = cm.gerar_cod(
                str(pacote or ""), str(alimentador or ""),
                str(projeto_investimento or ""), str(quantidade or ""),
                str(caracteristica or ""), str(coord_final or ""),
                pi_base=str(pi_base or "") or None,
            )
        except ValueError as exc:
            return {"ok": False, "cod": "", "error": str(exc)}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "cod": "", "error": f"gerar_cod: {exc}"}
        return {"ok": True, "cod": str(cod or ""), "error": ""}

    def calc_build_module_key(
        self, pi_base: Any = "", tensao: Any = "",
        caracteristica: Any = "", codigo_regional: Any = "",
    ) -> dict[str, Any]:
        """Constroi chave de modulo (CalculationManager.build_module_key)."""
        try:
            from runtime.calc import CalculationManager
            key = CalculationManager.build_module_key(
                str(pi_base or ""), str(tensao or ""),
                str(caracteristica or ""), str(codigo_regional or ""),
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "key": "", "error": f"build_key: {exc}"}
        return {"ok": True, "key": key, "error": ""}

    def calc_despacho_vt(self, cods: Any = None) -> dict[str, Any]:
        """Gera o texto de despacho VT a partir das obras informadas
        (CalculationManager.calcular_despacho_vt)."""
        if not isinstance(cods, (list, tuple)) or not cods:
            return {"ok": False, "texto": "", "error": "cods vazio"}
        cods_list = [str(c).strip() for c in cods if str(c or "").strip()]
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "texto": "", "error": err or "db indisponivel"}
        try:
            obras = db.fetch_by_cods(cods_list) or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "texto": "", "error": f"fetch: {exc}"}
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "texto": "", "error": "calc indisponivel"}
        try:
            texto = cm.calcular_despacho_vt(list(obras))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "texto": "", "error": f"despacho_vt: {exc}"}
        return {"ok": True, "texto": str(texto or ""), "error": ""}

    def calc_tensoes(self, alimentadores: Any = None) -> dict[str, Any]:
        """Tensao minima + menor media por patamar
        (CalculationManager.calcular_tensoes)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "tensao_min": None, "tensao_media_min": None,
                    "error": "calc indisponivel"}
        alims = [str(a).strip() for a in (alimentadores or [])
                 if str(a or "").strip()]
        if not alims:
            return {"ok": False, "tensao_min": None, "tensao_media_min": None,
                    "error": "alimentadores vazio"}
        files = self._read_tecnico_files()
        if files.get("error"):
            return {"ok": False, "tensao_min": None, "tensao_media_min": None,
                    "error": files["error"]}
        try:
            tmin, tmed = cm.calcular_tensoes(files["flow_mt"], alims)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "tensao_min": None, "tensao_media_min": None,
                    "error": f"calcular_tensoes: {exc}"}
        return {"ok": True, "tensao_min": tmin, "tensao_media_min": tmed,
                "error": ""}

    def calc_tensao_linha_minima(self, alimentadores: Any = None) -> dict[str, Any]:
        """Menor tensao de LINHA pu entre os alimentadores
        (CalculationManager.calcular_tensao_linha_minima)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "tensao_min_linha": None,
                    "error": "calc indisponivel"}
        alims = [str(a).strip() for a in (alimentadores or [])
                 if str(a or "").strip()]
        if not alims:
            return {"ok": False, "tensao_min_linha": None,
                    "error": "alimentadores vazio"}
        files = self._read_tecnico_files()
        if files.get("error"):
            return {"ok": False, "tensao_min_linha": None,
                    "error": files["error"]}
        try:
            v = cm.calcular_tensao_linha_minima(files["flow_mt"], alims)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "tensao_min_linha": None,
                    "error": f"tensao_linha_min: {exc}"}
        return {"ok": True, "tensao_min_linha": v, "error": ""}

    def calc_tensoes_max(self, alimentadores: Any = None) -> dict[str, Any]:
        """Tensao maxima + menor media por patamar
        (CalculationManager.calcular_tensoes_max)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "tensao_max": None, "tensao_media_min": None,
                    "error": "calc indisponivel"}
        alims = [str(a).strip() for a in (alimentadores or [])
                 if str(a or "").strip()]
        if not alims:
            return {"ok": False, "tensao_max": None, "tensao_media_min": None,
                    "error": "alimentadores vazio"}
        files = self._read_tecnico_files()
        if files.get("error"):
            return {"ok": False, "tensao_max": None, "tensao_media_min": None,
                    "error": files["error"]}
        try:
            tmax, tmed = cm.calcular_tensoes_max(files["flow_mt"], alims)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "tensao_max": None, "tensao_media_min": None,
                    "error": f"calcular_tensoes_max: {exc}"}
        return {"ok": True, "tensao_max": tmax, "tensao_media_min": tmed,
                "error": ""}

    def calc_carregamento(self, alimentadores: Any = None) -> dict[str, Any]:
        """Pior carregamento entre alimentadores
        (CalculationManager.calcular_carregamento)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "carregamento": None, "error": "calc indisponivel"}
        alims = [str(a).strip() for a in (alimentadores or [])
                 if str(a or "").strip()]
        if not alims:
            return {"ok": False, "carregamento": None, "error": "alimentadores vazio"}
        files = self._read_tecnico_files()
        if files.get("error"):
            return {"ok": False, "carregamento": None, "error": files["error"]}
        try:
            v = cm.calcular_carregamento(files["topologia"], alims)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "carregamento": None,
                    "error": f"carregamento: {exc}"}
        return {"ok": True, "carregamento": v, "error": ""}

    def calc_perdas(self, alimentadores: Any = None) -> dict[str, Any]:
        """Perdas por patamar + maior perda
        (CalculationManager.calcular_perdas)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "perdas_por_patamar": {}, "maior_perda": 0.0,
                    "error": "calc indisponivel"}
        alims = [str(a).strip() for a in (alimentadores or [])
                 if str(a or "").strip()]
        if not alims:
            return {"ok": False, "perdas_por_patamar": {}, "maior_perda": 0.0,
                    "error": "alimentadores vazio"}
        files = self._read_tecnico_files()
        if files.get("error"):
            return {"ok": False, "perdas_por_patamar": {}, "maior_perda": 0.0,
                    "error": files["error"]}
        try:
            perdas, maior = cm.calcular_perdas(files["flow_mt"], alims)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "perdas_por_patamar": {}, "maior_perda": 0.0,
                    "error": f"perdas: {exc}"}
        return {"ok": True, "perdas_por_patamar": dict(perdas or {}),
                "maior_perda": float(maior or 0.0), "error": ""}

    def calc_demanda_maxima(self, alimentadores: Any = None) -> dict[str, Any]:
        """Demanda maxima coincidente por alimentador (em MW)
        (CalculationManager.calcular_demanda_maxima)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "demanda_por_alim": {}, "error": "calc indisponivel"}
        alims = [str(a).strip() for a in (alimentadores or [])
                 if str(a or "").strip()]
        if not alims:
            return {"ok": False, "demanda_por_alim": {}, "error": "alimentadores vazio"}
        files = self._read_tecnico_files()
        if files.get("error"):
            return {"ok": False, "demanda_por_alim": {}, "error": files["error"]}
        try:
            d = cm.calcular_demanda_maxima(files["flow_mt"], alims)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "demanda_por_alim": {},
                    "error": f"demanda_maxima: {exc}"}
        return {"ok": True, "demanda_por_alim": dict(d or {}), "error": ""}

    def calc_chi_ci(self, alimentadores: Any = None) -> dict[str, Any]:
        """CHI + CI agregados entre alimentadores
        (CalculationManager.calcular_chi_ci)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "chi": 0, "ci": 0, "error": "calc indisponivel"}
        alims = [str(a).strip() for a in (alimentadores or [])
                 if str(a or "").strip()]
        if not alims:
            return {"ok": False, "chi": 0, "ci": 0, "error": "alimentadores vazio"}
        files = self._read_tecnico_files()
        if files.get("error"):
            return {"ok": False, "chi": 0, "ci": 0, "error": files["error"]}
        try:
            chi, ci = cm.calcular_chi_ci(files["confiabilidade"], alims)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "chi": 0, "ci": 0, "error": f"chi_ci: {exc}"}
        return {"ok": True, "chi": chi, "ci": ci, "error": ""}

    def calc_contas_contratos(self, alimentadores: Any = None) -> dict[str, Any]:
        """Contas/contratos antes vs depois
        (CalculationManager.calcular_contas_contratos)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "antes": 0, "depois": 0,
                    "error": "calc indisponivel"}
        alims = [str(a).strip() for a in (alimentadores or [])
                 if str(a or "").strip()]
        if not alims:
            return {"ok": False, "antes": 0, "depois": 0,
                    "error": "alimentadores vazio"}
        files = self._read_tecnico_files()
        if files.get("error"):
            return {"ok": False, "antes": 0, "depois": 0,
                    "error": files["error"]}
        try:
            a, d = cm.calcular_contas_contratos(files["confiabilidade"], alims)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "antes": 0, "depois": 0,
                    "error": f"contas_contratos: {exc}"}
        return {"ok": True, "antes": a, "depois": d, "error": ""}

    def calc_contas_contratos_beneficiadas(
        self, alimentadores: Any = None, projeto_investimento: Any = "",
    ) -> dict[str, Any]:
        """Contas/contratos beneficiadas considerando o PI
        (CalculationManager.calcular_contas_contratos_beneficiadas)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "total": 0, "error": "calc indisponivel"}
        alims = [str(a).strip() for a in (alimentadores or [])
                 if str(a or "").strip()]
        if not alims:
            return {"ok": False, "total": 0, "error": "alimentadores vazio"}
        pi = str(projeto_investimento or "").strip()
        if not pi:
            return {"ok": False, "total": 0, "error": "projeto_investimento vazio"}
        files = self._read_tecnico_files()
        if files.get("error"):
            return {"ok": False, "total": 0, "error": files["error"]}
        try:
            total = cm.calcular_contas_contratos_beneficiadas(
                files["topologia"], files["confiabilidade"], alims, pi,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "total": 0,
                    "error": f"contas_beneficiadas: {exc}"}
        return {"ok": True, "total": int(total or 0), "error": ""}
