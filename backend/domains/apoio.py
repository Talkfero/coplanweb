# -*- coding: utf-8 -*-
"""Mixin de dominio "apoio" da CoplanApi (extraido de main_web.py).

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


class ApoioMixin:

    # ------------------------------------------------------------------
    # Apoio (planilha xlsx) -- delega 100% ao SupportFileManager do
    # desktop (codigo5_coplan.SupportFileManager.load_support_file).
    # Cacheia o resultado para nao recarregar a cada API call.
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Apoio DB-backed (2026-05-07): planilha de apoio importada para
    # tabelas apoio_<aba> dentro do mesmo obras.db. Carregamento entre
    # sessoes vem direto do banco (sem reler xlsx). Botao "Atualizar
    # apoio" forca reimportacao.
    # Helpers compartilhados:
    #   _apoio_table_name(sheet)        : sheet -> nome de tabela ASCII safe
    #   _apoio_quote_ident(name)        : escapa identificador SQL com "..."
    #   _apoio_ensure_meta_table(db)    : cria apoio_meta se nao existe
    #   _apoio_meta_dict(db)            : le linha unica de apoio_meta
    #   _apoio_import_xlsx_to_db        : drop+create+insert de todas as abas
    #   _apoio_load_from_db             : reconstroi dict do _apoio_cache
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Helper auxiliar para tabelas extras (apoio_* / cenario_*) sem
    # compartilhar self.conn do DatabaseManager. Cada chamada abre sua
    # propria sqlite3.Connection na thread atual (resolve race quando
    # JS dispara N bridges em paralelo - pywebview WinForms usa thread-
    # pool por bridge call, e self.conn nao e' thread-safe).
    # ------------------------------------------------------------------
    @staticmethod
    def _open_aux_conn(db: Any):
        """Abre conn sqlite3 propria (sem tocar self.conn do DM).
        Devolve (conn, error_str). conn=None se falhar."""
        import sqlite3 as _sqlite3
        try:
            db_path = str(getattr(db, "db_path", "") or "")
        except Exception:  # noqa: BLE001
            db_path = ""
        if not db_path or not os.path.isfile(db_path):
            return None, "db_path indisponivel"
        try:
            conn = _sqlite3.connect(
                db_path, timeout=5.0, check_same_thread=False)
            return conn, ""
        except Exception as exc:  # noqa: BLE001
            return None, f"sqlite3.connect: {exc}"

    @staticmethod
    def _apoio_table_name(sheet_name: Any) -> str:
        """Sanitiza nome de aba do Excel para tabela SQLite ASCII safe.
        Resultado tem prefixo 'apoio_' + lowercase + ascii + underscores."""
        import unicodedata as _ud
        s = str(sheet_name or "").strip()
        if not s:
            return "apoio__unnamed"
        s_norm = _ud.normalize("NFKD", s).encode(
            "ascii", "ignore").decode("ascii")
        s_low = s_norm.lower()
        s_clean = re.sub(r"[^a-z0-9_]+", "_", s_low).strip("_")
        if not s_clean:
            s_clean = "unnamed"
        if s_clean[:1].isdigit():
            s_clean = "_" + s_clean
        return f"apoio_{s_clean}"

    @staticmethod
    def _apoio_quote_ident(name: Any) -> str:
        """Escapa identificador SQL (tabela ou coluna) com aspas duplas.
        Permite nomes originais PT-BR (Tensao, Superintendencia, etc.)
        sem quebrar SQL. Aspas duplas internas viram duplas-duplas."""
        return '"' + str(name).replace('"', '""') + '"'

    @classmethod
    def _apoio_ensure_meta_table(cls, db: Any) -> None:
        """Cria apoio_meta se nao existe. Conn aux thread-safe."""
        conn, _err = cls._open_aux_conn(db)
        if conn is None:
            return
        try:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS apoio_meta ("
                " id INTEGER PRIMARY KEY CHECK (id=1),"
                " last_path TEXT,"
                " last_mtime INTEGER,"
                " last_imported_at TEXT,"
                " last_user TEXT,"
                " sheet_count INTEGER,"
                " sheets_json TEXT,"
                " version TEXT"
                ")"
            )
            conn.commit()
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

    @classmethod
    def _apoio_meta_dict(cls, db: Any) -> dict[str, Any]:
        """Le linha unica de apoio_meta. Conn aux thread-safe."""
        conn, _err = cls._open_aux_conn(db)
        if conn is None:
            return {}
        row = None
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name='apoio_meta'"
            )
            if not cursor.fetchone():
                return {}
            cursor.execute(
                "SELECT last_path, last_mtime, last_imported_at,"
                " last_user, sheet_count, sheets_json, version"
                " FROM apoio_meta WHERE id=1"
            )
            row = cursor.fetchone()
        except Exception:  # noqa: BLE001
            return {}
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        if not row:
            return {}
        import json as _j
        try:
            sheets = _j.loads(row[5]) if row[5] else {}
        except Exception:  # noqa: BLE001
            sheets = {}
        return {
            "last_path":        str(row[0] or ""),
            "last_mtime":       int(row[1] or 0),
            "last_imported_at": str(row[2] or ""),
            "last_user":        str(row[3] or ""),
            "sheet_count":      int(row[4] or 0),
            "sheets":           sheets,
            "version":          str(row[6] or ""),
        }

    def _apoio_import_xlsx_to_db(
        self, db: Any, xlsx_path: str,
    ) -> dict[str, Any]:
        """Le todas as abas do xlsx + cria/recria tabelas apoio_<aba>
        + atualiza apoio_meta. Usa db._with_connection() (paridade com
        outros writers do DatabaseManager) para garantir conn aberta
        durante todo o trabalho. Sem isso, db.conn pode ser None apos
        boot (quando connect() fecha a conn ao sair do _with_connection)."""
        import pandas as _pd
        import getpass as _gp
        import json as _j
        print(f"[apoio] importing xlsx: {xlsx_path}", file=sys.stderr)
        try:
            sheets = _pd.read_excel(
                xlsx_path, sheet_name=None, dtype=str)
        except Exception as exc:  # noqa: BLE001
            print(f"[apoio] read_excel falhou: {exc}", file=sys.stderr)
            return {"ok": False, "error": f"read_excel: {exc}",
                    "sheet_count": 0}
        print(f"[apoio] {len(sheets)} aba(s) lidas: "
              f"{list(sheets.keys())}", file=sys.stderr)
        sheet_map: dict[str, str] = {}
        conn, err = self._open_aux_conn(db)
        if conn is None:
            return {"ok": False, "error": err or "conn indisponivel",
                    "sheet_count": 0}
        try:
            cursor = conn.cursor()
            # Garante apoio_meta com a conn ativa.
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS apoio_meta ("
                " id INTEGER PRIMARY KEY CHECK (id=1),"
                " last_path TEXT,"
                " last_mtime INTEGER,"
                " last_imported_at TEXT,"
                " last_user TEXT,"
                " sheet_count INTEGER,"
                " sheets_json TEXT,"
                " version TEXT"
                ")"
            )
            for sheet_name, df in (sheets or {}).items():
                df = df.fillna("")
                table = self._apoio_table_name(sheet_name)
                sheet_map[str(sheet_name)] = table
                cursor.execute(
                    f'DROP TABLE IF EXISTS '
                    f'{self._apoio_quote_ident(table)}'
                )
                cols = [str(c) for c in df.columns]
                if not cols:
                    cursor.execute(
                        f'CREATE TABLE '
                        f'{self._apoio_quote_ident(table)}'
                        ' (_empty TEXT)'
                    )
                    continue
                col_defs = ", ".join(
                    f"{self._apoio_quote_ident(c)} TEXT" for c in cols
                )
                cursor.execute(
                    f'CREATE TABLE '
                    f'{self._apoio_quote_ident(table)}'
                    f' ({col_defs})'
                )
                if len(df) == 0:
                    continue
                placeholders = ", ".join(["?"] * len(cols))
                col_list = ", ".join(
                    self._apoio_quote_ident(c) for c in cols
                )
                rows_to_insert = [
                    tuple("" if v is None else str(v) for v in r)
                    for r in df.values.tolist()
                ]
                cursor.executemany(
                    f'INSERT INTO '
                    f'{self._apoio_quote_ident(table)}'
                    f' ({col_list}) VALUES ({placeholders})',
                    rows_to_insert,
                )
                print(
                    f"[apoio]   {sheet_name} -> {table} "
                    f"({len(rows_to_insert)} linhas, {len(cols)} cols)",
                    file=sys.stderr,
                )
            # Atualiza apoio_meta (DELETE+INSERT id=1)
            try:
                mtime = int(os.path.getmtime(xlsx_path))
            except OSError:
                mtime = 0
            try:
                user = _gp.getuser() or "?"
            except Exception:  # noqa: BLE001
                user = "?"
            cursor.execute("DELETE FROM apoio_meta WHERE id=1")
            cursor.execute(
                "INSERT INTO apoio_meta (id, last_path, last_mtime,"
                " last_imported_at, last_user, sheet_count,"
                " sheets_json, version)"
                " VALUES (1, ?, ?, ?, ?, ?, ?, ?)",
                (
                    xlsx_path, mtime,
                    datetime.now().isoformat(timespec="seconds"),
                    user, len(sheet_map), _j.dumps(sheet_map),
                    APP_VERSION,
                ),
            )
            conn.commit()
            print(
                f"[apoio] commit ok: {len(sheet_map)} tabela(s)"
                f" criadas",
                file=sys.stderr,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[apoio] import falhou: {exc!r}", file=sys.stderr)
            return {"ok": False, "error": f"import_to_db: {exc}",
                    "sheet_count": 0}
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        return {
            "ok": True, "error": "",
            "sheet_count": len(sheet_map),
            "sheets":      sheet_map,
            "path":        xlsx_path,
        }

    def _apoio_load_from_db(self, db: Any) -> dict[str, Any]:
        """Le tabelas apoio_apoio + apoio_modulo do banco e reconstroi
        o dict no shape esperado pelo _apoio_cache. Devolve {} quando
        nao ha apoio importado (banco virgem ou tabelas faltando).
        Usa db._with_connection() para garantir conn aberta."""
        meta = self._apoio_meta_dict(db)
        if not meta or not meta.get("last_path"):
            return {}
        import pandas as _pd
        apoio_tab = self._apoio_table_name("apoio")
        modulo_tab = self._apoio_table_name("modulo")
        conn, _err = self._open_aux_conn(db)
        if conn is None:
            return {}
        try:
            df_apoio = _pd.read_sql_query(
                f'SELECT * FROM {self._apoio_quote_ident(apoio_tab)}',
                conn,
            )
            df_modulo = _pd.read_sql_query(
                f'SELECT * FROM {self._apoio_quote_ident(modulo_tab)}',
                conn,
            )
        except Exception:  # noqa: BLE001
            return {}
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            from core.services.apoio_service import (  # type: ignore[import-not-found]
                carregar_dados_apoio_from_dfs,
            )
            from core.exceptions import ApoioFileError  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001
            return {}
        try:
            dados = carregar_dados_apoio_from_dfs(df_apoio, df_modulo)
        except ApoioFileError:
            return {}
        except Exception:  # noqa: BLE001
            return {}
        # Mesmo shape que SupportFileManager.load_support_file devolve.
        dados_alim_dict = {
            nome: {
                "TENSÃO":           d.tensao,
                "REGIONAL":         d.regional,
                "SUPERINTENDÊNCIA": d.superintendencia,
                "SE":               d.se,
            }
            for nome, d in dados.dados_alimentador.items()
        }
        return {
            "alimentadores":              list(dados.alimentadores),
            "dados_alimentador":          dados_alim_dict,
            "projetos_investimento":      list(dados.projetos_investimento),
            "caracteristicas":            list(dados.caracteristicas),
            "nomes_projetos_pre_definidos": list(dados.nomes_projetos),
            "modulos": {
                chave: m.valor for chave, m in dados.modulos.items()
            },
        }

    def _load_apoio_into_manager(
        self, path: str = "", *, force_reload: bool = False,
    ) -> dict[str, Any]:
        """Hidrata self._apoio_cache. Ordem de tentativa:
            1. Cache hit em memoria (mesmo path) — retorno imediato
            2. (se nao force_reload) tabelas apoio_* no banco — DB-backed
            3. Le xlsx em ``path`` + importa para o banco + hidrata cache

        Idempotente: chamado sem ``path`` no boot tenta apenas
        passos 1 e 2. ``force_reload=True`` (botao "Atualizar apoio")
        sempre relê o xlsx + reimporta o banco.
        """
        if self._support_manager is None:
            self._ensure_managers()
        if self._support_manager is None:
            return {"ok": False, "error": "support_manager indisponivel"}

        def _shape(cache: dict[str, Any], src_path: str,
                   source: str, cached: bool) -> dict[str, Any]:
            return {
                "ok": True, "error": "", "path": src_path,
                "alimentadores":     list(cache.get("alimentadores") or []),
                "caracteristicas":   list(cache.get("caracteristicas") or []),
                "projetos_investimento": list(
                    cache.get("projetos_investimento") or []),
                "nomes_projetos_pre_definidos": list(
                    cache.get("nomes_projetos_pre_definidos") or []),
                "modulos_count":     len(cache.get("modulos") or {}),
                "source":            source,
                "cached":            cached,
            }

        # ---- 1. Cache hit em memoria ----
        if (not force_reload
                and self._apoio_path_loaded == path
                and getattr(self, "_apoio_cache", None)):
            return _shape(self._apoio_cache, path, "cache", True)

        # ---- 2. DB-backed (sem path obrigatorio) ----
        # Quando boot chama sem path, tenta hidratar do banco direto.
        if not force_reload:
            db, _err = self._ensure_db_connected()
            if db is not None:
                cached = self._apoio_load_from_db(db)
                if cached:
                    self._apoio_cache = cached
                    meta = self._apoio_meta_dict(db)
                    self._apoio_path_loaded = str(meta.get("last_path") or "")
                    self._data_state_set(
                        "apoio", "CARREGADO_VALIDADO",
                        path=self._apoio_path_loaded,
                        version_token=str(meta.get("last_mtime") or 0))
                    return _shape(cached, self._apoio_path_loaded, "db", False)

        # ---- 3. Le xlsx + importa para o banco ----
        if not path:
            self._data_state_set(
                "apoio", "INVALIDADO", path="",
                error="apoio nao importado e path nao fornecido")
            return {"ok": False,
                    "error": "apoio nao importado: forneca xlsx"}
        try:
            sucesso, dados = self._support_manager.load_support_file(path)
        except Exception as exc:  # noqa: BLE001
            self._data_state_set(
                "apoio", "INVALIDADO", path=path,
                error=f"load_support_file: {exc}")
            return {"ok": False, "error": f"load_support_file: {exc}"}
        if not sucesso:
            self._apoio_cache = {}
            self._apoio_path_loaded = ""
            self._data_state_set(
                "apoio", "INVALIDADO", path=path,
                error="planilha de apoio invalida")
            return {"ok": False, "error": "planilha de apoio invalida"}
        self._apoio_cache = dados or {}
        self._apoio_path_loaded = path
        try:
            mtime = int(os.path.getmtime(path))
        except OSError:
            mtime = 0
        self._data_state_set(
            "apoio", "CARREGADO_VALIDADO", path=path,
            version_token=str(mtime))
        # Importa para o banco (propaga erro: usuario precisa saber).
        import_err = ""
        import_sheets = 0
        try:
            db, db_err = self._ensure_db_connected()
            if db is None:
                import_err = (
                    db_err or "banco nao conectado - tabelas apoio_*"
                    " nao criadas"
                )
            else:
                imp = self._apoio_import_xlsx_to_db(db, path)
                if imp.get("ok"):
                    import_sheets = int(imp.get("sheet_count") or 0)
                else:
                    import_err = str(imp.get("error") or
                                     "import retornou not-ok")
        except Exception as exc:  # noqa: BLE001
            import_err = f"_apoio_import_xlsx_to_db: {exc}"
            print(f"[main_web] {import_err}", file=sys.stderr)
        result = _shape(self._apoio_cache, path, "xlsx", False)
        result["import_sheets"] = import_sheets
        if import_err:
            # Mantem ok=True (cache em memoria carregou) mas sinaliza
            # falha de persistencia para o JS toastar warning.
            result["import_warning"] = import_err
        return result

    def load_apoio(self, path: Any = "") -> dict[str, Any]:
        """API publica DB-backed (2026-05-07):
          * ``path`` vazio: hidrata do banco. Sem fallback xlsx.
            Se tabelas apoio_* nao existem, retorna erro pedindo
            'Atualizar apoio'.
          * ``path`` informado: importa xlsx + popula tabelas apoio_*
            + salva path no config. Esta e a UNICA rota que le xlsx
            (junto com apoio_reload_from_xlsx*)."""
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}"}
        self._ensure_managers()
        target = str(path or "").strip()
        # Sem path: SEMPRE banco (sem fallback xlsx).
        if not target:
            r0 = self._load_apoio_into_manager("")
            if r0.get("ok"):
                return r0
            return {"ok": False, "error":
                    "apoio nao importado: use 'Atualizar apoio' em"
                    " Configuracoes > Geral"}
        if not os.path.exists(target):
            return {"ok": False, "error": f"arquivo nao encontrado: {target}"}
        r = self._load_apoio_into_manager(target)
        if r.get("ok"):
            try:
                ConfigManager.save_config({"apoio": target})
                self._config = None
            except Exception as exc:  # noqa: BLE001
                print(f"[main_web] save_config(apoio) falhou: {exc}",
                      file=sys.stderr)
        return r

    # ------------------------------------------------------------------
    # Apoio DB-backed (2026-05-07): bridges para o JS consumir info
    # sobre a importacao + forcar reload sob demanda.
    # ------------------------------------------------------------------
    def apoio_meta(self) -> dict[str, Any]:
        """Devolve info da ultima importacao da planilha de apoio para
        o banco. Shape: {ok, last_path, last_imported_at, last_user,
        sheet_count, sheets, hidratado}.

        ``hidratado`` indica se o cache em memoria esta populado a
        partir das tabelas apoio_* (i.e. nao precisa abrir xlsx)."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel",
                    "hidratado": bool(self._apoio_cache)}
        try:
            meta = self._apoio_meta_dict(db)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc),
                    "hidratado": bool(self._apoio_cache)}
        return {
            "ok": True, "error": "",
            "last_path":         meta.get("last_path", ""),
            "last_mtime":        meta.get("last_mtime", 0),
            "last_imported_at":  meta.get("last_imported_at", ""),
            "last_user":         meta.get("last_user", ""),
            "sheet_count":       meta.get("sheet_count", 0),
            "sheets":            meta.get("sheets", {}),
            "version":           meta.get("version", ""),
            "hidratado":         bool(self._apoio_cache),
        }

    def apoio_reload_from_xlsx(self, path: Any = "") -> dict[str, Any]:
        """Forca reimportacao do xlsx + reescrita das tabelas apoio_*.
        Path vazio: usa apoio_meta.last_path. Sincrono."""
        target = str(path or "").strip()
        if not target:
            db, _err = self._ensure_db_connected()
            if db is not None:
                meta = self._apoio_meta_dict(db)
                target = str(meta.get("last_path") or "")
        if not target:
            return {"ok": False, "error":
                    "nenhum xlsx conhecido - selecione um arquivo"}
        if not os.path.isfile(target):
            return {"ok": False,
                    "error": f"arquivo nao encontrado: {target}"}
        return self._load_apoio_into_manager(target, force_reload=True)

    def apoio_reload_from_xlsx_async(self, path: Any = "") -> dict[str, Any]:
        """Versao async (worker thread + progress, reusa Bloco 5).
        JS abre modal de progresso e polla progress_state()."""
        target = str(path or "").strip()
        if not target:
            db, _err = self._ensure_db_connected()
            if db is not None:
                meta = self._apoio_meta_dict(db)
                target = str(meta.get("last_path") or "")
        if not target:
            return {"ok": False, "started": False,
                    "error": "nenhum xlsx conhecido"}
        if not os.path.isfile(target):
            return {"ok": False, "started": False,
                    "error": f"arquivo nao encontrado: {target}"}
        with _OP_LOCK:
            if not _OP_STATE.get("finished"):
                return {"ok": False, "started": False,
                        "error": "outra operacao em andamento"}
        op_id = _op_reset(
            f"Importando apoio ({os.path.basename(target)})...")

        def _worker():
            try:
                _op_set_progress(0, 1, "Lendo xlsx...")
                res = self._load_apoio_into_manager(
                    target, force_reload=True)
                _op_set_progress(1, 1, "Concluido")
                _op_finish(result=res, error="")
            except Exception as exc:  # noqa: BLE001
                _op_finish(result=None, error=f"worker: {exc}")

        t = threading.Thread(
            target=_worker, daemon=True,
            name=f"coplan-apoio-reload-{op_id}",
        )
        t.start()
        return {"ok": True, "started": True, "op_id": op_id, "error": ""}

    def pick_and_load_apoio(self) -> dict[str, Any]:
        """Atalho: file dialog + load_apoio. Usado pelo botao
        'Procurar...' do card Empresa quando o usuario quer trocar."""
        picked = self.pick_apoio_file()
        if not picked.get("ok"):
            return picked
        return self.load_apoio(picked.get("path", ""))

    def get_apoio_state(self) -> dict[str, Any]:
        """Estado atual do apoio: caminho carregado + counts. Util pro
        JS verificar se ja tem dado disponivel."""
        cache = getattr(self, "_apoio_cache", None) or {}
        return {
            "ok": bool(cache),
            "path": getattr(self, "_apoio_path_loaded", "") or "",
            "alimentadores_count": len(cache.get("alimentadores") or []),
            "caracteristicas_count": len(cache.get("caracteristicas") or []),
            "projetos_investimento_count": len(
                cache.get("projetos_investimento") or []),
            "nomes_projetos_count": len(
                cache.get("nomes_projetos_pre_definidos") or []),
            "modulos_count": len(cache.get("modulos") or {}),
        }

    # --- Fase 4: Apoio listings completas ----------------------------

    def _apoio_cache_dict(self) -> dict[str, Any]:
        """Devolve _apoio_cache, hidratando do banco se vazio.
        Centraliza leitura de apoio para todas as bridges apoio_get_*."""
        cache = getattr(self, "_apoio_cache", None) or {}
        if cache:
            return cache
        # Tenta hidratar do banco
        db, _err = self._ensure_db_connected()
        if db is None:
            return {}
        loaded = self._apoio_load_from_db(db)
        if loaded:
            self._apoio_cache = loaded
            meta = self._apoio_meta_dict(db)
            self._apoio_path_loaded = str(meta.get("last_path") or "")
            return loaded
        return {}

    def apoio_get_projetos_investimento(self) -> dict[str, Any]:
        """Lista de projetos de investimento (DB-backed via apoio_apoio).
        Use 'Atualizar apoio' em Configuracoes para popular."""
        cache = self._apoio_cache_dict()
        items = list(cache.get("projetos_investimento") or [])
        return {"ok": True, "items": items, "error": ""}

    def apoio_get_caracteristicas(self) -> dict[str, Any]:
        """Lista de caracteristicas (DB-backed via apoio_apoio)."""
        cache = self._apoio_cache_dict()
        items = list(cache.get("caracteristicas") or [])
        return {"ok": True, "items": items, "error": ""}

    def apoio_get_nomes_projetos(self) -> dict[str, Any]:
        """Lista de nomes de projeto pre-definidos (DB-backed)."""
        cache = self._apoio_cache_dict()
        items = list(cache.get("nomes_projetos_pre_definidos") or [])
        return {"ok": True, "items": items, "error": ""}

    def apoio_clear(self) -> dict[str, Any]:
        """Limpa apenas o cache em memoria (forca proxima leitura a
        re-hidratar do banco via _apoio_cache_dict). NAO apaga as
        tabelas apoio_* do banco -- use 'Atualizar apoio' para
        reescrever."""
        try:
            self._apoio_cache = {}
            self._apoio_path_loaded = ""
            # support_manager.clear_data tambem zera self.dados em
            # memoria (fallback para a rota force_reload=True).
            if self._support_manager is not None:
                try:
                    self._support_manager.clear_data()
                except Exception:  # noqa: BLE001
                    pass
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"clear: {exc}"}
        return {"ok": True, "error": ""}
