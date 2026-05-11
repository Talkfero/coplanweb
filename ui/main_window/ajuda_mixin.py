"""Mixin de Ajuda -- 2 metodos, ~14 linhas.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 1).
"""
from __future__ import annotations

from PySide6 import QtWidgets


class AjudaMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def show_help_main(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Ajuda",
            "Use a barra de ferramentas para conectar ou criar um banco, "
            "importar e exportar dados e carregar a planilha de apoio."
        )

    def show_help_cadastro(self) -> None:
        QtWidgets.QMessageBox.information(
            self,
            "Ajuda - Cadastro de Obras",
            "Preencha os dados da obra e clique em 'Salvar Obra'.\n"
            "Use 'Calcular Valor da Obra' para estimar custos."
        )
