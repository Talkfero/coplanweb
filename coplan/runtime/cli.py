"""CLI helpers + logging avancado + setup_application.

Extraidos de codigo5_coplan.py:
- _UserContextFilter: injeta nome do usuario nos logs
- _install_exception_hooks: captura excecoes nao tratadas (main + threads)
- configure_logging: configura logging para arquivo + stdout
- reset_config_to_defaults: restaura config.json basico
- show_config_info: imprime config atual
- run_long_process_example: dispara LongProcessWorker
- setup_application: copia arquivos essenciais para distribuicao
- main_cli: entry-point CLI (argparse)
"""
from __future__ import annotations

import argparse
import getpass
import logging
import logging.handlers
import os
import shutil
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6 import QtCore

from runtime.config import (
    APP_DIRS,
    DEFAULT_CRITERIOS,
    DEFAULT_PIORA_MERCADO,
    ConfigManager,
)
from runtime.qss import _resolve_qss_path
from runtime.workers import LongProcessWorker

LOGGER = logging.getLogger("codigo5_coplan")


# ---------------------------------------------------------------------------
# Logging avancado
# ---------------------------------------------------------------------------
class _UserContextFilter(logging.Filter):
    def __init__(self, user: str):
        super().__init__()
        self._user = user

    def filter(self, record: logging.LogRecord) -> bool:
        record.user = self._user
        return True


def _install_exception_hooks() -> None:
    def _handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        exc_value = exc_value or exc_type("Exceção sem valor associado.")
        logging.getLogger(__name__).exception(
            "Exceção não tratada.",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def _handle_thread_exception(args: threading.ExceptHookArgs) -> None:
        exc_value = args.exc_value or args.exc_type("Exceção em thread sem valor associado.")
        thread_name = args.thread.name if args.thread else "desconhecida"
        logging.getLogger(__name__).exception(
            "Exceção não tratada em thread %s.",
            thread_name,
            exc_info=(args.exc_type, exc_value, args.exc_traceback),
        )

    sys.excepthook = _handle_exception
    if hasattr(threading, "excepthook"):
        threading.excepthook = _handle_thread_exception


def configure_logging(log_file: Optional[str] = None):
    """Configura o logging para gravar as mensagens em um arquivo de log."""
    if log_file is None:
        log_file = os.path.join(APP_DIRS["logs"], "app.log")
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [user=%(user)s pid=%(process)d] "
        "%(name)s:%(lineno)d - %(message)s"
    )
    user_filter = _UserContextFilter(getpass.getuser())
    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(user_filter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(user_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    _install_exception_hooks()
    root_logger.info("Logging configurado com sucesso.")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------
def reset_config_to_defaults():
    """Restaura parâmetros padrão sem apagar caminhos já configurados."""
    default_config = {
        "empresa_sigla": "MA",
        "modulos": {},
        "regional_map": {},
        "criterios_planejamento": DEFAULT_CRITERIOS.copy(),
        "piora_mercado": DEFAULT_PIORA_MERCADO.copy(),
        "descricao_obra_templates": {},
    }
    ConfigManager.save_config(default_config)


def show_config_info():
    """Exibe no console as configurações atuais carregadas, útil para debug."""
    cfg = ConfigManager.load_config()
    LOGGER.info("Configurações Atuais:")
    for k, v in cfg.items():
        LOGGER.info("  %s: %s", k, v)


# ---------------------------------------------------------------------------
# Demo: long process via QThreadPool
# ---------------------------------------------------------------------------
def run_long_process_example(main_window):
    """Dispara o LongProcessWorker pelo QThreadPool global."""
    worker = LongProcessWorker(param="algum_parametro")
    worker.long_process_finished.connect(
        main_window.on_long_process_finished,
        QtCore.Qt.ConnectionType.QueuedConnection,
    )
    QtCore.QThreadPool.globalInstance().start(worker)


# ---------------------------------------------------------------------------
# Setup de distribuicao + CLI
# ---------------------------------------------------------------------------
def setup_application(dist_folder="dist"):
    """Copia arquivos essenciais para uma pasta de distribuição."""
    if not os.path.exists(dist_folder):
        os.makedirs(dist_folder)
    arquivos_essenciais = {
        "config.json": ConfigManager.CONFIG_FILE,
        "custom_style.qss": _resolve_qss_path("custom_style.qss"),
        "app.log": os.path.join(APP_DIRS["logs"], "app.log"),
    }
    for nome_arquivo, caminho_origem in arquivos_essenciais.items():
        if caminho_origem and os.path.exists(caminho_origem):
            destino = os.path.join(dist_folder, nome_arquivo)
            shutil.copy2(caminho_origem, destino)
            logging.info(f"Arquivo '{nome_arquivo}' copiado para '{dist_folder}'.")
        else:
            logging.warning(f"Arquivo essencial '{nome_arquivo}' não encontrado.")


def main_cli():
    """Entry-point CLI (sem GUI). Aceita --setup e --reset-config."""
    parser = argparse.ArgumentParser(description="Ferramenta de Gerenciamento de Obras")
    parser.add_argument("--setup", action="store_true", help="Executa rotinas de setup para distribuição.")
    parser.add_argument("--reset-config", action="store_true", help="Restaura config.json para os valores padrão.")
    args = parser.parse_args()

    if args.setup:
        setup_application()
    if args.reset_config:
        reset_config_to_defaults()

    logging.info("Execução via linha de comando finalizada.")
