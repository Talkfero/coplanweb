# -*- coding: utf-8 -*-
"""Mixin de dominio "cenarios" da CoplanApi (extraido de main_web.py).

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


class CenariosMixin:

    # ------------------------------------------------------------------
    # Cenarios DB-backed (2026-05-08): overrides isolados por cenario
    #
    # Tabelas envolvidas (3):
    #   * cenarios_meta            (criada pelo CAPEX): metadados
    #   * cenarios_obras           (criada pelo CAPEX): cod -> ano_final
    #   * cenario_obras_overrides  (criada por nos):    diffs por coluna
    #
    # Quando cenario X esta ativo (config['cenario_ativo']):
    #   - Visualizar mostra APENAS obras com cod em cenarios_obras WHERE
    #     cenario_nome=X
    #   - Leituras aplicam overrides: cada coluna pode ter valor distinto
    #     do que esta em obras (sem nunca tocar obras)
    #   - Save_obra grava o diff em cenario_obras_overrides; obras nunca
    #     muda enquanto cenario ativo
    #   - Operacoes massa (excluir, atualizar valor, marcar correcao) sao
    #     bloqueadas com mensagem clara
    #
    # Referencia: CAPEX define cenarios_meta + cenarios_obras com schema
    # fixo. Ver apps/capex/web/main_web.py:521+ (constantes
    # SCENARIO_METADATA_TABLE = "cenarios_meta", SCENARIO_OBRAS_TABLE =
    # "cenarios_obras").
    # ------------------------------------------------------------------
    @classmethod
    def _cenario_ensure_overrides_table(cls, db: Any) -> None:
        """Cria cenario_obras_overrides. Conn aux thread-safe."""
        conn, _err = cls._open_aux_conn(db)
        if conn is None:
            return
        try:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS cenario_obras_overrides ("
                " cenario_nome TEXT NOT NULL,"
                " cod TEXT NOT NULL,"
                " coluna TEXT NOT NULL,"
                " valor TEXT,"
                " atualizado_em TEXT,"
                " atualizado_por TEXT,"
                " PRIMARY KEY (cenario_nome, cod, coluna)"
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

    def _cenario_active_name(self) -> str:
        """Le config['cenario_ativo']. '' = sem cenario ativo.

        FIX 2026-05-08: cenario_active_set invalida self._config (=None)
        para refletir mudancas de outros campos. Aqui recarregamos do
        disco quando vazio, senao o cenario salvo nao seria visto pelas
        chamadas subsequentes (filtro de obras, save_obra, etc.)."""
        if self._config is None:
            try:
                self._reload_config()
            except Exception:  # noqa: BLE001
                pass
        cfg = self._config or {}
        return str(cfg.get("cenario_ativo") or "").strip()

    def _cenario_cod_set(
        self, db: Any, cenario_nome: str,
    ) -> tuple[set[str], dict[str, Any]]:
        """Le cenarios_obras para um cenario, retornando:
            ({cod1, cod2, ...}, {cod -> {ano_final, ano_origem}})
        Vazio se tabela nao existe ou cenario sem obras."""
        if not cenario_nome:
            return set(), {}
        conn, _err = self._open_aux_conn(db)
        if conn is None:
            return set(), {}
        rows = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name='cenarios_obras'"
            )
            if not cursor.fetchone():
                return set(), {}
            cursor.execute(
                "SELECT cod, ano_final, ano_origem"
                " FROM cenarios_obras WHERE cenario_nome = ?",
                (cenario_nome,),
            )
            rows = cursor.fetchall() or []
        except Exception:  # noqa: BLE001
            return set(), {}
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        cod_set: set[str] = set()
        info: dict[str, Any] = {}
        for r in rows:
            c = str(r[0] or "").strip()
            if not c:
                continue
            cod_set.add(c)
            info[c] = {
                "ano_final":  int(r[1]) if r[1] is not None else None,
                "ano_origem": int(r[2]) if r[2] is not None else None,
            }
        return cod_set, info

    def _cenario_overrides_map(
        self, db: Any, cenario_nome: str,
    ) -> dict[str, dict[str, str]]:
        """Le cenario_obras_overrides retornando {cod -> {coluna -> valor}}."""
        if not cenario_nome:
            return {}
        self._cenario_ensure_overrides_table(db)
        out: dict[str, dict[str, str]] = {}
        conn, _err = self._open_aux_conn(db)
        if conn is None:
            return {}
        rows = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT cod, coluna, valor FROM cenario_obras_overrides"
                " WHERE cenario_nome = ?",
                (cenario_nome,),
            )
            rows = cursor.fetchall() or []
        except Exception:  # noqa: BLE001
            return {}
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        for r in rows:
            cod = str(r[0] or "").strip()
            col = str(r[1] or "").strip()
            val = "" if r[2] is None else str(r[2])
            if not cod or not col:
                continue
            out.setdefault(cod, {})[col] = val
        return out

    def _cenario_apply_to_row(
        self,
        row: list[Any] | tuple[Any, ...],
        cols: list[str],
        cod: str,
        cen_info: dict[str, Any],
        overrides: dict[str, str],
    ) -> list[Any]:
        """Devolve uma copia de ``row`` com:
        - ano_ substituido por cenarios_obras.ano_final (se houver)
        - cada coluna em overrides substituida pelo valor do override
        Sem mutar a row original."""
        new_row = list(row)
        # ano_final do cenario tem prioridade quando NAO ha override
        # explicito de ano_ em cenario_obras_overrides.
        ano_final = (cen_info or {}).get("ano_final")
        if ano_final is not None:
            try:
                idx_ano = cols.index("ano_")
                if "ano_" not in overrides:
                    new_row[idx_ano] = str(ano_final)
            except ValueError:
                pass
        # Aplica overrides genericos
        for col_name, val in (overrides or {}).items():
            try:
                idx_col = cols.index(col_name)
                new_row[idx_col] = val
            except ValueError:
                continue
        return new_row

    def _apply_cenario_to_rows(
        self, db: Any, raw_rows: list[Any], cols: list[str],
    ) -> list[Any]:
        """Aplica cenario ativo a um conjunto de rows ja fetched:
        restringe aos CODs do cenario e aplica overrides. Idempotente:
        sem cenario ativo devolve raw_rows inalterado. Usado pelos
        export_* para garantir paridade com get_obras."""
        cen_nome = self._cenario_active_name()
        if not cen_nome:
            return list(raw_rows)
        try:
            cod_set, cen_info = self._cenario_cod_set(db, cen_nome)
            ovmap = self._cenario_overrides_map(db, cen_nome)
        except Exception:  # noqa: BLE001
            return list(raw_rows)
        if not cod_set:
            # cenario com 0 obras (ou tabelas inexistentes)
            return []
        try:
            idx_cod = cols.index("cod")
        except ValueError:
            return list(raw_rows)
        filtered: list[Any] = []
        for r in raw_rows:
            cod_r = str(r[idx_cod] if idx_cod < len(r) else "").strip()
            if cod_r not in cod_set:
                continue
            filtered.append(self._cenario_apply_to_row(
                r, cols, cod_r,
                cen_info.get(cod_r) or {},
                ovmap.get(cod_r) or {},
            ))
        return filtered

    # -------- Bridges publicas --------

    def cenario_list(self) -> dict[str, Any]:
        """Lista cenarios disponiveis (le cenarios_meta + count obras).
        Devolve [{nome, descricao, total_obras, criado_em, criado_por,
        atualizado_em, atualizado_por, solicitado_em}, ...] ordenado
        por atualizado_em desc.

        Vazio quando o CAPEX nao criou tabelas no banco ainda."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "cenarios": [], "error": err or "db"}
        conn, err_open = self._open_aux_conn(db)
        if conn is None:
            return {"ok": True, "cenarios": [], "error": err_open or ""}
        rows = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
                " AND name='cenarios_meta'"
            )
            if not cursor.fetchone():
                return {"ok": True, "cenarios": [], "error": ""}
            cursor.execute(
                "SELECT nome, descricao, solicitado_em, criado_em,"
                " criado_por, atualizado_em, atualizado_por,"
                " total_obras"
                " FROM cenarios_meta"
                " ORDER BY COALESCE(atualizado_em, criado_em) DESC"
            )
            rows = cursor.fetchall() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "cenarios": [], "error": str(exc)}
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        out = []
        for r in rows:
            out.append({
                "nome":          str(r[0] or ""),
                "descricao":     str(r[1] or ""),
                "solicitado_em": str(r[2] or ""),
                "criado_em":     str(r[3] or ""),
                "criado_por":    str(r[4] or ""),
                "atualizado_em": str(r[5] or ""),
                "atualizado_por": str(r[6] or ""),
                "total_obras":   int(r[7] or 0),
            })
        return {"ok": True, "cenarios": out, "error": ""}

    def cenario_active_get(self) -> dict[str, Any]:
        """Devolve {ativo: nome, ano_final_count, overrides_count}.
        ativo='' quando nenhum cenario esta ativo."""
        nome = self._cenario_active_name()
        if not nome:
            return {"ok": True, "ativo": "", "error": ""}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": True, "ativo": nome, "error": err or "",
                    "ano_final_count": 0, "overrides_count": 0}
        cod_set, _info = self._cenario_cod_set(db, nome)
        ovmap = self._cenario_overrides_map(db, nome)
        return {
            "ok": True, "ativo": nome, "error": "",
            "ano_final_count": len(cod_set),
            "overrides_count": sum(len(v) for v in ovmap.values()),
        }

    def cenario_active_set(self, nome: Any = "") -> dict[str, Any]:
        """Ativa ou desativa cenario. ``nome`` vazio = desativa.
        Salva em config['cenario_ativo'] persistente."""
        try:
            from codigo5_coplan import ConfigManager  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}"}
        nome_s = str(nome or "").strip()
        # Valida que o cenario existe (se nao vazio)
        if nome_s:
            r = self.cenario_list()
            if r.get("ok"):
                nomes = {c.get("nome") for c in (r.get("cenarios") or [])}
                if nome_s not in nomes:
                    return {"ok": False,
                            "error": f"cenario nao encontrado: {nome_s}"}
        try:
            ConfigManager.save_config({"cenario_ativo": nome_s})
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        # Recarrega config (em vez de so invalidar) para que
        # _cenario_active_name veja o novo valor imediatamente
        # mesmo se chamadas concorrentes ja terem feito
        # `cfg = self._config or {}` antes do reload.
        try:
            self._reload_config()
        except Exception:  # noqa: BLE001
            self._config = None
        if nome_s:
            return {"ok": True, "ativo": nome_s, "error": ""}
        return {"ok": True, "ativo": "", "error": ""}

    def cenario_get_overrides(
        self, nome: Any = "", cod: Any = "",
    ) -> dict[str, Any]:
        """Devolve overrides salvos. Se cod informado, filtra. Se nome
        vazio, usa o cenario ativo."""
        nome_s = str(nome or "").strip() or self._cenario_active_name()
        if not nome_s:
            return {"ok": False, "error": "nenhum cenario informado",
                    "items": []}
        cod_s = str(cod or "").strip()
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db", "items": []}
        self._cenario_ensure_overrides_table(db)
        conn, err_open = self._open_aux_conn(db)
        if conn is None:
            return {"ok": False, "error": err_open or "conn", "items": []}
        rows = []
        try:
            cursor = conn.cursor()
            if cod_s:
                cursor.execute(
                    "SELECT cod, coluna, valor, atualizado_em,"
                    " atualizado_por FROM cenario_obras_overrides"
                    " WHERE cenario_nome=? AND cod=?"
                    " ORDER BY coluna",
                    (nome_s, cod_s),
                )
            else:
                cursor.execute(
                    "SELECT cod, coluna, valor, atualizado_em,"
                    " atualizado_por FROM cenario_obras_overrides"
                    " WHERE cenario_nome=?"
                    " ORDER BY cod, coluna",
                    (nome_s,),
                )
            rows = cursor.fetchall() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "items": []}
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        items = [
            {"cod": str(r[0] or ""),
             "coluna": str(r[1] or ""),
             "valor": str(r[2] or ""),
             "atualizado_em": str(r[3] or ""),
             "atualizado_por": str(r[4] or "")}
            for r in rows
        ]
        return {"ok": True, "items": items, "cenario": nome_s,
                "count": len(items), "error": ""}

    def cenario_clear_overrides(
        self,
        nome: Any = "",
        cod: Any = "",
        coluna: Any = "",
    ) -> dict[str, Any]:
        """Remove overrides. Se ``coluna`` informado, so essa coluna.
        Se ``cod`` informado, so dessa obra. Sem coluna nem cod,
        zera TODOS os overrides do cenario."""
        nome_s = str(nome or "").strip() or self._cenario_active_name()
        if not nome_s:
            return {"ok": False, "error": "nenhum cenario informado"}
        cod_s = str(cod or "").strip()
        col_s = str(coluna or "").strip()
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db"}
        self._cenario_ensure_overrides_table(db)
        conn, err_open = self._open_aux_conn(db)
        if conn is None:
            return {"ok": False, "error": err_open or "conn"}
        removed = 0
        try:
            cursor = conn.cursor()
            if cod_s and col_s:
                cursor.execute(
                    "DELETE FROM cenario_obras_overrides"
                    " WHERE cenario_nome=? AND cod=? AND coluna=?",
                    (nome_s, cod_s, col_s),
                )
            elif cod_s:
                cursor.execute(
                    "DELETE FROM cenario_obras_overrides"
                    " WHERE cenario_nome=? AND cod=?",
                    (nome_s, cod_s),
                )
            else:
                cursor.execute(
                    "DELETE FROM cenario_obras_overrides"
                    " WHERE cenario_nome=?",
                    (nome_s,),
                )
            removed = cursor.rowcount
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        return {"ok": True, "removed": int(removed or 0),
                "cenario": nome_s, "error": ""}

    def cenario_obras_branches(
        self, cods: Any = None,
    ) -> dict[str, Any]:
        """Para cada cod (opcional, padrao todos), devolve lista de
        cenarios onde a obra TEM ALGUMA versao diferente.

        Une 2 fontes:
        - cenarios_obras (CAPEX): obra pertence ao cenario (ano_final
          pode diferir de ano_origem; sempre conta como versao).
        - cenario_obras_overrides (COPLAN): editou outros campos.

        Resposta: {ok, items: {cod: [{cenario, campos: [str,...],
                  atualizado_em, atualizado_por,
                  ano_final, ano_origem}, ...]}}."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "items": {}, "error": err or "db"}
        cod_list: list[str] = []
        if isinstance(cods, (list, tuple)):
            cod_list = [
                str(c).strip() for c in cods if str(c or "").strip()
            ]
        conn, _err = self._open_aux_conn(db)
        if conn is None:
            return {"ok": True, "items": {}, "error": ""}
        # grouped: cod -> cenario_nome -> dict
        grouped: dict[str, dict[str, dict[str, Any]]] = {}
        try:
            cursor = conn.cursor()

            def _table_exists(name: str) -> bool:
                cursor.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table'"
                    " AND name=?",
                    (name,),
                )
                return cursor.fetchone() is not None

            # ----- 1) cenarios_obras (do CAPEX) -----
            if _table_exists("cenarios_obras"):
                if cod_list:
                    if len(cod_list) > 900:
                        cod_list = cod_list[:900]
                    placeholders = ",".join(["?"] * len(cod_list))
                    cursor.execute(
                        f"SELECT co.cod, co.cenario_nome, co.ano_final,"
                        f" co.ano_origem, COALESCE(cm.atualizado_em,"
                        f" cm.criado_em, '') AS em,"
                        f" COALESCE(cm.atualizado_por,"
                        f" cm.criado_por, '') AS por"
                        f" FROM cenarios_obras co"
                        f" LEFT JOIN cenarios_meta cm"
                        f" ON cm.nome = co.cenario_nome"
                        f" WHERE co.cod IN ({placeholders})",
                        cod_list,
                    )
                else:
                    cursor.execute(
                        "SELECT co.cod, co.cenario_nome, co.ano_final,"
                        " co.ano_origem, COALESCE(cm.atualizado_em,"
                        " cm.criado_em, '') AS em,"
                        " COALESCE(cm.atualizado_por,"
                        " cm.criado_por, '') AS por"
                        " FROM cenarios_obras co"
                        " LEFT JOIN cenarios_meta cm"
                        " ON cm.nome = co.cenario_nome"
                    )
                for r in cursor.fetchall() or []:
                    cod = str(r[0] or "").strip()
                    cen = str(r[1] or "").strip()
                    if not cod or not cen:
                        continue
                    af = r[2]
                    ao = r[3]
                    em = str(r[4] or "").strip()
                    por = str(r[5] or "").strip()
                    cen_d = grouped.setdefault(cod, {}).setdefault(cen, {
                        "cenario": cen, "campos": [],
                        "atualizado_em": "", "atualizado_por": "",
                        "ano_final": None, "ano_origem": None,
                    })
                    cen_d["ano_final"] = (
                        int(af) if af is not None else None
                    )
                    cen_d["ano_origem"] = (
                        int(ao) if ao is not None else None
                    )
                    # Se ano_final difere de ano_origem, conta como
                    # alteracao de "ano_" no campos do tooltip.
                    if (af is not None and ao is not None
                            and int(af) != int(ao)):
                        if "ano_" not in cen_d["campos"]:
                            cen_d["campos"].append("ano_")
                    if em > cen_d["atualizado_em"]:
                        cen_d["atualizado_em"] = em
                        cen_d["atualizado_por"] = por

            # ----- 2) cenario_obras_overrides (do COPLAN) -----
            if _table_exists("cenario_obras_overrides"):
                if cod_list:
                    placeholders = ",".join(["?"] * len(cod_list))
                    cursor.execute(
                        f"SELECT cod, cenario_nome, coluna, valor,"
                        f" atualizado_em, atualizado_por"
                        f" FROM cenario_obras_overrides"
                        f" WHERE cod IN ({placeholders})",
                        cod_list,
                    )
                else:
                    cursor.execute(
                        "SELECT cod, cenario_nome, coluna, valor,"
                        " atualizado_em, atualizado_por"
                        " FROM cenario_obras_overrides"
                    )
                for r in cursor.fetchall() or []:
                    cod = str(r[0] or "").strip()
                    cen = str(r[1] or "").strip()
                    col = str(r[2] or "").strip()
                    em = str(r[4] or "").strip()
                    por = str(r[5] or "").strip()
                    if not cod or not cen or not col:
                        continue
                    cen_d = grouped.setdefault(cod, {}).setdefault(cen, {
                        "cenario": cen, "campos": [],
                        "atualizado_em": "", "atualizado_por": "",
                        "ano_final": None, "ano_origem": None,
                    })
                    if col not in cen_d["campos"]:
                        cen_d["campos"].append(col)
                    if em > cen_d["atualizado_em"]:
                        cen_d["atualizado_em"] = em
                        cen_d["atualizado_por"] = por
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "items": {}, "error": str(exc)}
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass

        items: dict[str, list[dict[str, Any]]] = {}
        for cod, cen_d in grouped.items():
            items[cod] = sorted(
                cen_d.values(),
                key=lambda x: x.get("atualizado_em") or "",
                reverse=True,
            )
        return {"ok": True, "items": items, "error": ""}

    def _cenario_save_overrides(
        self,
        db: Any,
        cenario_nome: str,
        cod: str,
        diff_pairs: list[tuple[str, Any]],
    ) -> int:
        """INSERT OR REPLACE em cenario_obras_overrides para cada
        (coluna, valor) em diff_pairs. Devolve quantas linhas escreveu."""
        if not (cenario_nome and cod and diff_pairs):
            return 0
        self._cenario_ensure_overrides_table(db)
        import getpass as _gp
        try:
            user = _gp.getuser() or "?"
        except Exception:  # noqa: BLE001
            user = "?"
        now = datetime.now().isoformat(timespec="seconds")
        wrote = 0
        conn, _err = self._open_aux_conn(db)
        if conn is None:
            return 0
        try:
            cursor = conn.cursor()
            for col, val in diff_pairs:
                cursor.execute(
                    "INSERT OR REPLACE INTO cenario_obras_overrides"
                    " (cenario_nome, cod, coluna, valor,"
                    " atualizado_em, atualizado_por)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (cenario_nome, cod, col,
                     "" if val is None else str(val),
                     now, user),
                )
                wrote += 1
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"[cenario] save_overrides falhou: {exc}",
                  file=sys.stderr)
            return 0
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        return wrote
