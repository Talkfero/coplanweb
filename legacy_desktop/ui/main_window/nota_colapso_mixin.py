"""Mixin Nota de Colapso -- 1 metodo, ~96 linhas.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 1).
A logica de calculo da nota ja esta em ``core/services/nota_colapso_service``
desde o Passo 2; aqui ficou apenas a orquestracao Qt (fetch, dialog,
exportar XLSX).
"""
from __future__ import annotations

import pandas as pd
from PySide6 import QtWidgets


class NotaColapsoMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def gerar_nota_colapso_excel(self) -> None:
        # Acessa simbolos do codigo5 via legacy_module() -- ver explicacao
        # em plano_obras_mixin.abrir_dialogo_plano.
        from ui.main_window import legacy_module
        legacy = legacy_module()
        DataStateManager = legacy.DataStateManager
        open_file = legacy.open_file

        if not self.require_state(
            "Gerar nota de Colapso", {"db": DataStateManager.CARREGADO_VALIDADO}
        ):  # [RB-RESTORE-OLD]
            return
        try:
            obras = self.db_manager.fetch_all(self.db_manager.allowed_pacotes)
            col_names = self.db_manager.get_column_names()
            cod_index = col_names.index("cod")
            rows = []

            # Função de conversão que retorna 0.0 para valores vazios ou menores/iguais a zero
            conv = lambda s: 0.0 if (s := str(s).strip()) == "" else (
                (lambda v: v if v > 0 else 0.0)(
                    float(
                        s.replace(".", "").replace(",", ".")
                        if ("," in s and "." in s and s.rfind(",") > s.rfind("."))
                        else s.replace(",", ".") if "," in s
                        else s
                    )
                )
            )

            for obra in obras:
                cod = obra[cod_index]
                # Calcula a nota e o critério usando a função já existente
                nota, criterio = self.calc_manager.calcular_nota_colapso_obra(obra)
                nota_formatada = f"{nota:.2f}".replace(".", ",") if nota is not None else ""

                # Extração dos valores usados para o cálculo, utilizando a nova função conv
                idx_carreg_ini = col_names.index("carregamento_inicial")
                idx_carreg_fin = col_names.index("carregamento_final")
                carreg_inicial_str = str(obra[idx_carreg_ini]).strip() or (
                    str(obra[idx_carreg_fin]).strip() if len(obra) > idx_carreg_fin else ""
                )
                carreg_inicial = conv(carreg_inicial_str)

                idx_carreg_max = col_names.index("carregamento_max_registrado_atual")
                carreg_max_str = str(obra[idx_carreg_max]).strip()
                carreg_max = conv(carreg_max_str)

                idx_tmin_ini = col_names.index("tensao_min_inicial")
                idx_tmin_fin = col_names.index("tensao_min_final")
                tensao_min_inicial_str = str(obra[idx_tmin_ini]).strip() or (
                    str(obra[idx_tmin_fin]).strip() if len(obra) > idx_tmin_fin else ""
                )
                tensao_min_inicial = conv(tensao_min_inicial_str)

                idx_tmax_ini = col_names.index("tensao_max_inicial")
                idx_tmax_fin = col_names.index("tensao_max_final")
                tensao_max_inicial_str = str(obra[idx_tmax_ini]).strip() or (
                    str(obra[idx_tmax_fin]).strip() if len(obra) > idx_tmax_fin else ""
                )
                tensao_max_inicial = conv(tensao_max_inicial_str)

                idx_treg = col_names.index("tensao_min_registrada_atual")
                tensao_registrada_str = str(obra[idx_treg]).strip() or (
                    str(obra[idx_tmin_ini]).strip() if len(obra) > idx_tmin_ini else ""
                )
                if "/" in tensao_registrada_str:
                    partes = tensao_registrada_str.split("/")
                    tensao_min_atual = conv(partes[0].strip())
                    tensao_max_atual = conv(partes[1].strip())
                else:
                    tensao_min_atual = conv(tensao_registrada_str)
                    tensao_max_atual = conv(tensao_registrada_str)

                valores_usados = (
                    f"Carreg. Inicial: {carreg_inicial}, Carreg. Máx: {carreg_max}; "
                    f"Tensão Min. Inicial: {tensao_min_inicial}, Tensão Max. Inicial: {tensao_max_inicial}; "
                    f"Tensão Min. Atual: {tensao_min_atual}, Tensão Max. Atual: {tensao_max_atual}"
                )

                valores_exibidos = valores_usados if (nota == 0 or nota is None) else ""

                rows.append({
                    "cod": cod,
                    "Nota Colapso": nota_formatada,
                    "Critério definido": criterio,
                    "Valores Considerados": valores_exibidos
                })

            df = pd.DataFrame(rows)
            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Salvar Nota de Colapso", "", "Excel Files (*.xlsx)"
            )
            if file_path:
                df.to_excel(file_path, index=False)
                open_file(file_path)
                QtWidgets.QMessageBox.information(
                    self,
                    "Sucesso",
                    f"Nota de Colapso exportada para {file_path}"
                )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Erro", f"Erro ao gerar nota de Colapso: {str(e)}")
