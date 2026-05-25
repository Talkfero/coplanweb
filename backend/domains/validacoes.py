# -*- coding: utf-8 -*-
"""Mixin de dominio "validacoes" da CoplanApi (extraido de main_web.py).

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


class ValidacoesMixin:

    # --- Fase 5: Validacoes pre-acao (dry-run) ------------------------

    def validate_alimentadores(
        self, alimentador: Any = "", beneficiados: Any = None,
    ) -> dict[str, Any]:
        """Valida nomes de alimentador (sem '_').
        (salvar_obra_service.aplicar_alimentador_validations)"""
        try:
            from core.services.salvar_obra_service import (
                aplicar_alimentador_validations,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "erros": [f"import: {exc}"]}
        benef_list: list[str] = []
        if isinstance(beneficiados, str):
            import re as _re
            benef_list = [
                p.strip() for p in _re.split(r"[,;|\n]+", beneficiados)
                if p and p.strip()
            ]
        elif isinstance(beneficiados, (list, tuple)):
            benef_list = [str(p).strip() for p in beneficiados if str(p or "").strip()]
        try:
            erros = aplicar_alimentador_validations(
                str(alimentador or ""), benef_list,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "erros": [f"validate: {exc}"]}
        return {"ok": True, "erros": list(erros), "valido": not erros}

    def validate_obra_integridade(self, payload: Any) -> dict[str, Any]:
        """Valida integridade minima de UMA obra (dict).
        (row_helpers.validate_min_integrity em modo single-row)"""
        if not isinstance(payload, dict):
            return {"ok": False, "valido": False,
                    "motivos": ["payload nao e dict"]}
        try:
            from runtime.row_helpers import validate_min_integrity
            ok, _counters, samples = validate_min_integrity([payload])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "valido": False,
                    "motivos": [f"validate: {exc}"]}
        return {"ok": True, "valido": bool(ok),
                "motivos": list(samples or [])}

    def validate_ganhos(
        self, payload: Any, tolerancia: Any = None,
    ) -> dict[str, Any]:
        """Valida consistencia ganhos antes/depois/total
        (row_helpers.validate_ganhos_consistency)."""
        if not isinstance(payload, dict):
            return {"ok": False, "valido": False, "motivos": ["payload nao e dict"]}
        try:
            from runtime.row_helpers import (
                _get_ganhos_tolerancia, validate_ganhos_consistency,
            )
            tol = (
                float(tolerancia)
                if tolerancia is not None
                else _get_ganhos_tolerancia(self._config or None)
            )
            ok, motivos = validate_ganhos_consistency(payload, tol)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "valido": False,
                    "motivos": [f"validate: {exc}"]}
        return {"ok": True, "valido": bool(ok),
                "motivos": list(motivos or [])}

    def find_duplicate(self, payload: Any) -> dict[str, Any]:
        """Procura obra duplicada no banco para o payload informado
        (row_helpers.find_duplicate_in_db)."""
        if not isinstance(payload, dict):
            return {"ok": False, "duplicate": None,
                    "error": "payload nao e dict"}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "duplicate": None,
                    "error": err or "db indisponivel"}
        try:
            from runtime.row_helpers import find_duplicate_in_db
            dup = find_duplicate_in_db(db, payload)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "duplicate": None,
                    "error": f"find_duplicate: {exc}"}
        return {"ok": True,
                "duplicate": dict(dup) if isinstance(dup, dict) else None,
                "error": ""}

    def avaliar_diff_obra(self, cod: Any, payload: Any) -> dict[str, Any]:
        """Dry-run: avalia o diff que UM save_obra faria, sem persistir.
        (salvar_obra_service.avaliar_diff)"""
        cod_s = str(cod or "").strip()
        if not isinstance(payload, dict):
            return {"ok": False, "campos_alterados": [],
                    "campos_criticos_alterados": [],
                    "despacho_status": "", "historico_col": None,
                    "historico_base": "",
                    "error": "payload nao e dict"}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "campos_alterados": [],
                    "campos_criticos_alterados": [],
                    "despacho_status": "", "historico_col": None,
                    "historico_base": "",
                    "error": err or "db indisponivel"}
        try:
            cols = list(db.get_column_names() or [])
            old_map: dict[str, Any] = {}
            if cod_s:
                row = db.fetch_by_cod(cod_s)
                if row:
                    old_map = {c: row[i] if i < len(row) else ""
                               for i, c in enumerate(cols)}
            from core.services.salvar_obra_service import avaliar_diff
            decision = avaliar_diff(payload, old_map, db_columns=cols)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "campos_alterados": [],
                    "campos_criticos_alterados": [],
                    "despacho_status": "", "historico_col": None,
                    "historico_base": "",
                    "error": f"avaliar_diff: {exc}"}
        return {
            "ok": True,
            "campos_alterados": list(decision.campos_alterados),
            "campos_criticos_alterados": list(decision.campos_criticos_alterados),
            "despacho_status": str(decision.despacho_status or ""),
            "historico_col": decision.historico_col,
            "historico_base": str(decision.historico_base or ""),
            "error": "",
        }

    def check_bloqueado_despachada(
        self, cod: Any, payload: Any,
    ) -> dict[str, Any]:
        """True se save deve ser bloqueado por DESPACHADA + criticos
        (salvar_obra_service.bloqueado_por_despachada)."""
        diff = self.avaliar_diff_obra(cod, payload)
        if not diff.get("ok"):
            return {"ok": False, "bloqueado": False, "error": diff.get("error", "")}
        try:
            from core.services.salvar_obra_service import (
                DiffResult, bloqueado_por_despachada,
            )
            decision = DiffResult(
                campos_alterados=list(diff["campos_alterados"]),
                campos_criticos_alterados=list(diff["campos_criticos_alterados"]),
                despacho_status=diff["despacho_status"],
                historico_col=diff["historico_col"],
                historico_base=diff["historico_base"],
            )
            blocked = bloqueado_por_despachada(decision)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "bloqueado": False,
                    "error": f"check_bloqueado: {exc}"}
        return {"ok": True, "bloqueado": bool(blocked), "error": ""}

    # --- Fase 8: Helpers diversos ------------------------------------

    def parse_cod_pep(self, cod: Any = "") -> dict[str, Any]:
        """Parse de COD_PEP em campos {empresa, yy, regional, agrup, seq, letra}
        (text_utils.parse_cod_pep)."""
        try:
            from runtime.text_utils import parse_cod_pep as _parse
            parsed = _parse(str(cod or ""))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "parsed": None, "error": f"parse: {exc}"}
        if parsed is None:
            return {"ok": False, "parsed": None,
                    "error": "formato invalido"}
        return {"ok": True, "parsed": dict(parsed), "error": ""}

    def resolve_pi_base(
        self, pi: Any = "", prompt_user: Any = False,
    ) -> dict[str, Any]:
        """Resolve PI -> PI_BASE (pi_base.get_pi_base).
        prompt_user=False evita Qt popup; usa silencioso."""
        try:
            from runtime.pi_base import get_pi_base
            base = get_pi_base(str(pi or ""), prompt_user=bool(prompt_user))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "pi_base": "", "error": f"resolve: {exc}"}
        return {"ok": True, "pi_base": str(base or ""), "error": ""}

    def get_dup_key(self, payload: Any) -> dict[str, Any]:
        """Chave de duplicidade canonica de uma obra
        (row_helpers.build_dup_key). Util pra UI alertar pre-save."""
        if not isinstance(payload, dict):
            return {"ok": False, "key": "", "error": "payload nao e dict"}
        try:
            from runtime.row_helpers import build_dup_key
            key = build_dup_key(payload)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "key": "", "error": f"dup_key: {exc}"}
        return {"ok": True, "key": str(key or ""), "error": ""}

    def get_scope_key(self, payload: Any) -> dict[str, Any]:
        """Chave de escopo (pacote|alim|ano) usada por tecnico/snapshots
        (row_helpers.build_scope_key)."""
        if not isinstance(payload, dict):
            return {"ok": False, "key": "", "error": "payload nao e dict"}
        try:
            from runtime.row_helpers import build_scope_key
            key = build_scope_key(payload)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "key": "", "error": f"scope_key: {exc}"}
        return {"ok": True, "key": str(key or ""), "error": ""}

    def is_obra_aprovada(self, payload: Any) -> dict[str, Any]:
        """True se row['obra_aprovada'] == 'SIM' (row_helpers.is_aprovada)."""
        if not isinstance(payload, dict):
            return {"ok": False, "aprovada": False,
                    "error": "payload nao e dict"}
        try:
            from runtime.row_helpers import is_aprovada
            aprov = bool(is_aprovada(payload))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "aprovada": False,
                    "error": f"is_aprovada: {exc}"}
        return {"ok": True, "aprovada": aprov, "error": ""}

    def open_path_in_os(self, path: Any = "") -> dict[str, Any]:
        """Abre arquivo/pasta no app padrao do SO (dialogs.open_file).
        Util pos-export pra mostrar o arquivo gerado."""
        path_s = str(path or "").strip()
        if not path_s:
            return {"ok": False, "error": "path vazio"}
        if not os.path.exists(path_s):
            return {"ok": False, "error": f"path nao existe: {path_s}"}
        try:
            from runtime.dialogs import open_file
            open_file(path_s)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"open: {exc}"}
        return {"ok": True, "error": ""}
