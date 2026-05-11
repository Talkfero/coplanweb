"""Widgets Qt customizados + InfoAlim TypedDict.

Extraidos de codigo5_coplan.py:
- CopyListWidget: QListWidget que copia textos selecionados
- VisibleRowTableWidget: QTableWidget que ignora linhas ocultas
- TemplatePlainTextEdit: editor com autocomplete de colunas {coluna}
- InfoAlim: TypedDict de metadata por alimentador
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, TypedDict, cast

from PySide6 import QtCore, QtGui, QtWidgets


class CopyListWidget(QtWidgets.QListWidget):
    """QListWidget que permite copiar textos selecionados."""

    def keyPressEvent(self, event):
        if event.matches(QtGui.QKeySequence.StandardKey.Copy):
            itens = self.selectedItems()
            if itens:
                texto = "\n".join(i.text() for i in itens)
                QtWidgets.QApplication.clipboard().setText(texto)
            event.accept()
        else:
            super().keyPressEvent(event)


class VisibleRowTableWidget(QtWidgets.QTableWidget):
    """QTableWidget que ignora linhas ocultas ao selecionar tudo."""

    def keyPressEvent(self, event):
        if event.matches(QtGui.QKeySequence.StandardKey.SelectAll):
            self.clearSelection()
            for row in range(self.rowCount()):
                if not self.isRowHidden(row):
                    self.selectRow(row)
            event.accept()
        else:
            super().keyPressEvent(event)

    def selectedVisibleRows(self):
        """Retorna os índices das linhas visíveis atualmente selecionadas."""
        return [
            i for i in self.selectionModel().selectedRows()
            if not self.isRowHidden(i.row())
        ]


class TemplatePlainTextEdit(QtWidgets.QPlainTextEdit):
    """Editor com autocomplete de colunas para templates {coluna}."""

    def __init__(self, columns: list[str], parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._columns = columns
        self._model = QtCore.QStringListModel(self._columns, self)
        self._completer = QtWidgets.QCompleter(self._model, self)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setWidget(self)
        self._completer.activated.connect(self._insert_completion)
        self.installEventFilter(self)

    def set_columns(self, columns: list[str]) -> None:
        self._columns = columns
        self._model.setStringList(self._columns)

    def insert_placeholder(self, column_name: str) -> None:
        self._insert_completion(column_name)

    def _placeholder_context(self) -> tuple[int, str]:
        cursor = self.textCursor()
        pos = cursor.position()
        text = self.toPlainText()
        last_open = text.rfind("{", 0, pos)
        last_close = text.rfind("}", 0, pos)
        if last_open == -1 or last_open < last_close:
            return -1, ""
        prefix = text[last_open + 1 : pos]
        return last_open, prefix

    def _is_valid_prefix(self, prefix: str) -> bool:
        return bool(re.match(r"^[A-Za-z0-9_]*$", prefix))

    def _insert_completion(self, completion: str) -> None:
        cursor = self.textCursor()
        pos = cursor.position()
        start, _ = self._placeholder_context()
        if start >= 0:
            cursor.setPosition(start + 1)
            cursor.setPosition(pos, QtGui.QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(f"{completion}}}")
        else:
            cursor.insertText(f"{{{completion}}}")
        self.setTextCursor(cursor)

    def _update_completer(self, force_open: bool = False) -> None:
        start, prefix = self._placeholder_context()
        if start < 0 or not self._is_valid_prefix(prefix):
            self._completer.popup().hide()
            return
        if not prefix and not force_open and not self._completer.popup().isVisible():
            return
        self._completer.setCompletionPrefix(prefix)
        self._completer.complete(self.cursorRect())

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self and event.type() == QtCore.QEvent.Type.KeyPress:
            key_event = cast(QtGui.QKeyEvent, event)
            key = key_event.key()
            text = key_event.text()
            popup_visible = self._completer.popup().isVisible()

            if popup_visible and key in (
                QtCore.Qt.Key.Key_Return,
                QtCore.Qt.Key.Key_Enter,
                QtCore.Qt.Key.Key_Tab,
                QtCore.Qt.Key.Key_Backtab,
            ):
                completion = self._completer.currentCompletion()
                if completion:
                    self._insert_completion(completion)
                self._completer.popup().hide()
                return True

            if popup_visible and key == QtCore.Qt.Key.Key_Escape:
                self._completer.popup().hide()
                return True

            if text == "{":
                QtCore.QTimer.singleShot(0, lambda: self._update_completer(True))
                return False

            if text == "}":
                QtCore.QTimer.singleShot(0, self._completer.popup().hide)
                return False

            if text and (text.isalnum() or text == "_"):
                QtCore.QTimer.singleShot(0, self._update_completer)
                return False

            if key in (QtCore.Qt.Key.Key_Backspace, QtCore.Qt.Key.Key_Delete):
                QtCore.QTimer.singleShot(0, self._completer.popup().hide)
                return False

        return super().eventFilter(obj, event)


class InfoAlim(TypedDict):
    first_codigo: Optional[int]
    first_antes: Optional[Dict[str, Any]]
    last_codigo: Optional[int]
    last_depois: Optional[Dict[str, Any]]
