# -*- coding: utf-8 -*-
"""Estado e constantes de modulo compartilhadas pela CoplanApi.

Modulo "folha" (so depende da stdlib) para evitar import circular: tanto
`main_web` quanto os mixins em `backend.domains.*` importam daqui.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

# Raiz do repositorio (backend/_state.py -> backend/ -> raiz). Usado para
# resolver <HERE>/logs e para a lista de paths. Mesmo valor que o diretorio
# do main_web.py (entrypoint na raiz).
HERE = Path(__file__).resolve().parent.parent

# Versao do main_web (independente da versao do desktop). Bumpa quando
# uma feature web visivel pro usuario muda.
APP_VERSION = "web-0.2.0"


# ----------------------------------------------------------------------
# Bloco 5 (Auditoria #44): Sistema de progress + cancel para operacoes
# longas. Singleton por processo - uma operacao de cada vez. JS faz
# polling de progress_state() e pode cancelar via progress_cancel().
# Op longa roda em threading.Thread (daemon) para nao bloquear o bridge.
# ----------------------------------------------------------------------
_OP_LOCK = threading.Lock()
_OP_STATE: dict[str, Any] = {
    "id": "",
    "label": "",
    "processed": 0,
    "total": 0,
    "started_at": 0.0,
    "finished": True,
    "cancel_requested": False,
    "result": None,
    "error": "",
}


def _op_reset(label: str) -> str:
    """Reinicia _OP_STATE para uma nova operacao. Retorna op_id novo."""
    import time as _t
    import uuid as _u
    op_id = _u.uuid4().hex[:12]
    with _OP_LOCK:
        _OP_STATE.update({
            "id":               op_id,
            "label":            str(label or ""),
            "processed":        0,
            "total":            0,
            "started_at":       _t.time(),
            "finished":         False,
            "cancel_requested": False,
            "result":           None,
            "error":            "",
        })
    return op_id


def _op_set_progress(processed: int, total: int, label: str = "") -> None:
    """Atualiza progresso. Chamado pela worker thread."""
    with _OP_LOCK:
        _OP_STATE["processed"] = int(processed)
        _OP_STATE["total"] = int(total)
        if label:
            _OP_STATE["label"] = str(label)


def _op_check_cancel() -> bool:
    """Le flag de cancel (set por progress_cancel())."""
    with _OP_LOCK:
        return bool(_OP_STATE.get("cancel_requested"))


def _op_finish(result: Any = None, error: str = "") -> None:
    """Marca a operacao como finalizada (pela worker thread)."""
    with _OP_LOCK:
        _OP_STATE["finished"] = True
        _OP_STATE["result"] = result
        _OP_STATE["error"] = str(error or "")


def _op_snapshot() -> dict[str, Any]:
    """Devolve copia thread-safe do estado atual (para o JS pollar)."""
    with _OP_LOCK:
        return dict(_OP_STATE)
