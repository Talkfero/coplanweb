"""Persistencia SQLite -- DatabaseManager + helpers de lock/retry + cod_pep.

Extraidos de codigo5_coplan.py. Tudo relacionado a banco mora aqui:
- Re-exports de constantes/excecoes de core/repositories/sqlite_*
- Wrappers que injetam log_connect_debug
- backup_on_error / with_lock_action / retry_on_busy decorators
- DBCallableWorker (Qt) + run_write_in_qthread_if_ui_thread
- get_empresa_sigla_from_config + cod_pep + helpers
- ensure_schema_business_patch
- class DatabaseManager (~1800 linhas)
"""
from __future__ import annotations

import datetime
import getpass
import logging
import os
import re
import shutil
import sqlite3
import threading
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional, Sequence

try:  # Qt e' opcional: a app web (headless) nao instala PySide6.
    from PySide6 import QtCore, QtWidgets  # type: ignore[import-not-found]
    from PySide6.QtCore import QObject, Signal, Slot  # type: ignore[import-not-found]
    _HAS_QT = True
except ModuleNotFoundError:  # web: o worker Qt/UI-thread nunca e exercido
    QtCore = QtWidgets = None  # type: ignore[assignment]
    QObject = object  # type: ignore[assignment,misc]
    Signal = Slot = None  # type: ignore[assignment]
    _HAS_QT = False

from runtime.text_utils import normalize_key, normalize_text, parse_cod_pep, ts_log, ts_now
from runtime.config import (
    APP_DIRS,
    EMPRESA_SIGLAS_VALIDAS,
    GANHOS_NUMERIC_FIELDS,
    ORDERED_COLUMNS,
    REGIONAL_TO_COD,
    ROOT_COLUMNS,
    ConfigManager,
)
# DataAccessLayer = ObraReadRepo (alias preservado do legado)
from core.repositories.obra_read_repo import ObraReadRepo as DataAccessLayer

# Re-exports de core/repositories/sqlite_connection (Passo 5b.ii).
from core.repositories.sqlite_connection import (  # noqa: F401
    DATABASE_BUSY_CODE,
    DATABASE_LOCKED_CODE,
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_CONNECT_TIMEOUT_S,
    DatabaseBusyError,
    DatabaseLockedError,
    _SQLiteWriteOwner,
    is_database_busy_exception,
    is_database_locked_exception,
    is_sqlite_busy_error,
)

LOGGER = logging.getLogger("codigo5_coplan")


# ---------------------------------------------------------------------------
# Constantes preservadas como fallback (nao mais usadas pelo core).
# ---------------------------------------------------------------------------
_SQLITE_BUSY_ERRORS = (
    "database is locked",
    "database is busy",
    "database table is locked",
    "database schema is locked",
)
_DATABASE_BUSY_TEXT_TOKENS = (
    "banco em uso por outro usuario",
    "banco em uso por outro usuário",
    "banco em utilização",
    "banco ocupado",
)


# ---------------------------------------------------------------------------
# Lock files (wrappers em core/repositories/sqlite_lock)
# ---------------------------------------------------------------------------
def get_lock_info_path(db_path: str | None) -> str:
    from core.repositories.sqlite_lock import get_lock_info_path as _impl
    return _impl(db_path)


def write_lock_info(db_path: str | None) -> None:
    from core.repositories.sqlite_lock import write_lock_info as _impl
    _impl(db_path)


def clear_lock_info(db_path: str | None) -> None:
    from core.repositories.sqlite_lock import clear_lock_info as _impl
    _impl(db_path)


def create_lock_info(lock_path: str, action: str) -> None:
    from core.repositories.sqlite_lock import create_lock_info as _impl
    _impl(lock_path, action)


def remove_lock_info(lock_path: str) -> None:
    from core.repositories.sqlite_lock import remove_lock_info as _impl
    _impl(lock_path)


def read_lock_info(lock_path: str) -> dict[str, Any] | None:
    from core.repositories.sqlite_lock import read_lock_info as _impl
    return _impl(lock_path)


def _lock_info_summary(lock_info: dict[str, Any] | None) -> str:
    from core.repositories.sqlite_lock import lock_info_summary as _impl
    return _impl(lock_info)


def _format_lock_time(value: Any) -> str:
    from core.repositories.sqlite_lock import _format_lock_time as _impl
    return _impl(value)


def build_database_busy_message(lock_info: dict[str, Any] | None = None) -> str:
    from core.repositories.sqlite_lock import build_database_busy_message as _impl
    return _impl(lock_info)


def build_database_locked_message(lock_info: dict[str, Any] | None = None) -> str:
    from core.repositories.sqlite_lock import build_database_locked_message as _impl
    return _impl(lock_info)


# ---------------------------------------------------------------------------
# Logging especifico de conexao (rastreio de busy/locked + Qt thread)
# ---------------------------------------------------------------------------
def log_connect_debug(
    stage: str,
    db_path: str | None,
    *,
    exc: Exception | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    db_path_s = str(db_path or "").strip()
    lock_path = get_lock_info_path(db_path_s)
    lock_exists = bool(lock_path and os.path.exists(lock_path))
    lock_info = read_lock_info(lock_path) if lock_exists else None
    file_exists = bool(db_path_s and os.path.exists(db_path_s))
    file_size = -1
    if file_exists:
        try:
            file_size = os.path.getsize(db_path_s)
        except Exception:
            file_size = -1
    exc_text = ""
    if exc is not None:
        exc_text = f"{type(exc).__name__}: {exc}"
    payload = extra if isinstance(extra, dict) else {}
    app = QtWidgets.QApplication.instance() if QtWidgets is not None else None
    ui_thread_name = ""
    on_ui_thread = False
    try:
        if app is not None:
            ui_thread_name = str(app.thread().objectName() or "<qt-main>")
            on_ui_thread = QtCore.QThread.currentThread() == app.thread()
    except Exception:
        ui_thread_name = ""
        on_ui_thread = False
    try:
        LOGGER.warning(
            "[DB-CONNECT-DEBUG] stage=%s db_path=%s exists=%s size=%s "
            "lock_path=%s lock_exists=%s lock=%s busy=%s pid=%s tid=%s "
            "qt_ui_thread=%s on_ui_thread=%s extra=%s exc=%s",
            stage,
            db_path_s or "<vazio>",
            file_exists,
            file_size,
            lock_path or "<vazio>",
            lock_exists,
            _lock_info_summary(lock_info),
            is_database_busy_exception(exc) if exc is not None else False,
            os.getpid(),
            threading.get_ident(),
            ui_thread_name or "<n/a>",
            on_ui_thread,
            payload,
            exc_text or "<none>",
        )
    except Exception as log_exc:
        logging.warning(
            "[DB-CONNECT-DEBUG] Falha ao registrar log stage=%s erro=%s",
            stage,
            log_exc,
        )


# ---------------------------------------------------------------------------
# Connection wrappers (injetam log_connect_debug)
# ---------------------------------------------------------------------------
def open_sqlite_safe(db_path: str) -> sqlite3.Connection:
    from core.repositories.sqlite_connection import open_sqlite_safe as _impl
    return _impl(db_path, log_callback=log_connect_debug)


@contextmanager
def write_transaction_safe(db_manager):
    from core.repositories.sqlite_connection import write_transaction_safe as _impl
    with _impl(db_manager, log_callback=log_connect_debug) as cur:
        yield cur


def run_sql_write_safe(
    db_path: str,
    sql: str,
    params: Sequence[Any] = (),
    *,
    action: str = "Escrita em banco",
    retries: int = 0,
    retry_delay_ms: int = 500,
) -> tuple[bool, str | None]:
    from core.repositories.sqlite_connection import run_sql_write_safe as _impl
    return _impl(
        db_path,
        sql,
        params,
        action=action,
        retries=retries,
        retry_delay_ms=retry_delay_ms,
        log_callback=log_connect_debug,
    )


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------
def backup_on_error(method):
    """Wrapper que faz rollback + backup em caso de erro nao-busy."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:
            if isinstance(exc, DatabaseBusyError):
                raise
            if isinstance(exc, sqlite3.OperationalError) and is_sqlite_busy_error(exc):
                raise
            if getattr(self, "conn", None):
                try:
                    self.conn.rollback()
                except Exception:
                    pass
            backup_path = self.backup_database()
            if backup_path:
                logging.error(f"Backup criado devido a erro em {backup_path}")
            raise
    return wrapper


def with_lock_action(action: str):
    action_s = str(action or "").strip() or "Salvando alterações"

    def decorator(method):
        @wraps(method)
        def wrapper(self, *args, **kwargs):
            previous_action = getattr(self, "_current_lock_action", "Salvando alterações")
            self._current_lock_action = action_s
            try:
                return method(self, *args, **kwargs)
            finally:
                self._current_lock_action = previous_action

        return wrapper

    return decorator


def retry_on_busy(max_retries: int = 0, base_delay: float = 0.5):
    def decorator(method):
        @wraps(method)
        def wrapper(*args, **kwargs):
            t_retries = ts_now()
            retry_count = 0
            busy_events = 0
            slept_total = 0.0
            last_busy_error = ""
            last_busy_details = ""

            def _classify_busy(exc_obj: Exception) -> tuple[str, str]:
                details = str(getattr(exc_obj, "details", "") or exc_obj)
                text = details.lower()
                if "database is locked" in text:
                    return "database is locked", details
                if "database is busy" in text:
                    return "database is busy", details
                if "database table is locked" in text:
                    return "database table is locked", details
                if "database schema is locked" in text:
                    return "database schema is locked", details
                return "busy/locked", details

            for attempt in range(max_retries + 1):
                try:
                    result = method(*args, **kwargs)
                    if busy_events:
                        ts_log(
                            f"retry_on_busy({method.__name__}) tentativas={attempt + 1}, "
                            f"busy_events={busy_events}, retries={retry_count}, "
                            f"erro='{last_busy_error}', detalhe='{last_busy_details}', "
                            f"dormiu_total={slept_total:.3f}s",
                            t_retries,
                        )
                    return result
                except DatabaseBusyError as exc:
                    busy_events += 1
                    last_busy_error, last_busy_details = _classify_busy(exc)
                    if attempt >= max_retries:
                        ts_log(
                            f"retry_on_busy({method.__name__}) tentativas={attempt + 1}, "
                            f"busy_events={busy_events}, retries={retry_count}, "
                            f"erro='{last_busy_error}', detalhe='{last_busy_details}', "
                            f"dormiu_total={slept_total:.3f}s",
                            t_retries,
                        )
                        raise
                    delay = max(base_delay, 0.0)
                    logging.warning(
                        "retry_on_busy(%s): erro '%s' (%s) (tentativa %s/%s), "
                        "dormindo %.3fs antes de tentar novamente.",
                        method.__name__,
                        last_busy_error,
                        last_busy_details,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                    )
                    time.sleep(delay)
                    slept_total += delay
                    retry_count += 1
                except sqlite3.OperationalError as exc:
                    if not is_sqlite_busy_error(exc):
                        raise
                    busy_events += 1
                    last_busy_error, last_busy_details = _classify_busy(exc)
                    if attempt >= max_retries:
                        ts_log(
                            f"retry_on_busy({method.__name__}) tentativas={attempt + 1}, "
                            f"busy_events={busy_events}, retries={retry_count}, "
                            f"erro='{last_busy_error}', detalhe='{last_busy_details}', "
                            f"dormiu_total={slept_total:.3f}s",
                            t_retries,
                        )
                        owner = args[0] if args else None
                        db_path = getattr(owner, "db_path", None) if owner else None
                        raise DatabaseBusyError(
                            db_path,
                            details=last_busy_details,
                        ) from exc
                    delay = max(base_delay, 0.0)
                    logging.warning(
                        "retry_on_busy(%s): erro '%s' (%s) (tentativa %s/%s), "
                        "dormindo %.3fs antes de tentar novamente.",
                        method.__name__,
                        last_busy_error,
                        last_busy_details,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                    )
                    time.sleep(delay)
                    slept_total += delay
                    retry_count += 1
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Qt: DBCallableWorker + run_write_in_qthread_if_ui_thread
# ---------------------------------------------------------------------------
if _HAS_QT:
    class DBCallableWorker(QObject):
        finished = Signal(object, object)

        def __init__(self, operation: Callable[[], Any]) -> None:
            super().__init__()
            self._operation = operation

        @Slot()
        def run(self) -> None:
            try:
                result = self._operation()
                self.finished.emit(result, None)
            except Exception as exc:
                self.finished.emit(None, exc)
else:  # web headless: Qt ausente; o worker nunca e instanciado
    DBCallableWorker = None  # type: ignore[assignment,misc]


def run_write_in_qthread_if_ui_thread(method):
    @wraps(method)
    def wrapper(*args, **kwargs):
        app = QtWidgets.QApplication.instance() if QtWidgets is not None else None
        if app is None:
            return method(*args, **kwargs)
        ui_thread = app.thread()
        if QtCore.QThread.currentThread() != ui_thread:
            return method(*args, **kwargs)

        result_holder: dict[str, Any] = {"result": None, "error": None}
        thread = QtCore.QThread()
        worker = DBCallableWorker(lambda: method(*args, **kwargs))
        loop = QtCore.QEventLoop()

        worker.moveToThread(thread)

        def on_finished(result: Any, error: Any) -> None:
            result_holder["result"] = result
            result_holder["error"] = error
            loop.quit()

        thread.started.connect(worker.run)
        worker.finished.connect(on_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.start()
        try:
            loop.exec()
        finally:
            try:
                running = thread.isRunning()
            except RuntimeError:
                running = False
            if running:
                try:
                    thread.quit()
                except RuntimeError:
                    pass
                try:
                    thread.wait(5000)
                except RuntimeError:
                    pass
            else:
                try:
                    thread.wait(100)
                except RuntimeError:
                    pass
            try:
                thread.deleteLater()
            except RuntimeError:
                pass

        error = result_holder.get("error")
        if error is not None:
            raise error
        return result_holder.get("result")

    return wrapper


# ---------------------------------------------------------------------------
# Helpers de COD_PEP (extraidos de codigo5_coplan.py)
# ---------------------------------------------------------------------------
def _ensure_empresa_cod_pep_tail(columns: Sequence[str]) -> list[str]:
    cols = [str(c) for c in list(columns or [])]
    reordered = [c for c in cols if c not in {"empresa", "cod_pep"}]
    if "empresa" in cols:
        reordered.append("empresa")
    if "cod_pep" in cols:
        reordered.append("cod_pep")
    return reordered


def _coerce_obra_row_dict(db, obra_row_or_dict: Any) -> dict[str, Any]:
    if isinstance(obra_row_or_dict, dict):
        return dict(obra_row_or_dict)
    if isinstance(obra_row_or_dict, Sequence) and not isinstance(obra_row_or_dict, (str, bytes)):
        cols = []
        try:
            cols = list(db.get_column_names())
        except Exception:
            cols = []
        if cols:
            size = min(len(cols), len(obra_row_or_dict))
            return {cols[i]: obra_row_or_dict[i] for i in range(size)}
    return {}


def get_empresa_sigla_from_config(config: dict | None = None) -> str:
    if config is None or not isinstance(config, dict):
        config = ConfigManager.load_config()
    candidates = [
        config.get("empresa_sigla"),
        config.get("empresa"),
        config.get("sigla_empresa"),
    ]
    for raw in candidates:
        sigla = normalize_text(raw)
        if sigla in EMPRESA_SIGLAS_VALIDAS:
            return sigla
    raise ValueError(
        "Empresa não configurada corretamente. Defina a sigla em Configurações Gerais "
        f"({', '.join(sorted(EMPRESA_SIGLAS_VALIDAS))})."
    )


def cod_pep(
    db,
    obra_row_or_dict,
    empresa_sigla: str,
    selected_cods: list[str] | None = None,
    selected_years: list[str] | None = None,
) -> str:
    # Numeração sempre global:
    # - SSSS é único por empresa em toda a base (todos os anos).
    # - AAA é único dentro do ano da própria obra.
    # Os parâmetros selected_cods/selected_years são mantidos por
    # compatibilidade, mas NÃO restringem a busca de códigos existentes —
    # caso contrário cadastros feitos depois da geração produzem colisões.
    from core.services.row_helpers import first_non_empty_value as _first_non_empty_value

    _ = selected_cods, selected_years
    obra = _coerce_obra_row_dict(db, obra_row_or_dict)
    if not obra and isinstance(obra_row_or_dict, dict):
        obra = dict(obra_row_or_dict)
    obra_id = str(obra.get("cod") or obra.get("id") or "").strip() or "<sem-cod>"

    empresa = normalize_text(empresa_sigla)
    if empresa not in EMPRESA_SIGLAS_VALIDAS:
        raise ValueError(
            f"Sigla de empresa inválida para COD_PEP: '{empresa_sigla}'. "
            f"Permitidas: {', '.join(sorted(EMPRESA_SIGLAS_VALIDAS))}."
        )

    yy = datetime.datetime.now().strftime("%y")
    regional_desc = _first_non_empty_value(obra, ["nome_regional", "regional_desc", "regional"])
    regional_key = normalize_text(regional_desc)
    regional_cod = REGIONAL_TO_COD.get(regional_key)
    if not regional_cod:
        msg = (
            f"COD_PEP não gerado para obra {obra_id}: regional '{regional_desc}' "
            "não encontrada no mapeamento."
        )
        LOGGER.warning(msg)
        print(msg)
        return ""

    ano_obra = str(obra.get("ano_", "")).strip()
    nome_projeto = str(obra.get("nome_projeto", "")).strip()
    pacote_atual = _first_non_empty_value(
        obra, ["pacote", "tipo_pacote", "pasta_tecnica", "pasta técnica"]
    )
    pacote_atual_key = str(pacote_atual or "").strip().upper()
    if not ano_obra:
        msg = f"COD_PEP não gerado para obra {obra_id}: ano_ ausente (ano_='{ano_obra}')."
        LOGGER.warning(msg)
        print(msg)
        return ""
    ano_obra_key = str(ano_obra).strip()
    nome_projeto_key = str(nome_projeto or "").strip().upper()
    if not nome_projeto_key:
        nome_projeto_key = f"__SEM_PROJETO__:{obra_id}"

    if not getattr(db, "conn", None):
        with db._with_connection():
            return cod_pep(db, obra, empresa)
    cursor = db._get_cursor()
    if not cursor:
        return ""

    ano_col_sql = (
        db._escape_identifier("ano_")
        if hasattr(db, "_escape_identifier")
        else '"ano_"'
    )

    agrup = None
    anomalia_detectada = False
    encontrados: list[tuple[str, str]] = []
    # Reuso de AAA por projeto: busca GLOBAL por nome_projeto.
    # Se existir registro do mesmo projeto+pacote+ano, reusa o AAA.
    cursor.execute(
        "SELECT cod_pep, ano_, tipo_pacote FROM obras "
        "WHERE UPPER(TRIM(COALESCE(nome_projeto, '')))=? "
        "AND cod_pep IS NOT NULL AND TRIM(cod_pep)<>''",
        (nome_projeto_key,),
    )
    rows = cursor.fetchall()
    if rows and pacote_atual_key:
        for cod_existente, ano_exist, pacote_exist in rows:
            ano_exist_key = str(ano_exist or "").strip()
            pacote_exist_key = str(pacote_exist or "").strip().upper()
            encontrados.append((ano_exist_key, str(pacote_exist or "").strip()))
            if pacote_exist_key == pacote_atual_key and ano_exist_key == ano_obra_key:
                parsed = parse_cod_pep(cod_existente)
                if parsed:
                    agrup = parsed["agrup"]
                    break
        if agrup is None:
            for _, ano_exist, pacote_exist in rows:
                ano_exist_key = str(ano_exist or "").strip()
                pacote_exist_key = str(pacote_exist or "").strip().upper()
                if pacote_exist_key == pacote_atual_key and ano_exist_key != ano_obra_key:
                    anomalia_detectada = True
                    break

    if agrup is None:
        # AAA é único dentro do ano: varre todas as obras do mesmo ano,
        # independente de filtro de escopo, para não colidir com registros
        # cadastrados depois da geração em lote.
        max_agrup = -1
        cursor.execute(
            f"SELECT cod_pep FROM obras "
            f"WHERE TRIM(COALESCE({ano_col_sql}, ''))=? "
            f"AND cod_pep IS NOT NULL AND TRIM(cod_pep)<>''",
            (ano_obra_key,),
        )
        for (cod_existente,) in cursor.fetchall():
            parsed = parse_cod_pep(cod_existente)
            if parsed:
                max_agrup = max(max_agrup, int(parsed["agrup"]))
        agrup = max_agrup + 1
    if anomalia_detectada:
        if not encontrados:
            encontrados = [
                (str(ano_exist or "").strip(), str(pacote_exist or "").strip())
                for _, ano_exist, pacote_exist in rows
            ]
        LOGGER.warning(
            "ANOMALIA COD_PEP: obra=%s nome_projeto=%s pacote_atual=%s ano_obra=%s encontrados=%s",
            obra_id,
            nome_projeto_key,
            pacote_atual_key,
            ano_obra,
            encontrados,
        )
    if not (0 <= int(agrup) <= 999):
        raise ValueError(
            f"Limite de agrupamento AAA excedido para o ano {ano_obra_key}. "
            f"Valor calculado: {agrup}."
        )

    # SSSS é único por empresa DENTRO DO ANO DE GERAÇÃO (YY): reinicia a
    # cada ano, pois o YY já diferencia o COD_PEP (26-...-0001 ≠ 27-...-0001),
    # então não há sobrescrita e a identidade da obra não se perde.
    # Aloca o MENOR sequencial disponível no ano (preenche buracos): escolhe
    # o primeiro inteiro >= 0 não ocupado. Reaproveita faixas livres antes
    # de avançar (ex.: 125..499 livres com 500..888 ocupados -> usa 125,
    # depois 889). Sequenciais já existentes nunca mudam.
    # "Em uso" (no ano YY) = SSSS nas obras atuais UNIÃO SSSS já emitidos
    # algum dia (tabela cod_pep_emitidos, escopada por empresa+yy): assim um
    # SSSS de obra EXCLUÍDA do mesmo ano permanece reservado e nunca volta.
    used_seqs: set[int] = set()
    cursor.execute(
        "SELECT cod_pep FROM obras "
        "WHERE empresa=? "
        "AND cod_pep IS NOT NULL AND TRIM(cod_pep)<>''",
        (empresa,),
    )
    for (cod_existente,) in cursor.fetchall():
        parsed = parse_cod_pep(cod_existente)
        if parsed and parsed["empresa"] == empresa and parsed["yy"] == yy:
            used_seqs.add(int(parsed["seq"]))
    try:
        cursor.execute(
            "SELECT seq FROM cod_pep_emitidos WHERE empresa=? AND yy=?",
            (empresa, yy),
        )
        for (seq_emit,) in cursor.fetchall():
            used_seqs.add(int(seq_emit))
    except Exception:  # noqa: BLE001
        pass  # tabela pode não existir em banco ainda não migrado
    seq = 0
    while seq in used_seqs:
        seq += 1
    if not (0 <= int(seq) <= 9999):
        raise ValueError(
            f"Não há sequencial SSSS livre (0000-9999) para empresa "
            f"{empresa} no ano {yy}."
        )

    bay_local = obra.get("novo_bay")
    if bay_local in (None, ""):
        bay_local = obra.get("bay_novo", "")
    projeto_tem_bay_novo = normalize_text(bay_local) == "SIM"

    # Se qualquer obra do mesmo projeto tiver bay novo = SIM, todas recebem sufixo A.
    if not projeto_tem_bay_novo and nome_projeto:
        bay_col = None
        try:
            cols_obras = {str(c) for c in (db.get_column_names() or [])}
            if "novo_bay" in cols_obras:
                bay_col = "novo_bay"
            elif "bay_novo" in cols_obras:
                bay_col = "bay_novo"
        except Exception:
            bay_col = "novo_bay"
        if bay_col:
            bay_col_sql = (
                db._escape_identifier(bay_col)
                if hasattr(db, "_escape_identifier")
                else '"' + str(bay_col).replace('"', '""') + '"'
            )
            try:
                cursor.execute(
                    f"SELECT 1 FROM obras "
                    f"WHERE ano_=? AND nome_projeto=? "
                    f"AND UPPER(TRIM(COALESCE({bay_col_sql}, '')))='SIM' "
                    "LIMIT 1",
                    (ano_obra, nome_projeto),
                )
                projeto_tem_bay_novo = cursor.fetchone() is not None
            except Exception:
                pass

    letra = "A" if projeto_tem_bay_novo else "U"
    resultado = f"{empresa}-{yy}-{regional_cod}-{int(agrup):03d}-{int(seq):04d}-{letra}"
    # Reserva permanente do SSSS no registro de emitidos (INSERT OR IGNORE).
    # Comita junto com a escrita da obra; se a obra for excluida depois, o
    # registro permanece e o SSSS nunca volta a ser disponibilizado.
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO cod_pep_emitidos "
            "(empresa, yy, seq, cod_pep, obra_cod, emitido_em) "
            "VALUES (?,?,?,?,?,?)",
            (empresa, yy, int(seq), resultado, obra_id,
             datetime.datetime.now().strftime('%d/%m/%y %H:%M')),
        )
    except Exception:  # noqa: BLE001
        pass  # tabela pode não existir em banco ainda não migrado
    debug_msg = (
        f"COD_PEP DEBUG obra={obra_id} empresa={empresa} yy={yy} "
        f"regional_cod={regional_cod} agrup={int(agrup):03d} seq={int(seq):04d} letra={letra}"
    )
    print(debug_msg)
    LOGGER.info(debug_msg)
    return resultado


def ensure_schema_business_patch(db_manager) -> None:
    if not db_manager:
        return
    if not getattr(db_manager, "conn", None):
        with db_manager._with_connection():
            return ensure_schema_business_patch(db_manager)
    cursor = db_manager._get_cursor()
    if not cursor:
        return
    with db_manager.write_transaction():
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS tecnico_scope_tokens ("
            "scope_key TEXT PRIMARY KEY, "
            "token TEXT NOT NULL, "
            "updated_at TEXT"
            ")"
        )
    try:
        from core.repositories.sqlite_schema import list_table_columns
        existing_cols = set(list_table_columns(cursor, "obras"))
    except Exception:
        existing_cols = set()
    required_cols = {
        "criterios_status": "TEXT",
        "criterios_motivos": "TEXT",
        "criterios_limite_carreg": "TEXT",
        "despacho_status": "TEXT DEFAULT 'NAO_DESPACHADA'",
        "despacho_em": "TEXT",
        "despacho_ref": "TEXT",
    }
    missing_cols = [col for col in required_cols if col not in existing_cols]
    if missing_cols:
        with db_manager.write_transaction():
            for col in missing_cols:
                cursor.execute(
                    f"ALTER TABLE obras ADD COLUMN {col} {required_cols[col]}"
                )
        db_manager.update_columns()


# ---------------------------------------------------------------------------
# DatabaseManager (gigante, ~1800 linhas) -- extraido de codigo5_coplan.py
# ---------------------------------------------------------------------------
class DatabaseManager:
    conn: Optional[sqlite3.Connection]
    cursor: Optional[sqlite3.Cursor]

    def __init__(self):
        self.conn = None
        self.cursor = None
        self.columns = []
        # Lista de colunas base da aplicação
        self.root_columns = ROOT_COLUMNS.copy()
        self.db_path = None
        self.data_access_layer: DataAccessLayer | None = None
        # Lista de pacotes permitidos para edição/visualização
        # ``None`` indica que todos os pacotes são permitidos
        self.allowed_pacotes = None
        self._last_backup_by_label: Dict[str, datetime.datetime] = {}
        self._current_lock_action = "Salvando alterações"

    def get_empresa_sigla_from_config(self) -> str:
        """Retorna a sigla da empresa configurada ou vazio quando indisponível."""
        try:
            return normalize_text(get_empresa_sigla_from_config())
        except Exception:
            return ""

    # === SCHEMA VERSIONING BEGIN ===
    CURRENT_SCHEMA_VERSION = 1
    SCHEMA_VERSION_KEY = "schema_version"

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Atualização de meta do schema")
    def create_meta_table_if_needed(self) -> None:
        """Wrapper -- delega CREATE TABLE meta ao core/repositories/sqlite_schema."""
        cursor = self._get_cursor()
        if not cursor:
            return
        with self.write_transaction():
            from core.repositories.sqlite_schema import (
                create_meta_table_if_needed as _impl,
            )
            _impl(cursor)

    def get_schema_version(self) -> int:
        """Wrapper -- delega leitura ao core; preserva log de warning na UI."""
        self.create_meta_table_if_needed()
        cursor = self._get_cursor()
        if not cursor:
            return 0
        try:
            from core.repositories.sqlite_schema import read_schema_version as _impl
            return _impl(cursor, self.SCHEMA_VERSION_KEY)
        except Exception as exc:
            LOGGER.warning("Falha ao ler schema_version, assumindo 0: %s", exc)
            return 0

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Atualização de versão do schema")
    def set_schema_version(self, version: int) -> None:
        """Wrapper -- delega INSERT/UPDATE ao core/repositories/sqlite_schema."""
        cursor = self._get_cursor()
        if not cursor:
            return
        with self.write_transaction():
            from core.repositories.sqlite_schema import write_schema_version as _impl
            _impl(cursor, version, self.SCHEMA_VERSION_KEY)

    def migrate_0_to_1(self) -> None:
        """Migra schema 0 -> 1: rename de nivel_tensao + indice unico."""
        LOGGER.info("Migration 0 -> 1: iniciando ajustes iniciais de schema.")
        cursor = self._get_cursor()
        if not cursor:
            LOGGER.warning("Migration 0 -> 1: cursor indisponível.")
            return
        try:
            from core.repositories.sqlite_schema import (
                list_table_columns,
                rename_column_if_needed,
            )
            cols = list_table_columns(cursor, "obras")
            if "nivel_tensao" in cols and "nivel_tensao_obra" not in cols:
                LOGGER.info("Migration 0 -> 1: renomeando coluna nivel_tensao.")
                with self.write_transaction():
                    rename_column_if_needed(
                        cursor, "obras", "nivel_tensao", "nivel_tensao_obra"
                    )
        except Exception as exc:
            LOGGER.warning("Migration 0 -> 1: falha ao renomear coluna: %s", exc)

        LOGGER.info("Migration 0 -> 1: garantindo índice único.")
        self._create_unique_index()
        LOGGER.info("Migration 0 -> 1: concluída.")

    def run_schema_migrations(self) -> None:
        current_version = self.get_schema_version()
        if current_version >= self.CURRENT_SCHEMA_VERSION:
            LOGGER.info("Schema já está na versão %s.", current_version)
            return

        for version in range(current_version, self.CURRENT_SCHEMA_VERSION):
            next_version = version + 1
            migrate_fn = getattr(self, f"migrate_{version}_to_{next_version}", None)
            if not migrate_fn:
                LOGGER.error(
                    "Migração ausente: %s -> %s. Interrompendo.",
                    version,
                    next_version,
                )
                return
            LOGGER.info("Executando migração %s -> %s.", version, next_version)
            migrate_fn()
            self.set_schema_version(next_version)
            LOGGER.info("Migração %s -> %s finalizada.", version, next_version)
    # === SCHEMA VERSIONING END ===

    def _get_cursor(self):
        if not self.conn:
            return None
        if not self.cursor:
            self.cursor = self.conn.cursor()
        return self.cursor

    @contextmanager
    def _with_connection(self):
        if self.conn:
            log_connect_debug(
                "db_manager._with_connection.reuse",
                self.db_path,
                extra={"has_cursor": self.cursor is not None},
            )
            yield self.conn
            return
        if not self.db_path:
            log_connect_debug("db_manager._with_connection.no_db_path", self.db_path)
            yield None
            return
        log_connect_debug("db_manager._with_connection.opening", self.db_path)
        conn: sqlite3.Connection | None = None
        try:
            conn = open_sqlite_safe(self.db_path)
            self.conn = conn
            self.cursor = conn.cursor()
            self._apply_sqlite_pragmas()
            log_connect_debug(
                "db_manager._with_connection.ready",
                self.db_path,
                extra={"in_transaction": bool(conn.in_transaction)},
            )
            yield conn
        except Exception as exc:
            log_connect_debug("db_manager._with_connection.error", self.db_path, exc=exc)
            raise
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception as exc:
                    log_connect_debug(
                        "db_manager._with_connection.close_error",
                        self.db_path,
                        exc=exc,
                    )
                finally:
                    self.conn = None
                    self.cursor = None
            log_connect_debug("db_manager._with_connection.closed", self.db_path)

    def _ensure_cache_loaded(self) -> None:
        t_total = ts_now()
        if not self.db_path:
            return
        # Recria o DAL quando e None OU aponta para outro banco (troca de
        # banco) -- senao continuaria lendo o banco anterior.
        if (self.data_access_layer is None
                or getattr(self.data_access_layer, "db_path", None) != self.db_path):
            t_dal = ts_now()
            self.data_access_layer = DataAccessLayer(
                self.db_path,
                self.columns,
                self._normalize_row,
            )
            ts_log("Criar DataAccessLayer", t_dal)
        data_access_layer = self.data_access_layer
        if data_access_layer is None:
            return
        data_access_layer.set_columns(self.columns)
        t_load = ts_now()
        data_access_layer.ensure_loaded()
        ts_log("DataAccessLayer.ensure_loaded()", t_load)
        ts_log("_ensure_cache_loaded TOTAL", t_total)

    def _refresh_cache(self) -> None:
        if not self.db_path:
            return
        # Recria o DAL quando ele e None OU aponta para outro banco (troca
        # de banco): o ObraReadRepo guarda db_path no construtor, entao
        # reusar o antigo releria o banco anterior.
        if (self.data_access_layer is None
                or getattr(self.data_access_layer, "db_path", None) != self.db_path):
            self.data_access_layer = DataAccessLayer(
                self.db_path,
                self.columns,
                self._normalize_row,
            )
        data_access_layer = self.data_access_layer
        if data_access_layer is None:
            return
        data_access_layer.set_columns(self.columns)
        data_access_layer.refresh_cache()

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Conexão e preparação do banco")
    def connect(self, db_path):
        t_connect_total = ts_now()
        t_start = ts_now()
        ts_log("connect(): INICIO", t_start)
        self.db_path = db_path
        log_connect_debug(
            "db_manager.connect.start",
            db_path,
            extra={
                "action": getattr(self, "_current_lock_action", ""),
                "has_existing_conn": self.conn is not None,
            },
        )
        try:
            os.chmod(db_path, 0o600)
        except Exception:
            pass
        log_connect_debug("db_manager.connect.enter_with_connection", db_path)
        with self._with_connection() as conn:
            log_connect_debug("db_manager.connect.step.apply_sqlite_pragmas", db_path)
            t_apply_pragmas = ts_now()
            self._apply_sqlite_pragmas()
            ts_log("após _apply_sqlite_pragmas()", t_apply_pragmas)
            log_connect_debug("db_manager.connect.step.create_table_if_needed", db_path)
            t_create_table = ts_now()
            self.create_table_if_needed()
            ts_log("após create_table_if_needed()", t_create_table)
            log_connect_debug("db_manager.connect.step.run_schema_migrations", db_path)
            t_schema = ts_now()
            self.run_schema_migrations()
            ts_log("após run_schema_migrations()", t_schema)
            log_connect_debug("db_manager.connect.step.ensure_schema_business_patch", db_path)
            t_business_patch = ts_now()
            ensure_schema_business_patch(self)
            ts_log("após ensure_schema_business_patch(self)", t_business_patch)
            log_connect_debug("db_manager.connect.step.update_columns_first", db_path)
            t_update_first = ts_now()
            self.update_columns()
            ts_log("após update_columns() (primeiro)", t_update_first)
            t_rename = ts_now()
            try:
                cursor = self._get_cursor()
                if cursor:
                    cursor.execute("PRAGMA table_info(obras)")
                    info = [c[1] for c in cursor.fetchall()]
                    if "nivel_tensao" in info and "nivel_tensao_obra" not in info:
                        with self.write_transaction():
                            cursor.execute(
                                "ALTER TABLE obras RENAME COLUMN nivel_tensao TO nivel_tensao_obra"
                            )
            except Exception:
                pass
            ts_log("após o bloco de rename nivel_tensao -> nivel_tensao_obra", t_rename)
            log_connect_debug("db_manager.connect.step.audit_columns", db_path)
            t_audit_cols = ts_now()
            for col in [
                "data_criacao",
                "data_modificacao",
                "criado_por",
                "modificado_por",
                "ganhos_totais_antes",
                "ganhos_totais_depois",
                "ganhos_totais_atual",
            ]:
                self.add_column_if_missing(col)
            ts_log("após o loop de colunas de auditoria", t_audit_cols)
            t_pi_base = ts_now()
            self.add_column_if_missing("pi_base")
            ts_log('após add_column_if_missing("pi_base")', t_pi_base)
            t_obra_aprovada = ts_now()
            self.add_column_if_missing("obra_aprovada")
            ts_log('após add_column_if_missing("obra_aprovada")', t_obra_aprovada)
            t_tensao_operacao = ts_now()
            self.add_column_if_missing("tensao_operacao")
            ts_log('após add_column_if_missing("tensao_operacao")', t_tensao_operacao)
            t_tensao_min = ts_now()
            self.add_column_if_missing("tensao_min_linha_inicial")
            self.add_column_if_missing("tensao_min_linha_final")
            ts_log("após colunas tensao_min_linha_*", t_tensao_min)
            t_snapshot = ts_now()
            self.add_column_if_missing("tecnico_snapshot_token")
            self.add_column_if_missing("tecnico_snapshot_at")
            self.add_column_if_missing("tecnico_snapshot_src")
            self.add_column_if_missing("tecnico_dirty")
            ts_log("após colunas snapshot técnico", t_snapshot)
            t_pep = ts_now()
            self.add_column_if_missing("empresa")
            self.add_column_if_missing("cod_pep")
            ts_log("após colunas PEP (empresa, cod_pep)", t_pep)
            log_connect_debug("db_manager.connect.step.update_columns_second", db_path)
            t_update_second = ts_now()
            self.update_columns()
            ts_log("após update_columns() (segundo)", t_update_second)

            log_connect_debug("db_manager.connect.step.check_normalize_decimal", db_path)
            t_normalize_check = ts_now()
            normalize_needed = True
            try:
                normalize_needed = self._has_numeric_decimal_dot_in_db()
            except Exception as exc:
                logging.info(
                    "Falha na checagem de ponto decimal; executando normalização por segurança: %s",
                    exc,
                )
                normalize_needed = True
            ts_log("checagem _has_numeric_decimal_dot_in_db()", t_normalize_check)
            logging.info(
                "Normalização decimal necessária: %s",
                "SIM" if normalize_needed else "NÃO",
            )
            if normalize_needed:
                log_connect_debug("db_manager.connect.step.normalize_decimal_in_db", db_path)
                t_normalize = ts_now()
                self.normalize_decimal_in_db()
                ts_log("após normalize_decimal_in_db()", t_normalize)
            else:
                logging.info(
                    "[TIMESTAMP] normalize_decimal_in_db() pulado (sem ponto decimal detectado)"
                )
            log_connect_debug("db_manager.connect.step.create_unique_index", db_path)
            t_unique = ts_now()
            self._create_unique_index()
            ts_log("após _create_unique_index()", t_unique)
            log_connect_debug("db_manager.connect.step.weekly_backup", db_path)
            t_backup = ts_now()
            self.weekly_backup()
            ts_log("após weekly_backup()", t_backup)
        log_connect_debug("db_manager.connect.step.refresh_cache", db_path)
        t_refresh = ts_now()
        self._refresh_cache()
        ts_log("após _refresh_cache()", t_refresh)
        # Registro permanente de PEPs emitidos (cria tabela + backfill).
        try:
            self._ensure_cod_pep_ledger()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Falha ao garantir cod_pep_emitidos: %s", exc)
        ts_log("connect(): FIM", t_connect_total)
        log_connect_debug(
            "db_manager.connect.success",
            db_path,
            extra={"columns_count": len(self.columns)},
        )

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Criação da tabela de obras")
    @retry_on_busy()
    def create_table_if_needed(self):
        if not self.conn:
            with self._with_connection():
                return self.create_table_if_needed()
        cols_def = ["cod TEXT PRIMARY KEY"]
        for col in ORDERED_COLUMNS:
            if col == "cod":
                continue
            if col == "tecnico_dirty":
                cols_def.append(f"{col} TEXT DEFAULT 'NÃO'")
            else:
                cols_def.append(f"{col} TEXT")
        sql = "CREATE TABLE IF NOT EXISTS obras (\n            " + ",\n            ".join(cols_def) + "\n        );"
        cursor = self._get_cursor()
        if not cursor:
            return
        with self.write_transaction():
            cursor.execute(sql)
        self.update_columns()

    def update_columns(self):
        """Atualiza a lista de colunas com base na tabela atual."""
        if not self.conn:
            with self._with_connection():
                return self.update_columns()
        cursor = self._get_cursor()
        if not cursor:
            self.columns = []
            return
        try:
            from core.repositories.sqlite_schema import (
                compute_ordered_columns,
                list_table_columns,
            )
            existing = list_table_columns(cursor, "obras")
            ordered = compute_ordered_columns(existing, ORDERED_COLUMNS)
            self.columns = _ensure_empresa_cod_pep_tail(ordered)
        except Exception:
            self.columns = []
        if self.data_access_layer is not None:
            self.data_access_layer.set_columns(self.columns)

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Ajuste de estrutura de colunas")
    @retry_on_busy()
    def add_column_if_missing(self, column_name):
        """Adiciona uma nova coluna à tabela se ela ainda não existir."""
        if not self.conn:
            with self._with_connection():
                return self.add_column_if_missing(column_name)
        col_s = str(column_name).strip()
        if (not col_s) or col_s.lower().startswith("unnamed:"):
            return
        column_name = col_s
        if column_name not in self.columns:
            cursor = self._get_cursor()
            if not cursor:
                return
            with self.write_transaction():
                col_sql = '"' + str(column_name).replace('"', '""') + '"'
                if column_name == "tecnico_dirty":
                    cursor.execute(
                        f"ALTER TABLE obras ADD COLUMN {col_sql} TEXT DEFAULT 'NÃO'"
                    )
                else:
                    cursor.execute(f"ALTER TABLE obras ADD COLUMN {col_sql} TEXT")
            self.update_columns()

    @staticmethod
    def _escape_identifier(name: str) -> str:
        """Wrapper -- delega ao core/repositories/sqlite_schema.escape_identifier."""
        from core.repositories.sqlite_schema import escape_identifier as _impl
        return _impl(name)

    @staticmethod
    def _sanitize_alimentador(value):
        """Substitui espaços por underscores no valor informado."""
        if isinstance(value, str):
            return value.replace(" ", "_")
        return value

    @staticmethod
    def _normalize_decimal(value):
        """Converte valores como '1.23' para '1,23'."""
        if isinstance(value, str):
            val = value.strip()
            if re.fullmatch(r"-?\d+\.\d+", val):
                return val.replace(".", ",")
        return value

    def _normalize_row(self, row):
        return [self._normalize_decimal(v) for v in row]

    # === BACKUP POLICY BEGIN ===
    def _backup_dir(self) -> str:
        backup_dir = APP_DIRS.get("backups")
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            return backup_dir
        if self.db_path:
            return os.path.dirname(self.db_path)
        return os.getcwd()

    def _backup_prefix(self) -> str:
        if not self.db_path:
            return "database"
        return os.path.basename(self.db_path)

    def get_db_dir(self) -> str:
        if not self.db_path:
            return ""
        return os.path.dirname(self.db_path)

    def _backup_path(self, suffix: str) -> str:
        return os.path.join(self._backup_dir(), f"{self._backup_prefix()}.{suffix}.bak")

    def _prune_backups(self, kind: str, limit: int) -> None:
        if not self.db_path:
            return
        backup_dir = self._backup_dir()
        prefix = f"{self._backup_prefix()}."
        if kind == "timestamp":
            pattern = re.compile(rf"^{re.escape(prefix)}\d{{14}}\.bak$")
        else:
            pattern = re.compile(rf"^{re.escape(prefix)}\d{{4}}_semana\d{{2}}\.bak$")

        try:
            candidates = []
            for name in os.listdir(backup_dir):
                if pattern.match(name):
                    path = os.path.join(backup_dir, name)
                    try:
                        mtime = os.path.getmtime(path)
                    except OSError:
                        continue
                    candidates.append((mtime, path))
            candidates.sort(key=lambda item: item[0], reverse=True)
            for _, path in candidates[limit:]:
                try:
                    os.remove(path)
                    logging.info("Backup antigo removido: %s", path)
                except Exception as exc:
                    logging.warning("Falha ao remover backup antigo %s: %s", path, exc)
        except Exception as exc:
            logging.warning("Falha ao aplicar política de retenção: %s", exc)

    def _should_skip_labeled_backup(self, label: str, min_interval_minutes: int) -> bool:
        if not label or min_interval_minutes <= 0:
            return False
        last_backup = self._last_backup_by_label.get(label)
        if not last_backup:
            return False
        return datetime.datetime.now() - last_backup < datetime.timedelta(minutes=min_interval_minutes)

    def backup_database(self, label: Optional[str] = None, min_interval_minutes: int = 0):
        """Cria um backup do arquivo do banco de dados atual."""
        if not self.db_path or not os.path.exists(self.db_path):
            return None
        if label and self._should_skip_labeled_backup(label, min_interval_minutes):
            logging.info("Backup '%s' ignorado por intervalo mínimo.", label)
            return None
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            backup_path = self._backup_path(timestamp)
            shutil.copy2(self.db_path, backup_path)
            os.chmod(backup_path, 0o600)
            self._last_backup_by_label[label or ""] = datetime.datetime.now()
            self._prune_backups("timestamp", 30)
            return backup_path
        except Exception as e:
            logging.error(f"Falha ao criar backup do banco: {e}")
            return None

    def weekly_backup(self):
        """Gera backup semanal nomeado por ano e semana."""
        if not self.db_path or not os.path.exists(self.db_path):
            return None
        try:
            year, week, _ = datetime.date.today().isocalendar()
            backup_path = self._backup_path(f"{year}_semana{week:02d}")
            if os.path.exists(backup_path):
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(backup_path))
                if datetime.datetime.now() - mtime < datetime.timedelta(days=7):
                    return backup_path
            shutil.copy2(self.db_path, backup_path)
            os.chmod(backup_path, 0o600)
            self._prune_backups("weekly", 12)
            return backup_path
        except Exception as e:
            logging.error(f"Falha ao criar backup semanal: {e}")
            return None
    # === BACKUP POLICY END ===

    def set_allowed_pacotes(self, pacotes):
        """Define a lista de pacotes permitidos. ``None`` libera todos."""
        if pacotes is None:
            self.allowed_pacotes = None
        else:
            self.allowed_pacotes = [str(p).strip() for p in pacotes]

    def _apply_novo_bay_rules(self, data, exclude_cod=None):
        """Aplica as regras de consistência ao campo ``novo_bay``."""
        # get_pi_base permanece em codigo5_coplan (depende de PI_BASE_MAP/Qt prompt).
        from runtime.pi_base import get_pi_base  # noqa: PLC0415

        try:
            valor = str(data.get("novo_bay", "")).strip().upper()
            if valor != "SIM":
                data["novo_bay"] = "NÃO"
                return data

            pi = str(data.get("projeto_investimento", "")).strip().upper()
            pi_base = get_pi_base(pi, prompt_user=False).strip().upper()
            if pi != "DISTRIBUIÇÃO" and pi_base != "DISTRIBUIÇÃO":
                data["novo_bay"] = "NÃO"
                return data

            ano = str(data.get("ano_", "")).strip()
            alimentador = str(data.get("alimentador_principal", "")).strip()
            nome_proj = str(data.get("nome_projeto", "")).strip()
            if not (ano and alimentador and nome_proj):
                data["novo_bay"] = "NÃO"
                return data

            alimentador = self._sanitize_alimentador(alimentador)

            sql = (
                "SELECT 1 FROM obras "
                "WHERE ano_=? AND alimentador_principal=? AND nome_projeto=? "
                "AND UPPER(novo_bay)=?"
            )
            params = [ano, alimentador, nome_proj, "SIM"]
            if exclude_cod is not None:
                sql += " AND cod <> ?"
                params.append(exclude_cod)

            cursor = self._get_cursor()
            if cursor:
                cursor.execute(sql, params)
                if cursor.fetchone():
                    data["novo_bay"] = "NÃO"
        except Exception:
            pass

        return data

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Normalização de dados")
    @retry_on_busy()
    def normalize_decimal_in_db(self):
        """Atualiza registros existentes substituindo ponto por vírgula."""
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return
            all_updates = []
            cols = [c for c in self.get_column_names() if c != "cod"]
            for col in cols:
                col_sql = '"' + str(col).replace('"', '""') + '"'
                cursor.execute(f"SELECT cod, {col_sql} FROM obras")
                for cod, val in cursor.fetchall():
                    new_val = self._normalize_decimal(val)
                    if new_val != val:
                        all_updates.append(
                            (f"UPDATE obras SET {col_sql} = ? WHERE cod = ?", (new_val, cod))
                        )
            if all_updates:
                with self.write_transaction():
                    for sql, params in all_updates:
                        cursor.execute(sql, params)

    def _has_numeric_decimal_dot_in_db(self) -> bool:
        candidate_tokens = [
            "tensao", "carreg", "perda", "ganho", "valor", "quant",
            "chi", "ci", "kva", "kw", "mva", "mv", "cliente", "conta",
        ]
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return False
            cols = [c for c in self.get_column_names() if c != "cod"]
            if not cols:
                return False
            candidate_cols = [
                col
                for col in cols
                if any(token in str(col).lower() for token in candidate_tokens)
            ]
            if not candidate_cols:
                candidate_cols = cols
            for col in candidate_cols:
                col_sql = '"' + str(col).replace('"', '""') + '"'
                cursor.execute(
                    "SELECT 1 FROM obras "
                    f"WHERE {col_sql} IS NOT NULL "
                    f"AND TRIM({col_sql}) <> '' "
                    f"AND {col_sql} NOT LIKE '%,%' "
                    f"AND {col_sql} GLOB '*[0-9].[0-9]*' "
                    "LIMIT 1"
                )
                if cursor.fetchone():
                    return True
        return False

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Atualização de índice")
    @retry_on_busy()
    def _create_unique_index(self):
        """Cria índice único para (nome_projeto, codigo_item) quando ambos são preenchidos."""
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return
            try:
                with self.write_transaction():
                    cursor.execute(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_nome_codigo ON obras (nome_projeto, codigo_item) "
                        "WHERE nome_projeto <> '' AND codigo_item <> ''"
                    )
            except Exception:
                pass

    def exists_codigo_item(self, nome_projeto, codigo_item, exclude_cod=None):
        """Verifica se já existe obra com mesmo nome_projeto e codigo_item."""
        if not nome_projeto or not codigo_item:
            return False
        self._ensure_cache_loaded()
        if not self.data_access_layer:
            return False
        rows = self.data_access_layer.get_rows_by_project(nome_projeto)
        idx_item = self.columns.index("codigo_item") if "codigo_item" in self.columns else -1
        idx_cod = self.columns.index("cod") if "cod" in self.columns else -1
        if idx_item < 0:
            return False
        for row in rows:
            if str(row[idx_item]).strip() != str(codigo_item).strip():
                continue
            if exclude_cod is not None and idx_cod >= 0 and str(row[idx_cod]) == str(exclude_cod):
                continue
            return True
        return False

    def fetch_all(self, pacotes=None):
        """Retorna todas as obras, opcionalmente filtrando por pacotes."""
        if pacotes is None:
            pacotes = self.allowed_pacotes
        self._ensure_cache_loaded()
        if not self.data_access_layer:
            return []
        return self.data_access_layer.get_all(pacotes)

    def fetch_by_cod(self, cod):
        self._ensure_cache_loaded()
        if not self.data_access_layer:
            return None
        row = self.data_access_layer.get_by_cod(cod)
        if row and self.allowed_pacotes and row[self.columns.index("tipo_pacote")] not in self.allowed_pacotes:
            return None
        return row if row else None

    def fetch_by_cods(self, cods: list[str], pacotes=None) -> list[list[Any]]:
        if pacotes is None:
            pacotes = self.allowed_pacotes
        self._ensure_cache_loaded()
        if not self.data_access_layer:
            return []
        return self.data_access_layer.get_rows_by_cods(cods, pacotes)

    def _resolve_obra_id_column(self) -> str | None:
        cols = list(self.get_column_names() or [])
        for expected in ("cod", "id"):
            expected_norm = normalize_key(expected)
            for col in cols:
                if normalize_key(col) == expected_norm:
                    return col
        return None

    def _resolve_pacote_column(self) -> str | None:
        cols = list(self.get_column_names() or [])
        for expected in ("tipo_pacote", "pacote"):
            expected_norm = normalize_key(expected)
            for col in cols:
                if normalize_key(col) == expected_norm:
                    return col
        return None

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Geração de COD_PEP")
    @retry_on_busy()
    def gerar_cod_pep_para_cods(
        self,
        cods: list[str],
        empresa_sigla: str,
        somente_vazios: bool = True,
        scope_years: list[str] | None = None,
        reiniciar_numeracao: bool = False,
        progress_callback: Callable[[int, int, str], None] | None = None,
        cancel_callback: Callable[[], bool] | None = None,
    ) -> tuple[int, int, list[str]]:
        cods_norm: list[str] = []
        seen: set[str] = set()
        for raw_cod in cods or []:
            cod_txt = str(raw_cod or "").strip()
            if cod_txt and cod_txt not in seen:
                seen.add(cod_txt)
                cods_norm.append(cod_txt)
        if not cods_norm:
            return 0, 0, []

        empresa_norm = normalize_text(empresa_sigla)
        if empresa_norm not in EMPRESA_SIGLAS_VALIDAS:
            return 0, 0, [f"Sigla de empresa inválida: '{empresa_sigla}'."]

        atualizados = 0
        ignorados = 0
        erros: list[str] = []
        total_cods = len(cods_norm)
        cancelado = False

        def _emit_progress(processados: int, texto: str) -> None:
            if not progress_callback:
                return
            try:
                progress_callback(processados, total_cods, texto)
            except Exception:
                LOGGER.debug("Falha ao emitir progresso de COD_PEP.", exc_info=True)

        _emit_progress(0, f"Gerando COD_PEP... (0/{total_cods})")

        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return 0, 0, ["Cursor do banco indisponível."]

            self.add_column_if_missing("empresa")
            self.add_column_if_missing("cod_pep")
            self.update_columns()

            cols = list(self.get_column_names())
            id_col = self._resolve_obra_id_column()
            if not id_col:
                return 0, 0, ["Coluna de identificação (cod/id) não encontrada em obras."]

            id_col_sql = self._escape_identifier(id_col)
            cols_sql = ", ".join(self._escape_identifier(col) for col in cols)
            pacote_col = self._resolve_pacote_column()
            allowed_norm: list[str] = []
            if self.allowed_pacotes and pacote_col:
                allowed_norm = [
                    str(p).strip()
                    for p in self.allowed_pacotes
                    if str(p).strip()
                ]
            _ = scope_years

            row_map: dict[str, dict[str, Any]] = {}
            chunk_size = 900
            for start in range(0, len(cods_norm), chunk_size):
                chunk = cods_norm[start : start + chunk_size]
                placeholders = ",".join(["?"] * len(chunk))
                sql = f"SELECT {cols_sql} FROM obras WHERE {id_col_sql} IN ({placeholders})"
                params: list[Any] = list(chunk)
                if allowed_norm and pacote_col:
                    pacote_sql = self._escape_identifier(pacote_col)
                    pac_placeholders = ",".join(["?"] * len(allowed_norm))
                    sql += f" AND {pacote_sql} IN ({pac_placeholders})"
                    params.extend(allowed_norm)
                cursor.execute(sql, params)
                for fetched in cursor.fetchall():
                    row_dict = {
                        col: fetched[idx] if idx < len(fetched) else ""
                        for idx, col in enumerate(cols)
                    }
                    row_id = str(row_dict.get(id_col) or "").strip()
                    if row_id:
                        row_map[row_id] = row_dict

            cod_pep_sql = self._escape_identifier("cod_pep")
            empresa_sql = self._escape_identifier("empresa")
            if reiniciar_numeracao and cods_norm:
                LOGGER.info(
                    "COD_PEP: reiniciando numeração no escopo atual (obras=%s).",
                    len(cods_norm),
                )
                chunk_size_reset = 900
                for start in range(0, len(cods_norm), chunk_size_reset):
                    chunk = cods_norm[start : start + chunk_size_reset]
                    placeholders = ",".join(["?"] * len(chunk))
                    with self.write_transaction():
                        cursor.execute(
                            f"UPDATE obras SET {cod_pep_sql}='' "
                            f"WHERE {id_col_sql} IN ({placeholders})",
                            chunk,
                        )
                for row_dict in row_map.values():
                    row_dict["cod_pep"] = ""

            def _pep_order_key(cod_id: str) -> tuple[Any, Any, Any, str]:
                row_dict = row_map.get(cod_id) or {}
                ano_txt = str(row_dict.get("ano_") or "").strip()
                try:
                    ano_key: tuple[int, Any] = (0, int(ano_txt))
                except Exception:
                    ano_key = (1, ano_txt.upper())

                projeto_key = str(row_dict.get("nome_projeto") or "").strip().upper()
                codigo_item_txt = str(row_dict.get("codigo_item") or "").strip()
                codigo_item_digits = re.sub(r"\D", "", codigo_item_txt)
                if codigo_item_digits:
                    item_key: tuple[int, Any, str] = (
                        0,
                        int(codigo_item_digits),
                        codigo_item_txt.upper(),
                    )
                else:
                    item_key = (1, codigo_item_txt.upper(), "")

                return ano_key, projeto_key, item_key, cod_id

            cods_ordenados = sorted(cods_norm, key=_pep_order_key)

            for idx, cod_id in enumerate(cods_ordenados, start=1):
                if cancel_callback:
                    try:
                        if cancel_callback():
                            cancelado = True
                            break
                    except Exception:
                        pass
                row_dict = row_map.get(cod_id)
                if not row_dict:
                    erros.append(
                        f"Obra {cod_id}: não encontrada ou fora dos pacotes permitidos."
                    )
                    _emit_progress(idx, f"Gerando COD_PEP... ({idx}/{total_cods})")
                    continue

                cod_existente = str(row_dict.get("cod_pep") or "").strip()
                if somente_vazios and cod_existente:
                    ignorados += 1
                    _emit_progress(idx, f"Gerando COD_PEP... ({idx}/{total_cods})")
                    continue

                try:
                    novo_cod = str(
                        cod_pep(self, row_dict, empresa_norm) or ""
                    ).strip()
                except Exception as exc:
                    erros.append(f"Obra {cod_id}: {exc}")
                    _emit_progress(idx, f"Gerando COD_PEP... ({idx}/{total_cods})")
                    continue

                if not novo_cod:
                    erros.append(f"Obra {cod_id}: COD_PEP vazio após cálculo.")
                    _emit_progress(idx, f"Gerando COD_PEP... ({idx}/{total_cods})")
                    continue

                try:
                    with self.write_transaction():
                        cursor.execute(
                            f"UPDATE obras SET {cod_pep_sql}=?, {empresa_sql}=? WHERE {id_col_sql}=?",
                            (novo_cod, empresa_norm, cod_id),
                        )
                except DatabaseBusyError:
                    raise
                except Exception as exc:
                    erros.append(f"Obra {cod_id}: falha ao atualizar ({exc}).")
                    _emit_progress(idx, f"Gerando COD_PEP... ({idx}/{total_cods})")
                    continue

                if cursor.rowcount and cursor.rowcount > 0:
                    atualizados += 1
                else:
                    erros.append(f"Obra {cod_id}: não foi atualizada.")
                _emit_progress(idx, f"Gerando COD_PEP... ({idx}/{total_cods})")

        self._refresh_cache()
        if cancelado:
            LOGGER.info("Geração de COD_PEP interrompida por cancelamento do usuário.")
        return atualizados, ignorados, erros

    def fetch_by_project(
        self,
        nome_projeto: str,
        ano: str | None = None,
        pacote: str | None = None,
        *,
        order_by_codigo_item: bool = False,
    ) -> list[list[Any]]:
        self._ensure_cache_loaded()
        if not self.data_access_layer:
            return []
        rows = self.data_access_layer.get_rows_by_project(nome_projeto, ano=ano, pacote=pacote)
        if self.allowed_pacotes:
            idx_pacote = self.columns.index("tipo_pacote") if "tipo_pacote" in self.columns else -1
            if idx_pacote >= 0:
                rows = [row for row in rows if row[idx_pacote] in self.allowed_pacotes]
        if order_by_codigo_item and "codigo_item" in self.columns:
            idx_codigo = self.columns.index("codigo_item")
            try:
                rows.sort(key=lambda x: int(re.sub(r"\D", "", str(x[idx_codigo])) or 0))
            except Exception:
                pass
        return rows

    def get_next_codigo_item(self, nome_projeto: str) -> int:
        rows = self.fetch_by_project(nome_projeto)
        if not rows or "codigo_item" not in self.columns:
            return 1
        idx_codigo = self.columns.index("codigo_item")
        max_val = 0
        for row in rows:
            try:
                valor = int(re.sub(r"\D", "", str(row[idx_codigo])) or 0)
            except Exception:
                valor = 0
            max_val = max(max_val, valor)
        return max_val + 1

    def _prepare_empresa_cod_pep(
        self,
        data: dict[str, Any],
        existing_map: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cols = self.get_column_names()
        has_empresa = "empresa" in cols
        has_cod_pep = "cod_pep" in cols
        if not has_empresa and not has_cod_pep:
            return data

        existing_map = existing_map or {}
        if has_empresa and self._is_missing(data.get("empresa")) and not self._is_missing(existing_map.get("empresa")):
            data["empresa"] = existing_map.get("empresa")
        if has_cod_pep and self._is_missing(data.get("cod_pep")) and not self._is_missing(existing_map.get("cod_pep")):
            data["cod_pep"] = existing_map.get("cod_pep")
        merged = dict(existing_map)
        merged.update(data)

        empresa_raw = merged.get("empresa", "")
        empresa_sigla = normalize_text(empresa_raw)
        if empresa_sigla:
            if empresa_sigla not in EMPRESA_SIGLAS_VALIDAS:
                raise ValueError(
                    f"Sigla de empresa inválida: '{empresa_raw}'. "
                    f"Permitidas: {', '.join(sorted(EMPRESA_SIGLAS_VALIDAS))}."
                )
        else:
            empresa_sigla = get_empresa_sigla_from_config()

        if has_empresa:
            data["empresa"] = empresa_sigla
            merged["empresa"] = empresa_sigla

        if has_cod_pep:
            cod_existente = str(existing_map.get("cod_pep", "") or "").strip()
            cod_informado = str(data.get("cod_pep", "") or "").strip()
            if not cod_existente and not cod_informado:
                gerado = cod_pep(self, merged, empresa_sigla)
                if gerado:
                    data["cod_pep"] = gerado
            elif cod_informado and has_empresa and "empresa" not in data:
                parsed = parse_cod_pep(cod_informado)
                if parsed and parsed.get("empresa") in EMPRESA_SIGLAS_VALIDAS:
                    data["empresa"] = parsed["empresa"]
        return data

    @backup_on_error
    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Salvando obra")
    @retry_on_busy()
    def insert_obra(self, dados):
        """Insere uma obra usando mapeamento por nome das colunas."""
        # get_pi_base permanece em codigo5_coplan (Qt prompt + PI_BASE_MAP).
        from runtime.pi_base import get_pi_base  # noqa: PLC0415

        with self._with_connection():
            cols = self.get_column_names()
            if isinstance(dados, dict):
                data = dados.copy()
                if 'alimentador_principal' in data:
                    if '_' in str(data['alimentador_principal']):
                        raise ValueError("O campo 'alimentador_principal' não deve conter sublinhado (_).")
                    data['alimentador_principal'] = self._sanitize_alimentador(data['alimentador_principal'])
                if 'alimentadores_beneficiados' in data:
                    for item in re.split(r'[,;|\n]+', str(data['alimentadores_beneficiados'])):
                        if '_' in item:
                            raise ValueError("O campo 'alimentadores_beneficiados' não deve conter sublinhado (_).")
                if 'projeto_investimento' in data:
                    base = get_pi_base(str(data['projeto_investimento']), prompt_user=False)
                    data.setdefault('pi_base', base)
                agora = datetime.datetime.now().strftime('%d/%m/%y %H:%M')
                usuario = getpass.getuser()
                if 'data_criacao' in cols:
                    data.setdefault('data_criacao', agora)
                if 'data_modificacao' in cols:
                    data.setdefault('data_modificacao', agora)
                if 'criado_por' in cols:
                    data.setdefault('criado_por', usuario)
                if 'modificado_por' in cols:
                    data.setdefault('modificado_por', usuario)
                if 'pi_base' in cols and 'pi_base' not in data and 'projeto_investimento' in data:
                    data['pi_base'] = get_pi_base(data['projeto_investimento'], prompt_user=False)
                if 'obra_aprovada' in cols:
                    data.setdefault('obra_aprovada', 'NÃO')
                if 'tecnico_dirty' in cols:
                    data.setdefault('tecnico_dirty', 'NÃO')
                data = self._apply_novo_bay_rules(data)
                data = self._prepare_empresa_cod_pep(data)
                if self.allowed_pacotes and data.get("tipo_pacote") not in self.allowed_pacotes:
                    raise PermissionError("Pacote não permitido")
                values = [self._normalize_decimal(data.get(col, "")) for col in cols]
            else:
                values = [self._normalize_decimal(v) for v in list(dados or [])]
                if len(values) < len(cols):
                    values.extend([""] * (len(cols) - len(values)))
                else:
                    values = values[:len(cols)]
                agora = datetime.datetime.now().strftime('%d/%m/%y %H:%M')
                usuario = getpass.getuser()
                for field, val in [('data_criacao', agora), ('data_modificacao', agora), ('criado_por', usuario), ('modificado_por', usuario)]:
                    if field in cols:
                        idx = cols.index(field)
                        if idx < len(values):
                            values[idx] = val
                if 'pi_base' in cols and 'projeto_investimento' in cols:
                    idx_pi = cols.index('pi_base')
                    idx_proj = cols.index('projeto_investimento')
                    if idx_pi < len(values) and idx_proj < len(values):
                        values[idx_pi] = get_pi_base(values[idx_proj], prompt_user=False)
                if 'alimentador_principal' in cols:
                    idx = cols.index('alimentador_principal')
                    if idx < len(values):
                        if '_' in str(values[idx]):
                            raise ValueError("O campo 'alimentador_principal' não deve conter sublinhado (_).")
                        values[idx] = self._sanitize_alimentador(values[idx])
                if 'alimentadores_beneficiados' in cols:
                    idx = cols.index('alimentadores_beneficiados')
                    if idx < len(values):
                        for item in re.split(r'[,;|\n]+', str(values[idx])):
                            if '_' in item:
                                raise ValueError("O campo 'alimentadores_beneficiados' não deve conter sublinhado (_).")
                if 'obra_aprovada' in cols:
                    idx = cols.index('obra_aprovada')
                    if idx < len(values):
                        if not values[idx]:
                            values[idx] = 'NÃO'
                    else:
                        values.extend([''] * (idx - len(values) + 1))
                        values[idx] = 'NÃO'
                if "tecnico_dirty" in cols:
                    idx = cols.index("tecnico_dirty")
                    if idx < len(values):
                        if not values[idx]:
                            values[idx] = "NÃO"
                    else:
                        values.extend([""] * (idx - len(values) + 1))
                        values[idx] = "NÃO"
                data_check = {col: values[i] if i < len(values) else '' for i, col in enumerate(cols)}
                data_check = self._apply_novo_bay_rules(data_check)
                data_check = self._prepare_empresa_cod_pep(data_check)
                values = [self._normalize_decimal(data_check.get(col, "")) for col in cols]
            if self.allowed_pacotes and 'tipo_pacote' in cols:
                idx = cols.index('tipo_pacote')
                pac = values[idx] if idx < len(values) else ''
                if pac not in self.allowed_pacotes:
                    raise PermissionError("Pacote não permitido")
            from core.repositories.obra_sql_helpers import build_insert_sql
            sql = build_insert_sql("obras", cols)
            cursor = self._get_cursor()
            if not cursor:
                return
            try:
                with self.write_transaction():
                    cursor.execute(sql, values)
            except sqlite3.IntegrityError as e:
                raise ValueError(
                    "Já existe uma obra com este código de item para o projeto informado."
                ) from e
        self._refresh_cache()

    def _is_zero_or_blank(self, value):
        """Retorna ``True`` se ``value`` estiver vazio ou representar zero."""
        if value is None:
            return True
        s = str(value).strip()
        if s == "":
            return True
        try:
            return float(s.replace(",", ".")) == 0.0
        except ValueError:
            return False

    def _is_missing(self, value) -> bool:
        """Retorna True apenas quando o valor NÃO foi encontrado.
        Zero é considerado valor válido.
        """
        if value is None:
            return True
        try:
            if isinstance(value, float) and value != value:  # NaN
                return True
        except Exception:
            pass
        return str(value).strip() == ""

    def _normalize_numeric_value(self, value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return None
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return None

    def build_merge_updates(self, existing: dict, incoming: dict) -> dict:
        """Constroi dict de updates para merge na importacao Excel.

        Regra (apos correcao 2026-05-13): para CADA coluna do incoming
        com valor nao-vazio, sobrescreve o valor existente se for
        diferente. Antes, colunas ja preenchidas eram preservadas
        (so blanks eram completados). O usuario relatou que isto
        impedia atualizar planilhas com correcoes em colunas ja
        populadas -- agora merge atualiza tambem campos preenchidos.

        Campos especiais mantem regras proprias:
        - cod, data_criacao, criado_por: nunca atualiza.
        - descricao_obra: se diferente, anexa em observacoes_gerais
          como "Descricao adicional: ..." (logica abaixo).
        - empresa, cod_pep: normaliza antes de comparar.
        - GANHOS_NUMERIC_FIELDS: compara como numero.
        """
        cols = self.get_column_names()
        updates: dict[str, Any] = {}
        for col in cols:
            if col in {"cod", "data_criacao", "criado_por"}:
                continue
            if col == "descricao_obra":
                continue
            if col not in incoming:
                continue
            new_val = incoming.get(col)
            if self._is_missing(new_val):
                continue

            if col in {"empresa", "cod_pep"}:
                if col == "empresa":
                    empresa_nova = normalize_text(new_val)
                    empresa_atual = normalize_text(existing.get(col))
                    if empresa_nova and empresa_atual != empresa_nova:
                        updates[col] = empresa_nova
                else:
                    cod_pep_novo = str(new_val or "").strip()
                    cod_pep_atual = str(existing.get(col) or "").strip()
                    if cod_pep_novo and cod_pep_atual != cod_pep_novo:
                        updates[col] = cod_pep_novo
                continue

            if col in GANHOS_NUMERIC_FIELDS:
                new_num = self._normalize_numeric_value(new_val)
                if new_num is None:
                    continue
                existing_num = self._normalize_numeric_value(existing.get(col))
                if existing_num != new_num:
                    updates[col] = self._normalize_decimal(new_val)
                continue

            # Caso generico: atualiza se o novo valor difere do existente
            # (case-sensitive, sem normalizar). Antes, so atualizava
            # colunas vazias -- regra invertida para permitir corrigir
            # dados via re-importacao do Excel.
            new_normalized = self._normalize_decimal(new_val)
            existing_val = existing.get(col)
            if self._is_missing(existing_val):
                updates[col] = new_normalized
            else:
                existing_normalized = self._normalize_decimal(existing_val)
                if str(existing_normalized) != str(new_normalized):
                    updates[col] = new_normalized

        desc_new = str(incoming.get("descricao_obra") or "").strip()
        desc_existing = str(existing.get("descricao_obra") or "").strip()
        if desc_new:
            if not desc_existing:
                updates["descricao_obra"] = desc_new
            elif desc_new != desc_existing:
                obs_col = "observacoes_gerais" if "observacoes_gerais" in cols else None
                if obs_col:
                    existing_obs = str(existing.get(obs_col) or "").strip()
                    entry = f"Descrição adicional: {desc_new}"
                    if entry not in existing_obs:
                        updates[obs_col] = (
                            f"{existing_obs}\n{entry}".strip()
                            if existing_obs
                            else entry
                        )

        return updates

    @backup_on_error
    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Atualizando obra")
    @retry_on_busy()
    def update_obra(self, dados, cod, skip_blank=False):
        """Atualiza uma obra usando mapeamento por nome das colunas."""
        # get_pi_base permanece em codigo5_coplan.
        from runtime.pi_base import get_pi_base  # noqa: PLC0415

        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return
            cols = self.get_column_names()
            existing = self.fetch_by_cod(cod)
            existing_map = dict(zip(cols, existing)) if existing else {}

            if isinstance(dados, dict):
                data = dados.copy()
                if "alimentador_principal" in data:
                    if '_' in str(data['alimentador_principal']):
                        raise ValueError("O campo 'alimentador_principal' não deve conter sublinhado (_).")
                    data["alimentador_principal"] = self._sanitize_alimentador(data["alimentador_principal"])
                if 'alimentadores_beneficiados' in data:
                    for item in re.split(r'[,;|\n]+', str(data['alimentadores_beneficiados'])):
                        if '_' in item:
                            raise ValueError("O campo 'alimentadores_beneficiados' não deve conter sublinhado (_).")
                if "pi_base" in cols and "pi_base" not in data and "projeto_investimento" in data:
                    data["pi_base"] = get_pi_base(data["projeto_investimento"], prompt_user=False)

                if "novo_bay" in data:
                    merged = existing_map.copy()
                    merged.update(data)
                    merged = self._apply_novo_bay_rules(merged, exclude_cod=cod)
                    data["novo_bay"] = merged.get("novo_bay")

                agora = datetime.datetime.now().strftime("%d/%m/%y %H:%M")
                usuario = getpass.getuser()
                if "data_modificacao" in cols:
                    data["data_modificacao"] = agora
                if "modificado_por" in cols:
                    data["modificado_por"] = usuario

                if skip_blank:
                    for col, val in list(data.items()):
                        if (
                            self._is_missing(val)
                            and col != "nome_projeto"
                            and not self._is_missing(existing_map.get(col, ""))
                        ):
                            data[col] = existing_map.get(col, "")

                data = self._prepare_empresa_cod_pep(data, existing_map=existing_map)

                for col in list(data.keys()):
                    data[col] = self._normalize_decimal(data[col])

                pac = data.get("tipo_pacote", existing_map.get("tipo_pacote"))
                if self.allowed_pacotes and pac not in self.allowed_pacotes:
                    raise PermissionError("Pacote não permitido")

                cols = list(data.keys())
                from core.repositories.obra_sql_helpers import build_update_sql
                sql = build_update_sql("obras", cols, ["cod"])
                try:
                    with self.write_transaction():
                        cursor.execute(sql, [data[col] for col in cols] + [cod])
                except sqlite3.IntegrityError as e:
                    raise ValueError(
                        "Já existe uma obra com este código de item para o projeto informado."
                    ) from e
            else:
                cols = [c for c in cols if c != "cod"]
                values = [self._normalize_decimal(v) for v in list(dados or [])]
                if len(values) < len(cols):
                    values.extend([""] * (len(cols) - len(values)))
                else:
                    values = values[:len(cols)]
                agora = datetime.datetime.now().strftime("%d/%m/%y %H:%M")
                usuario = getpass.getuser()
                if "data_modificacao" in cols:
                    idx = cols.index("data_modificacao")
                    if idx < len(values):
                        values[idx] = agora
                if "modificado_por" in cols:
                    idx = cols.index("modificado_por")
                    if idx < len(values):
                        values[idx] = usuario
                for field, default in [("data_criacao", agora), ("criado_por", usuario)]:
                    if field in cols:
                        idx = cols.index(field)
                        if idx < len(values):
                            if existing_map.get(field):
                                values[idx] = existing_map[field]
                            elif not values[idx]:
                                values[idx] = default
                if "pi_base" in cols and "projeto_investimento" in cols:
                    idx_pi = cols.index("pi_base")
                    idx_proj = cols.index("projeto_investimento")
                    if idx_pi < len(values) and idx_proj < len(values):
                        values[idx_pi] = get_pi_base(values[idx_proj], prompt_user=False)
                if "alimentador_principal" in cols:
                    idx = cols.index("alimentador_principal")
                    if idx < len(values):
                        if '_' in str(values[idx]):
                            raise ValueError("O campo 'alimentador_principal' não deve conter sublinhado (_).")
                        values[idx] = self._sanitize_alimentador(values[idx])
                if 'alimentadores_beneficiados' in cols:
                    idx = cols.index('alimentadores_beneficiados')
                    if idx < len(values):
                        for item in re.split(r'[,;|\n]+', str(values[idx])):
                            if '_' in item:
                                raise ValueError("O campo 'alimentadores_beneficiados' não deve conter sublinhado (_).")
                if "obra_aprovada" in cols:
                    idx = cols.index("obra_aprovada")
                    if idx < len(values):
                        if not values[idx]:
                            values[idx] = "NÃO"
                    else:
                        values.extend([""] * (idx - len(values) + 1))
                        values[idx] = "NÃO"
                data_check = {col: values[i] if i < len(values) else "" for i, col in enumerate(cols)}
                data_check = self._apply_novo_bay_rules(data_check, exclude_cod=cod)
                data_check = self._prepare_empresa_cod_pep(data_check, existing_map=existing_map)
                values = [self._normalize_decimal(data_check.get(col, "")) for col in cols]
                pac = None
                if "tipo_pacote" in cols:
                    idx = cols.index("tipo_pacote")
                    if pac is None and idx < len(values):
                        pac = values[idx]
                if self.allowed_pacotes and pac not in self.allowed_pacotes:
                    raise PermissionError("Pacote não permitido")
                from core.repositories.obra_sql_helpers import build_update_sql
                sql = build_update_sql("obras", cols, ["cod"])
                try:
                    with self.write_transaction():
                        cursor.execute(sql, values + [cod])
                except sqlite3.IntegrityError as e:
                    raise ValueError(
                        "Já existe uma obra com este código de item para o projeto informado."
                    ) from e
        self._refresh_cache()

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Preenchimento de COD_PEP pendente")
    @retry_on_busy()
    def preencher_cod_pep_pendentes(self) -> int:
        preenchidos = 0
        empresa_ajustada = 0
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return 0
            cols = self.get_column_names()
            if "empresa" not in cols or "cod_pep" not in cols:
                return 0

            empresa_default = ""
            try:
                empresa_default = get_empresa_sigla_from_config()
            except Exception as exc:
                LOGGER.warning("Sigla de empresa indisponível para preencher COD_PEP: %s", exc)

            cursor.execute(
                "SELECT cod, ano_, nome_projeto, codigo_item, nome_regional, novo_bay, tipo_pacote, empresa, cod_pep FROM obras"
            )
            rows = cursor.fetchall()
            if not rows:
                return 0

            def _codigo_item_num(v):
                s = str(v or "").strip()
                if not s:
                    return 10**9
                try:
                    return int(float(s.replace(",", ".").strip()))
                except Exception:
                    digits = "".join(ch for ch in s if ch.isdigit())
                    return int(digits) if digits else 10**9

            rows = sorted(
                rows,
                key=lambda r: (
                    str(r[1] or "").strip(),
                    str(r[2] or "").strip().upper(),
                    _codigo_item_num(r[3]),
                    str(r[0] or "").strip(),
                ),
            )

            for cod, ano_, nome_projeto, codigo_item, nome_regional, novo_bay, tipo_pacote, empresa, cod_atual in rows:
                cod_id = str(cod or "").strip() or "<sem-cod>"
                empresa_norm = normalize_text(empresa)
                cod_pep_atual = str(cod_atual or "").strip()

                if empresa_norm and empresa_norm not in EMPRESA_SIGLAS_VALIDAS:
                    LOGGER.warning(
                        "Empresa inválida '%s' na obra %s. Usando configuração atual.",
                        empresa,
                        cod_id,
                    )
                    empresa_norm = ""

                if not empresa_norm:
                    if not empresa_default:
                        LOGGER.warning(
                            "COD_PEP pendente sem empresa para obra %s e sem empresa padrão configurada.",
                            cod_id,
                        )
                        continue
                    empresa_norm = empresa_default
                    with self.write_transaction():
                        cursor.execute(
                            "UPDATE obras SET empresa=? WHERE cod=?",
                            (empresa_norm, cod),
                        )
                    empresa_ajustada += 1

                if cod_pep_atual:
                    continue

                obra = {
                    "cod": cod,
                    "ano_": ano_,
                    "nome_projeto": nome_projeto,
                    "codigo_item": codigo_item,
                    "nome_regional": nome_regional,
                    "novo_bay": novo_bay,
                    "tipo_pacote": tipo_pacote,
                    "empresa": empresa_norm,
                }
                try:
                    novo_cod = cod_pep(self, obra, empresa_norm)
                except Exception as exc:
                    LOGGER.warning(
                        "Falha ao gerar COD_PEP para obra %s: %s",
                        cod_id,
                        exc,
                    )
                    continue
                if not novo_cod:
                    continue
                with self.write_transaction():
                    cursor.execute(
                        "UPDATE obras SET empresa=?, cod_pep=? WHERE cod=?",
                        (empresa_norm, novo_cod, cod),
                    )
                preenchidos += 1

        if preenchidos or empresa_ajustada:
            self._refresh_cache()
        if preenchidos:
            print(f"COD_PEP BATCH: preenchidos={preenchidos}")
        LOGGER.info(
            "preencher_cod_pep_pendentes: cod_pep_preenchido=%s empresa_ajustada=%s",
            preenchidos,
            empresa_ajustada,
        )
        return preenchidos

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Zerar COD_PEP da base")
    @retry_on_busy()
    def zerar_cod_pep(self) -> int:
        """Esvazia o COD_PEP de TODAS as obras (acao destrutiva de admin)
        e LIMPA o registro de PEPs emitidos (cod_pep_emitidos). Retorna a
        contagem de obras afetadas. Apos zerar, a numeracao recomeca de
        fato do menor SSSS (0000) -- reset completo."""
        afetadas = 0
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return 0
            cols = self.get_column_names()
            if "cod_pep" not in cols:
                return 0
            cod_pep_sql = self._escape_identifier("cod_pep")
            with self.write_transaction():
                cursor.execute(
                    f"UPDATE obras SET {cod_pep_sql}='' "
                    f"WHERE {cod_pep_sql} IS NOT NULL "
                    f"AND TRIM({cod_pep_sql})<>''"
                )
                afetadas = int(cursor.rowcount or 0)
                # Reset real: limpa tambem o registro de emitidos, senao a
                # numeracao nao recomecaria do 0000 (os antigos seguiriam
                # reservados).
                try:
                    cursor.execute("DELETE FROM cod_pep_emitidos")
                except Exception:  # noqa: BLE001
                    pass  # tabela pode ainda nao existir
        self._refresh_cache()
        LOGGER.info("zerar_cod_pep: obras afetadas=%s", afetadas)
        print(f"COD_PEP ZERAR: afetadas={afetadas}")
        return afetadas

    def _ensure_cod_pep_ledger(self) -> None:
        """Cria a tabela ``cod_pep_emitidos`` (registro PERMANENTE de cada
        SSSS ja emitido por empresa+ano) e a semeia com os cod_pep atuais
        das obras. Um SSSS, uma vez emitido naquele ano (YY), fica reservado
        -- mesmo que a obra seja excluida -- evitando que um cod_pep liberado
        por exclusao seja reaproveitado. A numeracao reinicia a cada ano
        (escopo empresa+yy)."""
        if not self.conn:
            with self._with_connection():
                return self._ensure_cod_pep_ledger()
        cursor = self._get_cursor()
        if not cursor:
            return
        try:
            with self.write_transaction():
                # Migracao: schema antigo (sem coluna yy) e' recriado. A
                # tabela e' recurso novo (nao publicado), entao DROP e' seguro
                # -- o backfill repovoa a partir das obras.
                cursor.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='cod_pep_emitidos'"
                )
                if cursor.fetchone():
                    cursor.execute("PRAGMA table_info(cod_pep_emitidos)")
                    cols_tab = [c[1] for c in cursor.fetchall()]
                    if "yy" not in cols_tab:
                        cursor.execute("DROP TABLE cod_pep_emitidos")
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS cod_pep_emitidos ("
                    " empresa TEXT NOT NULL,"
                    " yy TEXT NOT NULL,"
                    " seq INTEGER NOT NULL,"
                    " cod_pep TEXT,"
                    " obra_cod TEXT,"
                    " emitido_em TEXT,"
                    " PRIMARY KEY (empresa, yy, seq))"
                )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Falha ao criar cod_pep_emitidos: %s", exc)
            return
        # Backfill: registra os cod_pep ja existentes nas obras (idempotente).
        try:
            cursor.execute(
                "SELECT empresa, cod_pep, cod FROM obras "
                "WHERE cod_pep IS NOT NULL AND TRIM(cod_pep)<>''"
            )
            rows = cursor.fetchall()
        except Exception:  # noqa: BLE001
            return
        agora = datetime.datetime.now().strftime('%d/%m/%y %H:%M')
        to_insert = []
        for empresa_r, cod_pep_r, obra_cod in rows:
            parsed = parse_cod_pep(cod_pep_r)
            if not parsed:
                continue
            emp = normalize_text(empresa_r) or parsed.get("empresa") or ""
            if not emp:
                continue
            to_insert.append(
                (emp, str(parsed["yy"]), int(parsed["seq"]), str(cod_pep_r),
                 str(obra_cod or ""), agora))
        if to_insert:
            try:
                with self.write_transaction():
                    cursor.executemany(
                        "INSERT OR IGNORE INTO cod_pep_emitidos "
                        "(empresa, yy, seq, cod_pep, obra_cod, emitido_em) "
                        "VALUES (?,?,?,?,?,?)",
                        to_insert,
                    )
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Falha no backfill de cod_pep_emitidos: %s", exc)

    def cod_pep_ledger_list(
        self, termo: str = "", empresa: str = "", yy: str = "",
        limit: int = 1000, offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Lista o registro de PEPs emitidos com filtros opcionais
        (termo casa cod_pep/obra_cod; empresa e yy exatos). Retorna
        (linhas, total) -- total ignora limit/offset (para paginacao)."""
        self._ensure_cod_pep_ledger()
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return [], 0
            where: list[str] = []
            params: list[Any] = []
            emp = normalize_text(empresa)
            if emp:
                where.append("empresa=?")
                params.append(emp)
            yy_s = str(yy or "").strip()
            if yy_s:
                where.append("yy=?")
                params.append(yy_s)
            termo_s = str(termo or "").strip()
            if termo_s:
                where.append("(UPPER(cod_pep) LIKE ? OR UPPER(obra_cod) LIKE ?)")
                like = "%" + termo_s.upper() + "%"
                params.extend([like, like])
            wsql = (" WHERE " + " AND ".join(where)) if where else ""
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM cod_pep_emitidos" + wsql, params)
                total = int((cursor.fetchone() or [0])[0] or 0)
                cursor.execute(
                    "SELECT empresa, yy, seq, cod_pep, obra_cod, emitido_em "
                    "FROM cod_pep_emitidos" + wsql
                    + " ORDER BY empresa, yy, seq LIMIT ? OFFSET ?",
                    params + [int(limit), int(offset)],
                )
                rows = [
                    {"empresa": r[0], "yy": r[1], "seq": int(r[2] or 0),
                     "cod_pep": r[3] or "", "obra_cod": r[4] or "",
                     "emitido_em": r[5] or ""}
                    for r in cursor.fetchall()
                ]
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("cod_pep_ledger_list: %s", exc)
                return [], 0
        return rows, total

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Inserir COD_PEP no registro")
    @retry_on_busy()
    def cod_pep_ledger_add(self, cod_pep: str, obra_cod: str = "") -> int:
        """Reserva manualmente um COD_PEP no registro. Faz parse para
        extrair empresa/yy/seq. Retorna 1 se inseriu, 0 se ja existia."""
        parsed = parse_cod_pep(cod_pep)
        if not parsed:
            raise ValueError(f"COD_PEP invalido: '{cod_pep}'")
        self._ensure_cod_pep_ledger()
        inserido = 0
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return 0
            agora = datetime.datetime.now().strftime('%d/%m/%y %H:%M')
            with self.write_transaction():
                cursor.execute(
                    "INSERT OR IGNORE INTO cod_pep_emitidos "
                    "(empresa, yy, seq, cod_pep, obra_cod, emitido_em) "
                    "VALUES (?,?,?,?,?,?)",
                    (parsed["empresa"], parsed["yy"], int(parsed["seq"]),
                     str(cod_pep).strip().upper(), str(obra_cod or ""), agora),
                )
                inserido = int(cursor.rowcount or 0)
        return inserido

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Remover COD_PEP do registro")
    @retry_on_busy()
    def cod_pep_ledger_remove(
        self, empresa: str, yy: str, seq: int,
    ) -> int:
        """Remove uma reserva do registro (libera o SSSS daquele ano para
        ser reaproveitado). Retorna a contagem removida."""
        self._ensure_cod_pep_ledger()
        removido = 0
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return 0
            with self.write_transaction():
                cursor.execute(
                    "DELETE FROM cod_pep_emitidos "
                    "WHERE empresa=? AND yy=? AND seq=?",
                    (normalize_text(empresa), str(yy or "").strip(), int(seq)),
                )
                removido = int(cursor.rowcount or 0)
        return removido

    def count_tecnico_dirty(self, pacotes=None) -> int:
        """Conta obras com dados técnicos desatualizados."""
        if pacotes is None:
            pacotes = self.allowed_pacotes
        self._ensure_cache_loaded()
        if not self.data_access_layer or "tecnico_dirty" not in self.columns:
            return 0
        return self.data_access_layer.count_tecnico_dirty(pacotes)

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Marcação técnica em massa")
    @retry_on_busy()
    def mark_tecnico_dirty_all(self) -> None:
        """Marca todas as obras como desatualizadas tecnicamente."""
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor or "tecnico_dirty" not in self.columns:
                return
            with self.write_transaction():
                cursor.execute(
                    "UPDATE obras SET tecnico_dirty = 'SIM' "
                    "WHERE tecnico_dirty IS NULL OR tecnico_dirty <> 'SIM'"
                )
        self._refresh_cache()

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Atualização de critérios por código")
    @retry_on_busy()
    def update_criterios_por_cod(self, updates: list[tuple[str, str, str, str]]) -> None:
        """Persiste os critérios calculados por obra."""
        if not updates:
            return
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return
            cols = self.get_column_names()
            required = {
                "cod",
                "criterios_status",
                "criterios_motivos",
                "criterios_limite_carreg",
            }
            if not required.issubset(set(cols)):
                return
            chunk_size = 200
            for start in range(0, len(updates), chunk_size):
                chunk = updates[start : start + chunk_size]
                with self.write_transaction():
                    cursor.executemany(
                        "UPDATE obras "
                        "SET criterios_status = ?, criterios_motivos = ?, criterios_limite_carreg = ? "
                        "WHERE cod = ?",
                        chunk,
                    )
        self._refresh_cache()

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Atualização de snapshot técnico")
    @retry_on_busy()
    def update_tecnico_snapshot_for_cods(
        self, cods: list[str], token: str, snapshot_at: str, snapshot_src: str
    ) -> None:
        """Atualiza snapshot técnico para os códigos informados."""
        if not cods:
            return
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return
            cols = self.get_column_names()
            if "tecnico_snapshot_token" not in cols:
                return
            placeholders = ",".join(["?"] * len(cods))
            sql = (
                "UPDATE obras SET tecnico_snapshot_token = ?, tecnico_snapshot_at = ?, "
                "tecnico_snapshot_src = ?, tecnico_dirty = 'NÃO' "
                f"WHERE cod IN ({placeholders})"
            )
            with self.write_transaction():
                cursor.execute(sql, [token, snapshot_at, snapshot_src] + list(cods))
        self._refresh_cache()

    @backup_on_error
    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Exclusão de obra")
    @retry_on_busy()
    def delete_obra(self, cod):
        if self.allowed_pacotes:
            self._ensure_cache_loaded()
            row = (
                self.data_access_layer.get_by_cod(cod)
                if self.data_access_layer
                else None
            )
            if not row:
                return
            idx = (
                self.get_column_names().index("tipo_pacote")
                if "tipo_pacote" in self.get_column_names()
                else -1
            )
            pac = row[idx] if idx >= 0 else None
            if pac not in self.allowed_pacotes:
                raise PermissionError("Pacote não permitido")
        with self._with_connection():
            cursor = self._get_cursor()
            if not cursor:
                return
            with self.write_transaction():
                from core.repositories.obra_sql_helpers import build_delete_sql
                cursor.execute(build_delete_sql("obras", ["cod"]), (cod,))
        self._refresh_cache()

    # === SQLITE MULTIUSER BEGIN ===
    def _apply_sqlite_pragmas(self):
        if not self.conn:
            return
        try:
            self.conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
            logging.info("PRAGMA busy_timeout=%s aplicado.", SQLITE_BUSY_TIMEOUT_MS)
        except Exception as exc:
            logging.warning("Falha ao aplicar PRAGMA busy_timeout: %s", exc)

        try:
            result = self.conn.execute("PRAGMA journal_mode=WAL").fetchone()
            applied = result[0] if result else "unknown"
            logging.info("PRAGMA journal_mode=%s aplicado.", applied)
        except Exception as exc:
            logging.warning("Falha ao aplicar WAL: %s", exc)

        try:
            self.conn.execute("PRAGMA synchronous = NORMAL")
            logging.info("PRAGMA synchronous=NORMAL aplicado.")
        except Exception as exc:
            logging.warning("Falha ao aplicar PRAGMA synchronous: %s", exc)

        try:
            self.conn.execute("PRAGMA temp_store = MEMORY")
            logging.info("PRAGMA temp_store=MEMORY aplicado.")
        except Exception as exc:
            logging.warning("Falha ao aplicar PRAGMA temp_store: %s", exc)

        try:
            self.conn.execute("PRAGMA foreign_keys = ON")
            logging.info("PRAGMA foreign_keys=ON aplicado.")
        except Exception as exc:
            logging.warning("Falha ao aplicar PRAGMA foreign_keys: %s", exc)

    @contextmanager
    def write_transaction(self):
        with write_transaction_safe(self):
            yield

    @run_write_in_qthread_if_ui_thread
    @with_lock_action("Transação de escrita")
    def run_write_transaction(
        self,
        operation: Callable[[], Any],
        retries: int = 0,
        base_delay: float = 0.5,
    ):
        for attempt in range(retries + 1):
            try:
                return operation()
            except DatabaseBusyError:
                if attempt >= retries:
                    raise
                delay = max(base_delay, 0.0)
                logging.warning(
                    "Banco ocupado, tentando novamente em %.0fms (tentativa %s/%s).",
                    delay * 1000,
                    attempt + 1,
                    retries,
                )
                time.sleep(delay)
            except sqlite3.OperationalError as exc:
                if not is_sqlite_busy_error(exc):
                    raise
                if attempt >= retries:
                    raise DatabaseBusyError(
                        self.db_path,
                        details=str(exc),
                    ) from exc
                delay = max(base_delay, 0.0)
                logging.warning(
                    "Banco ocupado, tentando novamente em %.0fms (tentativa %s/%s).",
                    delay * 1000,
                    attempt + 1,
                    retries,
                )
                time.sleep(delay)
        raise RuntimeError("Transação de escrita não finalizada.")
    # === SQLITE MULTIUSER END ===

    def get_column_names(self):
        return self.columns

    def count_obras(self, pacotes=None):
        """Retorna o total de obras cadastradas."""
        try:
            if pacotes is None:
                pacotes = self.allowed_pacotes
            self._ensure_cache_loaded()
            if not self.data_access_layer:
                return 0
            return self.data_access_layer.count(pacotes)
        except Exception as e:
            logging.error(f"Erro ao contar obras: {e}")
            return 0

    def get_last_modification_info(self, pacotes=None):
        """Obtém a data e o usuário da última modificação registrada."""
        try:
            if pacotes is None:
                pacotes = self.allowed_pacotes
            self._ensure_cache_loaded()
            if not self.data_access_layer:
                return None, None
            return self.data_access_layer.get_last_modification_info(pacotes)
        except Exception as e:
            logging.error(f"Erro ao obter última modificação: {e}")
        return None, None

    def get_distinct_values(self, column_name):
        """Retorna valores distintos da coluna especificada, respeitando allowed_pacotes."""
        try:
            self._ensure_cache_loaded()
            if not self.data_access_layer:
                return []
            return self.data_access_layer.get_distinct_values(column_name, self.allowed_pacotes)
        except Exception as e:
            logging.error(
                f"Erro ao obter valores distintos de {column_name}: {e}"
            )
            return []
