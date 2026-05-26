# -*- coding: utf-8 -*-
"""Mixin de dominio "banco" da CoplanApi (extraido de main_web.py).

Nao instanciar diretamente: compoe backend.api.CoplanApi via heranca.
"""
from __future__ import annotations

import getpass  # noqa: F401
import hashlib  # noqa: F401
import os  # noqa: F401
import re  # noqa: F401
import sys  # noqa: F401
import threading  # noqa: F401
from datetime import datetime  # noqa: F401
from pathlib import Path  # noqa: F401
from typing import Any, Callable  # noqa: F401

from backend._state import (  # noqa: F401
    APP_VERSION,
    HERE,
    _OP_LOCK,
    _OP_STATE,
    _op_check_cancel,
    _op_finish,
    _op_reset,
    _op_set_progress,
    _op_snapshot,
)


class BancoMixin:

    # ------------------------------------------------------------------
    # Botoes do header global (fora dos passos da Section 6 mas presentes
    # no Coplan UI.html e funcionais no desktop): Conectar Banco,
    # Importar Excel, Exportar Excel. Sao "atalhos" que reusam APIs
    # ja existentes.
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_db_minimum(db_path: str) -> tuple[bool, str]:
        """Paridade com BancoMixin._validate_db_minimum do desktop:
        verifica permissoes, tabela 'obras' e coluna minima 'cod' antes
        de salvar o caminho no config. Retorna (ok, motivo)."""
        if not db_path:
            return False, "caminho vazio"
        if not os.path.isfile(db_path):
            return False, f"arquivo nao encontrado: {db_path}"
        if not os.access(db_path, os.R_OK):
            return False, "sem permissao de leitura"
        if not os.access(db_path, os.W_OK):
            return False, "sem permissao de escrita"
        import sqlite3 as _sqlite3
        conn = None
        try:
            conn = _sqlite3.connect(db_path, timeout=5.0)
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='obras'"
            )
            if cur.fetchone() is None:
                return False, "tabela 'obras' inexistente"
            cur.execute("PRAGMA table_info(obras)")
            cols = {str(r[1]).strip().lower() for r in cur.fetchall() if len(r) > 1}
            if "cod" not in cols:
                return False, "coluna minima 'cod' ausente"
        except Exception as exc:  # noqa: BLE001
            return False, f"sqlite: {exc}"
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
        return True, ""

    def header_connect_db(self) -> dict[str, Any]:
        """Atalho header 'Conectar Banco': abre file dialog, valida
        (paridade com desktop), salva no config e reconecta. Limpa
        o cache de paths conectados."""
        r = self.pick_db_file()
        if not r.get("ok"):
            return r
        path = str(r.get("path") or "").strip()
        if not path:
            return {"ok": False, "error": "caminho vazio"}
        # Validacao igual ao desktop (BancoMixin._validate_db_minimum):
        # so persiste o caminho se o banco for compativel. Sem isto o
        # web salvava lixo no config e depois cada API quebrava com
        # "no such table: obras" / "no such column: cod".
        ok_valid, motivo = self._validate_db_minimum(path)
        if not ok_valid:
            return {"ok": False, "path": path, "error": motivo}
        save = self.save_config_empresa({"caminho_db": path})
        if not save.get("ok"):
            return save
        # Tenta conectar imediatamente para o feedback ser instantaneo.
        self._config = None
        self._connected_paths.clear()
        db, err = self._ensure_db_connected()
        return {
            "ok": db is not None and not err,
            "path": path,
            "error": err or "",
        }

    def header_import_excel(
        self, strategy: Any = "ask",
    ) -> dict[str, Any]:
        """Atalho header 'Importar Excel': le um xlsx/csv e aciona
        insert_obra para cada linha (mapeamento por nome de coluna,
        igual ao DatabaseManager.insert_obra).

        ``strategy`` define como tratar duplicadas (replica
        ``_prompt_duplicate_action`` do desktop):
          * ``"ask"`` (padrao): se houver duplicadas, retorna
            ``need_user_action=True`` com a lista para o JS perguntar
            ao usuario, sem importar nada
          * ``"merge"``: aplica build_merge_updates + update_obra
            (sobrescreve colunas preenchidas que diferem do Excel,
            inclusive ``ano_``; preserva ``cod``/``data_criacao``/
            ``criado_por``)
          * ``"create"``: ignora duplicidade e usa insert_obra
            (pode falhar por unique-index)
          * ``"skip"``: pula obras duplicadas
        """
        # File dialog que devolve {ok, path, error}. Antes usava
        # pick_ganhos_file() que retorna read_ganhos_file(path, 200) --
        # esse helper le headers/rows mas NAO devolve "path", fazendo
        # com que toda importacao retornasse "path vazio" silenciosamente.
        picked = self._pick_file_with_filters(
            "Planilhas (*.xlsx;*.xlsm;*.xls;*.csv;*.txt;*.tsv)")
        if not picked.get("ok"):
            return {"ok": False,
                    "error": picked.get("error") or "cancelado",
                    "imported": 0, "errors": []}
        path = picked.get("path") or ""
        if not path:
            return {"ok": False, "error": "path vazio",
                    "imported": 0, "errors": []}
        return self._import_excel_from_path(
            path, str(strategy or "ask").strip().lower())

    def import_excel_apply(
        self, path: Any = "", strategy: Any = "merge",
    ) -> dict[str, Any]:
        """Versao com strategy explicita para o JS chamar apos perguntar
        ao user. Path e' o mesmo retornado pelo header_import_excel
        anterior (cached em window.__coplanLastImportPath)."""
        path_s = str(path or "").strip()
        if not path_s:
            return {"ok": False, "error": "path vazio",
                    "imported": 0, "errors": []}
        if not os.path.isfile(path_s):
            return {"ok": False, "error": f"arquivo nao encontrado: {path_s}",
                    "imported": 0, "errors": []}
        return self._import_excel_from_path(
            path_s, str(strategy or "merge").strip().lower())

    # ------------------------------------------------------------------
    # Bloco 5 (Auditoria #44): bridges de progress + cancel
    # ------------------------------------------------------------------
    def progress_state(self) -> dict[str, Any]:
        """Devolve estado da operacao longa em andamento (ou da ultima
        finalizada). JS pollam isso a cada ~200ms enquanto o modal de
        progresso esta aberto."""
        return _op_snapshot()

    def progress_cancel(self) -> dict[str, Any]:
        """Sinaliza cancel para a operacao em andamento. Worker thread
        verifica via _op_check_cancel() em pontos seguros do loop."""
        with _OP_LOCK:
            if _OP_STATE.get("finished"):
                return {"ok": False,
                        "error": "nenhuma operacao em andamento"}
            _OP_STATE["cancel_requested"] = True
        return {"ok": True, "error": ""}

    # ------------------------------------------------------------------
    # save_log_txt: salva o conteudo de texto montado pelo modal de
    # detalhes pos-operacao (chaves inexistentes, falhas, erros, etc.).
    # Default folder = <HERE>/logs. Usuario escolhe nome final via
    # SAVE dialog. Usado por window.coplanShowErrorDetails (botao
    # "Salvar TXT...").
    # ------------------------------------------------------------------
    def save_log_txt(
        self, content: Any = "", default_name: Any = "log.txt",
    ) -> dict[str, Any]:
        try:
            import webview  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": "",
                    "error": f"pywebview indisponivel: {exc}"}
        text = str(content or "")
        name = str(default_name or "log.txt").strip() or "log.txt"
        # Sanitiza nome: troca caracteres problematicos em filenames.
        import re as _re_log
        name = _re_log.sub(r'[\\/:*?"<>|]', "_", name)
        if not name.lower().endswith(".txt"):
            name = name + ".txt"
        try:
            wins = webview.windows
            if not wins:
                return {"ok": False, "path": "",
                        "error": "janela nao encontrada"}
            dlg = self._wv_dialog_const("SAVE")
            if dlg is None:
                return {"ok": False, "path": "",
                        "error": "SAVE dialog indisponivel"}
            logs_dir = HERE / "logs"
            try:
                logs_dir.mkdir(exist_ok=True)
            except Exception:  # noqa: BLE001
                pass
            file_types = ("Texto (*.txt)", "Todos os arquivos (*.*)")
            result = wins[0].create_file_dialog(
                dlg, save_filename=name,
                directory=str(logs_dir),
                file_types=file_types,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": "",
                    "error": f"file dialog: {exc}"}
        if not result:
            return {"ok": False, "path": "", "error": "cancelado"}
        path = result if isinstance(result, str) else (
            result[0] if result else "")
        if not path:
            return {"ok": False, "path": "", "error": "caminho vazio"}
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": "",
                    "error": f"escrita: {exc}"}
        return {"ok": True, "path": str(path), "error": ""}

    def open_logs_folder(self) -> dict[str, Any]:
        """Abre <HERE>/logs no file manager do OS. Cria a pasta se
        ainda nao existir. Usado pelo modal de detalhes."""
        logs_dir = HERE / "logs"
        try:
            logs_dir.mkdir(exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": str(logs_dir),
                    "error": f"mkdir: {exc}"}
        try:
            import subprocess
            if sys.platform.startswith("win"):
                os.startfile(str(logs_dir))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(logs_dir)], check=False)
            else:
                subprocess.run(["xdg-open", str(logs_dir)], check=False)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": str(logs_dir),
                    "error": f"open: {exc}"}
        return {"ok": True, "path": str(logs_dir), "error": ""}

    def import_excel_async(
        self, path: Any = "", strategy: Any = "merge",
    ) -> dict[str, Any]:
        """Versao async de _import_excel_from_path: dispara worker thread
        e retorna imediatamente com op_id. JS deve abrir o modal de
        progresso e pollar progress_state() ate finished=True."""
        path_s = str(path or "").strip()
        if not path_s:
            return {"ok": False, "error": "path vazio", "started": False}
        if not os.path.isfile(path_s):
            return {"ok": False,
                    "error": f"arquivo nao encontrado: {path_s}",
                    "started": False}
        # Refuse se ja ha operacao em andamento
        with _OP_LOCK:
            if not _OP_STATE.get("finished"):
                return {
                    "ok": False,
                    "started": False,
                    "error": ("ja ha uma operacao em andamento: "
                              + str(_OP_STATE.get("label") or "")),
                }
        op_id = _op_reset(f"Importando Excel ({os.path.basename(path_s)})...")

        def _worker():
            try:
                strat = str(strategy or "merge").strip().lower()
                result = self._import_excel_from_path(path_s, strat)
                _op_finish(result=result, error="")
            except Exception as exc:  # noqa: BLE001
                _op_finish(result=None, error=f"worker: {exc}")

        t = threading.Thread(target=_worker, daemon=True,
                             name=f"coplan-import-{op_id}")
        t.start()
        return {"ok": True, "started": True, "op_id": op_id, "error": ""}

    def _import_excel_from_path(
        self, path: str, strategy: str,
    ) -> dict[str, Any]:
        """Importacao Excel com paridade ImportarExcelMixin.import_from_excel.

        Bloco 3 (Auditoria #24-#28 + M20):
          * #25 _clean_excel_columns: remove "Unnamed:" e vazias
          * #26 add_column_if_missing: empresa, cod_pep, e colunas novas
          * #27 gate root_columns subset of df.columns
          * #24 regra do `_` em alimentador_principal/beneficiados
          * #28 merge reaplica empresa da config + recalcula cod_pep
          * M20 grava arquivo de log <base>_log_importacao_<ts>.txt
        """
        import re as _re_local
        import datetime as _dt_local
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel",
                    "imported": 0, "errors": []}
        # ----- Le como dataframe -----
        try:
            import pandas as pd  # type: ignore[import-not-found]
            ext = os.path.splitext(path)[1].lower()
            if ext in (".xlsx", ".xlsm", ".xls"):
                df = pd.read_excel(path, dtype=str)
            else:
                df = pd.read_csv(path, sep=None, engine="python", dtype=str)
            df.fillna("", inplace=True)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"leitura: {exc}",
                    "imported": 0, "errors": []}

        # ----- #25 _clean_excel_columns -----
        try:
            from runtime.apoio import (  # type: ignore[import-not-found]
                _clean_excel_columns,
            )
            df, _clean_cols = _clean_excel_columns(df)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"clean_excel_columns: {exc}",
                    "imported": 0, "errors": []}

        # ----- #26 garante colunas PEP no schema -----
        try:
            db.add_column_if_missing("empresa")
            db.add_column_if_missing("cod_pep")
            db.update_columns()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"add_column_pep: {exc}",
                    "imported": 0, "errors": []}

        # ----- #27 gate root_columns subset of df.columns -----
        try:
            root_cols = list(getattr(db, "root_columns", []) or [])
        except Exception:  # noqa: BLE001
            root_cols = []
        df_cols_set = set(df.columns)
        if root_cols and not set(root_cols).issubset(df_cols_set):
            faltantes = [c for c in root_cols if c not in df_cols_set]
            return {
                "ok": False,
                "error": ("O arquivo Excel nao possui as colunas corretas. "
                          "Faltantes: " + ", ".join(faltantes[:10])
                          + ("..." if len(faltantes) > 10 else "")),
                "imported": 0,
                "errors": [],
                "missing_columns": faltantes,
            }

        # ----- #26 (parte 2) inclui colunas novas do Excel no banco -----
        try:
            existing_cols = set(db.get_column_names() or [])
            for col in df.columns:
                if col and col not in existing_cols:
                    db.add_column_if_missing(col)
            db.update_columns()
        except Exception as exc:  # noqa: BLE001
            # Nao fatal: registra mas segue. JS pode mostrar warn.
            pass  # noqa: BLE001

        # ----- Limpa rows + detecta duplicadas -----
        try:
            from runtime.row_helpers import (  # type: ignore[import-not-found]
                find_duplicate_in_db,
            )
        except Exception:  # noqa: BLE001
            find_duplicate_in_db = None
        duplicadas: list[dict[str, Any]] = []
        rows_clean: list[dict[str, Any]] = []
        total_rows = int(len(df.index))
        # Bloco 5: marca total no progress logo no inicio
        _op_set_progress(0, total_rows, "Detectando duplicadas...")
        for i, row in enumerate(df.to_dict(orient="records"), start=1):
            # Bloco 5: cancel-check periodico (a cada 50 linhas)
            if (i % 50) == 0 and _op_check_cancel():
                return {
                    "ok": False, "cancelled": True,
                    "imported": 0, "merged": 0, "skipped": 0,
                    "errors": ["Operacao cancelada pelo usuario."],
                    "error": "cancelado",
                    "total": total_rows,
                }
            cleaned = {
                str(k).strip(): ("" if v is None or (isinstance(v, float)
                                                    and v != v)
                                  else v)
                for k, v in row.items()
                if str(k).strip()
            }
            rows_clean.append(cleaned)
            if find_duplicate_in_db is None:
                continue
            try:
                dup = find_duplicate_in_db(db, cleaned)
            except Exception:  # noqa: BLE001
                dup = None
            if dup:
                duplicadas.append({
                    "linha": i,
                    "cod_excel": str(cleaned.get("cod") or ""),
                    "dup_cod": str((dup or {}).get("cod") or ""),
                })
            # Bloco 5: progresso na fase de scan duplicadas
            if (i % 25) == 0:
                _op_set_progress(
                    i, total_rows,
                    f"Detectando duplicadas... ({i}/{total_rows})")

        # ----- Modo "ask": pergunta estrategia -----
        if strategy == "ask":
            if duplicadas:
                return {
                    "ok": False,
                    "need_user_action": True,
                    "path": path,
                    "total": len(rows_clean),
                    "duplicadas": duplicadas[:50],
                    "duplicadas_count": len(duplicadas),
                    "imported": 0,
                    "errors": [],
                    "message": (str(len(duplicadas))
                                + " duplicada(s) detectada(s) - "
                                "escolha estrategia"),
                }
            # Sem duplicadas, segue como create.
            strategy = "create"

        # ----- Helpers para #28 merge: empresa + cod_pep -----
        try:
            from runtime.database import cod_pep as _cod_pep_calc  # noqa: PLC0415
            from runtime.text_utils import normalize_text as _norm_text  # noqa: PLC0415
        except Exception:  # noqa: BLE001
            _cod_pep_calc = None
            _norm_text = lambda s: str(s or "").strip().upper()  # noqa: E731

        def _empresa_from_row_or_config(row: dict[str, Any]) -> str:
            empresa_excel = row.get("empresa") if isinstance(row, dict) else ""
            empresa = _norm_text(empresa_excel)
            if empresa:
                return empresa
            try:
                return _norm_text(db.get_empresa_sigla_from_config())
            except Exception:  # noqa: BLE001
                return ""

        def _build_merge_updates_with_pep(
            existing: dict[str, Any], new_row: dict[str, Any],
        ) -> dict[str, Any]:
            updates = db.build_merge_updates(existing, new_row) or {}
            empresa_nova = _empresa_from_row_or_config(new_row)
            if empresa_nova:
                empresa_atual = _norm_text(existing.get("empresa"))
                if empresa_atual != empresa_nova:
                    updates["empresa"] = empresa_nova
            # cod_pep: prioriza Excel; recalcula se vazio
            cod_pep_excel = str((new_row.get("cod_pep") or "")).strip()
            cod_pep_novo = cod_pep_excel
            if not cod_pep_novo and empresa_nova and _cod_pep_calc is not None:
                obra_calc = dict(existing)
                is_missing = getattr(db, "_is_missing", None)
                for key, value in new_row.items():
                    if callable(is_missing):
                        if not is_missing(value):
                            obra_calc[key] = value
                    elif value not in (None, ""):
                        obra_calc[key] = value
                obra_calc["empresa"] = empresa_nova
                try:
                    cod_pep_novo = str(
                        _cod_pep_calc(db, obra_calc, empresa_nova) or ""
                    ).strip()
                except Exception:  # noqa: BLE001
                    cod_pep_novo = ""
            if cod_pep_novo:
                cod_pep_atual = str(existing.get("cod_pep") or "").strip()
                if cod_pep_atual != cod_pep_novo:
                    updates["cod_pep"] = cod_pep_novo
            return updates

        # ----- Loop principal -----
        imported = 0
        merged = 0
        skipped = 0
        ignorados_underscore = 0
        ignorados_permissao = 0
        error_log: list[str] = []
        # Errors curto pro JS toastar (compat retro)
        errors: list[str] = []
        dup_keys: dict[int, dict[str, Any]] = {}
        if find_duplicate_in_db is not None:
            for d in duplicadas:
                dup_keys[d["linha"]] = d

        # Bloco 5: reset progresso para a fase de gravacao
        total_processar = len(rows_clean)
        _op_set_progress(0, total_processar,
                         f"Importando registros... (0/{total_processar})")
        cancelled_mid = False

        # Linha do Excel = i + 1 (header) -> i+1 = linha real no .xlsx
        for i, cleaned in enumerate(rows_clean, start=1):
            # Bloco 5: cancel-check periodico (a cada 10 linhas no loop pesado)
            if (i % 10) == 0 and _op_check_cancel():
                cancelled_mid = True
                error_log.append(
                    f"Linha {i + 1}: cancelado pelo usuario "
                    f"(processadas {imported + merged}/{total_processar})."
                )
                break
            # Bloco 5: progresso a cada 5 linhas
            if (i % 5) == 0:
                _op_set_progress(
                    i, total_processar,
                    f"Importando registros... ({i}/{total_processar})")
            linha_excel = i + 1
            cod = str(cleaned.get("cod") or "")

            # ----- #24 regra do `_` em alimentador -----
            alim = str(cleaned.get("alimentador_principal") or "")
            benef = str(cleaned.get("alimentadores_beneficiados") or "")
            if "_" in alim or any(
                "_" in b
                for b in _re_local.split(r"[,;|\n]+", benef)
            ):
                ignorados_underscore += 1
                error_log.append(
                    f"Linha {linha_excel} (cod={cod}): "
                    "Ignorado - alimentador_principal/beneficiados "
                    "contem sublinhado (_)."
                )
                continue

            is_dup = i in dup_keys
            if is_dup and strategy == "skip":
                skipped += 1
                continue
            if is_dup and strategy == "merge":
                try:
                    cod_dup = dup_keys[i].get("dup_cod") or ""
                    if not cod_dup:
                        msg = f"linha {linha_excel}: dup_cod vazio"
                        errors.append(msg)
                        error_log.append(msg)
                        continue
                    existing = db.fetch_by_cod(cod_dup)
                    if existing:
                        cols = list(db.get_column_names() or [])
                        existing_dict = dict(zip(cols, existing))
                        updates = _build_merge_updates_with_pep(
                            existing_dict, cleaned)
                        if updates:
                            db.update_obra(updates, cod_dup, skip_blank=True)
                            merged += 1
                        else:
                            skipped += 1
                            error_log.append(
                                f"Linha {linha_excel} (cod={cod}): "
                                "Duplicidade detectada, mas sem atualizacoes "
                                "aplicaveis."
                            )
                except Exception as exc:  # noqa: BLE001
                    msg = f"linha {linha_excel} (merge): {exc}"
                    errors.append(msg)
                    error_log.append(msg)
                    if len(errors) >= 20:
                        errors.append(
                            f"... +{len(rows_clean) - i} suprimida(s)")
                        break
                continue
            # ----- create -----
            try:
                db.insert_obra(cleaned)
                imported += 1
            except PermissionError as exc:
                # #6 categorizado: pacote nao permitido
                ignorados_permissao += 1
                msg = (
                    f"Linha {linha_excel} (cod={cod}): "
                    f"Permissao negada (pacote nao permitido). "
                    f"Detalhes: {exc}"
                )
                error_log.append(msg)
                if len(errors) < 20:
                    errors.append(msg)
            except Exception as exc:  # noqa: BLE001
                msg = f"Linha {linha_excel} (cod={cod}): {exc!r}"
                error_log.append(msg)
                if len(errors) < 20:
                    errors.append(msg)
                if len(errors) >= 20:
                    errors.append(
                        f"... +{len(rows_clean) - i} suprimida(s)")
                    # nao quebra: continua para acumular log completo

        # ----- Refresh de cache do db (paridade desktop) -----
        try:
            db.update_columns()
            refresh_cache = getattr(db, "_refresh_cache", None)
            if callable(refresh_cache):
                refresh_cache()
        except Exception:  # noqa: BLE001
            pass  # noqa: BLE001

        # ----- Registra no ledger os cod_pep que vieram na planilha -----
        # Importacao prioriza o cod_pep do Excel (preservado). Para que
        # esses tambem fiquem reservados (e nao sejam reaproveitados se a
        # obra for excluida depois), reaplica o backfill de cod_pep_emitidos.
        try:
            ensure_ledger = getattr(db, "_ensure_cod_pep_ledger", None)
            if callable(ensure_ledger):
                ensure_ledger()
        except Exception:  # noqa: BLE001
            pass

        # ----- M20 grava arquivo de log .txt -----
        log_path = ""
        if error_log:
            try:
                base, _ext = os.path.splitext(path)
                ts = _dt_local.datetime.now().strftime("%Y%m%d_%H%M%S")
                log_path = f"{base}_log_importacao_{ts}.txt"
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write("LOG DE ERROS DE IMPORTACAO\n")
                    f.write(f"Arquivo de origem: {path}\n")
                    ts_human = _dt_local.datetime.now().strftime(
                        "%d/%m/%Y %H:%M:%S")
                    f.write(f"Data/Hora: {ts_human}\n\n")
                    f.write(f"Linhas processadas: {len(rows_clean)}\n")
                    f.write(f"Importadas (insert): {imported}\n")
                    f.write(f"Atualizadas (merge): {merged}\n")
                    f.write(f"Puladas (skip): {skipped}\n")
                    f.write(
                        f"Ignoradas por _ no alimentador: "
                        f"{ignorados_underscore}\n"
                    )
                    f.write(
                        f"Ignoradas por permissao: {ignorados_permissao}\n\n"
                    )
                    f.write("--- Detalhes ---\n")
                    for line in error_log:
                        f.write(line + "\n")
            except Exception as exc:  # noqa: BLE001
                # Nao fatal: log nao gravado, mas JS recebe errors[]
                log_path = ""
                errors.append(f"log_path_fail: {exc}")

        # Bloco 5: marca progress como completo (100%)
        _op_set_progress(total_processar, total_processar,
                         "Concluido")
        return {
            "ok": (imported + merged) > 0,
            "cancelled": cancelled_mid,
            "imported": imported,
            "merged": merged,
            "skipped": skipped,
            "ignorados_underscore": ignorados_underscore,
            "ignorados_permissao": ignorados_permissao,
            "duplicadas_count": len(duplicadas),
            "strategy": strategy,
            "total": len(rows_clean),
            "errors": errors,
            "log_path": log_path,
            "error": "",
        }

    def header_export_excel(self) -> dict[str, Any]:
        """Atalho header 'Exportar Excel': delega para export_detalhamento
        sem cods (exporta tudo)."""
        return self.export_detalhamento([])

    def _pick_file_with_filters(self, filter_label: str) -> dict[str, Any]:
        try:
            import webview  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": "", "error": f"pywebview: {exc}"}
        try:
            wins = webview.windows
            if not wins:
                return {"ok": False, "path": "",
                        "error": "janela pywebview nao encontrada"}
            dlg = self._wv_dialog_const("OPEN")
            if dlg is None:
                return {"ok": False, "path": "", "error": "OPEN dialog indisponivel"}
            result = wins[0].create_file_dialog(
                dlg,
                allow_multiple=False,
                file_types=(filter_label, "Todos os arquivos (*.*)"),
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": "", "error": f"file dialog: {exc}"}
        if not result:
            return {"ok": False, "path": "", "error": "cancelado"}
        path = result[0] if isinstance(result, (list, tuple)) else str(result)
        return {"ok": True, "path": path, "error": ""}

    # ==================================================================
    # PARIDADE: gaps identificados no audit runtime/* + core/services/*
    # vs CoplanApi. Cada metodo abaixo delega para uma funcao publica
    # ja existente em runtime/* ou core/services/*. Sem nova logica.
    # ==================================================================

    # --- Fase 1: DB maintenance --------------------------------------

    def db_backup(self, label: Any = "") -> dict[str, Any]:
        """Cria backup timestamped do banco (db.backup_database)."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "path": "", "error": err or "db indisponivel"}
        try:
            label_s = str(label or "").strip() or None
            path = db.backup_database(label=label_s)
        except Exception as exc:  # noqa: BLE001
            friendly = self._friendly_busy_error(exc)
            out: dict[str, Any] = {
                "ok": False, "path": "",
                "error": friendly or f"backup: {exc}",
            }
            if friendly:
                out["blocked"] = "db_busy"
            return out
        if not path:
            return {"ok": False, "path": "", "error": "backup nao criado"}
        return {"ok": True, "path": str(path), "error": ""}

    def db_weekly_backup(self) -> dict[str, Any]:
        """Backup semanal nomeado por ano+semana (db.weekly_backup)."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "path": "", "error": err or "db indisponivel"}
        try:
            path = db.weekly_backup()
        except Exception as exc:  # noqa: BLE001
            friendly = self._friendly_busy_error(exc)
            out: dict[str, Any] = {
                "ok": False, "path": "",
                "error": friendly or f"weekly_backup: {exc}",
            }
            if friendly:
                out["blocked"] = "db_busy"
            return out
        if not path:
            return {"ok": False, "path": "", "error": "weekly backup nao criado"}
        return {"ok": True, "path": str(path), "error": ""}

    def db_normalize_decimal(self) -> dict[str, Any]:
        """Substitui ponto decimal por virgula em todas as colunas
        numericas. (db.normalize_decimal_in_db)"""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel"}
        try:
            db.normalize_decimal_in_db()
        except Exception as exc:  # noqa: BLE001
            friendly = self._friendly_busy_error(exc)
            out: dict[str, Any] = {
                "ok": False, "error": friendly or f"normalize: {exc}",
            }
            if friendly:
                out["blocked"] = "db_busy"
            return out
        return {"ok": True, "error": ""}

    def visualizar_columns_get_config(self) -> dict[str, Any]:
        db, err = self._ensure_db_connected()
        all_cols: list[str] = []
        if not err and db is not None:
            try:
                all_cols = list(db.get_column_names() or [])
            except Exception:  # noqa: BLE001
                all_cols = []
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "all": all_cols, "visible": [], "order": [],
                    "widths": {}, "error": str(exc)}
        ui_state = cfg.get("ui_state") or {}
        visualizar = ui_state.get("visualizar") or {}
        visible = visualizar.get("visible_columns")
        used_default = False
        if not isinstance(visible, list):
            # Fallback para formato legado columns_visible (dict)
            legacy_v = visualizar.get("columns_visible") or {}
            if isinstance(legacy_v, dict):
                visible = [c for c, on in legacy_v.items() if on]
            else:
                visible = None
        # NOVO: se visible vazio, ausente, OU == all (legado "todas
        # marcadas"), aplica a mascara padrao. Detectar "todas marcadas"
        # como inicial e' pratico: a primeira vez que o user abriu o app
        # antes do default ser introduzido, o config era populado com
        # todas as colunas. Tratamos isso como "no preference" =>
        # mostra a mascara default.
        if (not visible) or (
            isinstance(visible, list) and all_cols
            and len(visible) >= len(all_cols)
        ):
            if all_cols:
                visible = [c for c in self.DEFAULT_VIS_COLUMNS
                           if c in all_cols]
                used_default = True
            else:
                visible = list(self.DEFAULT_VIS_COLUMNS)
                used_default = True
        order = visualizar.get("columns_order") or []
        if not isinstance(order, list):
            order = []
        widths = visualizar.get("column_widths") or {}
        if not isinstance(widths, dict):
            widths = {}
        return {
            "ok": True,
            "all": all_cols,
            "visible": list(visible),
            "order": list(order),
            "widths": dict(widths),
            "default_columns": list(self.DEFAULT_VIS_COLUMNS),
            "using_default": used_default,
            "error": "",
        }

    def visualizar_columns_save_config(
        self, payload: Any = None,
    ) -> dict[str, Any]:
        """Persiste visible_columns/columns_order/column_widths.
        Aceita dict { visible: [...], order: [...], widths: {col: px} }."""
        if not isinstance(payload, dict):
            return {"ok": False, "error": "payload nao e dict"}
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"load_config: {exc}"}
        ui_state = cfg.get("ui_state") or {}
        visualizar = ui_state.get("visualizar") or {}
        if "visible" in payload and isinstance(payload["visible"], list):
            visualizar["visible_columns"] = list(payload["visible"])
            visualizar.pop("columns_visible", None)  # legado
        if "order" in payload and isinstance(payload["order"], list):
            visualizar["columns_order"] = list(payload["order"])
        if "widths" in payload and isinstance(payload["widths"], dict):
            # Sanitiza para int
            clean_widths: dict[str, int] = {}
            for k, v in payload["widths"].items():
                try:
                    clean_widths[str(k)] = int(v)
                except (TypeError, ValueError):
                    pass
            visualizar["column_widths"] = clean_widths
        ui_state["visualizar"] = visualizar
        cfg["ui_state"] = ui_state
        try:
            ConfigManager.save_config(cfg, overwrite=True)
        except TypeError:
            # Versao antiga sem 'overwrite' kwarg
            try:
                ConfigManager.save_config(cfg)
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"save: {exc}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return {"ok": True, "error": ""}

    def visualizar_columns_reset(self) -> dict[str, Any]:
        """Limpa toda a config de colunas (volta ao default)."""
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"load_config: {exc}"}
        ui_state = cfg.get("ui_state") or {}
        visualizar = ui_state.get("visualizar") or {}
        for k in ("visible_columns", "columns_visible",
                  "columns_order", "column_widths"):
            visualizar.pop(k, None)
        ui_state["visualizar"] = visualizar
        cfg["ui_state"] = ui_state
        try:
            ConfigManager.save_config(cfg, overwrite=True)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return {"ok": True, "error": ""}

    def db_create_new(self, path: Any = "") -> dict[str, Any]:
        """Cria um banco SQLite vazio no path informado e ativa-o como
        'banco corrente'. Equivalente a create_new_database do desktop:
          1. Abre file save dialog (se path vazio)
          2. db.connect(path) -> cria tabela obras + colunas legadas
          3. Salva config['obras'] = path
          4. Retorna pra recarregar a tabela
        """
        target = str(path or "").strip()
        # Se path nao foi passado, abrir file dialog SAVE
        if not target:
            try:
                import webview  # type: ignore[import-not-found]
                wins = webview.windows
                if not wins:
                    return {"ok": False, "path": "",
                            "error": "janela pywebview nao encontrada"}
                dlg_const = self._wv_dialog_const("SAVE")
                if dlg_const is None:
                    return {"ok": False, "path": "",
                            "error": "SAVE dialog indisponivel"}
                result = wins[0].create_file_dialog(
                    dlg_const,
                    save_filename="novo_banco.db",
                    file_types=("SQLite Database (*.db)",),
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "path": "",
                        "error": f"file dialog: {exc}"}
            if not result:
                return {"ok": False, "path": "", "error": "cancelado"}
            target = (result[0] if isinstance(result, (list, tuple))
                      else str(result))
        if not target:
            return {"ok": False, "path": "", "error": "path vazio"}
        # Garante extensao .db
        if not target.lower().endswith(".db"):
            target = target + ".db"
        # Garante diretorio existente
        try:
            os.makedirs(os.path.dirname(os.path.abspath(target)) or ".",
                        exist_ok=True)
        except OSError as exc:
            return {"ok": False, "path": target,
                    "error": f"mkdir: {exc}"}
        # Conecta (cria tabela vazia + migracoes)
        self._ensure_managers()
        if self._db_manager is None:
            return {"ok": False, "path": target,
                    "error": "DatabaseManager indisponivel"}
        try:
            self._db_manager.connect(target)
            # Limpa pacotes filtrados (set_allowed_pacotes(None) do desktop)
            try:
                self._db_manager.set_allowed_pacotes(None)
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            self._data_state_set(
                "db", "INVALIDADO", path=target,
                error=f"connect: {exc}")
            return {"ok": False, "path": target,
                    "error": f"connect: {exc}"}
        # Salva no config
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
            cfg["obras"] = target
            ConfigManager.save_config(cfg)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": target,
                    "error": f"save_config: {exc}"}
        self._config = None
        self._connected_paths.discard(target)
        self._connected_paths.add(target)
        try:
            self._data_state_set(
                "db", "CARREGADO_VALIDADO", path=target,
                version_token=str(int(os.path.getmtime(target))))
        except OSError:
            pass
        return {"ok": True, "path": target, "error": ""}

    def db_save_as(self, path: Any = "") -> dict[str, Any]:
        """Salva uma copia do banco corrente em outro lugar (backup
        manual). Equivalente a salvar_banco_dados do desktop.
        Usa shutil.copy2 (preserva mtime). NAO troca o banco corrente."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "path": "",
                    "error": err or "db indisponivel"}
        cfg = self._config or {}
        src = str(cfg.get("obras") or "").strip()
        if not src or not os.path.isfile(src):
            return {"ok": False, "path": "",
                    "error": "banco corrente nao encontrado"}
        target = str(path or "").strip()
        if not target:
            try:
                import webview  # type: ignore[import-not-found]
                wins = webview.windows
                if not wins:
                    return {"ok": False, "path": "",
                            "error": "janela pywebview nao encontrada"}
                dlg_const = self._wv_dialog_const("SAVE")
                if dlg_const is None:
                    return {"ok": False, "path": "",
                            "error": "SAVE dialog indisponivel"}
                result = wins[0].create_file_dialog(
                    dlg_const,
                    save_filename=os.path.basename(src),
                    file_types=("SQLite Database (*.db)",),
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "path": "",
                        "error": f"file dialog: {exc}"}
            if not result:
                return {"ok": False, "path": "", "error": "cancelado"}
            target = (result[0] if isinstance(result, (list, tuple))
                      else str(result))
        if not target:
            return {"ok": False, "path": "", "error": "path vazio"}
        if not target.lower().endswith(".db"):
            target = target + ".db"
        if os.path.abspath(target) == os.path.abspath(src):
            return {"ok": False, "path": target,
                    "error": "destino igual a origem"}
        try:
            import shutil  # noqa: PLC0415
            shutil.copy2(src, target)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": target,
                    "error": f"copy: {exc}"}
        return {"ok": True, "path": target, "error": ""}

    def db_export_to(
        self,
        cods: Any = None,
        path: Any = "",
        include_aprovadas: Any = False,
    ) -> dict[str, Any]:
        """Exporta obras selecionadas para um banco destino (cria/sobrescreve).
        Equivalente simplificado a exportar_para_banco do desktop:
          1. Filtra cods (descarta aprovadas se include_aprovadas=False)
          2. Cria/conecta o banco destino (mesmo schema)
          3. Insere cada obra (insert_obra)
        Retorna {ok, path, exported, ignoradas_aprovadas, errors}.
        Aviso: NAO replica toda a logica de _exportar_para_banco_write_phase
        (que valida integridade campo a campo, ganhos, etc.). Para esses
        casos, usar a versao desktop ou estender no futuro."""
        cods_list = [str(c).strip() for c in (cods or []) if str(c or "").strip()]
        if not cods_list:
            return {"ok": False, "path": "", "exported": 0,
                    "ignoradas_aprovadas": 0, "errors": ["cods vazio"]}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "path": "", "exported": 0,
                    "ignoradas_aprovadas": 0,
                    "errors": [err or "db indisponivel"]}
        # Gating aprovadas
        gate = self.gate_aprovadas_for_action(
            cods_list, include_aprovadas=bool(include_aprovadas))
        targets = gate.get("targets") or []
        ignoradas_aprovadas = len(gate.get("aprovadas") or [])
        if not targets:
            return {"ok": False, "path": "", "exported": 0,
                    "ignoradas_aprovadas": ignoradas_aprovadas,
                    "errors": ["sem obras elegiveis (todas aprovadas)"]}
        # Resolve destino
        target = str(path or "").strip()
        if not target:
            try:
                import webview  # type: ignore[import-not-found]
                wins = webview.windows
                if not wins:
                    return {"ok": False, "path": "", "exported": 0,
                            "ignoradas_aprovadas": ignoradas_aprovadas,
                            "errors": ["janela pywebview nao encontrada"]}
                dlg_const = self._wv_dialog_const("SAVE")
                result = wins[0].create_file_dialog(
                    dlg_const,
                    save_filename="export_obras.db",
                    file_types=("SQLite Database (*.db)",),
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "path": "", "exported": 0,
                        "ignoradas_aprovadas": ignoradas_aprovadas,
                        "errors": [f"file dialog: {exc}"]}
            if not result:
                return {"ok": False, "path": "", "exported": 0,
                        "ignoradas_aprovadas": ignoradas_aprovadas,
                        "errors": ["cancelado"]}
            target = (result[0] if isinstance(result, (list, tuple))
                      else str(result))
        if not target.lower().endswith(".db"):
            target = target + ".db"
        # Cria DatabaseManager auxiliar para o destino
        try:
            from runtime.database import DatabaseManager  # noqa: PLC0415
            dest_db = DatabaseManager()
            dest_db.connect(target)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": target, "exported": 0,
                    "ignoradas_aprovadas": ignoradas_aprovadas,
                    "errors": [f"conectar destino: {exc}"]}
        # Le cada obra do banco corrente e insere no destino
        try:
            cols = list(db.get_column_names() or [])
            rows = list(db.fetch_by_cods(targets) or [])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": target, "exported": 0,
                    "ignoradas_aprovadas": ignoradas_aprovadas,
                    "errors": [f"fetch_by_cods: {exc}"]}
        exported = 0
        errors: list[str] = []
        for row in rows:
            try:
                dados = dict(zip(cols, row))
                dest_db.insert_obra(dados)
                exported += 1
            except Exception as exc:  # noqa: BLE001
                cod = str(dados.get("cod") or "?") if "cod" in cols else "?"
                errors.append(f"{cod}: {exc}")
        return {
            "ok": exported > 0,
            "path": target,
            "exported": exported,
            "ignoradas_aprovadas": ignoradas_aprovadas,
            "total_targets": len(targets),
            "errors": errors,
        }

    def db_mark_tecnico_dirty_all(self) -> dict[str, Any]:
        """Marca TODAS as obras como tecnico_dirty='SIM'."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel"}
        try:
            db.mark_tecnico_dirty_all()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"mark_dirty: {exc}"}
        return {"ok": True, "error": ""}

    def db_count_tecnico_dirty(self) -> dict[str, Any]:
        """Quantas obras estao com snapshot tecnico desatualizado."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "count": 0, "error": err or "db indisponivel"}
        try:
            count = int(db.count_tecnico_dirty() or 0)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "count": 0, "error": f"count: {exc}"}
        return {"ok": True, "count": count, "error": ""}

    def db_last_modification_info(self) -> dict[str, Any]:
        """Data + usuario da ultima modificacao no banco."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "data": "", "usuario": "",
                    "error": err or "db indisponivel"}
        try:
            data, usuario = db.get_last_modification_info()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "data": "", "usuario": "",
                    "error": f"last_mod: {exc}"}
        return {"ok": True, "data": str(data or ""),
                "usuario": str(usuario or ""), "error": ""}

    def db_mark_refresh_point(self) -> dict[str, Any]:
        """Marca o instante atual como 'snapshot' do banco. Equivalente
        a _mark_db_refresh_point do EstadoFontesMixin: chamado depois
        de uma leitura completa (list_obras refresh) pra usar de baseline
        em db_check_external_update."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel"}
        try:
            data, usuario = db.get_last_modification_info()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"last_mod: {exc}"}
        self._last_db_refresh_data = str(data or "")
        self._last_db_refresh_user = str(usuario or "")
        self._last_db_modification_warned = ""
        return {
            "ok": True,
            "data": self._last_db_refresh_data,
            "usuario": self._last_db_refresh_user,
        }

    def db_check_external_update(self) -> dict[str, Any]:
        """Compara data_modificacao atual com a snap salva por
        db_mark_refresh_point. Retorna mudou=True se outro usuario
        gravou no banco entre os dois pontos. Equivalente a
        _warn_external_db_update do desktop."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "mudou": False,
                    "error": err or "db indisponivel"}
        try:
            data, usuario = db.get_last_modification_info()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "mudou": False,
                    "error": f"last_mod: {exc}"}
        atual = str(data or "")
        atual_user = str(usuario or "")
        baseline = self._last_db_refresh_data
        if not baseline:
            # Sem snapshot anterior: marca este ponto como baseline
            # (primeira chamada da sessao) e reporta sem mudanca.
            self._last_db_refresh_data = atual
            self._last_db_refresh_user = atual_user
            return {"ok": True, "mudou": False, "data": atual,
                    "usuario": atual_user, "first_call": True}
        mudou = (atual != baseline)
        # Evita avisar 2 vezes pelo mesmo timestamp
        ja_avisado = (mudou and self._last_db_modification_warned == atual)
        if mudou and not ja_avisado:
            self._last_db_modification_warned = atual
        return {
            "ok": True,
            "mudou": mudou,
            "ja_avisado": ja_avisado,
            "data": atual,
            "usuario": atual_user,
            "baseline": baseline,
            "baseline_user": self._last_db_refresh_user,
        }

    def db_next_codigo_item(self, nome_projeto: Any) -> dict[str, Any]:
        """Proximo codigo_item disponivel para um projeto."""
        nome = str(nome_projeto or "").strip()
        if not nome:
            return {"ok": False, "next": 0, "error": "nome_projeto vazio"}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "next": 0, "error": err or "db indisponivel"}
        try:
            nxt = int(db.get_next_codigo_item(nome) or 1)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "next": 0, "error": f"next_item: {exc}"}
        return {"ok": True, "next": nxt, "error": ""}

    def db_exists_codigo_item(
        self, nome_projeto: Any, codigo_item: Any, exclude_cod: Any = None,
    ) -> dict[str, Any]:
        """Verifica se ja existe obra com mesmo (nome_projeto, codigo_item)."""
        nome = str(nome_projeto or "").strip()
        item = str(codigo_item or "").strip()
        if not nome or not item:
            return {"ok": True, "exists": False, "error": ""}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "exists": False,
                    "error": err or "db indisponivel"}
        try:
            exists = bool(
                db.exists_codigo_item(
                    nome, item,
                    exclude_cod=str(exclude_cod) if exclude_cod else None,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "exists": False,
                    "error": f"exists_codigo_item: {exc}"}
        return {"ok": True, "exists": exists, "error": ""}

    # --- Fase 2: COD PEP em lote -------------------------------------

    def cod_pep_gerar_lote(
        self,
        cods: Any = None,
        empresa_sigla: Any = "",
        somente_vazios: Any = True,
        reiniciar_numeracao: Any = False,
    ) -> dict[str, Any]:
        """Gera COD_PEP para varios COD de uma vez (db.gerar_cod_pep_para_cods).
        Retorna {atualizados, ignorados, erros}."""
        if not isinstance(cods, (list, tuple)) or not cods:
            return {"ok": False, "atualizados": 0, "ignorados": 0,
                    "erros": ["cods vazio"]}
        cods_list = [str(c).strip() for c in cods if str(c or "").strip()]
        if not cods_list:
            return {"ok": False, "atualizados": 0, "ignorados": 0,
                    "erros": ["cods vazio"]}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "atualizados": 0, "ignorados": 0,
                    "erros": [err or "db indisponivel"]}
        # Resolve empresa: prioriza o passado, senao usa o config.
        sigla = str(empresa_sigla or "").strip().upper()
        if not sigla:
            try:
                from runtime.database import get_empresa_sigla_from_config
                sigla = get_empresa_sigla_from_config(self._config or None)
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "atualizados": 0, "ignorados": 0,
                        "erros": [f"empresa_sigla nao resolvida: {exc}"]}
        try:
            atualizados, ignorados, erros = db.gerar_cod_pep_para_cods(
                cods_list,
                sigla,
                somente_vazios=bool(somente_vazios),
                reiniciar_numeracao=bool(reiniciar_numeracao),
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atualizados": 0, "ignorados": 0,
                    "erros": [f"gerar_cod_pep_lote: {exc}"]}
        return {
            "ok": True,
            "atualizados": int(atualizados or 0),
            "ignorados": int(ignorados or 0),
            "erros": list(erros or []),
        }

    def cod_pep_preencher_pendentes(self) -> dict[str, Any]:
        """Preenche COD_PEP de obras que ainda nao tem
        (db.preencher_cod_pep_pendentes). Retorna {preenchidos}."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "preenchidos": 0,
                    "error": err or "db indisponivel"}
        try:
            preenchidos = int(db.preencher_cod_pep_pendentes() or 0)
        except Exception as exc:  # noqa: BLE001
            friendly = self._friendly_busy_error(exc)
            out: dict[str, Any] = {
                "ok": False, "preenchidos": 0,
                "error": friendly or f"preencher_pendentes: {exc}",
            }
            if friendly:
                out["blocked"] = "db_busy"
            return out
        return {"ok": True, "preenchidos": preenchidos, "error": ""}

    def cod_pep_zerar(self, confirmacao: Any = "") -> dict[str, Any]:
        """Zera o COD_PEP de TODAS as obras (acao destrutiva de admin).
        Exige confirmacao == 'ZERAR' (trava anti-acidente, espelha o
        'EXCLUIR' da exclusao). Retorna {ok, zerados}."""
        if str(confirmacao or "").strip().upper() != "ZERAR":
            return {"ok": False, "zerados": 0,
                    "error": "confirmacao invalida: digite ZERAR"}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "zerados": 0,
                    "error": err or "db indisponivel"}
        try:
            zerados = int(db.zerar_cod_pep() or 0)
        except Exception as exc:  # noqa: BLE001
            friendly = self._friendly_busy_error(exc)
            out: dict[str, Any] = {
                "ok": False, "zerados": 0,
                "error": friendly or f"zerar_cod_pep: {exc}",
            }
            if friendly:
                out["blocked"] = "db_busy"
            return out
        return {"ok": True, "zerados": zerados, "error": ""}

    # --- Fase 6: CSV import/export -----------------------------------

    def csv_export(self, destino: Any = "") -> dict[str, Any]:
        """Exporta todas as obras para arquivo CSV
        (file_io.exportar_relatorio_csv)."""
        destino_s = str(destino or "").strip()
        if not destino_s:
            # destino padrao: pasta downloads + timestamp
            target = self._default_export_dir()
            fname = (
                f"coplan_obras_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            destino_s = str(target / fname)
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "path": "",
                    "error": err or "db indisponivel"}
        try:
            from runtime.file_io import exportar_relatorio_csv
            ok = exportar_relatorio_csv(db, destino_s)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "path": "", "error": f"csv_export: {exc}"}
        if not ok:
            return {"ok": False, "path": "", "error": "exportacao falhou"}
        return {"ok": True, "path": destino_s, "error": ""}

    def csv_import(self, origem: Any = "") -> dict[str, Any]:
        """Importa CSV para o banco (file_io.carregar_relatorio_csv).
        Retorna {ignorados}."""
        origem_s = str(origem or "").strip()
        if not origem_s:
            return {"ok": False, "ignorados": 0,
                    "error": "origem vazia"}
        if not os.path.isfile(origem_s):
            return {"ok": False, "ignorados": 0,
                    "error": f"arquivo nao existe: {origem_s}"}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "ignorados": 0,
                    "error": err or "db indisponivel"}
        try:
            from runtime.file_io import carregar_relatorio_csv
            ok, ignorados = carregar_relatorio_csv(db, origem_s)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "ignorados": 0,
                    "error": f"csv_import: {exc}"}
        if not ok:
            return {"ok": False, "ignorados": int(ignorados or 0),
                    "error": "importacao falhou"}
        # Reserva no ledger os cod_pep vindos do CSV (idempotente).
        try:
            ensure_ledger = getattr(db, "_ensure_cod_pep_ledger", None)
            if callable(ensure_ledger):
                ensure_ledger()
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "ignorados": int(ignorados or 0), "error": ""}

    def csv_pick_and_import(self) -> dict[str, Any]:
        """Abre FileDialog pra escolher CSV e importa direto."""
        try:
            import webview
            window = webview.windows[0] if webview.windows else None
            if not window:
                return {"ok": False, "ignorados": 0,
                        "error": "janela indisponivel"}
            result = window.create_file_dialog(
                _wv_dialog_const("OPEN"),
                allow_multiple=False,
                file_types=("CSV (*.csv)", "Todos (*.*)"),
            )
            if not result:
                return {"ok": False, "ignorados": 0, "error": "cancelado"}
            path = result[0] if isinstance(result, (list, tuple)) else str(result)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "ignorados": 0,
                    "error": f"file_dialog: {exc}"}
        return self.csv_import(path)
