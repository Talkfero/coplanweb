"""Helpers de conexao SQLite com retry/lock-aware.

Migrado de ``codigo5_coplan.py`` (Passo 5b.ii). Reproduz literalmente:

- ``open_sqlite_safe``     : abre conexao com WAL, busy_timeout, FK on, etc.
- ``write_transaction_safe``: context manager com BEGIN IMMEDIATE + write_lock_info
- ``run_sql_write_safe``    : orquestra retry em busy
- ``DatabaseBusyError``     : excecao tipada que carrega mensagem PT-BR
- predicados ``is_sqlite_busy_error`` / ``is_database_busy_exception`` /
  ``is_database_locked_exception``

Sem Qt. Logs detalhados podem ser injetados via ``log_callback`` (a UI
passa ``log_connect_debug`` que tem informacao de QThread; service usa
``logging.getLogger`` por padrao).
"""
from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional, Sequence

from core.repositories.sqlite_lock import (
    build_database_busy_message,
    clear_lock_info,
    get_lock_info_path,
    read_lock_info,
    write_lock_info,
)


LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes (migradas do codigo5_coplan.py linhas 2306-2322)
# ---------------------------------------------------------------------------
SQLITE_BUSY_TIMEOUT_MS = 1200
SQLITE_CONNECT_TIMEOUT_S = 1.2
DATABASE_BUSY_CODE = "DATABASE_BUSY"
DATABASE_LOCKED_CODE = DATABASE_BUSY_CODE  # alias preservado do legado

_SQLITE_BUSY_ERRORS = (
    "database is locked",
    "database is busy",
    "database table is locked",
    "database schema is locked",
)
_DATABASE_BUSY_TEXT_TOKENS = (
    "banco em uso por outro usuario",
    "banco em uso por outro usu\u00e1rio",
    "banco em utiliza\u00e7\u00e3o",
    "banco ocupado",
)


# ---------------------------------------------------------------------------
# Excecoes
# ---------------------------------------------------------------------------
class DatabaseBusyError(RuntimeError):
    """Banco SQLite em uso por outro processo/usuario.

    Constroi a mensagem PT-BR a partir do .lock (via core.sqlite_lock).
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        lock_path: Optional[str] = None,
        details: Optional[str] = None,
    ) -> None:
        self.db_path = str(db_path or "").strip() or None
        self.lock_path = lock_path or get_lock_info_path(self.db_path)
        self.details = details
        lock_info = read_lock_info(self.lock_path)
        message = build_database_busy_message(lock_info)
        super().__init__(message)


# Alias preservado do legado (linha 2461 do codigo5_coplan.py).
DatabaseLockedError = DatabaseBusyError


# ---------------------------------------------------------------------------
# Predicados de classificacao de excecao
# ---------------------------------------------------------------------------
def is_sqlite_busy_error(exc: Exception) -> bool:
    """``True`` se for ``sqlite3.OperationalError`` com mensagem de busy/lock."""
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    msg = str(exc).lower()
    return any(token in msg for token in _SQLITE_BUSY_ERRORS)


def is_database_busy_exception(exc: Any) -> bool:
    """``True`` se for ``DatabaseBusyError``, ``OperationalError`` de busy,
    ou string contendo o codigo/tokens conhecidos."""
    if isinstance(exc, DatabaseBusyError):
        return True
    if isinstance(exc, sqlite3.OperationalError):
        return is_sqlite_busy_error(exc)
    text = str(exc or "").lower()
    if DATABASE_BUSY_CODE.lower() in text:
        return True
    if any(token in text for token in _DATABASE_BUSY_TEXT_TOKENS):
        return True
    return any(token in text for token in ("database is locked", "database is busy"))


def is_database_locked_exception(exc: Any) -> bool:
    """Alias de ``is_database_busy_exception`` (legado tem ambos)."""
    return is_database_busy_exception(exc)


# ---------------------------------------------------------------------------
# Owner para conexao+cursor (consumido por write_transaction_safe)
# ---------------------------------------------------------------------------
@dataclass
class _SQLiteWriteOwner:
    """Container minimo de db_path/conn/cursor para
    ``write_transaction_safe`` quando nao ha um DatabaseManager pleno."""

    db_path: str
    conn: Optional[sqlite3.Connection] = None
    cursor: Optional[sqlite3.Cursor] = None


# ---------------------------------------------------------------------------
# Helpers internos de tracing
# ---------------------------------------------------------------------------
def _ts_log(label: str, start_ts: float) -> None:
    """Replica ``ts_log`` do codigo5: mede delta e loga."""
    elapsed = time.perf_counter() - start_ts
    logging.info(f"[TIMESTAMP] {label} levou {elapsed:.3f}s")


def _call_log_callback(
    callback: Optional[Callable[..., None]],
    stage: str,
    db_path: Optional[str],
    *,
    exc: Optional[Exception] = None,
    extra: Optional[dict] = None,
) -> None:
    """Chama o callback se nao for None (silencia excecoes)."""
    if callback is None:
        return
    try:
        callback(stage, db_path, exc=exc, extra=extra)
    except Exception:
        # Logging de debug nunca deve quebrar a operacao de DB.
        pass


# ---------------------------------------------------------------------------
# open_sqlite_safe
# ---------------------------------------------------------------------------
def open_sqlite_safe(
    db_path: str,
    *,
    connect_timeout_s: float = SQLITE_CONNECT_TIMEOUT_S,
    busy_timeout_ms: int = SQLITE_BUSY_TIMEOUT_MS,
    log_callback: Optional[Callable[..., None]] = None,
) -> sqlite3.Connection:
    """Abre conexao SQLite com PRAGMAs do legado.

    Aplica:

    - ``journal_mode=WAL``
    - ``synchronous=NORMAL``
    - ``temp_store=MEMORY``
    - ``busy_timeout=<busy_timeout_ms>``
    - ``foreign_keys=ON``

    O ``log_callback`` (opcional) recebe ``(stage, db_path, *, exc, extra)``
    e e usado para tracing detalhado (ex: a UI passa ``log_connect_debug``
    com info de QThread).
    """
    t_total = time.perf_counter()
    t_start = time.perf_counter()
    _ts_log("open_sqlite_safe(): INICIO", t_start)
    _call_log_callback(
        log_callback,
        "open_sqlite_safe.start",
        db_path,
        extra={"timeout_s": connect_timeout_s, "busy_timeout_ms": busy_timeout_ms},
    )
    try:
        t_connect = time.perf_counter()
        conn = sqlite3.connect(
            db_path,
            timeout=connect_timeout_s,
            isolation_level=None,
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        _ts_log("open_sqlite_safe(): sqlite3.connect()", t_connect)
        _call_log_callback(log_callback, "open_sqlite_safe.connected", db_path)
        cur = conn.cursor()
        t_busy = time.perf_counter()
        journal_row = cur.execute("PRAGMA journal_mode=WAL;").fetchone()
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA temp_store=MEMORY;")
        cur.execute(f"PRAGMA busy_timeout={busy_timeout_ms};")
        cur.execute("PRAGMA foreign_keys=ON;")
        _ts_log("open_sqlite_safe(): PRAGMA busy_timeout", t_busy)
        journal_mode = (
            str(journal_row[0]).strip()
            if isinstance(journal_row, tuple) and journal_row
            else ""
        )
        _call_log_callback(
            log_callback,
            "open_sqlite_safe.ready",
            db_path,
            extra={"journal_mode": journal_mode or "<unknown>"},
        )
        return conn
    except Exception as exc:
        _call_log_callback(log_callback, "open_sqlite_safe.error", db_path, exc=exc)
        raise
    finally:
        _ts_log("open_sqlite_safe(): FIM", t_total)


# ---------------------------------------------------------------------------
# write_transaction_safe
# ---------------------------------------------------------------------------
@contextmanager
def write_transaction_safe(
    db_manager: Any,
    *,
    log_callback: Optional[Callable[..., None]] = None,
) -> Iterator[sqlite3.Cursor]:
    """Context manager: abre conexao se necessaria, BEGIN IMMEDIATE, commit/rollback.

    O ``db_manager`` e um objeto duck-typed que pode ser:

    - um ``_SQLiteWriteOwner`` (apenas db_path)
    - um ``DatabaseManager`` pleno do codigo5 (com ``conn``, ``cursor``,
      ``_get_cursor``).

    Cria/limpa o .lock automaticamente para indicar uso a outras sessoes.
    """
    conn: Optional[sqlite3.Connection] = None
    cursor: Optional[sqlite3.Cursor] = None
    owns_connection = False
    started = False
    lock_created = False

    db_path = str(getattr(db_manager, "db_path", "") or "").strip()
    if not db_path:
        raise ValueError("db_path n\u00e3o definido para transa\u00e7\u00e3o de escrita.")

    original_conn = getattr(db_manager, "conn", None)
    original_cursor = getattr(db_manager, "cursor", None)

    try:
        conn = original_conn
        if conn is None:
            conn = open_sqlite_safe(db_path, log_callback=log_callback)
            owns_connection = True
            if hasattr(db_manager, "conn"):
                db_manager.conn = conn

        cursor = getattr(db_manager, "cursor", None)
        if cursor is None and hasattr(db_manager, "_get_cursor"):
            try:
                cursor = db_manager._get_cursor()
            except Exception:
                cursor = None
        if cursor is None:
            cursor = conn.cursor()
            if hasattr(db_manager, "cursor"):
                db_manager.cursor = cursor

        if not conn.in_transaction:
            cursor.execute("BEGIN IMMEDIATE")
            started = True
            write_lock_info(db_path)
            lock_created = True

        yield cursor

        if started:
            conn.commit()
    except sqlite3.OperationalError as exc:
        if started and conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        if is_sqlite_busy_error(exc):
            raise DatabaseBusyError(db_path=db_path, details=str(exc)) from exc
        raise
    except Exception:
        if started and conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if lock_created:
            clear_lock_info(db_path)
        if owns_connection and conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            if hasattr(db_manager, "conn"):
                db_manager.conn = original_conn
            if hasattr(db_manager, "cursor"):
                db_manager.cursor = original_cursor


# ---------------------------------------------------------------------------
# run_sql_write_safe
# ---------------------------------------------------------------------------
def run_sql_write_safe(
    db_path: str,
    sql: str,
    params: Sequence[Any] = (),
    *,
    action: str = "Escrita em banco",
    retries: int = 0,
    retry_delay_ms: int = 500,
    log_callback: Optional[Callable[..., None]] = None,
) -> tuple[bool, Optional[str]]:
    """Executa SQL de escrita com retry em busy.

    Retorna ``(True, None)`` em sucesso, ``(False, DATABASE_BUSY_CODE)`` se
    todas as tentativas falharam por busy, ou ``(False, str(exc))`` para
    qualquer outra excecao. ``action`` e mantido por compatibilidade com a
    assinatura legada (atualmente nao usado dentro da funcao).
    """
    del action  # legado tambem nao usa internamente
    attempts = max(0, int(retries)) + 1
    owner = _SQLiteWriteOwner(str(db_path or "").strip())

    for attempt in range(attempts):
        try:
            with write_transaction_safe(owner, log_callback=log_callback) as cur:
                cur.execute(sql, tuple(params))
            return True, None
        except DatabaseBusyError:
            if attempt + 1 < attempts:
                time.sleep(max(retry_delay_ms, 0) / 1000.0)
                continue
            return False, DATABASE_BUSY_CODE
        except Exception as exc:
            return False, str(exc)

    return False, DATABASE_BUSY_CODE
