# -*- coding: utf-8 -*-
import sys, os, json, sqlite3, datetime, tempfile, textwrap, multiprocessing, math
import time
import getpass
import logging
import logging.handlers
import argparse
import shutil
import subprocess
import traceback
import csv
import hashlib
import unicodedata
import threading
from functools import wraps
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Callable, Any, TypedDict, Sequence, cast
from pathlib import Path

import re
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
# PyQt widgets and utilities
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import (
    Signal,
    Slot,
    QObject,
    Qt,
    QThread,
    QTimer,
    QDateTime,
    QDate,
    QSize,
    QPoint,
)
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QToolBar,
    QStyle,
    QToolButton,
    QSizePolicy,
    QFrame,
    QHBoxLayout,
    QWidget,
    QSpacerItem,
)
from weakref import WeakKeyDictionary
from ui_helpers import (
    matches_filter_value,
    matches_cod_terms,
)
from visualizar_pagination import paginate_visualizar_rows, format_pagination_label
from footer_more_actions import (
    get_collapsed_action_keys,
    iter_default_entries,
    should_show_more_actions_button,
)

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))


# Re-exports: setup_logging/ts_now/ts_log foram extraidos para
# runtime/text_utils.py (refactor 2026-05-05). Importamos aqui pra manter
# `from codigo5_coplan import setup_logging` funcionando.
from runtime.text_utils import setup_logging, ts_now, ts_log  # noqa: E402,F401


LOGGER = logging.getLogger(__name__)

# Re-exports: open_file/show_user_error/_as_tool_button extraidos para
# runtime/dialogs.py.
from runtime.dialogs import (  # noqa: E402,F401
    _TOOLBUTTON_SLOTS,
    _as_tool_button,
    open_file,
    show_user_error,
)


# Re-exports: normalize_key/_compact_key foram extraidos para runtime/text_utils.py
from runtime.text_utils import normalize_key, _compact_key  # noqa: E402,F401


# Re-exports: EMPRESA_SIGLAS_VALIDAS / REGIONAL_TO_COD foram extraidos
# para runtime/config.py (refactor 2026-05-05).
from runtime.config import EMPRESA_SIGLAS_VALIDAS, REGIONAL_TO_COD  # noqa: E402,F401


# Re-export: normalize_text foi extraido para runtime/text_utils.py
from runtime.text_utils import normalize_text  # noqa: E402,F401


# Re-exports: helpers de COD_PEP extraidos para runtime/database.py
# (junto com cod_pep e DatabaseManager).
from runtime.text_utils import parse_cod_pep  # noqa: E402,F401
from runtime.database import (  # noqa: E402,F401
    _coerce_obra_row_dict,
    _ensure_empresa_cod_pep_tail,
    get_empresa_sigla_from_config,
)


# Re-exports: cod_pep + ensure_schema_business_patch extraidos para
# runtime/database.py.
from runtime.database import (  # noqa: E402,F401
    cod_pep,
    ensure_schema_business_patch,
)


# Re-exports: 28 row helpers wrappers + Qt confirmations extraidos para
# runtime/row_helpers.py (Iter 6).
from runtime.row_helpers import (  # noqa: E402,F401
    _expand_key_variants,
    _find_column_name,
    _first_non_empty_value,
    _format_processing_summary,
    _get_ganhos_tolerancia,
    _has_any_value,
    _is_tecnico_dirty_value,
    _normalize_description,
    _parse_float,
    _row_has_any_key,
    _row_id_value,
    _row_integrity_reasons,
    _selected_ids_from_view,
    _sort_row_id,
    build_dup_key,
    build_scope_key,
    filter_targets_by_aprovacao,
    find_duplicate_in_db,
    get_row_value_by_key,
    get_selected_or_visible_rows,
    get_selected_rows,
    is_aprovada,
    require_ganhos_ok_or_confirm,
    require_integrity_or_block,
    require_tecnico_clean_or_confirm,
    sort_processing_rows,
    validate_ganhos_consistency,
    validate_min_integrity,
)



# ==========================================================
# DATA ACCESS LAYER (DAL) – COPLAN
# Responsável apenas por acesso ao banco e cache em memória
# NÃO contém UI, Qt, QMessageBox, prints ou regra de negócio
# ==========================================================
# DataAccessLayer migrado para core/repositories/obra_read_repo.py
# (Passo 6b da separacao UI/Core). Re-exportado com o nome legado para
# preservar todas as referencias no codigo legado e em testes externos.
from core.repositories.obra_read_repo import ObraReadRepo as DataAccessLayer

# Re-exports: DataSourceState/DataStateManager/get_app_dirs/APP_DIRS
# foram extraidos para runtime/config.py.
from runtime.config import (  # noqa: E402,F401
    APP_DIRS,
    DataSourceState,
    DataStateManager,
    get_app_dirs,
)


# Re-exports: cache de Excel + _clean_excel_columns extraidos para
# runtime/apoio.py.
from runtime.apoio import (  # noqa: E402,F401
    _EXCEL_CACHE_DIR,
    _clean_excel_columns,
    cache_get_df,
    cache_key_for_file,
    cache_set_df,
    read_excel_cached,
)


# Lista padrao de Projetos de Investimento (PIs) e metadata consolidada
# DEFAULT_PI_METADATA migrado para core/services/pi_metadata_service.py
# (Passo 4 da separacao UI/Core). Importamos a constante para preservar
# referencia em todo o codigo legado.
from core.services.pi_metadata_service import DEFAULT_PI_METADATA

# Etapa B.1: helpers puros do save_data extraidos para core/services/.
from core.services.salvar_obra_service import (
    SalvarObraInput,
    aplicar_alimentador_validations,
    aplicar_historico_ao_dict,
    avaliar_diff,
    bloqueado_por_despachada,
    build_obra_dados,
    montar_historico_msg,
)

STANDARD_PIS = [entry["nome"] for entry in DEFAULT_PI_METADATA]


# Re-exports: PI metadata helpers (wrappers) extraidos para runtime/calc.py.
from runtime.calc import (  # noqa: E402,F401
    _normalize_pi_metadata_entry,
    get_pi_abreviacao,
    get_pi_default_description_template,
    get_pi_extra_module_keys,
    get_pi_metadata,
    get_pi_metadata_entries,
    get_pi_metadata_map,
    get_pi_tipo_base,
)

# Re-exports: PI base helpers + boot sequence extraidos para runtime/pi_base.py.
from runtime.pi_base import (  # noqa: E402,F401
    PI_BASE_CUSTOM,
    PI_BASE_MAP,
    _dedupe_pi_base_custom,
    _find_custom_pi_base,
    _is_pi_base_known,
    _normalize_pi_base_name,
    get_all_pi_bases,
    get_pi_base,
    set_extra_keys_for_pi,
)

# Re-exports adicionais que estavam encavalados no bloco PI base original:
# constantes de planejamento (REGIONAL_MAP/ROOT_COLUMNS/...), diff_fields
# e ConfigManager. Mantemos aqui pra preservar `from codigo5_coplan import X`.
from runtime.calc import diff_fields  # noqa: E402,F401
from runtime.config import (  # noqa: E402,F401
    CAMPOS_CRITICOS_MUDANCA,
    DEFAULT_CRITERIOS,
    DEFAULT_EXPORT_PROFILES,
    DEFAULT_GANHOS_TOLERANCIA,
    DEFAULT_PIORA_MERCADO,
    GANHOS_ANTES_FIELDS,
    GANHOS_DEPOIS_FIELDS,
    GANHOS_NUMERIC_FIELDS,
    GANHO_ANTES_TOTAL_FIELDS,
    GANHO_DEPOIS_TOTAL_FIELDS,
    GANHO_TOTAL_FIELDS,
    ORDERED_COLUMNS,
    REGIONAL_MAP,
    ROOT_COLUMNS,
    TECNICO_REQUIRED_FILES,
    ConfigManager,
)

# Gerenciador do Arquivo de Apoio

# Re-export: SupportFileManager extraido para runtime/apoio.py.
from runtime.apoio import SupportFileManager  # noqa: E402,F401
# Re-exports: helpers de SQLite (locks, retry, decorators, workers) foram
# extraidos para runtime/database.py. A classe DatabaseManager grande
# permanece logo abaixo neste arquivo (ainda nao foi extraida).
from runtime.database import (  # noqa: E402,F401
    DATABASE_BUSY_CODE,
    DATABASE_LOCKED_CODE,
    DBCallableWorker,
    DatabaseBusyError,
    DatabaseLockedError,
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_CONNECT_TIMEOUT_S,
    _DATABASE_BUSY_TEXT_TOKENS,
    _SQLITE_BUSY_ERRORS,
    _SQLiteWriteOwner,
    _format_lock_time,
    _lock_info_summary,
    backup_on_error,
    build_database_busy_message,
    build_database_locked_message,
    clear_lock_info,
    create_lock_info,
    get_lock_info_path,
    is_database_busy_exception,
    is_database_locked_exception,
    is_sqlite_busy_error,
    log_connect_debug,
    open_sqlite_safe,
    read_lock_info,
    remove_lock_info,
    retry_on_busy,
    run_sql_write_safe,
    run_write_in_qthread_if_ui_thread,
    with_lock_action,
    write_lock_info,
    write_transaction_safe,
)


# Re-export: DatabaseManager extraido para runtime/database.py.
from runtime.database import DatabaseManager  # noqa: E402,F401

# Re-export: CalculationManager extraido para runtime/calc.py.
from runtime.calc import CalculationManager  # noqa: E402,F401

# Re-exports: workers Qt extraidos para runtime/workers.py.
from runtime.workers import (  # noqa: E402,F401
    DBWriteWorker,
    ExportExcelWorker,
    ImportExcelWorker,
    LongProcessWorker,
    ProgressRelay,
)

# Re-exports: render_template / get_descricao_obra_from_template (eram
# definidos depois das classes Workers no original; preservamos aqui).
from runtime.text_utils import render_template  # noqa: E402,F401
from runtime.calc import get_descricao_obra_from_template  # noqa: E402,F401

# Re-exports: ler_arquivo_com_codificacoes + carregar_arquivos extraidos para runtime/file_io.py.
from runtime.file_io import carregar_arquivos, ler_arquivo_com_codificacoes  # noqa: E402,F401

# Re-exports: widgets Qt customizados extraidos para runtime/widgets.py.
from runtime.widgets import (  # noqa: E402,F401
    CopyListWidget,
    InfoAlim,
    TemplatePlainTextEdit,
    VisibleRowTableWidget,
)

# ===========================================================================
# Mixins de MainWindow (Etapa C -- separacao por sub-feature)
# ===========================================================================
from ui.main_window.ajuda_mixin import AjudaMixin
from ui.main_window.apoio_mixin import ApoioMixin
from ui.main_window.atualizar_obra_mixin import AtualizarObraMixin
from ui.main_window.banco_mixin import BancoMixin
from ui.main_window.cadastro_mixin import CadastroMixin
from ui.main_window.cod_pep_mixin import CodPepMixin
from ui.main_window.config_mixin import ConfigMixin
from ui.main_window.estado_fontes_mixin import EstadoFontesMixin
from ui.main_window.excluir_obra_mixin import ExcluirObraMixin
from ui.main_window.exportar_excel_mixin import ExportarExcelMixin
from ui.main_window.filtros_paginacao_mixin import FiltrosPaginacaoMixin
from ui.main_window.ganhos_mixin import GanhosMixin
from ui.main_window.importar_excel_mixin import ImportarExcelMixin
from ui.main_window.nota_colapso_mixin import NotaColapsoMixin
from ui.main_window.outros_mixin import OutrosMixin
from ui.main_window.plano_obras_mixin import PlanoObrasMixin
from ui.main_window.relatorio_criterios_mixin import RelatorioCriteriosMixin
from ui.main_window.resumo_regional_mixin import ResumoRegionalMixin
from ui.main_window.resumo_volumetria_mixin import ResumoVolumetriaMixin
from ui.main_window.status_bar_chrome_mixin import StatusBarChromeMixin
from ui.main_window.tecnico_snapshot_mixin import TecnicoSnapshotMixin
from ui.main_window.visualizar_colunas_mixin import VisualizarColunasMixin
from ui.main_window.visualizar_mixin import VisualizarMixin


class MainWindow(
    AjudaMixin,
    PlanoObrasMixin,
    NotaColapsoMixin,
    OutrosMixin,
    ExcluirObraMixin,
    TecnicoSnapshotMixin,
    ConfigMixin,
    VisualizarColunasMixin,
    ResumoRegionalMixin,
    StatusBarChromeMixin,
    ImportarExcelMixin,
    ApoioMixin,
    BancoMixin,
    ExportarExcelMixin,
    CodPepMixin,
    FiltrosPaginacaoMixin,
    EstadoFontesMixin,
    AtualizarObraMixin,
    VisualizarMixin,
    RelatorioCriteriosMixin,
    CadastroMixin,
    ResumoVolumetriaMixin,
    GanhosMixin,
    QtWidgets.QMainWindow,
):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("COPLAN — Cadastro e Visualização de Obras")
        self.resize(1280, 860)
        # Ícone do aplicativo (quando disponível localmente)
        try:
            icon_candidates = [
                os.path.join(MODULE_DIR, "frontend", "assets", "cadastro-de-obras.ico"),
                os.path.join(MODULE_DIR, "cadastro-de-obras.ico"),
                os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "cadastro-de-obras.ico"),
            ]
            for icon_path in icon_candidates:
                if os.path.isfile(icon_path):
                    self.setWindowIcon(QIcon(icon_path))
                    break
        except Exception:
            pass

        # Inicializa os atributos
        self.config = ConfigManager.load_config()
        # === PI_BASE CUSTOM BEGIN ===
        self.pi_base_custom = _dedupe_pi_base_custom(
            self.config.get("pi_base_custom", [])
        )
        PI_BASE_CUSTOM[:] = list(self.pi_base_custom)
        PI_BASE_MAP.update(self.config.get("pi_base_map", {}))
        # === PI_BASE CUSTOM END ===
        # === STATUSBAR HEIGHT CONTROL BEGIN ===
        self._loading_ui_state = True
        ui_state = self.config.get("ui_state", {})
        self._statusbar_compact_pref = bool(ui_state.get("statusbar_compact", False))
        self._statusbar_height_expanded = 48
        self._statusbar_height_compact = 28
        # === STATUSBAR HEIGHT CONTROL END ===
        # === VISUALIZAR: COLUMN WIDTH PERSIST BEGIN ===
        self._visualizar_col_widths: dict[str, int] = {}
        self._visualizar_col_widths_flush_token = 0
        self._restoring_visualizar_layout = False
        # === VISUALIZAR: COLUMN WIDTH PERSIST END ===
        self.db_manager = DatabaseManager()
        self.support_manager = SupportFileManager()
        self.calc_manager = CalculationManager(self.support_manager, prompt_pi_base=False)
        self.data_state = DataStateManager()  # [RB-1.1]

        self.obra_em_edicao = None
        self.selected_pis = []  # Armazena seleção múltipla de PIs
        self.projeto_obras = None
        self.projeto_temp_data = []
        self.projeto_index = 0
        self.projeto_novo_ano = None  # Ano definido na primeira obra ao atualizar projeto
        self.projeto_novo_nome = None  # Nome definido na primeira obra ao atualizar projeto
        self.plano_update_active = False
        self.blocked_rows = set()
        self.plano_rows = set()
        self.plano_update_params = None
        self._last_db_refresh_timestamp = None
        self._last_db_refresh_user = None
        self._last_db_modification_warned = None
        self._impact_modules: Dict[str, str] = {}
        self._impact_message = ""
        self._config_tab_visibility_guard = False
        self._visualizar_source_rows: list[tuple[tuple[Any, ...], Optional[bool]]] = []
        self._visualizar_filtered_rows: list[tuple[tuple[Any, ...], Optional[bool]]] = []
        self._visualizar_page_size = 300
        self._visualizar_current_page = 1
        self._footer_overflow_actions: list[tuple[str, Callable[..., None]]] = []
        self._footer_overflow_managed_buttons: list[QtWidgets.QWidget] = []
        self._footer_overflow_threshold = 1260
        self._export_progress_dialog: QtWidgets.QProgressDialog | None = None
        self._export_worker: ExportExcelWorker | None = None
        self.initUI()
        self._build_toolbar()
        self._initialize_saved_paths()

        # Ativa a solicitação de PI base somente após a inicialização
        self.calc_manager.prompt_pi_base = True
        self.refresh_action_availability()  # [RB-1.1]

    # col_index: movido para ui.main_window mixin (Etapa C Tier 4)

    # === CONFIG COLUNAS VISUALIZAR BEGIN ===
    # _get_visualizar_columns_candidates: movido para ui.main_window mixin (Etapa C Tier 2)

    # _load_visualizar_columns_config: movido para ui.main_window mixin (Etapa C Tier 2)

    # _save_visualizar_columns_config: movido para ui.main_window mixin (Etapa C Tier 2)

    # _clear_visualizar_columns_config: movido para ui.main_window mixin (Etapa C Tier 2)

    # === VISUALIZAR: COLUMN WIDTH PERSIST BEGIN ===
    # _get_visualizar_column_names: movido para ui.main_window mixin (Etapa C Tier 2)

    # _apply_visualizar_column_widths: movido para ui.main_window mixin (Etapa C Tier 2)

    # _on_visualizar_section_resized: movido para ui.main_window mixin (Etapa C Tier 2)

    # _flush_visualizar_column_widths: movido para ui.main_window mixin (Etapa C Tier 2)
    # === VISUALIZAR: COLUMN WIDTH PERSIST END ===

    # apply_visualizar_columns_config: movido para ui.main_window mixin (Etapa C Tier 2)

    # show_visualizar_columns_dialog: movido para ui.main_window mixin (Etapa C Tier 2)
    # === CONFIG COLUNAS VISUALIZAR END ===

    # === VISUALIZAR: READONLY + COPY BEGIN ===
    # _copy_visualizar_selection_to_clipboard: movido para ui.main_window mixin (Etapa C Tier 2)
    # === VISUALIZAR: READONLY + COPY END ===

    # === TEMPLATE DESCRICAO_OBRA BEGIN ===
    # === PI_BASE CUSTOM BEGIN ===
    # open_manage_pi_base_dialog: movido para ui.main_window mixin (Etapa C Tier 4)
    # === PI_BASE CUSTOM END ===

    # _build_template_data: movido para ui.main_window mixin (Etapa C Tier 3)

    # setup_tab_configuracoes: movido para ui.main_window mixin (Etapa C Tier 2)

    # _refresh_configuracoes_ui: movido para ui.main_window mixin (Etapa C Tier 2)

    # _save_empresa_config: movido para ui.main_window mixin (Etapa C Tier 2)

    # _restore_criterios_config: movido para ui.main_window mixin (Etapa C Tier 4)

    # _save_criterios_config: movido para ui.main_window mixin (Etapa C Tier 4)

    # _restore_piora_config: movido para ui.main_window mixin (Etapa C Tier 4)

    # _save_piora_config: movido para ui.main_window mixin (Etapa C Tier 4)

    # _setup_template_settings_tab: movido para ui.main_window mixin (Etapa C Tier 3)

    # open_configuracoes_tab: movido para ui.main_window mixin (Etapa C Tier 2)

    # _is_configuracoes_tab_visible: movido para ui.main_window mixin (Etapa C Tier 2)

    # _show_configuracoes_tab: movido para ui.main_window mixin (Etapa C Tier 2)

    # _hide_configuracoes_tab: movido para ui.main_window mixin (Etapa C Tier 2)

    # _on_main_tab_changed: movido para ui.main_window mixin (Etapa C Tier 2)

    # _open_configuracoes_tab: movido para ui.main_window mixin (Etapa C Tier 2)

    # open_descricao_template_dialog: movido para ui.main_window mixin (Etapa C Tier 3)
    # === TEMPLATE DESCRICAO_OBRA END ===

    # ensure_db_connected: movido para ui.main_window mixin (Etapa C Tier 3)
    
    # _path_exists: movido para ui.main_window mixin (Etapa C Tier 3)

    # _ganhos_folder: movido para ui.main_window mixin (Etapa C Tier 4)

    # _schedule_ganhos_refresh: movido para ui.main_window mixin (Etapa C Tier 4)

    # _flush_ganhos_refresh: movido para ui.main_window mixin (Etapa C Tier 4)

    # _build_toolbar: movido para ui.main_window mixin (Etapa C Tier 2)


    # _initialize_saved_paths: movido para ui.main_window mixin (Etapa C Tier 2)

    def initUI(self):
        self.tabs = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tabs)

        # Barra de status fixa para exibir caminhos (sempre visível e legível)
        self.status = self.statusBar()
        self.status.setSizeGripEnabled(True)

        self.db_path_label = QtWidgets.QLabel()
        self.db_path_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.db_path_label.setMinimumWidth(450)
        self.db_path_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.db_path_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self.support_path_label = QtWidgets.QLabel()
        self.support_path_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.support_path_label.setMinimumWidth(450)
        self.support_path_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        self.support_path_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self.db_valid_label = QtWidgets.QLabel()
        self.db_valid_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )

        self.apoio_valid_label = QtWidgets.QLabel()
        self.apoio_valid_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )

        self.tecnico_valid_label = QtWidgets.QLabel()
        self.tecnico_valid_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )

        self.impact_label = QtWidgets.QLabel()
        self.impact_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self.impact_label.setWordWrap(True)
        self.impact_label.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        reliability_widget = QtWidgets.QWidget()
        reliability_layout = QtWidgets.QHBoxLayout(reliability_widget)
        reliability_layout.setContentsMargins(0, 0, 0, 0)
        reliability_layout.setSpacing(12)
        reliability_layout.addWidget(self.db_valid_label)
        reliability_layout.addWidget(self.apoio_valid_label)
        reliability_layout.addWidget(self.tecnico_valid_label)
        reliability_layout.addWidget(self.impact_label)

        self.status.addWidget(reliability_widget, 1)
        # === STATUSBAR HEIGHT CONTROL BEGIN ===
        self.status_expand_container = QtWidgets.QWidget()
        status_expand_layout = QtWidgets.QHBoxLayout(self.status_expand_container)
        status_expand_layout.setContentsMargins(0, 0, 0, 0)
        status_expand_layout.setSpacing(12)
        status_expand_layout.addWidget(self.db_path_label, 1)
        status_expand_layout.addWidget(self.support_path_label, 2)
        self.status.addPermanentWidget(self.status_expand_container, 1)

        self.btn_statusbar_toggle = QtWidgets.QToolButton()
        self.btn_statusbar_toggle.setCheckable(True)
        self.btn_statusbar_toggle.setAutoRaise(True)
        self.btn_statusbar_toggle.setToolTip("Compactar / Expandir rodapé")
        self.btn_statusbar_toggle.toggled.connect(self.set_statusbar_height)
        self.btn_statusbar_toggle.toggled.connect(self._persist_statusbar_compact)
        self.status.addPermanentWidget(self.btn_statusbar_toggle)
        # === STATUSBAR HEIGHT CONTROL END ===
        self._db_path_full_text = ""
        self._support_path_full_text = ""

        self.tab_visualizar = QtWidgets.QWidget()
        self.tab_cadastro = QtWidgets.QWidget()
        self.tab_configuracoes = QtWidgets.QWidget()
        self.tab_ganhos = QtWidgets.QWidget()
        self.tab_resumo = QtWidgets.QWidget()

        self.tabs.addTab(self.tab_visualizar, "Visualizar Obras")
        self.tabs.addTab(self.tab_cadastro, "Cadastro de Obras")
        self.tabs.addTab(self.tab_ganhos, "Ganhos")
        self.tabs.addTab(self.tab_resumo, "Resumo")

        self.tabs.currentChanged.connect(self._on_main_tab_changed)  # [RB-RESTORE-OLD]

        self.setup_tab_visualizar()
        self.setup_tab_cadastro()
        self.setup_tab_configuracoes()
        self.setup_tab_ganhos()
        self.setup_tab_resumo()

        # === STATUSBAR HEIGHT CONTROL BEGIN ===
        self.btn_statusbar_toggle.setChecked(self._statusbar_compact_pref)
        self.set_statusbar_height(self._statusbar_compact_pref)
        self._loading_ui_state = False
        # === STATUSBAR HEIGHT CONTROL END ===

        self.field_ganhos_totais_depois.textChanged.connect(
            lambda: (
                self.popular_quadro_resumo_from_ganhos_depois(
                    self.field_alimentador.currentText(),
                    ";".join(
                        self.list_alimentadores_benef.item(i).text()
                        for i in range(self.list_alimentadores_benef.count())
                    ),
                ),
                self.popular_resumo_ganhos_projeto(
                    self.field_projeto.text().strip()
                ),
            )
        )

        # Atalhos de teclado para salvar a obra nas abas de Cadastro e Ganhos
        self.shortcut_salvar_cadastro = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+B"), self.tab_cadastro
        )
        # O sinal 'activated' de QShortcut não possui parâmetros.
        # Conecte diretamente sem especificar tipo de parâmetro.
        self.shortcut_salvar_cadastro.activated.connect(self.save_data)

        self.shortcut_salvar_ganhos = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+B"), self.tab_ganhos
        )
        # O sinal 'activated' de QShortcut não aceita parâmetro 'int'.
        self.shortcut_salvar_ganhos.activated.connect(self.save_data)

        # O tema visual é aplicado globalmente via custom_style.qss (QApplication).
        # Mantemos apenas o objectName da janela para referência no QSS.
        self.setObjectName("appMainWindow")
        self.update_db_path_label()

    # === STATUSBAR HEIGHT CONTROL BEGIN ===
    # set_statusbar_height: movido para ui.main_window mixin (Etapa C Tier 2)

    # _persist_statusbar_compact: movido para ui.main_window mixin (Etapa C Tier 2)
    # === STATUSBAR HEIGHT CONTROL END ===

    # _compute_file_token: movido para ui.main_window mixin (Etapa C Tier 2)

    # _compute_folder_token: movido para ui.main_window mixin (Etapa C Tier 2)

    # _compute_tecnico_snapshot_token: movido para ui.main_window mixin (Etapa C Tier 2)

    # _get_tecnico_snapshot_source: movido para ui.main_window mixin (Etapa C Tier 2)

    @run_write_in_qthread_if_ui_thread
    def _apply_tecnico_token_change_db(self, new_token: str) -> bool:
        if not getattr(self.db_manager, "conn", None):
            return False
        if self.db_manager.count_obras() == 0:
            return False

        def apply_fallback() -> bool:
            LOGGER.warning("fallback por falta de evidência de escopo")
            try:
                self.db_manager.mark_tecnico_dirty_all()
                return True
            except Exception as exc:
                LOGGER.warning("Falha no fallback de técnico_dirty: %s", exc)
                return False

        dirty_applied = False
        try:
            with self.db_manager._with_connection():
                cursor = self.db_manager._get_cursor()
                if not cursor:
                    return apply_fallback()

                columns = self.db_manager.get_column_names()
                if "cod" not in columns:
                    return apply_fallback()

                idx_cod = columns.index("cod")
                obras = self.db_manager.fetch_all(self.db_manager.allowed_pacotes)
                scope_to_cods: dict[str, list[str]] = {}
                for row in obras:
                    row_dict = {
                        col: row[i] if i < len(row) else ""
                        for i, col in enumerate(columns)
                    }
                    scope_key = build_scope_key(row_dict)
                    if not scope_key:
                        continue
                    cod = str(row[idx_cod] or "").strip()
                    if not cod:
                        continue
                    scope_to_cods.setdefault(scope_key, []).append(cod)

                if not scope_to_cods:
                    return apply_fallback()

                scopes_changed: set[str] = set()
                updated_at = datetime.datetime.now().strftime("%d/%m/%y %H:%M")
                for scope_key in scope_to_cods:
                    cursor.execute(
                        "SELECT token FROM tecnico_scope_tokens WHERE scope_key = ?",
                        (scope_key,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        with self.db_manager.write_transaction():
                            cursor.execute(
                                "INSERT INTO tecnico_scope_tokens "
                                "(scope_key, token, updated_at) VALUES (?, ?, ?)",
                                (scope_key, new_token, updated_at),
                            )
                    else:
                        old_scope_token = str(row[0] or "")
                        if old_scope_token != new_token:
                            scopes_changed.add(scope_key)

                if scopes_changed:
                    cods_to_dirty = sorted(
                        {cod for scope in scopes_changed for cod in scope_to_cods[scope]}
                    )
                    placeholders = ",".join(["?"] * len(cods_to_dirty))
                    with self.db_manager.write_transaction():
                        cursor.execute(
                            "UPDATE obras SET tecnico_dirty = 'SIM' "
                            f"WHERE cod IN ({placeholders})",
                            cods_to_dirty,
                        )
                    for scope_key in scopes_changed:
                        with self.db_manager.write_transaction():
                            cursor.execute(
                                "UPDATE tecnico_scope_tokens "
                                "SET token = ?, updated_at = ? "
                                "WHERE scope_key = ?",
                                (new_token, updated_at, scope_key),
                            )
                    dirty_applied = True
        except Exception:
            dirty_applied = apply_fallback()

        return dirty_applied

    # _handle_tecnico_token_change: movido para ui.main_window mixin (Etapa C Tier 2)

    # update_tecnico_dirty_indicator: movido para ui.main_window mixin (Etapa C Tier 2)

    # atualizar_snapshot_tecnico_selecionados: movido para ui.main_window mixin (Etapa C Tier 2)

    # _set_data_state: movido para ui.main_window mixin (Etapa C Tier 3)

    # _register_source_impact: movido para ui.main_window mixin (Etapa C Tier 3)

    # _update_impact_label: movido para ui.main_window mixin (Etapa C Tier 3)

    # _format_state_timestamp: movido para ui.main_window mixin (Etapa C Tier 3)

    # update_reliability_labels: movido para ui.main_window mixin (Etapa C Tier 3)

    # _validate_db_minimum: movido para ui.main_window mixin (Etapa C Tier 3)

    # _update_db_state: movido para ui.main_window mixin (Etapa C Tier 3)

    # _update_apoio_state: movido para ui.main_window mixin (Etapa C Tier 3)

    # _update_ganhos_path_state: movido para ui.main_window mixin (Etapa C Tier 3)

    # _validate_ganhos_files: movido para ui.main_window mixin (Etapa C Tier 4)

    # _update_tecnico_state: movido para ui.main_window mixin (Etapa C Tier 3)

    # require_state: movido para ui.main_window mixin (Etapa C Tier 3)

    # _go_to_required_source: movido para ui.main_window mixin (Etapa C Tier 3)

    # _mark_db_refresh_point: movido para ui.main_window mixin (Etapa C Tier 3)

    # _warn_external_db_update: movido para ui.main_window mixin (Etapa C Tier 3)

    # require_export_sources: movido para ui.main_window mixin (Etapa C Tier 3)

    # refresh_action_availability: movido para ui.main_window mixin (Etapa C Tier 3)

    # _with_loading_indicator: movido para ui.main_window mixin (Etapa C Tier 2)

    # load_last_support_file: movido para ui.main_window mixin (Etapa C Tier 3)

    # load_last_ganhos_path: movido para ui.main_window mixin (Etapa C Tier 4)

    # setup_tab_visualizar: movido para ui.main_window mixin (Etapa C Tier 4)

    # schedule_filter_table: movido para ui.main_window mixin (Etapa C Tier 3)


    # focus_global_filter: movido para ui.main_window mixin (Etapa C Tier 3)

    # clear_all_filters: movido para ui.main_window mixin (Etapa C Tier 3)

    # _collect_active_filters: movido para ui.main_window mixin (Etapa C Tier 3)

    # _update_filter_feedback: movido para ui.main_window mixin (Etapa C Tier 3)

    # _on_page_size_changed: movido para ui.main_window mixin (Etapa C Tier 3)

    # _go_to_previous_page: movido para ui.main_window mixin (Etapa C Tier 3)

    # _go_to_next_page: movido para ui.main_window mixin (Etapa C Tier 3)

    # _render_visualizar_page: movido para ui.main_window mixin (Etapa C Tier 3)

    # _setup_footer_icons: movido para ui.main_window mixin (Etapa C Tier 2)

    # _refresh_footer_overflow_menu: movido para ui.main_window mixin (Etapa C Tier 2)

    # _refresh_footer_responsive_actions: movido para ui.main_window mixin (Etapa C Tier 2)

    # matches_filter: movido para ui.main_window mixin (Etapa C Tier 3)

    # _gate_aprovadas_for_action: movido para ui.main_window mixin (Etapa C Tier 3)

    # _confirmar_exclusao_excepcional: movido para ui.main_window mixin (Etapa C Tier 3)

    # _registrar_exclusao_excepcional: movido para ui.main_window mixin (Etapa C Tier 3)


    # 2. Na função filter_table, inclua a verificação para o filtro de pacote:
    # filter_table: movido para ui.main_window mixin (Etapa C Tier 3)


    # _obter_obras_visiveis_resumo: movido para ui.main_window mixin (Etapa C Tier 4)


    # _obter_obras_visiveis_resumo_regional_se: movido para ui.main_window mixin (Etapa C Tier 2)


    # show_filter_dialog: movido para ui.main_window mixin (Etapa C Tier 3)






    # setup_tab_cadastro: movido para ui.main_window mixin (Etapa C Tier 4)
    # setup_tab_ganhos: movido para ui.main_window mixin (Etapa C Tier 4)

    # _init_resumo_grid: movido para ui.main_window mixin (Etapa C Tier 4)

    # add_resumo_bloco: movido para ui.main_window mixin (Etapa C Tier 4)

    # setup_tab_resumo: movido para ui.main_window mixin (Etapa C Tier 4)

    # _export_qtable_to_sheet: movido para ui.main_window mixin (Etapa C Tier 3)

    # on_exportar_resumo: movido para ui.main_window mixin (Etapa C Tier 4)

    # popular_volumetria_financeiro: movido para ui.main_window mixin (Etapa C Tier 4)

    # popular_resumo_regional_se: movido para ui.main_window mixin (Etapa C Tier 2)

    # mostrar_menu_export_resumo_regional: movido para ui.main_window mixin (Etapa C Tier 2)

    # _get_resumo_regional_export_df: movido para ui.main_window mixin (Etapa C Tier 2)

    # exportar_resumo_regional_se_excel: movido para ui.main_window mixin (Etapa C Tier 2)

    # exportar_resumo_regional_se_csv: movido para ui.main_window mixin (Etapa C Tier 2)

    # mostrar_menu_contexto_alimentadores: movido para ui.main_window mixin (Etapa C Tier 4)

    # remover_alimentador_beneficiado: movido para ui.main_window mixin (Etapa C Tier 3)

    # copiar_alimentadores_benef: movido para ui.main_window mixin (Etapa C Tier 3)

    # copiar_textos_lista: movido para ui.main_window mixin (Etapa C Tier 4)

    # popular_quadro_resumo_from_ganhos_depois: movido para ui.main_window mixin (Etapa C Tier 4)

    def _preencher_celula_criterio(self, tabela, row: int, col: int, celula) -> None:
        """Helper interno -- popula uma celula com cor verde/vermelho conforme ``celula.ok``.

        Usado por ``popular_quadro_resumo_from_ganhos_depois`` e
        ``popular_resumo_ganhos_projeto``.
        """
        item = QtWidgets.QTableWidgetItem(celula.text)
        if celula.ok is not None:
            color = QtGui.QColor(0, 200, 0) if celula.ok else QtGui.QColor(200, 0, 0)
            item.setForeground(QtGui.QBrush(color))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        tabela.setItem(row, col, item)

    # popular_resumo_ganhos_projeto: movido para ui.main_window mixin (Etapa C Tier 4)

    # mostrar_menu_contexto_subestacoes: movido para ui.main_window mixin (Etapa C Tier 4)

    # mostrar_menu_cabecalho: movido para ui.main_window mixin (Etapa C Tier 4)

    # mostrar_menu_linha: movido para ui.main_window mixin (Etapa C Tier 4)

    # recolher_coluna: movido para ui.main_window mixin (Etapa C Tier 4)

    # _on_load_db_and_apoio_clicked: movido para ui.main_window mixin (Etapa C Tier 3)


    # load_last_obras: movido para ui.main_window mixin (Etapa C Tier 4)

    # connect_database: movido para ui.main_window mixin (Etapa C Tier 3)

    # create_new_database: movido para ui.main_window mixin (Etapa C Tier 3)

    # choose_packages: movido para ui.main_window mixin (Etapa C Tier 4)

    # load_obras_into_table: movido para ui.main_window mixin (Etapa C Tier 4)

    # on_gerar_cod_pep_clicked: movido para ui.main_window mixin (Etapa C Tier 3)

    # delete_selected_obras: movido para ui.main_window mixin (Etapa C Tier 2)

    # marcar_obras_correcao: movido para ui.main_window mixin (Etapa C Tier 2)

    # _close_export_progress_dialog: movido para ui.main_window mixin (Etapa C Tier 3)

    # _on_export_worker_progress: movido para ui.main_window mixin (Etapa C Tier 3)

    # _on_export_worker_success: movido para ui.main_window mixin (Etapa C Tier 3)

    # _on_export_worker_error: movido para ui.main_window mixin (Etapa C Tier 3)

    # export_to_excel: movido para ui.main_window mixin (Etapa C Tier 3)

    # _prompt_export_columns_mode: movido para ui.main_window mixin (Etapa C Tier 3)

    # _get_visible_db_columns_from_table: movido para ui.main_window mixin (Etapa C Tier 3)

    # update_status_label: movido para ui.main_window mixin (Etapa C Tier 2)

    # resizeEvent: movido para ui.main_window mixin (Etapa C Tier 2)

    # _apply_elided_status_text: movido para ui.main_window mixin (Etapa C Tier 2)

    # _refresh_path_labels: movido para ui.main_window mixin (Etapa C Tier 2)

    # update_db_path_label: movido para ui.main_window mixin (Etapa C Tier 2)

    # _norm_alim: movido para ui.main_window mixin (Etapa C Tier 3)

    # _parse_ganhos_totais_depois: movido para ui.main_window mixin (Etapa C Tier 4)

    # _parse_ganhos_totais_metricas: movido para ui.main_window mixin (Etapa C Tier 4)

    # _split_alimentadores_benef: movido para ui.main_window mixin (Etapa C Tier 3)

    # _is_missing_value: movido para ui.main_window mixin (Etapa C Tier 4)

    # _avaliar_alim_por_ganhos: movido para ui.main_window mixin (Etapa C Tier 4)

    # verificar_criterios_planejamento_v2: movido para ui.main_window mixin (Etapa C Tier 4)

    # _avaliar_criterios_persistencia: movido para ui.main_window mixin (Etapa C Tier 4)

    # _build_criterios_persistencia_updates: movido para ui.main_window mixin (Etapa C Tier 4)

    # _get_visualizar_scope_rows/_cods/_ids/_years: movidos para
    # ui.main_window.outros_mixin (Etapa C Tier 1)

    # _buscar_anos_por_ids: movido para ui.main_window mixin (Etapa C Tier 4)

    # _filtrar_ids_por_anos: movido para ui.main_window mixin (Etapa C Tier 3)

    # _buscar_ids_por_pacotes: movido para ui.main_window mixin (Etapa C Tier 4)

    # _filtrar_ids_por_aprovacao: movido para ui.main_window mixin (Etapa C Tier 3)

    # _prompt_relatorio_criterios_scope: movido para ui.main_window mixin (Etapa C Tier 4)

    # montar_relatorio_criterios_por_projeto: movido para ui.main_window mixin (Etapa C Tier 4)

    # _fetch_obras_by_cods: movido para ui.main_window mixin (Etapa C Tier 4)

    # exportar_relatorio_criterios_excel: movido para ui.main_window mixin (Etapa C Tier 3)

    # verificar_criterios_planejamento: movido para ui.main_window mixin (Etapa C Tier 4)


    # _obra_atende: movido para ui.main_window mixin (Etapa C Tier 4)

    # _obra_suficiente: movido para ui.main_window mixin (Etapa C Tier 4)


    # open_criterios_dialog: movido para ui.main_window mixin (Etapa C Tier 4)

    # open_piora_dialog: movido para ui.main_window mixin (Etapa C Tier 4)

    # gerar_nota_colapso_excel: movido para ui.main_window.nota_colapso_mixin (Etapa C Tier 1)


    # export_success: movido para ui.main_window mixin (Etapa C Tier 3)

    # export_error: movido para ui.main_window mixin (Etapa C Tier 3)

    # on_import_success: movido para ui.main_window mixin (Etapa C Tier 3)

    # on_import_error: movido para ui.main_window mixin (Etapa C Tier 3)

    # on_long_process_finished: movido para ui.main_window mixin (Etapa C Tier 3)

    # _prompt_duplicate_action: movido para ui.main_window mixin (Etapa C Tier 3)

    # _merge_duplicate_record: movido para ui.main_window mixin (Etapa C Tier 3)

    # import_from_excel: movido para ui.main_window mixin (Etapa C Tier 3)


    # load_support_file: movido para ui.main_window mixin (Etapa C Tier 3)


    # calcular_valor_obra_handler: movido para ui.main_window mixin (Etapa C Tier 4)

    # gerar_detalhamento: movido para ui.main_window mixin (Etapa C Tier 4)

    # _parse_ganhos_totais_resumo: movido para ui.main_window mixin (Etapa C Tier 4)


    # _formatar_decimal_resumo: movido para ui.main_window mixin (Etapa C Tier 4)

    # _montar_resumo_detalhamento_excel: movido para ui.main_window mixin (Etapa C Tier 4)





    # validar_campos_obrigatorios: movido para ui.main_window mixin (Etapa C Tier 4)

    def save_data(self):
        if not self.require_state(
            "Salvar dados", {"db": DataStateManager.CARREGADO_VALIDADO}
        ):  # [RB-1.1]
            return
        campos_vazios = self.validar_campos_obrigatorios()
        if campos_vazios:
            msg = "Os seguintes campos obrigatórios estão vazios e precisam ser preenchidos:\n" + "\n".join(campos_vazios)
            QtWidgets.QMessageBox.warning(self, "Campos Obrigatórios", msg)
            return

        # Se o campo nome_projeto (field_projeto) não estiver vazio e o campo codigo_item (field_item) estiver vazio,
        # gera o número automaticamente, utilizando a função calcular_numero_item.
        nome_projeto = self.field_projeto.text().strip()
        if nome_projeto and not self.field_item.text().strip():
            novo_item = self.calcular_numero_item(nome_projeto)
            self.field_item.setText(str(novo_item))

        try:
            pacote = self.field_pacote.currentText().strip()
            alimentador = self.field_alimentador.currentText().strip()
            projeto_investimento = self.field_projeto_investimento.currentText().strip()
            beneficiados_lista = [
                self.list_alimentadores_benef.item(i).text()
                for i in range(self.list_alimentadores_benef.count())
            ]
            erros_alim = aplicar_alimentador_validations(alimentador, beneficiados_lista)
            if erros_alim:
                # Legado mostra apenas a primeira mensagem que casou e retorna.
                QtWidgets.QMessageBox.critical(self, "Erro", erros_alim[0])
                return

            # Solicita sempre o PI base para permitir alterações em PIs
            # que não fazem parte da lista padrão.
            pi_base = get_pi_base(projeto_investimento, prompt_user=True)
            quantidade = self.field_quantidade.text().strip()
            caracteristica = self.field_caracteristicas.currentText().strip()
            coord_fim = self.field_coord_fim.text().strip()

            obra_atual = None
            descricao_existente = ""
            old_map = {}
            if self.obra_em_edicao:
                obra_atual = self.db_manager.fetch_by_cod(self.obra_em_edicao)
                if obra_atual:
                    idx_desc = self.col_index("descricao_obra")
                    if idx_desc >= 0:
                        descricao_existente = str(obra_atual[idx_desc] or "").strip()
                    old_map = {
                        col: obra_atual[idx] for idx, col in enumerate(self.db_manager.columns)
                    }

            novo_cod = self.calc_manager.gerar_cod(
                pacote,
                alimentador,
                projeto_investimento,
                quantidade,
                caracteristica,
                coord_fim,
                pi_base,
            )

            tensao_operacao = (
                self.field_tensao_operacao.text().strip()
                or self.field_tensao.text().strip()
            )
            descricao_manual = ""
            field_desc = getattr(self, "field_descricao_obra", None)
            if field_desc is not None:
                if isinstance(field_desc, QtWidgets.QPlainTextEdit):
                    descricao_manual = field_desc.toPlainText().strip()
                else:
                    descricao_manual = field_desc.text().strip()

            descricao_obra = descricao_existente or descricao_manual
            if not descricao_obra:
                gerar = QtWidgets.QMessageBox.question(
                    self,
                    "Descrição da Obra",
                    "Nenhuma descrição foi informada. Deseja gerar a descrição automaticamente?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                    QtWidgets.QMessageBox.StandardButton.No,
                )
                if gerar == QtWidgets.QMessageBox.StandardButton.Yes:
                    data_map = self._build_template_data(
                        cod=novo_cod,
                        pi_base=pi_base,
                        projeto_investimento=projeto_investimento,
                    )
                    descricao_obra = self.calc_manager.gerar_descricao_obra(
                        pi_base,
                        data_map,
                    )
            snapshot_token = self._compute_tecnico_snapshot_token()
            snapshot_at = datetime.datetime.now().strftime("%d/%m/%y %H:%M")
            snapshot_src = self._get_tecnico_snapshot_source()

            if self.obra_em_edicao:
                if obra_atual:
                    # Obtém o código antigo da obra em edição usando o nome da coluna
                    idx_cod = self.col_index("cod")
                    cod_anterior = obra_atual[idx_cod] if idx_cod >= 0 else obra_atual[0]

                    if novo_cod != cod_anterior:
                        if self.projeto_obras is not None or getattr(self, "plano_update_active", False):
                            # Em atualização de projeto ou plano de obras sempre atualiza a obra existente
                            novo_cod = cod_anterior
                        else:
                            msg_box = QtWidgets.QMessageBox(self)
                            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Question)
                            msg_box.setWindowTitle("Código Alterado")
                            msg_box.setText(
                                "O código da obra foi alterado devido à modificação de campos essenciais.\n"
                                "Deseja criar uma nova obra ou atualizar a obra existente?"
                            )

                            nova_btn = msg_box.addButton(
                                "Nova Obra",
                                QtWidgets.QMessageBox.ButtonRole.YesRole
                            )
                            atualizar_btn = msg_box.addButton(
                                "Atualizar Obra",
                                QtWidgets.QMessageBox.ButtonRole.NoRole
                            )
                            cancelar_btn = msg_box.addButton(
                                "Cancelar",
                                QtWidgets.QMessageBox.ButtonRole.RejectRole
                            )

                            msg_box.setDefaultButton(atualizar_btn)
                            # ESC ou X → botão "Cancelar"
                            msg_box.setEscapeButton(cancelar_btn)

                            msg_box.exec()

                            clicked = msg_box.clickedButton()

                            # X ou "Cancelar" → não faz nada (não cria, não atualiza)
                            if clicked == cancelar_btn or clicked is None:
                                return

                            if clicked == nova_btn:
                                self.obra_em_edicao = None  # Criar uma nova obra
                            else:
                                novo_cod = cod_anterior      # Atualizar a obra existente


            dados = build_obra_dados(SalvarObraInput(
                cod=novo_cod,
                ano=self.field_ano.currentText().strip(),
                projeto_investimento=projeto_investimento,
                pi_base=pi_base,
                nome_projeto=self.field_projeto.text().strip(),
                codigo_item=self.field_item.text().strip(),
                alimentador_principal=alimentador,
                beneficiados_list=beneficiados_lista,
                coordenada_inicio=self.field_coord_inicio.text().strip(),
                coordenada_fim=coord_fim,
                quantidade_material=quantidade,
                caracteristicas_material=caracteristica,
                novo_bay=self.field_novo_bay.currentText().strip(),
                nivel_criticidade=self.field_criticidade.currentText().strip(),
                observacoes_gerais=self.field_observacoes.toPlainText().strip(),
                nome_regional=self.field_regional.text().strip(),
                nome_superintendencia=self.field_superintendencia.text().strip(),
                nivel_tensao_obra=self.field_tensao.text().strip(),
                tensao_operacao_explicita=self.field_tensao_operacao.text().strip(),
                subestacao=self.field_se.text().strip(),
                contas_contratos_previos=self.field_contas_antes.text().strip(),
                contas_contratos_posteriores=self.field_contas_depois.text().strip(),
                contas_contratos_beneficiadas=self.field_contas_benef.text().strip(),
                carregamento_inicial=self.field_carregamento_antes.text().strip(),
                carregamento_final=self.field_carregamento_depois.text().strip(),
                perdas_iniciais=self.field_perdas_antes.text().strip(),
                perdas_finais=self.field_perdas_depois.text().strip(),
                tensao_media_inicial=self.field_tensao_media_antes.text().strip(),
                tensao_media_final=self.field_tensao_media_depois.text().strip(),
                tensao_min_inicial=self.field_tensao_min_antes.text().strip(),
                tensao_min_final=self.field_tensao_min_depois.text().strip(),
                tensao_min_linha_inicial=self.field_tensao_min_linha_antes.text().strip(),
                tensao_min_linha_final=self.field_tensao_min_linha_depois.text().strip(),
                chi_inicial=self.field_chi_antes.text().strip(),
                ci_inicial=self.field_ci_antes.text().strip(),
                tensao_max_inicial=self.field_tensao_max_antes.text().strip(),
                tensao_max_final=self.field_tensao_max_depois.text().strip(),
                tensao_min_registrada_atual=self.edit_tensao_reg_atual.text().strip(),
                carregamento_max_registrado_atual=self.edit_carreg_reg_atual.text().strip(),
                tipo_pacote=self.field_pacote.currentText().strip(),
                obra_aprovada=self.field_obra_aprovada.currentText().strip(),
                valor_obra=self.field_valor_obra.text().strip(),
                cc_benef_chi_ci=self.field_cc_benef_chi_ci.text().strip(),
                chi_final=self.field_chi_depois.text().strip(),
                ci_final=self.field_ci_depois.text().strip(),
                descricao_obra=descricao_obra,
                manobra=self.field_manobra.currentText().strip(),
                ganhos_totais_antes=self.field_ganhos_totais_antes.text().strip(),
                ganhos_totais_depois=self.field_ganhos_totais_depois.text().strip(),
                ganhos_totais_atual=self.edit_ganhos_totais_atual.text().strip(),
                snapshot_token=snapshot_token,
                snapshot_at=snapshot_at,
                snapshot_src=snapshot_src,
            ))

            dados = self.db_manager._apply_novo_bay_rules(
                dados, exclude_cod=self.obra_em_edicao
            )
            diff = avaliar_diff(dados, old_map, db_columns=self.db_manager.columns)
            if bloqueado_por_despachada(diff):
                QtWidgets.QMessageBox.critical(
                    self,
                    "Aviso",
                    "Obra já DESPACHADA. Para alterar, marque como CORREÇÃO primeiro.",
                )
                return
            motivo = ""
            if diff.campos_criticos_alterados and obra_atual:
                # Em modo "atualizar projeto", o motivo escolhido na primeira
                # obra do projeto e reutilizado nas demais para evitar pedir
                # justificativa por obra. Reset acontece em iniciar/finalizar/
                # cancelar_atualizacao_projeto.
                motivo_reusado = None
                if self.projeto_obras is not None:
                    motivo_reusado = getattr(self, "projeto_motivo_critico", None)
                if motivo_reusado:
                    motivo = motivo_reusado
                else:
                    campos_txt = ", ".join(diff.campos_criticos_alterados)
                    motivo, ok = QtWidgets.QInputDialog.getText(
                        self,
                        "Mudança crítica",
                        f"Mudança crítica: {campos_txt}. Informe motivo (obrigatório).",
                    )
                    if not ok or not motivo.strip():
                        return
                    motivo = motivo.strip()
                    if self.projeto_obras is not None:
                        self.projeto_motivo_critico = motivo
            if diff.campos_alterados:
                if diff.historico_col is not None:
                    dados = aplicar_historico_ao_dict(dados, diff, motivo=motivo)
                else:
                    # Banco sem coluna de historico/observacoes: legado loga.
                    logging.info(montar_historico_msg(
                        campos_alterados=diff.campos_alterados,
                        campos_criticos_alterados=diff.campos_criticos_alterados,
                        motivo=motivo,
                    ))
            if self.projeto_obras is not None:
                if self.projeto_index == 0:
                    self.projeto_novo_ano = dados["ano_"]
                    self.projeto_novo_nome = dados["nome_projeto"]
                else:
                    if self.projeto_novo_ano is not None:
                        dados["ano_"] = self.projeto_novo_ano
                    if self.projeto_novo_nome is not None:
                        dados["nome_projeto"] = self.projeto_novo_nome
                if self.db_manager.exists_codigo_item(
                    dados.get("nome_projeto"),
                    dados.get("codigo_item"),
                    exclude_cod=self.obra_em_edicao,
                ):
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Erro",
                        "Já existe uma obra com este código de item para o projeto informado.",
                    )
                    return
                if any(
                    d.get("nome_projeto") == dados.get("nome_projeto")
                    and d.get("codigo_item") == dados.get("codigo_item")
                    for d in self.projeto_temp_data
                ):
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Erro",
                        "Já existe uma obra com este código de item para o projeto informado.",
                    )
                    return
                self.projeto_temp_data.append(dados)
                if self.projeto_index not in range(len(self.projeto_obras)):
                    self.projeto_index = len(self.projeto_temp_data) - 1
                if len(self.projeto_temp_data) < len(self.projeto_obras):
                    self.projeto_index += 1
                    self.load_projeto_obra()
                self.update_navegacao_projeto()
                #QtWidgets.QMessageBox.information(self, "Sucesso", "Obra armazenada temporariamente.")
            else:
                if self.db_manager.exists_codigo_item(
                    dados.get("nome_projeto"),
                    dados.get("codigo_item"),
                    exclude_cod=self.obra_em_edicao,
                ):
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Erro",
                        "Já existe uma obra com este código de item para o projeto informado.",
                    )
                    return
                if self.obra_em_edicao:
                    try:
                        self.db_manager.update_obra(dados, self.obra_em_edicao, skip_blank=True)
                    except ValueError as e:
                        QtWidgets.QMessageBox.critical(self, "Erro", str(e))
                        return
                    QtWidgets.QMessageBox.information(self, "Sucesso", "Obra atualizada com sucesso!")
                    self.obra_em_edicao = None
                else:
                    if self.db_manager.fetch_by_cod(novo_cod):
                        QtWidgets.QMessageBox.critical(self, "Erro", "Já existe uma obra com este código.")
                        return
                    duplicate = find_duplicate_in_db(self.db_manager, dados)
                    if duplicate:
                        action = self._prompt_duplicate_action(duplicate, dados)
                        if action == "cancel":
                            return
                        if action == "merge":
                            merged = self._merge_duplicate_record(duplicate, dados)
                            if merged:
                                QtWidgets.QMessageBox.information(
                                    self,
                                    "Sucesso",
                                    "Registro existente atualizado com sucesso!",
                                )
                                self.load_obras_into_table()
                                self.limpar_campos_cadastro()
                            else:
                                QtWidgets.QMessageBox.information(
                                    self,
                                    "Aviso",
                                    "Nenhuma atualização aplicável foi encontrada.",
                                )
                            return
                    try:
                        self.db_manager.insert_obra(dados)
                    except PermissionError as e:
                        QtWidgets.QMessageBox.warning(self, "Aviso", str(e))
                        return
                    except ValueError as e:
                        QtWidgets.QMessageBox.critical(self, "Erro", str(e))
                        return
                    QtWidgets.QMessageBox.information(self, "Sucesso", "Nova obra criada com sucesso!")

                self.load_obras_into_table()
                self.limpar_campos_cadastro()

        except PermissionError as e:
            QtWidgets.QMessageBox.warning(self, "Aviso", str(e))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao salvar obra: {str(e)}")


    # alimentador_selecionado: movido para ui.main_window mixin (Etapa C Tier 3)


    # limpar_campos_cadastro: movido para ui.main_window mixin (Etapa C Tier 4)


    # limpar_campos_ganhos: movido para ui.main_window mixin (Etapa C Tier 4)

        

    # adicionar_alimentador_benef: movido para ui.main_window mixin (Etapa C Tier 3)

    # selecionar_pasta_arquivos: movido para ui.main_window mixin (Etapa C Tier 4)

    # nova_se: movido para ui.main_window mixin (Etapa C Tier 4)

    # novo_al: movido para ui.main_window mixin (Etapa C Tier 4)

    # reconfiguracao: movido para ui.main_window mixin (Etapa C Tier 4)

    # alivio_se: movido para ui.main_window mixin (Etapa C Tier 4)

    # flexibilizacao: movido para ui.main_window mixin (Etapa C Tier 4)

    # preencher_novo_al: movido para ui.main_window mixin (Etapa C Tier 3)

    # gerar_ganhos_totais: movido para ui.main_window mixin (Etapa C Tier 4)

    # gerar_ganhos_totais_atual: movido para ui.main_window mixin (Etapa C Tier 4)

    # preencher_campos_antes: movido para ui.main_window mixin (Etapa C Tier 4)

    # preencher_campos_depois: movido para ui.main_window mixin (Etapa C Tier 4)

    # preencher_parametros_atuais: movido para ui.main_window mixin (Etapa C Tier 4)


    # preencher_ganhos_massa: movido para ui.main_window mixin (Etapa C Tier 4)
    # atualizar_obras: movido para ui.main_window mixin (Etapa C Tier 4)

    @run_write_in_qthread_if_ui_thread
    def _exportar_para_banco_write_phase(
        self,
        file_path: str,
        rows_valid: list[dict[str, Any]],
        ignoradas_aprovadas: int,
        ignoradas_integridade: int,
    ) -> tuple[str, str, str]:
        warning_schema_msg = ""
        info_msg = ""
        critical_msg = ""
        owner = _SQLiteWriteOwner(str(file_path or "").strip())
        try:
            with write_transaction_safe(owner) as cursor_export:
                cursor_export.execute("PRAGMA table_info(obras)")
                col_info = cursor_export.fetchall()
                columns = self.db_manager.get_column_names()
                if not col_info:
                    col_defs = ", ".join([f"{col} TEXT" for col in columns])
                    cursor_export.execute(f"CREATE TABLE obras ({col_defs})")
                    dest_columns = list(columns)
                else:
                    dest_columns = [row[1] for row in col_info]

                source_set = {c.lower() for c in columns}
                dest_set = {c.lower() for c in dest_columns}
                missing_in_dest = [c for c in columns if c.lower() not in dest_set]
                extra_in_dest = [c for c in dest_columns if c.lower() not in source_set]
                if missing_in_dest or extra_in_dest:
                    msg_parts = []
                    if missing_in_dest:
                        msg_parts.append(
                            "Colunas ausentes no banco de destino:\n- "
                            + "\n- ".join(missing_in_dest)
                        )
                    if extra_in_dest:
                        msg_parts.append(
                            "Colunas extras no banco de destino (não serão preenchidas):\n- "
                            + "\n- ".join(extra_in_dest)
                        )
                    warning_schema_msg = "\n\n".join(msg_parts)
                ids = []
                for row in rows_valid:
                    cod = get_row_value_by_key(row, "cod")
                    if cod:
                        ids.append(cod)
                ids = list(dict.fromkeys(ids))
                if not ids:
                    info_msg = "Nenhuma obra encontrada para exportar."
                else:
                    rows = self.db_manager.fetch_by_cods(ids)
                    processadas_ok = 0
                    falhas_total = 0
                    falhas: list[str] = []
                    idx_cod = columns.index("cod") if "cod" in columns else -1
                    common_columns = [c for c in columns if c.lower() in dest_set]
                    if not common_columns:
                        critical_msg = "Nenhuma coluna compatível encontrada entre origem e destino."
                    else:
                        cod_col = "cod" if "cod" in common_columns else ""
                        for row in rows:
                            cod = str(row[idx_cod]).strip() if idx_cod >= 0 else ""
                            mapped = [row[columns.index(col)] for col in common_columns]
                            ph = ",".join(["?"] * len(common_columns))
                            try:
                                if idx_cod >= 0 and cod_col:
                                    set_cols = [col for col in common_columns if col != cod_col]
                                    if set_cols:
                                        set_clause = ", ".join([f"{col}=?" for col in set_cols])
                                        params = [row[columns.index(col)] for col in set_cols] + [cod]
                                        cursor_export.execute(
                                            f"UPDATE obras SET {set_clause} WHERE cod=?",
                                            params,
                                        )
                                        if cursor_export.rowcount == 0:
                                            cursor_export.execute(
                                                f"INSERT INTO obras ({', '.join(common_columns)}) VALUES ({ph})",
                                                mapped,
                                            )
                                    else:
                                        cursor_export.execute(
                                            f"INSERT INTO obras ({', '.join(common_columns)}) VALUES ({ph})",
                                            mapped,
                                        )
                                else:
                                    cursor_export.execute(
                                        f"INSERT INTO obras ({', '.join(common_columns)}) VALUES ({ph})",
                                        mapped,
                                    )
                                processadas_ok += 1
                            except Exception as exc:
                                falhas_total += 1
                                if len(falhas) < 5:
                                    falhas.append(f"COD={cod or 'N/D'}: {exc}")
                        resumo = _format_processing_summary(
                            "Exportar para Banco",
                            processadas_ok,
                            ignoradas_aprovadas,
                            ignoradas_integridade,
                            falhas_total,
                            falhas,
                        )
                        info_msg = f"{resumo}\n\nDestino: {file_path}"
        except DatabaseBusyError as e:
            critical_msg = str(e)
        except Exception as e:
            critical_msg = f"Erro ao exportar dados para o banco: {str(e)}"
        return warning_schema_msg, info_msg, critical_msg

    # exportar_para_banco: movido para ui.main_window mixin (Etapa C Tier 3)

    # abrir_dialogo_plano, aplicar_atualizacao_plano, cancelar_atualizacao_plano_obras:
    # movidos para ui.main_window.plano_obras_mixin (Etapa C Tier 1)

    # get_alimentadores: movido para ui.main_window mixin (Etapa C Tier 3)

    # alimentadores_nos_arquivos: movido para ui.main_window mixin (Etapa C Tier 3)

    # update_subestacoes_list: movido para ui.main_window mixin (Etapa C Tier 3)

    # populate_combo_nome_projeto: movido para ui.main_window mixin (Etapa C Tier 3)

    # _preencher_nome_projeto_auto: movido para ui.main_window mixin (Etapa C Tier 3)

    # buscar_projetos: movido para ui.main_window mixin (Etapa C Tier 3)

    # carregar_dados_projeto: movido para ui.main_window mixin (Etapa C Tier 3)

    # verificar_pi_padrao: movido para ui.main_window mixin (Etapa C Tier 4)

    # selecionar_pis: movido para ui.main_window mixin (Etapa C Tier 4)

    # calcular_numero_item: movido para ui.main_window mixin (Etapa C Tier 4)

    # _on_visualizar_double_click: movido para ui.main_window mixin (Etapa C Tier 4)

    # _open_editar_obra_by_cod: movido para ui.main_window mixin (Etapa C Tier 4)

    # abrir_editar_obra: movido para ui.main_window mixin (Etapa C Tier 4)

    @run_write_in_qthread_if_ui_thread
    def _save_backup_db_file(self, db_backup_path: str) -> None:
        owner = _SQLiteWriteOwner(str(db_backup_path or "").strip())
        with write_transaction_safe(owner) as cursor_backup:
            cols = self.db_manager.get_column_names()
            col_defs = ", ".join([f"{c} TEXT" for c in cols])
            cursor_backup.execute(f"CREATE TABLE IF NOT EXISTS obras ({col_defs})")

            rows = self.db_manager.fetch_all(self.db_manager.allowed_pacotes)
            ph = ",".join(["?"] * len(cols))
            for row in rows:
                cursor_backup.execute(f"INSERT INTO obras VALUES ({ph})", row)

    # salvar_banco_dados: movido para ui.main_window mixin (Etapa C Tier 3)

    # ----- Métodos de Ajuda -----
    # show_help_main e show_help_cadastro: movidos para ui.main_window.ajuda_mixin (Etapa C Tier 1)

    # show_help_ganhos: movido para ui.main_window mixin (Etapa C Tier 4)

    # ----- Atualização sequencial de projeto -----
    # iniciar_atualizacao_projeto: movido para ui.main_window mixin (Etapa C Tier 4)

    # load_projeto_obra: movido para ui.main_window mixin (Etapa C Tier 4)

    # update_navegacao_projeto: movido para ui.main_window mixin (Etapa C Tier 4)

    # prev_projeto_obra: movido para ui.main_window mixin (Etapa C Tier 4)

    # next_projeto_obra: movido para ui.main_window mixin (Etapa C Tier 4)

    # finalizar_atualizacao_projeto: movido para ui.main_window mixin (Etapa C Tier 4)

    # cancelar_atualizacao_projeto: movido para ui.main_window mixin (Etapa C Tier 4)

    # enable_cadastro_fields: movido para ui.main_window mixin (Etapa C Tier 4)

    # preencher_campos_obra: movido para ui.main_window mixin (Etapa C Tier 4)

# Re-exports: dialogs (Ganhos/CodPep/Project/PlanoObras) extraidos para runtime/dialogs.py.
from runtime.dialogs import (  # noqa: E402,F401
    CodPepBatchDialog,
    GanhosMassaDialog,
    PlanoObrasDialog,
    ProjectSelectionDialog,
)

# Re-exports: QSS theme helpers + CLI helpers + paleta extraidos para runtime/qss.py + runtime/cli.py.
from runtime.qss import (  # noqa: E402,F401
    _EMBEDDED_MODERN_QSS,
    _resolve_qss_path,
    apply_windows_selection_color,
    load_qss_from_file,
)
from runtime.cli import (  # noqa: E402,F401
    reset_config_to_defaults,
    run_long_process_example,
    show_config_info,
)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    log_dir = APP_DIRS.get("logs") or os.path.join(os.getcwd(), "logs")
    setup_logging(log_dir)

    # Metadados e suporte a High-DPI para uma UI mais nítida em monitores modernos.
    QtWidgets.QApplication.setApplicationName("COPLAN")
    QtWidgets.QApplication.setApplicationDisplayName(
        "COPLAN — Cadastro e Visualização de Obras"
    )
    QtWidgets.QApplication.setOrganizationName("COPLAN")
    try:
        QtCore.QCoreApplication.setAttribute(
            QtCore.Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True
        )
        QtCore.QCoreApplication.setAttribute(
            QtCore.Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True
        )
    except Exception:
        pass

    app = QtWidgets.QApplication(sys.argv)
    # Usa o estilo base "Fusion" para garantir aparência consistente em todas as plataformas.
    try:
        app.setStyle("Fusion")
    except Exception:
        pass

    apply_windows_selection_color(app)

    # Carrega o tema visual moderno a partir de custom_style.qss.
    # Caso o arquivo não esteja disponível (ex.: build PyInstaller sem extras),
    # aplica um fallback embutido mantendo o visual moderno.
    qss_content = load_qss_from_file("custom_style.qss")
    if not qss_content:
        qss_content = _EMBEDDED_MODERN_QSS
    app.setStyleSheet(qss_content)

    # Exibe as configurações atuais no console para debug
    show_config_info()

    # Cria e exibe a janela principal
    window = MainWindow()
    window.show()

    # Exemplo de acionamento do worker de processo longo
    # run_long_process_example(window)

    sys.exit(app.exec())



# Re-exports: logging avancado extraido para runtime/cli.py.
from runtime.cli import (  # noqa: E402,F401
    _UserContextFilter,
    _install_exception_hooks,
    configure_logging,
)


# Re-exports: setup_application + main_cli extraidos para runtime/cli.py.
from runtime.cli import main_cli, setup_application  # noqa: E402,F401

if __name__ == "__main__":
    log_dir = APP_DIRS.get("logs") or os.path.join(os.getcwd(), "logs")
    setup_logging(log_dir)

    # Se argumentos foram passados, executa a CLI; caso contrário, abre a GUI.
    if len(sys.argv) > 1:
        main_cli()
        sys.exit(0)
    else:
        app = QtWidgets.QApplication(sys.argv)
        apply_windows_selection_color(app)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())

# Re-exports: CSV report helpers extraidos para runtime/file_io.py.
from runtime.file_io import carregar_relatorio_csv, exportar_relatorio_csv  # noqa: E402,F401

# Re-export: CsvReportDialog extraido para runtime/dialogs.py.
from runtime.dialogs import CsvReportDialog  # noqa: E402,F401
