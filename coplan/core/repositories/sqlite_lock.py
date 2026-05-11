"""Gestao do arquivo .lock que indica que um banco SQLite esta em uso.

Migrado de ``codigo5_coplan.py`` linhas 2325-2492 (Passo 5b.i da separacao
UI/Core). Reproduz literalmente o comportamento do legado:

- O .lock e um JSON com chaves ``user``, ``machine``, ``time`` (formato BR
  ``%d/%m/%Y %H:%M:%S``) e ``pid``.
- Falhas de I/O sao silenciadas (``write_lock_info`` e ``clear_lock_info``
  nunca propagam excecao -- preservam a UX do legado de "nunca quebrar"
  por causa do lock).
- ``read_lock_info`` aceita .lock antigos com chaves PT-BR
  (``usuario``/``maquina``/``hora``) e modernos (``user``/``machine``/``time``).
- Mensagens PT-BR para o usuario sao preservadas literalmente.
"""
from __future__ import annotations

import datetime
import getpass
import json
import os
from typing import Any, Optional


# ---------------------------------------------------------------------------
# I/O dos arquivos .lock
# ---------------------------------------------------------------------------
def get_lock_info_path(db_path: Optional[str]) -> str:
    """Retorna o caminho do arquivo .lock para um db_path. ``""`` se vazio."""
    db_path_s = str(db_path or "").strip()
    if not db_path_s:
        return ""
    return f"{db_path_s}.lock"


def write_lock_info(db_path: Optional[str]) -> None:
    """Grava JSON com user/machine/time/pid. Erros sao silenciados."""
    lock_file = get_lock_info_path(db_path)
    if not lock_file:
        return
    info = {
        "user": getpass.getuser(),
        "machine": os.environ.get("COMPUTERNAME"),
        "time": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "pid": os.getpid(),
    }
    try:
        with open(lock_file, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def clear_lock_info(db_path: Optional[str]) -> None:
    """Apaga o .lock se existir. Erros sao silenciados."""
    lock_file = get_lock_info_path(db_path)
    if not lock_file:
        return
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except Exception:
        pass


def create_lock_info(lock_path: str, action: str) -> None:
    """Alias de write_lock_info que aceita o caminho .lock direto.

    O parametro ``action`` e mantido para preservar a assinatura legada,
    mas atualmente nao e gravado no .lock (paridade com o legado).
    """
    del action  # legado tambem nao usa
    lock_path_s = str(lock_path or "").strip()
    if not lock_path_s:
        return
    db_path = (
        lock_path_s[:-5]
        if lock_path_s.lower().endswith(".lock")
        else lock_path_s
    )
    write_lock_info(db_path)


def remove_lock_info(lock_path: str) -> None:
    """Alias de clear_lock_info que aceita o caminho .lock direto."""
    lock_path_s = str(lock_path or "").strip()
    if not lock_path_s:
        return
    db_path = (
        lock_path_s[:-5]
        if lock_path_s.lower().endswith(".lock")
        else lock_path_s
    )
    clear_lock_info(db_path)


def read_lock_info(lock_path: str) -> Optional[dict[str, Any]]:
    """Le e parseia o .lock como JSON. ``None`` se inexistente/invalido."""
    lock_path_s = str(lock_path or "").strip()
    if not lock_path_s:
        return None
    try:
        with open(lock_path_s, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# Formatacao / mensagens
# ---------------------------------------------------------------------------
def lock_info_summary(lock_info: Optional[dict[str, Any]]) -> str:
    """Linha curta para log: ``user=X;machine=Y;time=Z;pid=W``.

    Aceita chaves PT-BR (``usuario``/``maquina``/``hora``) e EN
    (``user``/``machine``/``time``) para compatibilidade com locks antigos.
    """
    info = lock_info if isinstance(lock_info, dict) else {}
    if not info:
        return "none"
    user = str(info.get("user") or info.get("usuario") or "N/D")
    machine = str(info.get("machine") or info.get("maquina") or "N/D")
    when = str(info.get("time") or info.get("hora") or "N/D")
    pid = str(info.get("pid") or "N/D")
    return f"user={user};machine={machine};time={when};pid={pid}"


def _format_lock_time(value: Any) -> str:
    """Tenta parsear datetime em formato BR ou ISO. Fallback: texto cru."""
    txt = str(value or "").strip()
    if not txt:
        return "N/D"
    try:
        dt = datetime.datetime.strptime(txt, "%d/%m/%Y %H:%M:%S")
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        pass
    try:
        dt = datetime.datetime.fromisoformat(txt)
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return txt


def build_database_busy_message(
    lock_info: Optional[dict[str, Any]] = None,
) -> str:
    """Mensagem PT-BR para QMessageBox quando o banco esta ocupado."""
    info = lock_info if isinstance(lock_info, dict) else {}
    user = str(info.get("user") or info.get("usuario") or "N/D")
    machine = str(info.get("machine") or info.get("maquina") or "N/D")
    since = _format_lock_time(info.get("time") or info.get("hora"))
    return (
        "Banco em utiliza\u00e7\u00e3o por outro usu\u00e1rio\n\n"
        f"Usu\u00e1rio: {user}\n"
        f"M\u00e1quina: {machine}\n"
        f"Desde: {since}\n\n"
        "A opera\u00e7\u00e3o n\u00e3o foi executada."
    )


def build_database_locked_message(
    lock_info: Optional[dict[str, Any]] = None,
) -> str:
    """Alias de build_database_busy_message (mesma mensagem no legado)."""
    return build_database_busy_message(lock_info)
