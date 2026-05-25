"""Dialogs Qt + helpers de UI.

Extraidos de codigo5_coplan.py. Inclui:
- show_user_error / open_file / _as_tool_button (helpers basicos)
- GanhosMassaDialog: opcoes de ganhos em massa
- CodPepBatchDialog: dialog completo de geracao de COD_PEP
- ProjectSelectionDialog: escolha de projeto
- PlanoObrasDialog: atualizacao de plano de obras
- CsvReportDialog: import/export de CSV
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable
from weakref import WeakKeyDictionary

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QSizePolicy, QStyle, QToolButton, QWidget

from runtime.config import ConfigManager
from runtime.database import (
    DatabaseBusyError,
    DatabaseManager,
    build_database_busy_message,
    get_empresa_sigla_from_config,
    get_lock_info_path,
    is_database_busy_exception,
    read_lock_info,
)
from runtime.text_utils import parse_cod_pep, ts_log, ts_now


# ---------------------------------------------------------------------------
# Abrir arquivo no app padrao do sistema
# ---------------------------------------------------------------------------
def open_file(path: str):
    """Tenta abrir o arquivo indicado usando o aplicativo padrão."""
    try:
        url = QtCore.QUrl.fromLocalFile(os.path.abspath(path))
        QtGui.QDesktopServices.openUrl(url)
    except Exception as e:  # pragma: no cover
        logging.error(f"Erro ao abrir arquivo {path}: {e}")


# ---------------------------------------------------------------------------
# Erro padronizado (com tratamento especial para DatabaseBusyError)
# ---------------------------------------------------------------------------
def show_user_error(
    title: str,
    details: Any,
    hint: str,
    parent: QtWidgets.QWidget | None = None,
) -> None:
    """Exibe erro padronizado com detalhes e dica de correção."""
    if is_database_busy_exception(details):
        db_path = ""
        if isinstance(details, DatabaseBusyError):
            db_path = str(details.db_path or "").strip()
        try:
            if not db_path:
                db_manager = getattr(parent, "db_manager", None)
                db_path = str(getattr(db_manager, "db_path", "") or "").strip()
        except Exception:
            db_path = ""
        lock_info = read_lock_info(get_lock_info_path(db_path))
        QtWidgets.QMessageBox.warning(
            parent,
            "Banco em utilização",
            build_database_busy_message(lock_info),
        )
        return

    details_s = str(details or "")
    msg_box = QtWidgets.QMessageBox(parent)
    msg_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
    msg_box.setWindowTitle(title)
    msg_box.setText(title)
    if hint:
        msg_box.setInformativeText(hint)
    if details_s:
        msg_box.setDetailedText(details_s)
    msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
    msg_box.exec()


# ---------------------------------------------------------------------------
# QToolButton helper (converte botao em ToolButton com icone padrao)
# ---------------------------------------------------------------------------
_TOOLBUTTON_SLOTS: "WeakKeyDictionary[QToolButton, Callable[..., None]]" = WeakKeyDictionary()


def _as_tool_button(
    btn: QToolButton | None,
    parent: QWidget,
    text: str,
    std_icon: QStyle.StandardPixmap,
    clicked_slot: Callable[..., None] | None,
    *,
    show_text: bool = False,
):
    """
    Converte ou cria um QToolButton com ícone padrão e tooltip, mantendo o slot existente.
    """
    style = parent.style()
    icon = style.standardIcon(std_icon)

    reuse_existing = isinstance(btn, QToolButton)
    tbtn = btn if reuse_existing else QToolButton(parent)
    tbtn.setText(text)
    tbtn.setIcon(icon)
    tbtn.setIconSize(QSize(24, 24))
    tbtn.setToolTip(text)
    tbtn.setStatusTip("")
    tbtn.setAutoRaise(not show_text)
    tbtn.setToolButtonStyle(
        Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        if show_text
        else Qt.ToolButtonStyle.ToolButtonIconOnly
    )
    tbtn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    previous_slot = _TOOLBUTTON_SLOTS.get(tbtn)
    if reuse_existing and previous_slot is not None:
        try:
            tbtn.clicked.disconnect(previous_slot)
        except (TypeError, RuntimeError):
            pass

    if clicked_slot is not None:
        tbtn.clicked.connect(clicked_slot)
        _TOOLBUTTON_SLOTS[tbtn] = clicked_slot
    elif reuse_existing:
        _TOOLBUTTON_SLOTS.pop(tbtn, None)

    return tbtn


# ---------------------------------------------------------------------------
# GanhosMassaDialog -- opcoes de ganhos em massa
# ---------------------------------------------------------------------------
class GanhosMassaDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Opções de Ganhos em Massa")
        layout = QtWidgets.QVBoxLayout(self)
        help_btn = QtWidgets.QPushButton("?")
        help_btn.setFixedWidth(20)
        help_btn.clicked.connect(self.show_help)
        layout.addWidget(help_btn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self.check_antes = QtWidgets.QCheckBox("Inserir Ganhos Antes")
        self.check_depois = QtWidgets.QCheckBox("Inserir Ganhos Depois")
        self.check_atuais = QtWidgets.QCheckBox("Preencher Parâmetros Atuais")

        layout.addWidget(self.check_antes)
        layout.addWidget(self.check_depois)
        layout.addWidget(self.check_atuais)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def show_help(self):
        QtWidgets.QMessageBox.information(
            self,
            "Ajuda",
            "Marque as opções desejadas para inserir ganhos em massa utilizando os arquivos da pasta selecionada."
        )


# ---------------------------------------------------------------------------
# CodPepBatchDialog -- geracao de COD_PEP em lote
# ---------------------------------------------------------------------------
class CodPepBatchDialog(QtWidgets.QDialog):
    SCOPE_SELECTED = "selected"
    SCOPE_VISIBLE = "visible"
    SCOPE_PACKAGES = "packages"

    def __init__(
        self,
        db_manager: DatabaseManager,
        parent=None,
        *,
        has_selection: bool = False,
    ):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Gerar COD_PEP")
        self.resize(560, 560)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)

        grp_escopo = QtWidgets.QGroupBox("Escopo (quais obras processar)")
        escopo_layout = QtWidgets.QVBoxLayout(grp_escopo)
        escopo_layout.setSpacing(4)

        self.radio_selected = QtWidgets.QRadioButton("Obras selecionadas na tabela")
        self.radio_visible = QtWidgets.QRadioButton("Todas as obras visíveis (filtro atual)")
        self.radio_packages = QtWidgets.QRadioButton("Obras dos pacotes marcados abaixo")
        self.radio_selected.setEnabled(has_selection)

        escopo_layout.addWidget(self.radio_selected)
        escopo_layout.addWidget(self.radio_visible)
        escopo_layout.addWidget(self.radio_packages)

        self.list_packages = QtWidgets.QListWidget()
        self.list_packages.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.MultiSelection
        )
        self.list_packages.setMinimumHeight(120)
        escopo_layout.addWidget(self.list_packages)

        layout.addWidget(grp_escopo)

        grp_modo = QtWidgets.QGroupBox("Modo de geração")
        modo_layout = QtWidgets.QVBoxLayout(grp_modo)
        modo_layout.setSpacing(4)

        self.radio_modo_vazios = QtWidgets.QRadioButton(
            "Preencher apenas obras sem COD_PEP (recomendado)"
        )
        self.radio_modo_reiniciar = QtWidgets.QRadioButton(
            "Reiniciar COD_PEP das obras no escopo (apaga e regenera)"
        )
        self.radio_modo_vazios.setChecked(True)

        modo_layout.addWidget(self.radio_modo_vazios)
        modo_layout.addWidget(self.radio_modo_reiniciar)

        self.lbl_modo_warn = QtWidgets.QLabel(
            "⚠ A opção 'Reiniciar' apaga os COD_PEPs atuais das obras no escopo antes "
            "de regerar. A numeração SSSS continua considerando a base inteira."
        )
        self.lbl_modo_warn.setWordWrap(True)
        self.lbl_modo_warn.setStyleSheet("color: #b35c00;")
        self.lbl_modo_warn.setVisible(False)
        modo_layout.addWidget(self.lbl_modo_warn)

        layout.addWidget(grp_modo)

        grp_filtros = QtWidgets.QGroupBox("Filtros adicionais")
        filtros_layout = QtWidgets.QVBoxLayout(grp_filtros)
        filtros_layout.setSpacing(4)

        self.chk_incluir_aprovadas = QtWidgets.QCheckBox("Incluir obras aprovadas")
        self.chk_incluir_aprovadas.setChecked(False)
        filtros_layout.addWidget(self.chk_incluir_aprovadas)

        layout.addWidget(grp_filtros)

        self.lbl_info = QtWidgets.QLabel()
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(
            "color: #444; background: #f5f5f5; border: 1px solid #ddd; "
            "border-radius: 4px; padding: 6px;"
        )
        layout.addWidget(self.lbl_info)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = btn_box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText("Gerar COD_PEP")
        cancel_btn = btn_box.button(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        if cancel_btn is not None:
            cancel_btn.setText("Cancelar")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.radio_selected.toggled.connect(self._sync_packages_state)
        self.radio_visible.toggled.connect(self._sync_packages_state)
        self.radio_packages.toggled.connect(self._sync_packages_state)
        self.radio_modo_vazios.toggled.connect(self._sync_modo_state)
        self.radio_modo_reiniciar.toggled.connect(self._sync_modo_state)

        pacotes = self._load_packages()
        if pacotes:
            self.list_packages.addItems(pacotes)
        else:
            self.radio_packages.setEnabled(False)

        if has_selection:
            self.radio_selected.setChecked(True)
        else:
            self.radio_visible.setChecked(True)
        if not self.radio_selected.isChecked() and not self.radio_visible.isChecked():
            self.radio_packages.setChecked(True)

        self._sync_packages_state()
        self._sync_modo_state()
        self._refresh_info_label()

    def _load_packages(self) -> list[str]:
        pacotes: list[str] = []
        try:
            t_dist = ts_now()
            tipo_pacote_values = self.db_manager.get_distinct_values("tipo_pacote")
            ts_log('get_distinct_values("tipo_pacote")', t_dist)
            pacotes = [
                str(value).strip()
                for value in tipo_pacote_values
                if str(value).strip()
            ]
            if not pacotes:
                pacotes = [
                    str(value).strip()
                    for value in self.db_manager.get_distinct_values("pacote")
                    if str(value).strip()
                ]
        except Exception:
            pacotes = []

        if not pacotes:
            try:
                with self.db_manager._with_connection():
                    cursor = self.db_manager._get_cursor()
                    if cursor:
                        pacote_col = self.db_manager._resolve_pacote_column()
                        if pacote_col:
                            col_sql = self.db_manager._escape_identifier(pacote_col)
                            cursor.execute(
                                f"SELECT DISTINCT {col_sql} FROM obras "
                                f"WHERE {col_sql} IS NOT NULL AND TRIM({col_sql})<>'' "
                                f"ORDER BY {col_sql}"
                            )
                            pacotes = [
                                str(row[0]).strip()
                                for row in cursor.fetchall()
                                if str((row[0] if row else "") or "").strip()
                            ]
            except Exception:
                pacotes = []

        return sorted(dict.fromkeys(pacotes))

    def _sync_packages_state(self) -> None:
        enable = self.radio_packages.isChecked() and self.radio_packages.isEnabled()
        self.list_packages.setEnabled(enable)

    def _sync_modo_state(self) -> None:
        self.lbl_modo_warn.setVisible(self.radio_modo_reiniciar.isChecked())

    def _refresh_info_label(self) -> None:
        empresa_txt = "—"
        next_seq_txt = "—"
        total_txt = "—"
        try:
            config = getattr(self.db_manager, "config", None)
            if not isinstance(config, dict):
                config = ConfigManager.load_config()
            empresa_sigla = get_empresa_sigla_from_config(config)
            empresa_txt = empresa_sigla
            max_seq = -1
            total = 0
            with self.db_manager._with_connection():
                cursor = self.db_manager._get_cursor()
                if cursor:
                    cursor.execute(
                        "SELECT cod_pep FROM obras "
                        "WHERE empresa=? "
                        "AND cod_pep IS NOT NULL AND TRIM(cod_pep)<>''",
                        (empresa_sigla,),
                    )
                    for (cod_existente,) in cursor.fetchall():
                        total += 1
                        parsed = parse_cod_pep(cod_existente)
                        if parsed and parsed["empresa"] == empresa_sigla:
                            max_seq = max(max_seq, int(parsed["seq"]))
            next_seq_txt = f"{max_seq + 1:04d}"
            total_txt = str(total)
        except Exception:
            pass
        self.lbl_info.setText(
            "ℹ Regras de geração\n"
            "• SSSS (sequencial) é único por empresa em toda a base.\n"
            "• AAA (agrupamento) é único dentro do ano da obra.\n"
            "• Obras do mesmo projeto+pacote+ano reusam o mesmo AAA.\n"
            f"\nEmpresa configurada: {empresa_txt}  •  "
            f"COD_PEPs já gerados: {total_txt}  •  "
            f"Próximo SSSS: {next_seq_txt}"
        )

    def selected_scope(self) -> str:
        if self.radio_selected.isChecked():
            return self.SCOPE_SELECTED
        if self.radio_packages.isChecked():
            return self.SCOPE_PACKAGES
        return self.SCOPE_VISIBLE

    def selected_pacotes(self) -> list[str]:
        return [
            item.text().strip()
            for item in self.list_packages.selectedItems()
            if item.text().strip()
        ]

    def somente_vazios(self) -> bool:
        return self.radio_modo_vazios.isChecked()

    def incluir_aprovadas(self) -> bool:
        return self.chk_incluir_aprovadas.isChecked()

    def accept(self) -> None:
        if self.radio_packages.isChecked() and not self.selected_pacotes():
            QtWidgets.QMessageBox.warning(
                self,
                "Gerar COD_PEP",
                "Selecione ao menos um pacote para continuar.",
            )
            return
        if self.radio_modo_reiniciar.isChecked():
            resp = QtWidgets.QMessageBox.question(
                self,
                "Reiniciar COD_PEP",
                "Esta ação apaga os COD_PEPs atuais das obras no escopo "
                "e regenera a numeração.\n\n"
                "Os novos COD_PEPs respeitam o sequencial global já existente "
                "na base (não há risco de colisão com obras fora do escopo), "
                "mas os códigos atuais serão substituídos.\n\n"
                "Deseja continuar?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if resp != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        super().accept()


# ---------------------------------------------------------------------------
# ProjectSelectionDialog -- escolha de projeto
# ---------------------------------------------------------------------------
class ProjectSelectionDialog(QtWidgets.QDialog):
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.selected_project = None
        self.setWindowTitle("Escolher Projeto")
        self.resize(400, 300)
        layout = QtWidgets.QVBoxLayout(self)
        help_btn = QtWidgets.QPushButton("?")
        help_btn.setFixedWidth(20)
        help_btn.clicked.connect(self.show_help)
        layout.addWidget(help_btn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self.list_projects = QtWidgets.QListWidget()
        layout.addWidget(self.list_projects)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_select = QtWidgets.QPushButton("Selecionar")
        btn_select.clicked.connect(self.select_project)
        btn_layout.addWidget(btn_select)
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.populate_projects()
        self.list_projects.itemDoubleClicked.connect(self.select_project)

    def show_help(self):
        QtWidgets.QMessageBox.information(
            self,
            "Ajuda",
            "Escolha um projeto na lista e clique em 'Selecionar' ou dê duplo clique no item desejado."
        )

    def populate_projects(self):
        try:
            if not self.db_manager or not self.db_manager.db_path:
                QtWidgets.QMessageBox.critical(self, "Erro", "Banco de dados não conectado.")
                return
            projects = [
                str(row) for row in self.db_manager.get_distinct_values("nome_projeto") if row
            ]
            if projects:
                self.list_projects.addItems(projects)
            else:
                QtWidgets.QMessageBox.information(self, "Aviso", "Nenhum projeto encontrado.")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao buscar projetos: {str(e)}")

    def select_project(self):
        item = self.list_projects.currentItem()
        if item:
            self.selected_project = item.text()
            self.accept()


# ---------------------------------------------------------------------------
# PlanoObrasDialog -- atualizacao de plano de obras
# ---------------------------------------------------------------------------
class PlanoObrasDialog(QtWidgets.QDialog):
    def __init__(self, db_manager: DatabaseManager, parent=None, *, pacote=None,
                 data_inicial=None, data_final=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Atualizar Plano de Obras")
        layout = QtWidgets.QFormLayout(self)

        self.combo_pacote = QtWidgets.QComboBox()
        pacotes_iniciais = self.db_manager.allowed_pacotes
        if pacotes_iniciais:
            pacotes = list(dict.fromkeys([str(p).strip() for p in pacotes_iniciais if str(p).strip()]))
        else:
            t_dist = ts_now()
            pacotes = self.db_manager.get_distinct_values("tipo_pacote")
            ts_log('get_distinct_values("tipo_pacote")', t_dist)
        if pacotes:
            self.combo_pacote.addItems(pacotes)
            if pacote and pacote in pacotes:
                idx = self.combo_pacote.findText(pacote)
                if idx >= 0:
                    self.combo_pacote.setCurrentIndex(idx)
        layout.addRow("Pacote", self.combo_pacote)

        fmt = "dd/MM/yy HH:mm"
        self.dt_inicial = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.dt_inicial.setDisplayFormat(fmt)
        self.dt_inicial.setCalendarPopup(True)
        if data_inicial:
            try:
                self.dt_inicial.setDateTime(QtCore.QDateTime(data_inicial))
            except Exception:
                pass
        layout.addRow("Data/Hora Inicial", self.dt_inicial)

        self.dt_final = QtWidgets.QDateTimeEdit(QtCore.QDateTime.currentDateTime())
        self.dt_final.setDisplayFormat(fmt)
        self.dt_final.setCalendarPopup(True)
        if data_final:
            try:
                self.dt_final.setDateTime(QtCore.QDateTime(data_final))
            except Exception:
                pass
        layout.addRow("Data/Hora Final", self.dt_final)

        info_text = (
            "Data/Hora Inicial: obras com data de modificação até este momento "
            "não serão destacadas.\n"
            "Data/Hora Final: alterações entre a data inicial e este momento "
            "serão marcadas em cinza e aquelas posteriores ficarão em verde."
        )
        info_label = QtWidgets.QLabel(info_text)
        info_label.setWordWrap(True)
        layout.addRow(info_label)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addRow(btn_box)


# ---------------------------------------------------------------------------
# CsvReportDialog -- import/export de relatorio CSV
# ---------------------------------------------------------------------------
class CsvReportDialog(QtWidgets.QDialog):
    """Diálogo para exportar/importar relatórios CSV.

    Integra exportar_relatorio_csv / carregar_relatorio_csv (que ainda
    moram em codigo5_coplan) via lazy import.
    """
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Relatório CSV")
        layout = QtWidgets.QVBoxLayout(self)
        help_btn = QtWidgets.QPushButton("?")
        help_btn.setFixedWidth(20)
        help_btn.clicked.connect(self.show_help)
        layout.addWidget(help_btn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)

        self.label_info = QtWidgets.QLabel("Escolha exportar ou importar relatórios CSV:")
        layout.addWidget(self.label_info)

        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_export = QtWidgets.QPushButton("Exportar CSV")
        self.btn_export.clicked.connect(self.export_csv)
        btn_layout.addWidget(self.btn_export)

        self.btn_import = QtWidgets.QPushButton("Importar CSV")
        self.btn_import.clicked.connect(self.import_csv)
        btn_layout.addWidget(self.btn_import)

        layout.addLayout(btn_layout)

        btn_close = QtWidgets.QPushButton("Fechar")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close)

    def show_help(self):
        QtWidgets.QMessageBox.information(
            self,
            "Ajuda",
            "Use este diálogo para exportar os registros do banco para CSV ou importar um arquivo CSV existente."
        )

    def export_csv(self):
        # Lazy imports (require_tecnico_clean_or_confirm e exportar_relatorio_csv
        # ainda moram em codigo5_coplan).
        from runtime.file_io import exportar_relatorio_csv  # noqa: PLC0415
        from runtime.row_helpers import require_tecnico_clean_or_confirm  # noqa: PLC0415

        if not require_tecnico_clean_or_confirm(
            self, self.db_manager, "Exportar CSV"
        ):
            return
        parent = self.parent()
        require_export_sources = getattr(parent, "require_export_sources", None)
        if callable(require_export_sources):
            if not require_export_sources("Exportar relatório CSV"):
                return
        destino, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Salvar Relatório CSV", "", "Arquivos CSV (*.csv)")
        if destino:
            if exportar_relatorio_csv(self.db_manager, destino, self.db_manager.allowed_pacotes):
                QtWidgets.QMessageBox.information(self, "Sucesso", "Relatório CSV exportado com sucesso!")
            else:
                QtWidgets.QMessageBox.critical(self, "Erro", "Não foi possível exportar o relatório CSV.")

    def import_csv(self):
        from runtime.file_io import carregar_relatorio_csv  # noqa: PLC0415

        origem, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Importar CSV", "", "Arquivos CSV (*.csv)")
        if origem:
            ok, ignorados = carregar_relatorio_csv(self.db_manager, origem, parent=self)
            if ok:
                self.db_manager.update_columns()
                parent = self.parent()
                load_table = getattr(parent, "load_obras_into_table", None) if parent else None
                if callable(load_table):
                    load_table()
                msg = "Dados importados do CSV com sucesso!"
                if ignorados:
                    msg += f" {ignorados} registros ignorados."
                QtWidgets.QMessageBox.information(self, "Sucesso", msg)
            else:
                QtWidgets.QMessageBox.critical(self, "Erro", "Não foi possível importar os dados do CSV.")
