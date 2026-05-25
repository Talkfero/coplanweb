# -*- coding: utf-8 -*-
"""Mixin de dominio "criterios" da CoplanApi (extraido de main_web.py).

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


class CriteriosMixin:

    # ------------------------------------------------------------------
    # Passo 5.3 (Ganhos / criterios + status OK/Falhou):
    # Le criterios_planejamento + piora_mercado do config e devolve
    # tambem REGRAS DECLARATIVAS (label_pattern -> {op, key}) que o JS
    # usa para colorir cada linha da tabela e popular o card lateral.
    # ------------------------------------------------------------------
    def get_criterios(self) -> dict[str, Any]:
        try:
            from runtime.config import ConfigManager, DEFAULT_CRITERIOS, DEFAULT_PIORA_MERCADO  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}"}
        cfg = ConfigManager.load_config() or {}
        crit = dict(DEFAULT_CRITERIOS)
        crit.update(cfg.get("criterios_planejamento") or {})
        piora = dict(DEFAULT_PIORA_MERCADO)
        piora.update(cfg.get("piora_mercado") or {})

        # Regras declarativas para o JS aplicar status/critTxt:
        #   label_match: prefixo (case+acento insensitive) que casa com o
        #     primeiro coluna da tabela "Parametros de Ganhos".
        #   op: 'ge' (>=), 'le' (<=).
        #   key: chave a comparar com o valor "Depois" da linha.
        regras = [
            {"label_match": "tensao min linha", "op": "ge",
             "key": "tensao_min", "label": "≥ %.2f pu"},
            {"label_match": "tensao min",       "op": "ge",
             "key": "tensao_min", "label": "≥ %.2f pu"},
            {"label_match": "tensao maxima",    "op": "le",
             "key": "tensao_max", "label": "≤ %.2f pu"},
            {"label_match": "tensao max",       "op": "le",
             "key": "tensao_max", "label": "≤ %.2f pu"},
            # Carregamento usa dois limites; default usa o mais rigoroso
            # (sim_ou_vazio) -- a UI pode re-aplicar com NAO se obra nao
            # for aprovada via o filtro do form.
            {"label_match": "carregamento",     "op": "le",
             "key": "carregamento_limite_sim_ou_vazio",
             "label": "≤ %.0f%%"},
            {"label_match": "chi",              "op": "ge",
             "key": "chi_min", "label": "≥ %.2f"},
            {"label_match": "ci",               "op": "ge",
             "key": "ci_min", "label": "≥ %.2f"},
        ]
        return {
            "ok": True, "error": "",
            "criterios": crit,
            "piora_mercado": piora,
            "regras": regras,
        }

    def save_criterios(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"ok": False, "error": "payload nao e dict"}
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}"}

        crit_keys_pt = (
            ("tensao_min",                      "tensao_min"),
            ("tensao_max",                      "tensao_max"),
            ("carregamento_max",                "carregamento_limite_sim_ou_vazio"),
            ("carregamento_limite_sim_ou_vazio","carregamento_limite_sim_ou_vazio"),
            ("carregamento_limite_nao",         "carregamento_limite_nao"),
            ("chi_min",                         "chi_min"),
            ("ci_min",                          "ci_min"),
            ("clientes_maximo",                 "clientes_maximo"),
        )
        piora_keys = (
            ("piora_mercado",        "carregamento_percentual"),
            ("carregamento_percentual","carregamento_percentual"),
            ("tensao_delta",         "tensao_delta"),
            ("anos_horizonte",       "anos_horizonte"),
            ("postergacao_max_anos", "postergacao_max_anos"),
            ("postergacao_max",      "postergacao_max_anos"),
        )

        crit_part: dict[str, Any] = {}
        for inkey, outkey in crit_keys_pt:
            if inkey in payload:
                v = self._to_float(payload[inkey])
                if v is not None:
                    crit_part[outkey] = v
        piora_part: dict[str, Any] = {}
        for inkey, outkey in piora_keys:
            if inkey in payload:
                v = self._to_float(payload[inkey])
                if v is not None:
                    # anos_horizonte / postergacao_max_anos sao inteiros
                    if outkey in ("anos_horizonte", "postergacao_max_anos"):
                        piora_part[outkey] = int(round(v))
                    else:
                        piora_part[outkey] = v

        if not crit_part and not piora_part:
            return {"ok": False, "error": "payload sem campos conhecidos"}

        partial: dict[str, Any] = {}
        if crit_part:
            partial["criterios_planejamento"] = crit_part
        if piora_part:
            partial["piora_mercado"] = piora_part
        try:
            ConfigManager.save_config(partial)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return {"ok": True, "error": "",
                "saved_criterios": list(crit_part.keys()),
                "saved_piora": list(piora_part.keys())}

    def restore_criterios_defaults(self) -> dict[str, Any]:
        """Reseta criterios_planejamento + piora_mercado aos DEFAULTS do
        legado. Mantem demais chaves do config intactas."""
        try:
            from runtime.config import ConfigManager, DEFAULT_CRITERIOS, DEFAULT_PIORA_MERCADO  # noqa: PLC0415
            ConfigManager.save_config({
                "criterios_planejamento": dict(DEFAULT_CRITERIOS),
                "piora_mercado": dict(DEFAULT_PIORA_MERCADO),
            })
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"restore: {exc}"}
        self._config = None
        # Devolve estado atualizado para a UI re-renderizar.
        return self.get_criterios()

    # --- Fase 7: Criterios por obra/alim -----------------------------

    def _criterios_dict(self) -> dict[str, Any]:
        """Le criterios_planejamento do config + defaults."""
        try:
            from runtime.config import DEFAULT_CRITERIOS
        except Exception:  # noqa: BLE001
            return {}
        cfg = self._config or {}
        crit = dict(DEFAULT_CRITERIOS)
        crit.update(cfg.get("criterios_planejamento") or {})
        return crit

    def criterios_check_obra(self, cod: Any = "") -> dict[str, Any]:
        """Verifica se UMA obra atende aos criterios
        (relatorio_criterios_service.obra_atende). Retorna
        {atende, motivos}. atende: True/False/None (None = dados insuficientes)."""
        cod_s = str(cod or "").strip()
        if not cod_s:
            return {"ok": False, "atende": None, "motivos": ["cod vazio"]}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "atende": None,
                    "motivos": [err or "db indisponivel"]}
        try:
            row = db.fetch_by_cod(cod_s)
            cols = list(db.get_column_names() or [])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atende": None,
                    "motivos": [f"fetch: {exc}"]}
        if not row:
            return {"ok": False, "atende": None,
                    "motivos": [f"obra nao encontrada: {cod_s}"]}
        try:
            from core.services.relatorio_criterios_service import (
                _conv_float, _conv_int, _col_idx_map, obra_atende,
            )
            idx_full = _col_idx_map(cols, [
                "tensao_min_final", "tensao_max_final", "carregamento_final",
                "manobra", "contas_contratos_posteriores",
            ])
            idx = {
                "tmin": idx_full["tensao_min_final"],
                "tmax": idx_full["tensao_max_final"],
                "carreg": idx_full["carregamento_final"],
                "manobra": idx_full["manobra"],
                "clientes": idx_full["contas_contratos_posteriores"],
            }
            if any(v < 0 for v in idx.values()):
                return {"ok": False, "atende": None,
                        "motivos": ["colunas obrigatorias ausentes"]}
            atende, motivos = obra_atende(
                row, idx, self._criterios_dict(),
                _conv_float, _conv_int,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atende": None,
                    "motivos": [f"obra_atende: {exc}"]}
        return {"ok": True, "atende": atende,
                "motivos": list(motivos or []), "error": ""}

    def criterios_check_alim_por_ganhos(
        self, metrics: Any = None, manobra: Any = "",
    ) -> dict[str, Any]:
        """Avalia criterios para UM alimentador com seu dict ``metrics``
        (relatorio_criterios_service.avaliar_alim_por_ganhos).
        metrics deve ter chaves: tensaominima, tensaomax, carregamento, contas."""
        if not isinstance(metrics, dict):
            return {"ok": False, "atende": None,
                    "motivos": ["metrics nao e dict"]}
        try:
            from core.services.relatorio_criterios_service import (
                avaliar_alim_por_ganhos,
            )
            atende, motivos = avaliar_alim_por_ganhos(
                metrics, str(manobra or ""), self._criterios_dict(),
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atende": None,
                    "motivos": [f"avaliar_alim: {exc}"]}
        return {"ok": True, "atende": atende,
                "motivos": list(motivos or []), "error": ""}

    def criterios_verificar_v2(
        self, cods: Any = None,
    ) -> dict[str, Any]:
        """Verifica criterios V2 (cor unica por projeto) em massa
        (relatorio_criterios_service.verificar_criterios_v2).
        Retorna {results: [{cod, atende}]}."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "results": [],
                    "error": err or "db indisponivel"}
        try:
            cols = list(db.get_column_names() or [])
            cods_list: list[str] = []
            if isinstance(cods, (list, tuple)):
                cods_list = [str(c).strip() for c in cods if str(c or "").strip()]
            if cods_list:
                rows = db.fetch_by_cods(cods_list) or []
            else:
                rows = db.fetch_all() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "results": [], "error": f"fetch: {exc}"}
        try:
            from core.services.relatorio_criterios_service import (
                verificar_criterios_v2,
            )
            verdict = verificar_criterios_v2(
                rows, cols, criterios=self._criterios_dict(),
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "results": [],
                    "error": f"verificar_v2: {exc}"}
        i_cod = cols.index("cod") if "cod" in cols else -1
        out = []
        for row, atende in zip(rows, verdict):
            cod_v = str(row[i_cod] if 0 <= i_cod < len(row) else "").strip()
            out.append({"cod": cod_v, "atende": atende})
        return {"ok": True, "results": out, "error": ""}

    def criterios_verificar_v1(
        self, cods: Any = None,
    ) -> dict[str, Any]:
        """Verifica criterios V1 (modo legado, cor por obra)
        (relatorio_criterios_service.verificar_criterios_v1)."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "results": [],
                    "error": err or "db indisponivel"}
        try:
            cols = list(db.get_column_names() or [])
            cods_list: list[str] = []
            if isinstance(cods, (list, tuple)):
                cods_list = [str(c).strip() for c in cods if str(c or "").strip()]
            if cods_list:
                rows = db.fetch_by_cods(cods_list) or []
            else:
                rows = db.fetch_all() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "results": [], "error": f"fetch: {exc}"}
        try:
            from core.services.relatorio_criterios_service import (
                verificar_criterios_v1,
            )
            verdict = verificar_criterios_v1(
                rows, cols, criterios=self._criterios_dict(),
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "results": [],
                    "error": f"verificar_v1: {exc}"}
        i_cod = cols.index("cod") if "cod" in cols else -1
        out = []
        for row, atende in zip(rows, verdict):
            cod_v = str(row[i_cod] if 0 <= i_cod < len(row) else "").strip()
            out.append({"cod": cod_v, "atende": atende})
        return {"ok": True, "results": out, "error": ""}

    def criterios_persistir_status(
        self, cods: Any = None,
    ) -> dict[str, Any]:
        """Calcula + persiste o status de criterios em todas as obras
        (relatorio_criterios_service.{avaliar,build}_criterios_persistencia +
        db.update_criterios_por_cod). Atualiza criterios_status, motivos,
        limite_carreg na tabela obras."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "atualizadas": 0,
                    "error": err or "db indisponivel"}
        try:
            cols = list(db.get_column_names() or [])
            cods_list: list[str] = []
            if isinstance(cods, (list, tuple)):
                cods_list = [str(c).strip() for c in cods if str(c or "").strip()]
            if cods_list:
                rows = db.fetch_by_cods(cods_list) or []
            else:
                rows = db.fetch_all() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atualizadas": 0, "error": f"fetch: {exc}"}
        try:
            from core.services.relatorio_criterios_service import (
                avaliar_criterios_persistencia,
                build_criterios_persistencia_updates,
            )
            avaliacoes = avaliar_criterios_persistencia(
                rows, cols, criterios=self._criterios_dict(),
            )
            updates = build_criterios_persistencia_updates(
                avaliacoes, criterios=self._criterios_dict(),
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atualizadas": 0,
                    "error": f"build_updates: {exc}"}
        if not updates:
            return {"ok": True, "atualizadas": 0, "error": ""}
        try:
            db.update_criterios_por_cod(updates)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atualizadas": 0,
                    "error": f"update_criterios: {exc}"}
        return {"ok": True, "atualizadas": len(updates), "error": ""}
