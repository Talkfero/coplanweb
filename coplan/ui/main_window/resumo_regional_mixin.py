"""Mixin Resumo Regional (Quadrante 4) -- 6 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 2).

Atributos esperados em ``self``:
- ``self.tabelaResumoRegionalSe``, ``self._resumo_regional_se_df``,
  ``self._visualizar_filtered_rows``, ``self.db_manager``

Metodos esperados em ``self``:
- ``self.col_index``, ``self.require_export_sources``
"""
from __future__ import annotations

import math
import re

import pandas as pd
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt


class ResumoRegionalMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def _obter_obras_visiveis_resumo_regional_se(self):
        if not self._visualizar_filtered_rows:
            return []

        indices = {
            "projeto_investimento": self.col_index("projeto_investimento"),
            "nome_regional": self.col_index("nome_regional"),
            "alimentador_principal": self.col_index("alimentador_principal"),
            "subestacao": self.col_index("subestacao"),
            "nivel_tensao_obra": self.col_index("nivel_tensao_obra"),
            "tensao_operacao": self.col_index("tensao_operacao"),
            "quantidade_material": self.col_index("quantidade_material"),
            "coordenada_fim": self.col_index("coordenada_fim"),
            "observacoes_gerais": self.col_index("observacoes_gerais"),
        }

        if any(idx < 0 for idx in indices.values()):
            return []

        obras = []
        for row_data, _atende in self._visualizar_filtered_rows:
            registro = {}
            for chave, idx in indices.items():
                registro[chave] = str(row_data[idx]).strip() if idx < len(row_data) else ""
            obras.append(registro)

        return obras

    def popular_resumo_regional_se(self, obras_visiveis):
        tabela = getattr(self, "tabelaResumoRegionalSe", None)
        if tabela is None:
            return

        tabela.clear()
        tabela.setRowCount(0)
        tabela.setColumnCount(8)
        headers = [
            "PI",
            "Regional",
            "Alimentador",
            "Subestação",
            "Tensão",
            "Quantidade",
            "Coordenadas para",
            "Observação",
        ]
        tabela.setHorizontalHeaderLabels(headers)
        self._resumo_regional_se_df = pd.DataFrame(columns=headers)

        if not obras_visiveis:
            return

        df = pd.DataFrame(obras_visiveis)
        if df.empty:
            return

        for coluna in [
            "projeto_investimento",
            "nome_regional",
            "alimentador_principal",
            "subestacao",
            "nivel_tensao_obra",
            "tensao_operacao",
            "coordenada_fim",
            "observacoes_gerais",
        ]:
            df[coluna] = df[coluna].fillna("").astype(str).str.strip()

        def parse_number(valor):
            if isinstance(valor, (int, float)):
                return float(valor)
            if valor is None:
                return 0.0
            texto = str(valor).strip()
            if not texto:
                return 0.0
            texto = re.sub(r"[^0-9,.-]", "", texto)
            if not texto or texto in {"-", ",", "."}:
                return 0.0
            if "," in texto and "." in texto:
                if texto.rfind(",") > texto.rfind("."):
                    decimal_sep = ","
                    thousands_sep = "."
                else:
                    decimal_sep = "."
                    thousands_sep = ","
                texto = texto.replace(thousands_sep, "")
                texto = texto.replace(decimal_sep, ".")
            else:
                if "," in texto:
                    texto = texto.replace(".", "")
                    texto = texto.replace(",", ".")
                else:
                    texto = texto.replace(",", "")
            try:
                return float(texto)
            except ValueError:
                return 0.0

        def formatar_lista(valores):
            vistos: list[str] = []
            for valor in valores:
                texto = str(valor or "").strip()
                if not texto:
                    continue
                if texto not in vistos:
                    vistos.append(texto)
            return " / ".join(vistos)

        def formatar_quantidade(valor: float) -> str:
            try:
                valor_float = float(valor)
            except (TypeError, ValueError):
                return ""
            if math.isclose(valor_float, round(valor_float)):
                return str(int(round(valor_float)))
            texto = f"{valor_float:,.2f}"
            return texto.replace(",", "X").replace(".", ",").replace("X", ".")

        df["quantidade_material"] = df["quantidade_material"].apply(parse_number)
        df["tensao_preferencial"] = df["nivel_tensao_obra"].where(
            df["nivel_tensao_obra"] != "", df["tensao_operacao"]
        )

        agrupado = (
            df.groupby(
                ["projeto_investimento", "alimentador_principal"], dropna=False
            )
            .agg(
                nome_regional=("nome_regional", formatar_lista),
                subestacao=("subestacao", formatar_lista),
                tensao=("tensao_preferencial", formatar_lista),
                quantidade_material=("quantidade_material", "sum"),
                coordenada_fim=("coordenada_fim", formatar_lista),
                observacoes_gerais=("observacoes_gerais", formatar_lista),
            )
            .reset_index()
        )

        if agrupado.empty:
            return

        tabela.setRowCount(len(agrupado))

        export_rows: list[list[str]] = []
        for linha, registro in agrupado.iterrows():
            quantidade_formatada = formatar_quantidade(
                registro.get("quantidade_material", 0.0)
            )
            valores = [
                registro.get("projeto_investimento", ""),
                registro.get("nome_regional", ""),
                registro.get("alimentador_principal", ""),
                registro.get("subestacao", ""),
                registro.get("tensao", ""),
                quantidade_formatada,
                registro.get("coordenada_fim", ""),
                registro.get("observacoes_gerais", ""),
            ]
            export_rows.append(valores)
            for coluna, valor in enumerate(valores):
                item = QtWidgets.QTableWidgetItem(str(valor))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                tabela.setItem(linha, coluna, item)

        self._resumo_regional_se_df = pd.DataFrame(export_rows, columns=headers)

        tabela.resizeColumnsToContents()

    def mostrar_menu_export_resumo_regional(self, pos: QtCore.QPoint) -> None:
        menu = QtWidgets.QMenu(self)
        export_excel = menu.addAction("Exportar Quadrante 4 para Excel")
        export_csv = menu.addAction("Exportar Quadrante 4 para CSV")
        action = menu.exec(self.tabelaResumoRegionalSe.mapToGlobal(pos))
        if action == export_excel:
            self.exportar_resumo_regional_se_excel()
        elif action == export_csv:
            self.exportar_resumo_regional_se_csv()

    def _get_resumo_regional_export_df(self) -> pd.DataFrame:
        df = getattr(self, "_resumo_regional_se_df", None)
        if df is None:
            return pd.DataFrame(
                columns=[
                    "PI",
                    "Regional",
                    "Alimentador",
                    "Subestação",
                    "Tensão",
                    "Quantidade",
                    "Coordenadas para",
                    "Observação",
                ]
            )
        return df

    def exportar_resumo_regional_se_excel(self) -> None:
        from ui.main_window import legacy_module
        require_tecnico_clean_or_confirm = legacy_module().require_tecnico_clean_or_confirm

        if not require_tecnico_clean_or_confirm(
            self, self.db_manager, "Exportar Quadrante 4 para Excel"
        ):
            return
        if not self.require_export_sources("Exportar Quadrante 4"):  # [RB-4]
            return
        df = self._get_resumo_regional_export_df()
        if df.empty:
            QtWidgets.QMessageBox.information(
                self, "Exportar", "Não há dados para exportar."
            )
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exportar Quadrante 4",
            "",
            "Excel Files (*.xlsx)",
        )
        if not file_path:
            return

        try:
            df.to_excel(file_path, index=False)
            QtWidgets.QMessageBox.information(
                self,
                "Exportar",
                f"Quadrante 4 exportado para {file_path}",
            )
        except Exception as e:  # pragma: no cover - apenas interação com disco/GUI
            QtWidgets.QMessageBox.critical(
                self, "Erro", f"Erro ao exportar Quadrante 4: {e}"
            )

    def exportar_resumo_regional_se_csv(self) -> None:
        from ui.main_window import legacy_module
        require_tecnico_clean_or_confirm = legacy_module().require_tecnico_clean_or_confirm

        if not require_tecnico_clean_or_confirm(
            self, self.db_manager, "Exportar Quadrante 4 para CSV"
        ):
            return
        if not self.require_export_sources("Exportar Quadrante 4"):  # [RB-4]
            return
        df = self._get_resumo_regional_export_df()
        if df.empty:
            QtWidgets.QMessageBox.information(
                self, "Exportar", "Não há dados para exportar."
            )
            return

        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exportar Quadrante 4",
            "",
            "CSV Files (*.csv)",
        )
        if not file_path:
            return

        try:
            df.to_csv(file_path, index=False, sep=";")
            QtWidgets.QMessageBox.information(
                self,
                "Exportar",
                f"Quadrante 4 exportado para {file_path}",
            )
        except Exception as e:  # pragma: no cover - apenas interação com disco/GUI
            QtWidgets.QMessageBox.critical(
                self, "Erro", f"Erro ao exportar Quadrante 4: {e}"
            )
