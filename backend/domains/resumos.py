# -*- coding: utf-8 -*-
"""Mixin de dominio "resumos" da CoplanApi (extraido de main_web.py).

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


class ResumosMixin:

    # ------------------------------------------------------------------
    # Passo 6.1 (Resumo / KPIs): 5 cards do topo da aba Resumo.
    #   capex_total            = SUM(valor_obra)
    #   obras_total            = COUNT(*)
    #   km_total               = SUM(quantidade_material)        # km
    #   contas_beneficiadas    = SUM(contas_contratos_beneficiadas)
    #   postergacoes           = COUNT(obras com tipo_pacote contendo
    #                             'posterga' OU manobra contendo 'posterga')
    # Tudo via SQL com CAST/REPLACE para tratar valores armazenados como
    # texto pt-BR ('1.234,56'). Aceita filtro opcional ano (string).
    # ------------------------------------------------------------------
    @staticmethod
    def _sql_to_real(col: str) -> str:
        """Expressao SQLite que converte texto pt-BR em REAL.
        Ex.: '1.234,56' -> 1234.56  | '12,5' -> 12.5  | '12.5' -> 12.5
        Heuristica: remove '.' e troca ',' por '.'. Funciona quando o
        usuario *nao* mistura separadores de milhar com decimal en-US."""
        return (
            f"COALESCE("
            f"CAST(REPLACE(REPLACE(COALESCE({col},'0'),'.',''),',','.') AS REAL),"
            f"0)"
        )

    # ------------------------------------------------------------------
    # Visualizar Sprint 1 (Auditoria #1): endpoints de resumo aceitam
    # filtro `cods` opcional. JS publica coplanFilteredCods() (lista de
    # cods filtrados em Visualizar) e os 5 cards do Resumo passam essa
    # lista. Quando cods=None, comportamento legado (banco inteiro).
    # ------------------------------------------------------------------
    @staticmethod
    def _build_resumo_where(
        ano_s: str, cods: Any = None,
    ) -> tuple[str, list[Any]]:
        """Monta WHERE compartilhado entre os 5 endpoints de resumo.
        Suporta filtro por ano_ E/OU lista de cods. SQLite limita ~999
        placeholders; para listas maiores, trunca silenciosamente em 900
        (caso patologico - Visualizar dificilmente filtra tanto)."""
        clauses: list[str] = []
        params: list[Any] = []
        if ano_s:
            clauses.append("TRIM(COALESCE(ano_,''))=?")
            params.append(ano_s)
        if isinstance(cods, (list, tuple)) and cods:
            cods_clean = [
                str(c).strip() for c in cods if str(c or "").strip()
            ]
            if cods_clean:
                if len(cods_clean) > 900:
                    cods_clean = cods_clean[:900]
                placeholders = ",".join(["?"] * len(cods_clean))
                clauses.append(f"cod IN ({placeholders})")
                params.extend(cods_clean)
        if not clauses:
            return "", []
        return " WHERE " + " AND ".join(clauses), params

    def resumo_kpis(self, ano: Any = "", cods: Any = None) -> dict[str, Any]:
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {
                "ok": False, "error": err or "db indisponivel",
                "ano": str(ano or ""), "capex_total": 0.0,
                "obras_total": 0, "km_total": 0.0,
                "contas_beneficiadas": 0, "postergacoes": 0,
                "ano_dominante": None,
            }
        ano_s = str(ano or "").strip()
        ano_dominante = None
        try:
            with db._with_connection():
                cursor = db._get_cursor()
                if cursor is None:
                    return {"ok": False, "error": "cursor indisponivel"}
                where_clause, _params_list = self._build_resumo_where(ano_s, cods)
                params: tuple[Any, ...] = tuple(_params_list)
                cursor.execute(
                    "SELECT "
                    "  COUNT(*),"
                    f" SUM({self._sql_to_real('valor_obra')}),"
                    f" SUM({self._sql_to_real('quantidade_material')}),"
                    f" SUM({self._sql_to_real('contas_contratos_beneficiadas')}),"
                    "  SUM(CASE WHEN ("
                    "    UPPER(COALESCE(tipo_pacote,'')) LIKE '%POSTERGA%' OR"
                    "    UPPER(COALESCE(manobra,''))     LIKE '%POSTERGA%' OR"
                    "    UPPER(COALESCE(tipo_pacote,'')) LIKE '%PLPT%'"
                    "  ) THEN 1 ELSE 0 END)"
                    f" FROM obras{where_clause}",
                    params,
                )
                row = cursor.fetchone()
                if row is None:
                    return {"ok": False, "error": "sem dados"}
                obras_total = int(row[0] or 0)
                capex_total = float(row[1] or 0.0)
                km_total = float(row[2] or 0.0)
                contas_benef = int(row[3] or 0)
                postergacoes = int(row[4] or 0)

                # Ano dominante: util quando ano nao foi informado.
                if not ano_s:
                    try:
                        cursor.execute(
                            "SELECT ano_, COUNT(*) c FROM obras "
                            "WHERE ano_ IS NOT NULL AND TRIM(ano_)<>'' "
                            "GROUP BY ano_ ORDER BY c DESC LIMIT 1"
                        )
                        ar = cursor.fetchone()
                        ano_dominante = (str(ar[0]).strip()
                                         if ar and ar[0] is not None else None)
                    except Exception:  # noqa: BLE001
                        pass
                else:
                    ano_dominante = ano_s
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"sql: {exc}",
                    "ano": ano_s, "capex_total": 0.0, "obras_total": 0,
                    "km_total": 0.0, "contas_beneficiadas": 0,
                    "postergacoes": 0, "ano_dominante": None}
        return {
            "ok": True, "error": "",
            "ano": ano_s, "ano_dominante": ano_dominante,
            "capex_total": capex_total,
            "obras_total": obras_total,
            "km_total": km_total,
            "contas_beneficiadas": contas_benef,
            "postergacoes": postergacoes,
        }

    # ------------------------------------------------------------------
    # Passo 6.2 (Resumo / volumetria por regional): agrega obras +
    # valor_obra por nome_regional. Filtro opcional ano_. Resultado
    # ordenado por valor desc (maior em cima -- igual ao mock).
    # ------------------------------------------------------------------
    def resumo_volumetria_regional(
        self, ano: Any = "", cods: Any = None,
    ) -> dict[str, Any]:
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel",
                    "ano": str(ano or ""), "items": []}
        ano_s = str(ano or "").strip()
        try:
            with db._with_connection():
                cursor = db._get_cursor()
                if cursor is None:
                    return {"ok": False, "error": "cursor",
                            "ano": ano_s, "items": []}
                where, _params = self._build_resumo_where(ano_s, cods)
                params: tuple[Any, ...] = tuple(_params)
                cursor.execute(
                    "SELECT "
                    "  UPPER(TRIM(COALESCE(nome_regional,'(SEM REGIONAL)'))),"
                    "  COUNT(*),"
                    f" SUM({self._sql_to_real('valor_obra')})"
                    f" FROM obras{where} "
                    "GROUP BY UPPER(TRIM(COALESCE(nome_regional,'(SEM REGIONAL)')))",
                    params,
                )
                rows = cursor.fetchall() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"sql: {exc}", "ano": ano_s, "items": []}

        items = [
            {
                "regional": str(r[0] or ""),
                "obras": int(r[1] or 0),
                "valor": float(r[2] or 0.0),
            }
            for r in rows
        ]
        items.sort(key=lambda x: x["valor"], reverse=True)
        return {"ok": True, "error": "", "ano": ano_s, "items": items}

    def pacotes_distribution(
        self, ano: Any = "", cods: Any = None,
    ) -> dict[str, Any]:
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel",
                    "ano": str(ano or ""), "items": []}
        ano_s = str(ano or "").strip()
        try:
            with db._with_connection():
                cursor = db._get_cursor()
                if cursor is None:
                    return {"ok": False, "error": "cursor",
                            "ano": ano_s, "items": []}
                where, _params = self._build_resumo_where(ano_s, cods)
                params: tuple[Any, ...] = tuple(_params)
                cursor.execute(
                    "SELECT "
                    "  TRIM(COALESCE(tipo_pacote,'')),"
                    "  COUNT(*),"
                    f" SUM({self._sql_to_real('valor_obra')})"
                    f" FROM obras{where} GROUP BY TRIM(COALESCE(tipo_pacote,''))",
                    params,
                )
                rows = cursor.fetchall() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"sql: {exc}",
                    "ano": ano_s, "items": []}

        # Agrega entradas vazias em "Outros".
        bucket_outros = {"label": "Outros", "obras": 0, "valor": 0.0}
        explicit: list[dict[str, Any]] = []
        for r in rows:
            label = str(r[0] or "").strip()
            obras = int(r[1] or 0)
            valor = float(r[2] or 0.0)
            if not label:
                bucket_outros["obras"] += obras
                bucket_outros["valor"] += valor
            else:
                explicit.append({"label": label, "obras": obras, "valor": valor})
        explicit.sort(key=lambda x: x["valor"], reverse=True)
        if bucket_outros["obras"]:
            explicit.append(bucket_outros)

        total_valor = sum(x["valor"] for x in explicit)
        for x in explicit:
            x["pct"] = (x["valor"] / total_valor * 100.0) if total_valor else 0.0
            key = x["label"].upper()
            x["color"] = self.PACOTE_COLOR_MAP.get(key, "var(--text-soft)")
        return {
            "ok": True, "error": "", "ano": ano_s,
            "items": explicit, "total_valor": total_valor,
        }

    # ------------------------------------------------------------------
    # Passo 6.4 (Resumo / tabela completa "Quadro de Volumetria"):
    # 9 colunas por regional + linha TOTAL agregada. Colunas numericas
    # tratadas como REAL via _sql_to_real (string pt-BR).
    # ------------------------------------------------------------------
    def resumo_regional_table(
        self, ano: Any = "", cods: Any = None,
    ) -> dict[str, Any]:
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel",
                    "ano": str(ano or ""), "items": [], "total": None}
        ano_s = str(ano or "").strip()
        try:
            with db._with_connection():
                cursor = db._get_cursor()
                if cursor is None:
                    return {"ok": False, "error": "cursor",
                            "ano": ano_s, "items": [], "total": None}
                where, _params = self._build_resumo_where(ano_s, cods)
                params: tuple[Any, ...] = tuple(_params)
                # Por regional
                cursor.execute(
                    "SELECT "
                    "  UPPER(TRIM(COALESCE(nome_regional,'(SEM REGIONAL)'))) AS reg,"
                    "  COUNT(*) AS obras,"
                    f" SUM({self._sql_to_real('quantidade_material')}) AS km,"
                    f" AVG({self._sql_to_real('tensao_media_final')}) AS tensao_med,"
                    f" AVG({self._sql_to_real('chi_final')}) AS chi,"
                    f" AVG({self._sql_to_real('ci_final')}) AS ci,"
                    f" AVG({self._sql_to_real('carregamento_final')}) AS carreg,"
                    f" SUM({self._sql_to_real('contas_contratos_beneficiadas')}) AS contas,"
                    f" SUM({self._sql_to_real('valor_obra')}) AS valor"
                    f" FROM obras{where}"
                    " GROUP BY UPPER(TRIM(COALESCE(nome_regional,'(SEM REGIONAL)')))",
                    params,
                )
                rows = cursor.fetchall() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"sql: {exc}",
                    "ano": ano_s, "items": [], "total": None}

        items = []
        for r in rows:
            items.append({
                "regional":  str(r[0] or ""),
                "obras":     int(r[1] or 0),
                "km":        float(r[2] or 0.0),
                "tensao":    float(r[3] or 0.0),
                "chi":       float(r[4] or 0.0),
                "ci":        float(r[5] or 0.0),
                "carreg":    float(r[6] or 0.0),
                "contas":    int(r[7] or 0),
                "valor":     float(r[8] or 0.0),
            })
        items.sort(key=lambda x: x["valor"], reverse=True)

        # Total agregado: medias ponderadas pelo numero de obras quando
        # faz sentido (tensao/CHI/CI/carregamento). Soma para obras/km
        # /contas/valor.
        total_obras = sum(i["obras"] for i in items)
        total_km = sum(i["km"] for i in items)
        total_contas = sum(i["contas"] for i in items)
        total_valor = sum(i["valor"] for i in items)

        def _wavg(field: str) -> float:
            num = sum(i[field] * i["obras"] for i in items)
            return (num / total_obras) if total_obras else 0.0

        total_row = {
            "regional": "TOTAL",
            "obras":    total_obras,
            "km":       total_km,
            "tensao":   _wavg("tensao"),
            "chi":      _wavg("chi"),
            "ci":       _wavg("ci"),
            "carreg":   _wavg("carreg"),
            "contas":   total_contas,
            "valor":    total_valor,
        }
        return {"ok": True, "error": "", "ano": ano_s,
                "items": items, "total": total_row}

    # ------------------------------------------------------------------
    # Fase A6 (resumo_service.montar_resumo_ganhos_projeto):
    # consolida ganhos de TODAS as obras de um nome_projeto, por
    # alimentador. Equivalente a MainWindow.popular_resumo_ganhos_projeto.
    # ------------------------------------------------------------------
    def resumo_ganhos_projeto(self, nome_projeto: Any = "") -> dict[str, Any]:
        nome_s = str(nome_projeto or "").strip()
        if not nome_s:
            return {"ok": False, "error": "nome_projeto vazio",
                    "linhas": [], "projeto": ""}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel",
                    "linhas": [], "projeto": nome_s}
        try:
            with db._with_connection():
                cursor = db._get_cursor()
                if cursor is None:
                    return {"ok": False, "error": "cursor",
                            "linhas": [], "projeto": nome_s}
                cursor.execute(
                    "SELECT alimentador_principal, alimentadores_beneficiados,"
                    " codigo_item, ganhos_totais_depois"
                    " FROM obras"
                    " WHERE UPPER(TRIM(COALESCE(nome_projeto,'')))=UPPER(TRIM(?))",
                    (nome_s,),
                )
                rows = cursor.fetchall() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"sql: {exc}",
                    "linhas": [], "projeto": nome_s}

        try:
            from core.services.resumo_service import (  # type: ignore[import-not-found]
                montar_resumo_ganhos_projeto,
            )
            from runtime.config import DEFAULT_CRITERIOS  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}",
                    "linhas": [], "projeto": nome_s}

        criterios = dict(DEFAULT_CRITERIOS)
        criterios.update((self._config or {}).get("criterios_planejamento") or {})

        cols_used = [
            "alimentador_principal",
            "alimentadores_beneficiados",
            "codigo_item",
            "ganhos_totais_depois",
        ]
        try:
            linhas = montar_resumo_ganhos_projeto(
                rows=list(rows), cols=cols_used, criterios=criterios,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"montar_resumo_ganhos_projeto: {exc}",
                    "linhas": [], "projeto": nome_s}

        out: list[dict[str, Any]] = []
        for ln in linhas:
            out.append({
                "alimentador":   ln.alimentador,
                "carregamento":  {"text": ln.carregamento.text, "ok": ln.carregamento.ok},
                "tensao":        {"text": ln.tensao.text, "ok": ln.tensao.ok},
                "clientes_text": ln.clientes_text,
            })
        return {"ok": True, "error": "", "projeto": nome_s,
                "linhas": out, "obras_count": len(rows)}

    def list_projetos(self) -> dict[str, Any]:
        """Lista nomes_projeto distintos no banco para usar em selects."""
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "items": [], "error": err or "db indisponivel"}
        try:
            with db._with_connection():
                cursor = db._get_cursor()
                if cursor is None:
                    return {"ok": False, "items": [], "error": "cursor"}
                cursor.execute(
                    "SELECT DISTINCT TRIM(nome_projeto) FROM obras"
                    " WHERE TRIM(COALESCE(nome_projeto,''))<>''"
                    " ORDER BY 1"
                )
                items = [str(r[0]).strip() for r in cursor.fetchall() if r[0]]
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "items": [], "error": f"sql: {exc}"}
        return {"ok": True, "items": items, "error": ""}

    # ------------------------------------------------------------------
    # F16 - Atualizar Projeto navegacional (RB-3, AtualizarObraMixin):
    # Le todas as obras de um nome_projeto + tipo_pacote (mesma logica
    # de iniciar_atualizacao_projeto do desktop). O JS mantem o estado
    # de navegacao (index, edited, snapshots) e chama save_obra ao
    # finalizar para cada obra alterada.
    # ------------------------------------------------------------------
    def projeto_fetch_obras(
        self, nome_projeto: Any, tipo_pacote: Any = "",
    ) -> dict[str, Any]:
        """Retorna as obras de um projeto (filtradas opcionalmente por
        tipo_pacote) ordenadas por codigo_item. Equivalente a
        DatabaseManager.fetch_by_project + filtro pacote do desktop."""
        nome = str(nome_projeto or "").strip()
        if not nome:
            return {"ok": False, "obras": [], "error": "nome_projeto vazio"}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "obras": [],
                    "error": err or "db indisponivel"}
        try:
            cols = list(db.get_column_names() or [])
            todas = list(db.fetch_by_project(
                nome, order_by_codigo_item=True) or [])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "obras": [],
                    "error": f"fetch_by_project: {exc}"}

        pacote_ref = str(tipo_pacote or "").strip()
        if pacote_ref:
            i_pac = (cols.index("tipo_pacote")
                     if "tipo_pacote" in cols else -1)
            if i_pac >= 0:
                filtradas = [o for o in todas
                             if str(o[i_pac] or "").strip() == pacote_ref]
            else:
                filtradas = todas
        else:
            filtradas = todas

        # Converte para list of dicts (mais facil pro JS)
        obras = [dict(zip(cols, row)) for row in filtradas]
        i_cod = cols.index("cod") if "cod" in cols else -1
        cods = [str(row[i_cod] or "").strip()
                for row in filtradas if i_cod >= 0] if i_cod >= 0 else []
        return {
            "ok": True,
            "obras": obras,
            "cods": cods,
            "total": len(obras),
            "total_no_projeto": len(todas),
            "ignoradas_outro_pacote": len(todas) - len(filtradas),
            "nome_projeto": nome,
            "tipo_pacote": pacote_ref,
            "columns": cols,
            "error": "",
        }

    # ------------------------------------------------------------------
    # [M030] Wrappers de "Atualizar Projeto" (state machine vive no JS).
    # projeto_iniciar:  carrega lista de obras (alias de projeto_fetch_obras
    #                   com nome alinhado ao plano);
    # projeto_finalizar: itera payloads e salva cada um em sequencia,
    #                    propagando o motivo da primeira obra critica para
    #                    todas as demais (parity com modo "atualizar
    #                    projeto" do desktop).
    # projeto_avancar/voltar/cancelar vivem 100% no JS e nao precisam de
    # endpoint backend (sao pura troca de indice + clearForm).
    # ------------------------------------------------------------------
    def projeto_iniciar(
        self, nome_projeto: Any, tipo_pacote: Any = "",
    ) -> dict[str, Any]:
        """Alias semantico de projeto_fetch_obras + idx inicial. JS
        recebe o lote, mantem `idx`, `pendingPayloads[]` e dispara
        projeto_finalizar() ao final."""
        out = self.projeto_fetch_obras(nome_projeto, tipo_pacote)
        if not out.get("ok"):
            return out
        out["idx"] = 0
        return out

    def projeto_finalizar(
        self, payloads: Any = None, motivo: Any = "",
    ) -> dict[str, Any]:
        """Salva em sequencia todos os payloads do lote 'atualizar
        projeto'. Reusa save_obra; propaga o mesmo `motivo` para todas
        as obras (parity com codigo5_coplan: 'modo atualizar projeto
        reutiliza motivo da primeira obra')."""
        if not isinstance(payloads, list):
            return {"ok": False, "salvos": 0, "falhas": [],
                    "error": "payloads nao eh lista"}
        motivo_s = str(motivo or "").strip()
        salvos: list[dict[str, Any]] = []
        falhas: list[dict[str, Any]] = []
        for i, p in enumerate(payloads):
            if not isinstance(p, dict):
                falhas.append({"idx": i, "cod": "",
                               "error": "payload nao eh dict"})
                continue
            payload = dict(p)
            if motivo_s and "motivo_alteracao" not in payload:
                payload["motivo_alteracao"] = motivo_s
            try:
                resp = self.save_obra(payload)
            except Exception as exc:  # noqa: BLE001
                falhas.append({"idx": i, "cod": str(p.get("cod") or ""),
                               "error": f"save_obra: {exc}"})
                continue
            if resp.get("ok"):
                salvos.append({"idx": i, "cod": resp.get("cod") or "",
                               "mode": resp.get("mode") or ""})
            else:
                falhas.append({"idx": i, "cod": resp.get("cod") or "",
                               "error": resp.get("error") or "save falhou",
                               "requires_motivo": resp.get("requires_motivo"),
                               "blocked": resp.get("blocked")})
        return {
            "ok": not falhas,
            "salvos": len(salvos),
            "falhas": falhas,
            "salvos_detalhe": salvos,
            "motivo_aplicado": motivo_s,
            "error": "" if not falhas else f"{len(falhas)} falha(s)",
        }

    # ------------------------------------------------------------------
    # Fase A5 (resumo_service.montar_quadro_resumo_from_ganhos):
    # quadro de "Resumo dos Ganhos por Alimentador" para UMA obra,
    # baseado no campo `ganhos_totais_depois`. Reproduz
    # MainWindow.popular_quadro_resumo_from_ganhos_depois.
    # Aceita dois modos: por COD (le obra do banco) ou por payload
    # explicito (alim_principal, alim_benef, ganhos_str).
    # ------------------------------------------------------------------
    def quadro_resumo_ganhos(
        self,
        cod: Any = "",
        alimentador_principal: Any = "",
        alimentadores_beneficiados: Any = "",
        ganhos_totais_depois: Any = "",
    ) -> dict[str, Any]:
        alim_p = str(alimentador_principal or "").strip()
        alim_b = str(alimentadores_beneficiados or "")
        ganhos = str(ganhos_totais_depois or "")
        cod_s = str(cod or "").strip()

        # Modo COD: carrega da obra existente.
        if cod_s and not (alim_p or ganhos):
            db, err = self._ensure_db_connected()
            if err or db is None:
                return {"ok": False, "error": err or "db indisponivel",
                        "linhas": []}
            try:
                row = db.fetch_by_cod(cod_s)
                cols = list(db.get_column_names() or [])
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"fetch_by_cod: {exc}",
                        "linhas": []}
            if not row:
                return {"ok": False, "error": f"obra nao encontrada: {cod_s}",
                        "linhas": []}
            row_dict = {c: row[i] if i < len(row) else ""
                        for i, c in enumerate(cols)}
            alim_p = str(row_dict.get("alimentador_principal") or "").strip()
            alim_b = str(row_dict.get("alimentadores_beneficiados") or "")
            ganhos = str(row_dict.get("ganhos_totais_depois") or "")

        try:
            from core.services.resumo_service import (  # type: ignore[import-not-found]
                montar_quadro_resumo_from_ganhos,
            )
            from runtime.config import DEFAULT_CRITERIOS  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}", "linhas": []}

        criterios = dict(DEFAULT_CRITERIOS)
        criterios.update((self._config or {}).get("criterios_planejamento") or {})

        try:
            linhas = montar_quadro_resumo_from_ganhos(
                alimentador_principal=alim_p,
                alimentadores_beneficiados=alim_b,
                ganhos_totais_depois=ganhos,
                criterios=criterios,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"montar_quadro: {exc}",
                    "linhas": []}

        out: list[dict[str, Any]] = []
        for ln in linhas:
            out.append({
                "alimentador":   ln.alimentador,
                "carregamento":  {"text": ln.carregamento.text, "ok": ln.carregamento.ok},
                "tensao":        {"text": ln.tensao.text, "ok": ln.tensao.ok},
                "clientes_text": ln.clientes_text,
            })
        return {"ok": True, "error": "", "linhas": out}

    # ------------------------------------------------------------------
    # Fase A4 (resumo_service.montar_volumetria_financeiro):
    # pivot por (PI x Ano) com Valor/Fisico, formatado em pt-BR.
    # Reproduz MainWindow.popular_volumetria_financeiro do desktop.
    # ------------------------------------------------------------------
    def resumo_volumetria_financeiro(
        self, ano: Any = "", cods: Any = None,
    ) -> dict[str, Any]:
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel",
                    "ano": str(ano or ""), "cabecalhos": ["PI"], "linhas": []}
        try:
            ano_s = str(ano or "").strip()
            with db._with_connection():
                cursor = db._get_cursor()
                if cursor is None:
                    return {"ok": False, "error": "cursor",
                            "ano": str(ano or ""),
                            "cabecalhos": ["PI"], "linhas": []}
                where, _params = self._build_resumo_where(ano_s, cods)
                params: tuple[Any, ...] = tuple(_params)
                cursor.execute(
                    "SELECT projeto_investimento, ano_, valor_obra,"
                    " quantidade_material"
                    f" FROM obras{where}",
                    params,
                )
                rows = cursor.fetchall() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"sql: {exc}",
                    "ano": str(ano or ""),
                    "cabecalhos": ["PI"], "linhas": []}

        try:
            from core.services.resumo_service import (  # type: ignore[import-not-found]
                montar_volumetria_financeiro,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}",
                    "ano": str(ano or ""),
                    "cabecalhos": ["PI"], "linhas": []}

        obras_visiveis = [
            {
                "projeto_investimento": r[0],
                "ano_": r[1],
                "valor_obra": r[2],
                "quantidade_material": r[3],
            }
            for r in rows
        ]
        try:
            vol = montar_volumetria_financeiro(obras_visiveis)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"montar_volumetria: {exc}",
                    "ano": str(ano or ""),
                    "cabecalhos": ["PI"], "linhas": []}
        return {
            "ok": True, "error": "", "ano": str(ano or ""),
            "cabecalhos": list(vol.cabecalhos),
            "linhas": [list(linha) for linha in vol.linhas],
        }
