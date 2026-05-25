"""Mixin Tecnico Snapshot -- 7 metodos.

Extraido de ``codigo5_coplan.py::MainWindow`` na Etapa C (Tier 2).

**Excecao**: ``_apply_tecnico_token_change_db`` (com decorator
``@run_write_in_qthread_if_ui_thread``) permanece no ``codigo5_coplan.py``
porque o decorator precisa estar disponivel no momento da definicao
da classe -- e o legacy_module() nao consegue resolver decorators de
forma segura em todos os modos de execucao. Esse e um caso conhecido
para as Etapas D/E.

Atributos esperados em ``self`` (vindos da MainWindow base):
- ``self.db_manager``, ``self.config``, ``self.field_caminho_pasta``,
  ``self.data_state``, ``self.table_obras``, ``self.label_tecnico_status``

Metodos esperados em ``self``:
- ``self.require_state``, ``self.col_index``, ``self.update_reliability_labels``,
  ``self.load_obras_into_table``, ``self._apply_tecnico_token_change_db``
"""
from __future__ import annotations

import datetime
import hashlib
import os

from PySide6 import QtWidgets


class TecnicoSnapshotMixin:
    """Espera estar misturado em ``MainWindow(QMainWindow, ...)``."""

    def _compute_file_token(self, path: str) -> str:
        """Gera um token simples baseado em path/mtime/tamanho."""  # [RB-1.1]
        try:
            info = os.stat(path)
            raw = f"{os.path.abspath(path)}|{info.st_mtime}|{info.st_size}"
            return hashlib.sha1(raw.encode("utf-8")).hexdigest()
        except Exception:
            return ""

    def _compute_folder_token(self, folder: str, required_files: list[str]) -> str:
        """Gera um token simples baseado nos arquivos esperados."""  # [RB-1.1]
        parts = [os.path.abspath(folder)]
        for name in required_files:
            path = os.path.join(folder, name)
            try:
                info = os.stat(path)
                parts.append(f"{name}:{info.st_mtime}:{info.st_size}")
            except Exception:
                parts.append(f"{name}:missing")
        return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()

    def _compute_tecnico_snapshot_token(self) -> str:
        """Gera hash leve do contexto técnico (paths + mtimes)."""
        from ui.main_window import legacy_module
        TECNICO_REQUIRED_FILES = legacy_module().TECNICO_REQUIRED_FILES

        parts = []
        db_path = getattr(self.db_manager, "db_path", "") or ""
        apoio_path = self.config.get("apoio", "") or ""
        ganhos_path = self.field_caminho_pasta.text().strip() if hasattr(self, "field_caminho_pasta") else ""
        ganhos_path = ganhos_path or self.config.get("caminho_pasta_ganhos", "") or ""
        tecnico_path = self.data_state.get_state("tecnico_txt").path or ganhos_path

        if db_path:
            parts.append(f"db:{self._compute_file_token(db_path)}")
        if apoio_path:
            parts.append(f"apoio:{self._compute_file_token(apoio_path)}")
        if ganhos_path:
            parts.append(
                f"ganhos:{self._compute_folder_token(ganhos_path, TECNICO_REQUIRED_FILES)}"
            )
        if tecnico_path and tecnico_path != ganhos_path:
            parts.append(
                f"txt:{self._compute_folder_token(tecnico_path, TECNICO_REQUIRED_FILES)}"
            )

        raw = "|".join(parts)
        if not raw:
            return ""
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _get_tecnico_snapshot_source(self) -> str:
        """Retorna descrição curta das fontes técnicas atuais."""
        parts = []
        apoio_path = self.config.get("apoio", "") or ""
        ganhos_path = self.field_caminho_pasta.text().strip() if hasattr(self, "field_caminho_pasta") else ""
        ganhos_path = ganhos_path or self.config.get("caminho_pasta_ganhos", "") or ""
        tecnico_path = self.data_state.get_state("tecnico_txt").path or ganhos_path

        if apoio_path:
            parts.append(f"Apoio:{os.path.basename(apoio_path)}")
        if ganhos_path:
            parts.append(f"Ganhos:{os.path.basename(ganhos_path)}")
        if tecnico_path and tecnico_path != ganhos_path:
            parts.append(f"TXT:{os.path.basename(tecnico_path)}")

        return " | ".join(parts) if parts else "N/D"

    def _handle_tecnico_token_change(self, source: str, new_token: str) -> None:
        """Marca obras como desatualizadas quando o token técnico muda."""
        if not new_token:
            return
        old_token = self.data_state.get_state(source).version_token
        if not old_token or old_token == new_token:
            return
        dirty_applied = self._apply_tecnico_token_change_db(new_token)

        if dirty_applied:
            self.update_tecnico_dirty_indicator()
            if hasattr(self, "table_obras"):
                self.load_obras_into_table()

    def update_tecnico_dirty_indicator(self) -> None:
        """Atualiza indicador visual de dados técnicos desatualizados."""
        label = getattr(self, "label_tecnico_status", None)
        if label is None:
            return
        if not getattr(self.db_manager, "conn", None):
            label.setText("Dados técnicos atualizados após consolidação: N/D")
            label.setStyleSheet("")
            self.update_reliability_labels()  # [RB-5]
            return
        dirty_count = self.db_manager.count_tecnico_dirty()
        status = "SIM" if dirty_count > 0 else "NÃO"
        label.setText(
            f"Dados técnicos atualizados após consolidação: {status}"
            + (f" ({dirty_count})" if dirty_count > 0 else "")
        )
        if dirty_count > 0:
            label.setStyleSheet("color: #b91c1c; font-weight: 600;")
        else:
            label.setStyleSheet("color: #15803d; font-weight: 600;")
        self.update_reliability_labels()  # [RB-5]

    def atualizar_snapshot_tecnico_selecionados(self) -> None:
        from ui.main_window import legacy_module
        DataStateManager = legacy_module().DataStateManager

        if not self.require_state(
            "Atualizar snapshot técnico", {"db": DataStateManager.CARREGADO_VALIDADO}
        ):
            return
        indices = self.table_obras.selectedVisibleRows()
        if not indices:
            QtWidgets.QMessageBox.information(
                self, "Atualizar snapshot", "Selecione ao menos uma obra visível."
            )
            return
        idx_cod = self.col_index("cod")
        cods = []
        for index in indices:
            item = self.table_obras.item(index.row(), idx_cod) if idx_cod >= 0 else None
            if item and item.text().strip():
                cods.append(item.text().strip())
        if not cods:
            QtWidgets.QMessageBox.information(
                self, "Atualizar snapshot", "Nenhuma obra válida foi selecionada."
            )
            return
        token = self._compute_tecnico_snapshot_token()
        snapshot_at = datetime.datetime.now().strftime("%d/%m/%y %H:%M")
        snapshot_src = self._get_tecnico_snapshot_source()
        try:
            self.db_manager.update_tecnico_snapshot_for_cods(
                cods, token, snapshot_at, snapshot_src
            )
        except Exception as exc:
            QtWidgets.QMessageBox.warning(
                self,
                "Atualizar snapshot",
                str(exc),
            )
            return
        self.load_obras_into_table()
        self.update_tecnico_dirty_indicator()
        QtWidgets.QMessageBox.information(
            self, "Atualizar snapshot", "Snapshot técnico atualizado com sucesso."
        )
