"""Mixin Visualizar Colunas (config de colunas visiveis/ordem/widths) -- 11 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 2).

Atributos esperados em ``self``:
- ``self.db_manager``, ``self.table_obras``,
  ``self._visualizar_column_names``, ``self._visualizar_col_widths``,
  ``self._visualizar_col_widths_flush_token``,
  ``self._restoring_visualizar_layout``
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QTimer


class VisualizarColunasMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def _get_visualizar_columns_candidates(self) -> list[str]:
        from ui.main_window import legacy_module
        ORDERED_COLUMNS = legacy_module().ORDERED_COLUMNS

        cols_db: list[str] = []
        dbm = getattr(self, "db_manager", None)
        if dbm is not None and getattr(dbm, "conn", None):
            try:
                cols_db = dbm.get_column_names()
            except Exception:
                cols_db = []
        if not cols_db:
            return list(ORDERED_COLUMNS)
        ordered = [c for c in ORDERED_COLUMNS if c in cols_db]
        ordered.extend([c for c in cols_db if c not in ordered])
        return ordered

    def _load_visualizar_columns_config(self) -> tuple[list[str], bool, list[str], dict[str, int]]:
        from ui.main_window import legacy_module
        ConfigManager = legacy_module().ConfigManager

        config = ConfigManager.load_config()
        ui_state = config.get("ui_state", {})
        visualizar = ui_state.get("visualizar", {})
        visible = visualizar.get("visible_columns", None)
        visible_defined = "visible_columns" in visualizar
        if not visible_defined:
            legacy_visible = visualizar.get("columns_visible", None)
            if isinstance(legacy_visible, dict):
                visible = [col for col, is_visible in legacy_visible.items() if is_visible]
                visible_defined = True
        if not isinstance(visible, list):
            visible = []
        order = visualizar.get("columns_order", [])
        if not isinstance(order, list):
            order = []
        widths = visualizar.get("column_widths", {})
        if not isinstance(widths, dict):
            widths = {}
        return visible, visible_defined, order, widths

    def _save_visualizar_columns_config(self, visible: list[str], order: list[str]) -> None:
        from ui.main_window import legacy_module
        ConfigManager = legacy_module().ConfigManager
        ConfigManager.save_config(
            {"ui_state": {"visualizar": {"visible_columns": visible, "columns_order": order}}}
        )

    def _clear_visualizar_columns_config(self) -> None:
        from ui.main_window import legacy_module
        ConfigManager = legacy_module().ConfigManager

        config = ConfigManager.load_config()
        ui_state = config.setdefault("ui_state", {})
        visualizar = ui_state.get("visualizar", {})
        if not isinstance(visualizar, dict):
            visualizar = {}
        for key in ("visible_columns", "columns_visible", "columns_order", "column_widths"):
            visualizar.pop(key, None)
        ui_state["visualizar"] = visualizar
        config["ui_state"] = ui_state
        ConfigManager.save_config(config, overwrite=True)

    # === VISUALIZAR: COLUMN WIDTH PERSIST BEGIN ===
    def _get_visualizar_column_names(self) -> list[str]:
        cols_db = getattr(self, "_visualizar_column_names", None)
        if not cols_db:
            try:
                cols_db = self.db_manager.get_column_names()
            except Exception:
                cols_db = []
        return list(cols_db or [])

    def _apply_visualizar_column_widths(
        self,
        tabela: QtWidgets.QTableWidget,
        cols_db: list[str],
        widths_cfg: dict[str, int],
        visible_set: set[str],
    ) -> None:
        sanitized_widths: dict[str, int] = {}
        for col, width in widths_cfg.items():
            if col not in cols_db:
                continue
            try:
                sanitized_widths[col] = int(width)
            except (TypeError, ValueError):
                continue
        self._visualizar_col_widths = dict(sanitized_widths)
        for col, width in sanitized_widths.items():
            if col in visible_set:
                tabela.setColumnWidth(cols_db.index(col), width)

    def _on_visualizar_section_resized(self, logicalIndex: int, oldSize: int, newSize: int) -> None:
        tabela = getattr(self, "table_obras", None)
        if (
            self._restoring_visualizar_layout
            or tabela is None
            or tabela.columnCount() == 0
        ):
            return
        cols_db = self._get_visualizar_column_names()
        if not cols_db or logicalIndex < 0 or logicalIndex >= len(cols_db):
            return
        if tabela.isColumnHidden(logicalIndex):
            return
        col_name = cols_db[logicalIndex]
        self._visualizar_col_widths[col_name] = int(newSize)
        self._visualizar_col_widths_flush_token += 1
        token = self._visualizar_col_widths_flush_token
        QTimer.singleShot(300, lambda: self._flush_visualizar_column_widths(token))

    def _flush_visualizar_column_widths(self, token: int | None = None) -> None:
        from ui.main_window import legacy_module
        ConfigManager = legacy_module().ConfigManager

        if token is not None and token != self._visualizar_col_widths_flush_token:
            return
        if self._restoring_visualizar_layout:
            return
        cols_db = self._get_visualizar_column_names()
        if not cols_db:
            return
        widths = {
            col: int(width)
            for col, width in self._visualizar_col_widths.items()
            if col in cols_db
        }
        self._visualizar_col_widths = dict(widths)
        ConfigManager.save_config({"ui_state": {"visualizar": {"column_widths": widths}}})
    # === VISUALIZAR: COLUMN WIDTH PERSIST END ===

    def apply_visualizar_columns_config(self) -> None:
        from ui.main_window import legacy_module
        ORDERED_COLUMNS = legacy_module().ORDERED_COLUMNS

        tabela = getattr(self, "table_obras", None)
        if tabela is None or tabela.columnCount() == 0:
            return

        cols_db = self._get_visualizar_column_names()
        if not cols_db:
            return

        visible_cfg, visible_defined, order_cfg, widths_cfg = self._load_visualizar_columns_config()
        canonical = [c for c in ORDERED_COLUMNS if c in cols_db]
        canonical.extend([c for c in cols_db if c not in canonical])
        if order_cfg:
            order_final = [c for c in order_cfg if c in cols_db]
            order_final.extend([c for c in canonical if c not in order_final])
        else:
            order_final = canonical

        header = tabela.horizontalHeader()
        for visual_idx, col in enumerate(order_final):
            logical_idx = cols_db.index(col)
            current_visual = header.visualIndex(logical_idx)
            if current_visual != visual_idx:
                header.moveSection(current_visual, visual_idx)

        visible_set = set(visible_cfg) if visible_defined else set(cols_db)
        for col in cols_db:
            logical_idx = cols_db.index(col)
            visible = col in visible_set
            tabela.setColumnHidden(logical_idx, not visible)

        self._apply_visualizar_column_widths(tabela, cols_db, widths_cfg, visible_set)

    def show_visualizar_columns_dialog(self) -> None:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Configurar Colunas (Visualizar)")
        dialog.setMinimumWidth(420)
        layout = QtWidgets.QVBoxLayout(dialog)

        info = QtWidgets.QLabel("Marque as colunas visíveis e arraste para definir a ordem.")
        info.setWordWrap(True)
        layout.addWidget(info)

        list_widget = QtWidgets.QListWidget(dialog)
        list_widget.setDragDropMode(
            QtWidgets.QAbstractItemView.DragDropMode.InternalMove
        )
        list_widget.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        list_widget.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        layout.addWidget(list_widget)

        visible_cfg, visible_defined, order_cfg, _widths_cfg = self._load_visualizar_columns_config()
        candidates = self._get_visualizar_columns_candidates()
        if order_cfg:
            ordered = [c for c in order_cfg if c in candidates]
            ordered.extend([c for c in candidates if c not in ordered])
        else:
            ordered = candidates

        for col in ordered:
            item = QtWidgets.QListWidgetItem(col)
            item.setFlags(
                item.flags()
                | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                | QtCore.Qt.ItemFlag.ItemIsDragEnabled
            )
            is_visible = col in visible_cfg if visible_defined else True
            item.setCheckState(
                QtCore.Qt.CheckState.Checked
                if is_visible
                else QtCore.Qt.CheckState.Unchecked
            )
            list_widget.addItem(item)

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch(1)
        btn_apply = QtWidgets.QPushButton("Aplicar")
        btn_restore = QtWidgets.QPushButton("Restaurar padrão")
        btn_cancel = QtWidgets.QPushButton("Cancelar")
        btn_layout.addWidget(btn_apply)
        btn_layout.addWidget(btn_restore)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        def _collect_state() -> tuple[list[str], list[str]]:
            visible = []
            order = []
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                name = item.text()
                order.append(name)
                if item.checkState() == QtCore.Qt.CheckState.Checked:
                    visible.append(name)
            return visible, order

        def _apply():
            visible, order = _collect_state()
            self._save_visualizar_columns_config(visible, order)
            self.apply_visualizar_columns_config()
            dialog.accept()

        def _restore():
            self._restoring_visualizar_layout = True
            try:
                self._clear_visualizar_columns_config()
                self._visualizar_col_widths = {}
                list_widget.clear()
                for col in candidates:
                    item = QtWidgets.QListWidgetItem(col)
                    item.setFlags(
                        item.flags()
                        | QtCore.Qt.ItemFlag.ItemIsUserCheckable
                        | QtCore.Qt.ItemFlag.ItemIsDragEnabled
                    )
                    item.setCheckState(QtCore.Qt.CheckState.Checked)
                    list_widget.addItem(item)
                self.apply_visualizar_columns_config()
            finally:
                self._restoring_visualizar_layout = False

        btn_apply.clicked.connect(_apply)
        btn_restore.clicked.connect(_restore)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec()

    # === VISUALIZAR: READONLY + COPY BEGIN ===
    def _copy_visualizar_selection_to_clipboard(self, table: QtWidgets.QTableWidget) -> None:
        indices = table.selectedIndexes()
        if not indices:
            return
        indices_sorted = sorted(indices, key=lambda idx: (idx.row(), idx.column()))
        rows: dict[int, list[QtCore.QModelIndex]] = {}
        for index in indices_sorted:
            rows.setdefault(index.row(), []).append(index)
        lines = []
        for row in sorted(rows):
            cols = sorted(rows[row], key=lambda idx: idx.column())
            values = [str(idx.data() or "") for idx in cols]
            lines.append("\t".join(values))
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))
