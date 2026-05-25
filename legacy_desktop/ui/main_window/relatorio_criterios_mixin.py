"""Mixin Relatorio de Criterios -- 15 metodos (mostly wrappers).

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 4).
"""
from __future__ import annotations

from typing import Any, Sequence

import pandas as pd
from PySide6 import QtWidgets


class RelatorioCriteriosMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def _restore_criterios_config(self) -> None:
        from ui.main_window import legacy_module
        DEFAULT_CRITERIOS = legacy_module().DEFAULT_CRITERIOS
        self.cfg_spin_tmin.setValue(DEFAULT_CRITERIOS["tensao_min"])
        self.cfg_spin_tmax.setValue(DEFAULT_CRITERIOS["tensao_max"])
        self.cfg_spin_carreg_sim.setValue(DEFAULT_CRITERIOS["carregamento_limite_sim_ou_vazio"])
        self.cfg_spin_carreg_nao.setValue(DEFAULT_CRITERIOS["carregamento_limite_nao"])
        self.cfg_spin_clientes.setValue(DEFAULT_CRITERIOS["clientes_maximo"])

    def _save_criterios_config(self) -> None:
        from ui.main_window import legacy_module
        ConfigManager = legacy_module().ConfigManager
        criterios = {
            "tensao_min": self.cfg_spin_tmin.value(),
            "tensao_max": self.cfg_spin_tmax.value(),
            "carregamento_limite_sim_ou_vazio": self.cfg_spin_carreg_sim.value(),
            "carregamento_limite_nao": self.cfg_spin_carreg_nao.value(),
            "clientes_maximo": self.cfg_spin_clientes.value(),
        }
        self.config["criterios_planejamento"] = criterios
        ConfigManager.save_config({"criterios_planejamento": criterios})
        self.load_obras_into_table()
        QtWidgets.QMessageBox.information(
            self,
            "Configurações",
            "Critérios de planejamento salvos com sucesso.",
        )

    def _restore_piora_config(self) -> None:
        from ui.main_window import legacy_module
        DEFAULT_PIORA_MERCADO = legacy_module().DEFAULT_PIORA_MERCADO
        self.cfg_field_piora_carreg.setText(str(DEFAULT_PIORA_MERCADO["carregamento_percentual"]))
        self.cfg_field_piora_tensao.setText(str(DEFAULT_PIORA_MERCADO["tensao_delta"]))
        self.cfg_field_piora_anos.setText(str(DEFAULT_PIORA_MERCADO["anos_horizonte"]))

    def _save_piora_config(self) -> None:
        from ui.main_window import legacy_module
        ConfigManager = legacy_module().ConfigManager
        try:
            piora = {
                "carregamento_percentual": float(self.cfg_field_piora_carreg.text().replace(",", ".")),
                "tensao_delta": float(self.cfg_field_piora_tensao.text().replace(",", ".")),
                "anos_horizonte": int(self.cfg_field_piora_anos.text()),
            }
        except Exception:
            QtWidgets.QMessageBox.warning(
                self,
                "Configurações",
                "Valores inválidos na aba Piora de Mercado.",
            )
            return
        self.config["piora_mercado"] = piora
        ConfigManager.save_config({"piora_mercado": piora})
        self.load_obras_into_table()
        QtWidgets.QMessageBox.information(
            self,
            "Configurações",
            "Parâmetros de piora de mercado salvos com sucesso.",
        )

    def _avaliar_alim_por_ganhos(
        self, metrics: dict[str, float], manobra: str, criterios: dict
    ) -> tuple[bool | None, list[str]]:
        """Wrapper -- delega ao core/services/relatorio_criterios_service."""
        from core.services.relatorio_criterios_service import avaliar_alim_por_ganhos as _impl
        return _impl(metrics, manobra, criterios)

    def verificar_criterios_planejamento_v2(
        self,
        obras: Sequence[Sequence[Any]],
        columns: Sequence[str],
    ) -> list[bool | None]:
        """Wrapper -- delega ao core/services/relatorio_criterios_service."""
        from core.services.relatorio_criterios_service import verificar_criterios_v2 as _impl
        from ui.main_window import legacy_module
        DEFAULT_CRITERIOS = legacy_module().DEFAULT_CRITERIOS
        criterios = self.config.get("criterios_planejamento", DEFAULT_CRITERIOS)
        return _impl(obras, columns, criterios=criterios)

    def _avaliar_criterios_persistencia(
        self,
        row: Sequence[Any],
        idx: dict[str, int],
        criterios: dict,
    ) -> tuple[str, str, str]:
        """Wrapper -- delega ao core/services/relatorio_criterios_service."""
        from core.services.relatorio_criterios_service import avaliar_criterios_persistencia as _impl
        return _impl(row, idx, criterios)

    def _build_criterios_persistencia_updates(
        self,
        obras: Sequence[Sequence[Any]],
        columns: Sequence[str],
    ) -> list[tuple[str, str, str, str]]:
        """Wrapper -- delega ao core/services/relatorio_criterios_service."""
        from core.services.relatorio_criterios_service import build_criterios_persistencia_updates as _impl
        from ui.main_window import legacy_module
        DEFAULT_CRITERIOS = legacy_module().DEFAULT_CRITERIOS
        criterios = self.config.get("criterios_planejamento", DEFAULT_CRITERIOS)
        return _impl(obras, columns, criterios=criterios)

    def _buscar_anos_por_ids(self, ids: list[str]) -> list[str]:
        ids_norm: list[str] = []
        seen_ids: set[str] = set()
        for raw_id in ids or []:
            cod = str(raw_id or "").strip()
            if not cod or cod in seen_ids:
                continue
            seen_ids.add(cod)
            ids_norm.append(cod)
        if not ids_norm:
            return []
        try:
            years: list[str] = []
            seen_years: set[str] = set()
            with self.db_manager._with_connection():
                cursor = self.db_manager._get_cursor()
                if not cursor:
                    return []
                id_col = self.db_manager._resolve_obra_id_column()
                if not id_col:
                    return []
                cols = set(self.db_manager.get_column_names() or [])
                if "ano_" not in cols:
                    return []
                id_col_sql = self.db_manager._escape_identifier(id_col)
                ano_col_sql = self.db_manager._escape_identifier("ano_")
                chunk_size = 900
                for start in range(0, len(ids_norm), chunk_size):
                    chunk = ids_norm[start : start + chunk_size]
                    placeholders = ",".join(["?"] * len(chunk))
                    cursor.execute(
                        f"SELECT {ano_col_sql} FROM obras "
                        f"WHERE {id_col_sql} IN ({placeholders})",
                        chunk,
                    )
                    for row in cursor.fetchall():
                        ano_txt = str((row[0] if row else "") or "").strip()
                        if not ano_txt or ano_txt in seen_years:
                            continue
                        seen_years.add(ano_txt)
                        years.append(ano_txt)
            return years
        except Exception:
            return []

    def _buscar_ids_por_pacotes(
        self,
        pacotes: list[str],
        somente_vazios: bool,
    ) -> list[str]:
        pacotes_norm = [str(p).strip() for p in pacotes if str(p).strip()]
        if not pacotes_norm:
            return []

        ids: list[str] = []
        seen: set[str] = set()
        with self.db_manager._with_connection():
            cursor = self.db_manager._get_cursor()
            if not cursor:
                return []
            cols = set(self.db_manager.get_column_names())
            id_col = self.db_manager._resolve_obra_id_column()
            pacote_col = self.db_manager._resolve_pacote_column()
            if not id_col or not pacote_col:
                return []

            id_col_sql = self.db_manager._escape_identifier(id_col)
            pacote_col_sql = self.db_manager._escape_identifier(pacote_col)
            pacote_placeholders = ",".join(["?"] * len(pacotes_norm))
            where_parts = [f"{pacote_col_sql} IN ({pacote_placeholders})"]
            params: list[Any] = list(pacotes_norm)

            if somente_vazios and "cod_pep" in cols:
                cod_pep_sql = self.db_manager._escape_identifier("cod_pep")
                where_parts.append(f"({cod_pep_sql} IS NULL OR TRIM({cod_pep_sql})='')")

            allowed = getattr(self.db_manager, "allowed_pacotes", None) or []
            allowed_norm = [str(p).strip() for p in allowed if str(p).strip()]
            if allowed_norm:
                allowed_placeholders = ",".join(["?"] * len(allowed_norm))
                where_parts.append(f"{pacote_col_sql} IN ({allowed_placeholders})")
                params.extend(allowed_norm)

            sql = (
                f"SELECT {id_col_sql} FROM obras "
                f"WHERE {' AND '.join(where_parts)} "
                f"ORDER BY {id_col_sql}"
            )
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                row_id = str((row[0] if row else "") or "").strip()
                if not row_id or row_id in seen:
                    continue
                seen.add(row_id)
                ids.append(row_id)

        return ids

    def _prompt_relatorio_criterios_scope(
        self, has_selection: bool, has_hidden: bool
    ) -> str | None:
        if has_selection:
            msg = QtWidgets.QMessageBox(self)
            msg.setIcon(QtWidgets.QMessageBox.Icon.Question)
            msg.setWindowTitle("Exportar Relatório de Critérios")
            msg.setText("Quais obras deseja exportar?")
            btn_selected = msg.addButton(
                "Somente selecionadas", QtWidgets.QMessageBox.ButtonRole.AcceptRole
            )
            btn_visible = msg.addButton(
                "Somente visíveis (filtro atual)", QtWidgets.QMessageBox.ButtonRole.AcceptRole
            )
            btn_all = msg.addButton("Tudo", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = msg.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)
            msg.setDefaultButton(btn_selected)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == btn_cancel:
                return None
            if clicked == btn_selected:
                return "selected"
            if clicked == btn_visible:
                return "visible"
            if clicked == btn_all:
                return "all"
            return None

        if has_hidden:
            msg = QtWidgets.QMessageBox(self)
            msg.setIcon(QtWidgets.QMessageBox.Icon.Question)
            msg.setWindowTitle("Exportar Relatório de Critérios")
            msg.setText("Quais obras deseja exportar?")
            btn_visible = msg.addButton(
                "Somente visíveis (filtro atual)", QtWidgets.QMessageBox.ButtonRole.AcceptRole
            )
            btn_all = msg.addButton("Tudo", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = msg.addButton(QtWidgets.QMessageBox.StandardButton.Cancel)
            msg.setDefaultButton(btn_visible)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == btn_cancel:
                return None
            if clicked == btn_visible:
                return "visible"
            if clicked == btn_all:
                return "all"
            return None

        return "all"

    def montar_relatorio_criterios_por_projeto(
        self, cods: list[str] | None
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Retorna (df_projetos, df_alimentadores) com os critérios por projeto.

        Logica pura extraida para core/services/relatorio_criterios_service
        (Etapa B.4). A UI continua responsavel por fetch_all/fetch_by_cods
        e get_column_names.
        """
        from core.services.relatorio_criterios_service import (
            montar_relatorio_criterios_por_projeto as _impl,
        )
        from ui.main_window import legacy_module
        DEFAULT_CRITERIOS = legacy_module().DEFAULT_CRITERIOS

        if cods is None:
            obras = self.db_manager.fetch_all(self.db_manager.allowed_pacotes)
        else:
            obras = self._fetch_obras_by_cods(cods)
        columns = self.db_manager.get_column_names()
        criterios = self.config.get("criterios_planejamento", DEFAULT_CRITERIOS)

        relatorio = _impl(obras, columns, criterios=criterios)
        return relatorio.df_projetos, relatorio.df_alimentadores

    def verificar_criterios_planejamento(self, obras, columns):
        """DEPRECATED -- mantido para nao apagar codigo legado.

        Sem callers no codigo5 desde que ``verificar_criterios_planejamento_v2``
        foi adicionada. Logica pura extraida para
        core/services/relatorio_criterios_service.verificar_criterios_v1.
        """
        from core.services.relatorio_criterios_service import verificar_criterios_v1 as _impl
        from ui.main_window import legacy_module
        DEFAULT_CRITERIOS = legacy_module().DEFAULT_CRITERIOS
        criterios = self.config.get("criterios_planejamento", DEFAULT_CRITERIOS)
        return _impl(obras, columns, criterios=criterios)

    def open_criterios_dialog(self, *_args):
        self._open_configuracoes_tab("criterios")

    def open_piora_dialog(self, *_args):
        self._open_configuracoes_tab("piora")
