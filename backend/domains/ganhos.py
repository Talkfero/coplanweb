# -*- coding: utf-8 -*-
"""Mixin de dominio "ganhos" da CoplanApi (extraido de main_web.py).

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


class GanhosMixin:

    # ------------------------------------------------------------------
    # Passo 5.4 (Ganhos / Ganhos Atuais por alimentador):
    # Agrega valores das colunas tensao_min_registrada_atual /
    # carregamento_max_registrado_atual / ganhos_totais_atual entre as
    # obras que tem o alimentador no campo principal OU nos beneficiados.
    # Retorna agregados (min/max tensao, max carregamento, ultimo
    # ganhos_totais_atual nao vazio) prontos para o card.
    # ------------------------------------------------------------------
    @staticmethod
    def _to_float_brl(v: Any) -> float | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        # pt-BR: "1.234,56" -> "1234.56"; tambem aceita "1234.56"
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")
        # Limpa unidades comuns (pu, %, kV)
        s = re.sub(r"[^0-9.\-]", "", s)
        try:
            return float(s)
        except ValueError:
            return None

    def get_ganhos_atuais(self, alimentador: Any = "") -> dict[str, Any]:
        alim = str(alimentador or "").strip().upper()
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "alim": alim, "error": err or "db indisponivel",
                    "tensao_min": None, "tensao_max": None,
                    "carregamento_max": None, "ganhos_totais_atual": "",
                    "obras_count": 0}
        try:
            cursor = db._get_cursor()
            if cursor is None:
                return {"ok": False, "alim": alim, "error": "cursor",
                        "tensao_min": None, "tensao_max": None,
                        "carregamento_max": None, "ganhos_totais_atual": "",
                        "obras_count": 0}
            if alim:
                # Filtra por alimentador principal OU contido em
                # alimentadores_beneficiados (string separada por ;,).
                cursor.execute(
                    "SELECT tensao_min_registrada_atual, "
                    "       carregamento_max_registrado_atual, "
                    "       ganhos_totais_atual, alimentador_principal, "
                    "       alimentadores_beneficiados, cod "
                    "FROM obras "
                    "WHERE UPPER(COALESCE(alimentador_principal,''))=? "
                    "   OR UPPER(COALESCE(alimentadores_beneficiados,'')) LIKE ?",
                    (alim, f"%{alim}%"),
                )
            else:
                cursor.execute(
                    "SELECT tensao_min_registrada_atual, "
                    "       carregamento_max_registrado_atual, "
                    "       ganhos_totais_atual, alimentador_principal, "
                    "       alimentadores_beneficiados, cod "
                    "FROM obras"
                )
            rows = cursor.fetchall() or []
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "alim": alim, "error": f"sql: {exc}",
                    "tensao_min": None, "tensao_max": None,
                    "carregamento_max": None, "ganhos_totais_atual": "",
                    "obras_count": 0}

        # Filtragem extra em Python para garantir match correto na string
        # de beneficiados (LIKE pode pegar substring espuria).
        kept: list[tuple[Any, ...]] = []
        for r in rows:
            principal = str(r[3] or "").strip().upper()
            benef_raw = str(r[4] or "")
            benef_set = {
                p.strip().upper()
                for p in re.split(r"[;,|]+", benef_raw)
                if p.strip()
            }
            if not alim or principal == alim or alim in benef_set:
                kept.append(r)

        tensoes_min: list[float] = []
        carregs_max: list[float] = []
        ganhos_str = ""
        for r in kept:
            tm = self._to_float_brl(r[0])
            if tm is not None:
                tensoes_min.append(tm)
            cm = self._to_float_brl(r[1])
            if cm is not None:
                carregs_max.append(cm)
            g = str(r[2] or "").strip()
            if g and not ganhos_str:
                ganhos_str = g  # 1o nao-vazio (mesmo alimentador tende a ter so 1)

        # Tensao "min" e "max" registradas: usamos o minimo dos minimos
        # como "Min" e o maximo dos maximos como "Max" (usando a propria
        # coluna min_registrada para ambos limites; campo max_registrada
        # nao existe explicito).
        return {
            "ok": True, "alim": alim, "error": "",
            "tensao_min": min(tensoes_min) if tensoes_min else None,
            "tensao_max": max(tensoes_min) if tensoes_min else None,
            "carregamento_max": max(carregs_max) if carregs_max else None,
            "ganhos_totais_atual": ganhos_str,
            "obras_count": len(kept),
        }

    # ------------------------------------------------------------------
    # Ganhos / metodos auxiliares (leva B da migracao Ganhos).
    # G020 ganhos_form_state, G021 avaliar_ganhos_planejamento,
    # G022 avaliar_ganhos_postergacao, G024 ganhos_resolver_alimentador.
    # Origem desktop: ui/main_window/ganhos_mixin.py + cadastro_mixin.py
    # (atualizar_labels_planejamento_desde_tela:892-987) + visualizar_mixin
    # (_obra_suficiente:545-622) + core/services/relatorio_criterios_service
    # (obra_atende:149).
    # ------------------------------------------------------------------

    def ganhos_resolver_alimentador(self, cod: Any = "") -> dict[str, Any]:
        """[G024] Devolve {principal, beneficiados[], todos[]} dado o COD
        de uma obra. Beneficiados parseados por separador ; ou ,. Sem cod
        valido retorna ok=False."""
        c = str(cod or "").strip()
        if not c:
            return {"ok": False, "principal": "",
                    "beneficiados": [], "todos": [],
                    "error": "cod vazio"}
        try:
            obra = self.get_obra(c)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "principal": "",
                    "beneficiados": [], "todos": [],
                    "error": f"get_obra: {exc}"}
        if not obra or not obra.get("ok"):
            return {"ok": False, "principal": "",
                    "beneficiados": [], "todos": [],
                    "error": (obra or {}).get("error", "obra nao encontrada")}
        o = obra.get("obra") or {}
        principal = str(
            o.get("alimentador_principal")
            or o.get("alimentador") or ""
        ).strip()
        # get_obra ja faz o parser dos beneficiados e devolve em alim_benef.
        benef_list = obra.get("alim_benef") or []
        if not isinstance(benef_list, list):
            benef_raw = str(o.get("alimentadores_beneficiados") or "")
            tmp = benef_raw.replace(",", ";").split(";")
            benef_list = [s.strip() for s in tmp if s.strip()]
        benef_clean: list[str] = []
        seen = set()
        for b in benef_list:
            s = str(b or "").strip()
            if not s:
                continue
            up = s.upper()
            if up in seen:
                continue
            seen.add(up)
            benef_clean.append(s)
        todos = ([principal] if principal else []) + [
            b for b in benef_clean
            if b.upper() != principal.upper()
        ]
        return {
            "ok": True,
            "principal": principal,
            "beneficiados": benef_clean,
            "todos": todos,
            "error": "",
        }

    def ganhos_form_state(self, cod: Any = "") -> dict[str, Any]:
        """[G020] Agregador para popular toda a aba Ganhos numa unica
        chamada. Reusa get_criterios + get_ganhos_atuais + (opcional)
        quadro_resumo_ganhos quando cod for informado."""
        out: dict[str, Any] = {"ok": True, "error": ""}
        try:
            out["criterios"] = self.get_criterios()
        except Exception as exc:  # noqa: BLE001
            out["criterios"] = {"ok": False, "error": f"get_criterios: {exc}"}
        # Resolve alim do cod (se houver) para alimentar ganhos_atuais.
        alim_principal = ""
        c = str(cod or "").strip()
        if c:
            try:
                resolver = self.ganhos_resolver_alimentador(c)
                if resolver.get("ok"):
                    alim_principal = resolver.get("principal") or ""
                    out["alim"] = resolver
            except Exception as exc:  # noqa: BLE001
                out["alim"] = {"ok": False, "error": f"resolver: {exc}"}
        try:
            out["atual"] = self.get_ganhos_atuais(alim_principal)
        except Exception as exc:  # noqa: BLE001
            out["atual"] = {"ok": False, "error": f"get_ganhos_atuais: {exc}"}
        # Quadro resumo (parametros de ganhos por alimentador) — apenas
        # se cod foi informado.
        if c:
            try:
                out["quadro"] = self.quadro_resumo_ganhos(cod=c)
            except Exception as exc:  # noqa: BLE001
                out["quadro"] = {"ok": False, "error": f"quadro_resumo: {exc}"}
        out["cod"] = c
        return out

    def avaliar_ganhos_planejamento(
        self, payload: Any = None,
    ) -> dict[str, Any]:
        """[G021] Espelho web de _obra_atende (cadastro_mixin:920-933).
        Recebe valores DEPOIS da tela como dict simples e retorna
        {ok, atende, motivos}. Usa criterios do config + delega ao
        relatorio_criterios_service.obra_atende.

        payload esperado:
          {tensao_min, tensao_max, carregamento, contas, manobra}
        Aceita tambem chaves alternativas (tensao_min_final, etc.)."""
        if not isinstance(payload, dict):
            payload = {}

        def _get_first(*keys: str) -> Any:
            for k in keys:
                v = payload.get(k)
                if v not in (None, ""):
                    return v
            return None

        tmin = _get_first("tensao_min", "tensao_min_final", "tmin")
        tmax = _get_first("tensao_max", "tensao_max_final", "tmax")
        carreg = _get_first("carregamento", "carregamento_final", "carreg")
        contas = _get_first("contas", "contas_contratos_posteriores", "clientes")
        manobra = _get_first("manobra")

        # Linha sintetica + indices (formato esperado por obra_atende).
        row = [tmin, tmax, carreg, manobra, contas]
        idx = {"tmin": 0, "tmax": 1, "carreg": 2, "manobra": 3, "clientes": 4}

        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atende": None, "motivos": [],
                    "error": f"import config: {exc}"}
        try:
            cfg = ConfigManager.load_config() or {}
        except Exception:  # noqa: BLE001
            cfg = {}
        try:
            from runtime.config import DEFAULT_CRITERIOS  # type: ignore[import-not-found]
        except Exception:  # noqa: BLE001
            DEFAULT_CRITERIOS = {
                "tensao_min": 0.95, "tensao_max": 1.03,
                "carregamento_limite_sim_ou_vazio": 67.0,
                "carregamento_limite_nao": 100.0,
                "clientes_maximo": 6000,
            }
        criterios = cfg.get("criterios_planejamento", DEFAULT_CRITERIOS)

        def _conv_float(v: Any) -> float:
            try:
                return float(str(v).replace(",", ".")) if str(v).strip() else 0.0
            except Exception:  # noqa: BLE001
                return 0.0

        def _conv_int(v: Any) -> int:
            try:
                return int(float(str(v).replace(",", ".")))
            except Exception:  # noqa: BLE001
                return 0

        try:
            from core.services.relatorio_criterios_service import (  # type: ignore[import-not-found]
                obra_atende,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atende": None, "motivos": [],
                    "error": f"import obra_atende: {exc}"}
        try:
            atende, motivos = obra_atende(
                row, idx, criterios, _conv_float, _conv_int,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "atende": None, "motivos": [],
                    "error": f"obra_atende: {exc}"}
        return {
            "ok": True,
            "atende": atende,  # bool | None
            "motivos": list(motivos or []),
            "error": "",
        }

    def avaliar_ganhos_postergacao(
        self, payload: Any = None, anos: Any = None,
    ) -> dict[str, Any]:
        """[G022] Espelho web de _obra_suficiente
        (visualizar_mixin:545-622). Projeta degradacao N anos aplicando
        DEFAULT_PIORA_MERCADO (ou override do config) e avalia critérios
        ano a ano. Retorna {ok, suficiente, anos_alcancados, motivos}."""
        if not isinstance(payload, dict):
            payload = {}

        def _get_first(*keys: str) -> Any:
            for k in keys:
                v = payload.get(k)
                if v not in (None, ""):
                    return v
            return None

        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            from runtime.config import (  # type: ignore[import-not-found]
                DEFAULT_CRITERIOS, DEFAULT_PIORA_MERCADO,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "suficiente": None,
                    "anos_alcancados": 0, "motivos": [],
                    "error": f"import: {exc}"}
        try:
            cfg = ConfigManager.load_config() or {}
        except Exception:  # noqa: BLE001
            cfg = {}
        criterios = cfg.get("criterios_planejamento", DEFAULT_CRITERIOS)
        pioras = cfg.get("piora_mercado", DEFAULT_PIORA_MERCADO)

        # Conversao tolerante.
        def _f(v: Any) -> float | None:
            if v is None:
                return None
            s = str(v).strip()
            if not s:
                return None
            try:
                return float(s.replace(",", "."))
            except Exception:  # noqa: BLE001
                return None

        def _i(v: Any) -> int | None:
            f = _f(v)
            if f is None:
                return None
            try:
                return int(f)
            except Exception:  # noqa: BLE001
                return None

        tmin = _f(_get_first("tensao_min", "tensao_min_final"))
        tmax = _f(_get_first("tensao_max", "tensao_max_final"))
        carreg = _f(_get_first("carregamento", "carregamento_final"))
        contas = _i(_get_first("contas", "contas_contratos_posteriores"))
        manobra = str(_get_first("manobra") or "").strip().upper()

        if any(v is None for v in (tmin, tmax, carreg, contas)):
            return {"ok": True, "suficiente": None,
                    "anos_alcancados": 0,
                    "motivos": ["dados_insuficientes"],
                    "error": ""}

        try:
            anos_n = int(anos) if anos not in (None, "") else int(
                pioras.get("anos_horizonte", DEFAULT_PIORA_MERCADO["anos_horizonte"])
            )
        except Exception:  # noqa: BLE001
            anos_n = int(DEFAULT_PIORA_MERCADO["anos_horizonte"])

        delta_tensao = float(
            pioras.get("tensao_delta", DEFAULT_PIORA_MERCADO["tensao_delta"])
        )
        perc_carreg = float(
            pioras.get("carregamento_percentual",
                       DEFAULT_PIORA_MERCADO["carregamento_percentual"])
        )

        try:
            from core.services.relatorio_criterios_service import (  # type: ignore[import-not-found]
                obra_atende,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "suficiente": None,
                    "anos_alcancados": 0, "motivos": [],
                    "error": f"import obra_atende: {exc}"}

        idx = {"tmin": 0, "tmax": 1, "carreg": 2, "manobra": 3, "clientes": 4}

        def _conv_float(v: Any) -> float:
            try:
                return float(str(v).replace(",", ".")) if str(v).strip() else 0.0
            except Exception:  # noqa: BLE001
                return 0.0

        def _conv_int(v: Any) -> int:
            try:
                return int(float(str(v).replace(",", ".")))
            except Exception:  # noqa: BLE001
                return 0

        anos_ok = 0
        for _ in range(max(0, anos_n)):
            carreg = (carreg or 0.0) * (1.0 + (perc_carreg / 100.0))
            tmin = (tmin or 0.0) - delta_tensao
            tmax = (tmax or 0.0) - delta_tensao
            row = [tmin, tmax, carreg, manobra, contas]
            try:
                atende, motivos = obra_atende(
                    row, idx, criterios, _conv_float, _conv_int,
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "suficiente": None,
                        "anos_alcancados": anos_ok,
                        "motivos": [f"obra_atende_ano_{anos_ok+1}: {exc}"],
                        "error": str(exc)}
            if atende is None:
                return {"ok": True, "suficiente": None,
                        "anos_alcancados": anos_ok,
                        "motivos": list(motivos or ["dados_insuficientes"]),
                        "error": ""}
            if not atende:
                return {"ok": True, "suficiente": False,
                        "anos_alcancados": anos_ok,
                        "motivos": list(motivos or []),
                        "error": ""}
            anos_ok += 1

        return {"ok": True, "suficiente": True,
                "anos_alcancados": anos_ok,
                "motivos": [], "error": ""}

    @staticmethod
    def _norm_label(s: str) -> str:
        try:
            import unicodedata as _ud
            n = _ud.normalize("NFD", str(s or ""))
            n = "".join(c for c in n if not _ud.combining(c))
            return n.strip().lower()
        except Exception:  # noqa: BLE001
            return str(s or "").strip().lower()

    def pick_ganhos_file(self) -> dict[str, Any]:
        """Abre file dialog (single, filtros para xlsx/csv/txt) e devolve
        read_ganhos_file() do path escolhido. Cancelar -> ok=False sem erro."""
        try:
            import webview  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"pywebview indisponivel: {exc}"}
        try:
            wins = webview.windows
            if not wins:
                return {"ok": False, "error": "janela pywebview nao encontrada"}
            file_types = (
                "Planilhas/Texto (*.xlsx;*.xlsm;*.xls;*.csv;*.txt;*.tsv)",
                "Todos os arquivos (*.*)",
            )
            dlg = self._wv_dialog_const("OPEN")
            if dlg is None:
                return {"ok": False, "error": "OPEN dialog indisponivel"}
            result = wins[0].create_file_dialog(
                dlg, allow_multiple=False, file_types=file_types,
            )
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"file dialog: {exc}"}
        if not result:
            return {"ok": False, "error": "cancelado"}
        path = result[0] if isinstance(result, (list, tuple)) else str(result)
        return self.read_ganhos_file(path, 200)

    def _resolve_ganhos_columns(
        self, parametros: list[dict[str, Any]], slot: str
    ) -> dict[str, str]:
        """Casa cada parametro com sua coluna no banco com base no label.

        Retorna dict {coluna_db: valor} pronto para update_obra.
        slot in {'antes','depois','atual'}.
        """
        out: dict[str, str] = {}
        slot_norm = (slot or "antes").strip().lower()
        for p in parametros or []:
            lbl = self._norm_label(p.get("label", ""))
            if not lbl:
                continue
            valor = ""
            if slot_norm == "antes":
                valor = str(p.get("a") or "").strip()
            elif slot_norm == "depois":
                valor = str(p.get("d") or "").strip()
            else:
                # 'atual': usa o que estiver no campo "atual" se houver,
                # senao cai no Depois (heuristica).
                valor = str(p.get("atual") or p.get("d") or "").strip()
            if not valor:
                continue
            for prefix, col_a, col_d in self.GANHOS_LABEL_MAP:
                if lbl.startswith(prefix):
                    col = col_a if slot_norm == "antes" else col_d
                    out[col] = valor
                    break
        return out

    def apply_ganhos_to_obra(
        self,
        cod: Any,
        slot: Any = "antes",
        parametros: Any = None,
    ) -> dict[str, Any]:
        cod_s = str(cod or "").strip()
        if not cod_s:
            return {"ok": False, "error": "cod vazio", "cod": "",
                    "applied": 0}
        if not isinstance(parametros, list) or not parametros:
            return {"ok": False, "error": "parametros vazio", "cod": cod_s,
                    "applied": 0}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel",
                    "cod": cod_s, "applied": 0}
        cols_to_update = self._resolve_ganhos_columns(parametros, str(slot))
        if not cols_to_update:
            return {"ok": False, "error": "nenhum parametro casou com coluna",
                    "cod": cod_s, "applied": 0}
        try:
            db.update_obra(cols_to_update, cod_s, skip_blank=True)
        except Exception as exc:  # noqa: BLE001
            friendly = self._friendly_busy_error(exc)
            out: dict[str, Any] = {
                "ok": False, "error": friendly or str(exc),
                "cod": cod_s, "applied": 0,
            }
            if friendly:
                out["blocked"] = "db_busy"
            return out
        return {
            "ok": True, "error": "", "cod": cod_s,
            "slot": str(slot), "applied": len(cols_to_update),
            "columns": list(cols_to_update.keys()),
        }

    def ganhos_em_massa(
        self,
        cods: Any,
        slot: Any = "antes",
        parametros: Any = None,
    ) -> dict[str, Any]:
        """Aplica os mesmos parametros a varios COD. Util quando o mesmo
        arquivo de ganhos vale para multiplas obras (ex.: reconfiguracao
        de alimentador que afeta varias obras planejadas)."""
        if not isinstance(cods, (list, tuple)) or not cods:
            return {"ok": False, "error": "cods vazio", "applied": 0,
                    "results": []}
        results: list[dict[str, Any]] = []
        ok_count = 0
        for c in cods:
            r = self.apply_ganhos_to_obra(str(c), slot, parametros)
            results.append(r)
            if r.get("ok"):
                ok_count += 1
        return {
            "ok": ok_count > 0, "error": "",
            "applied": ok_count, "total": len(cods),
            "results": results,
        }

    # ------------------------------------------------------------------
    # Ganhos UI (RB-3 do desktop, GanhosMixin):
    # Orquestra preencher_campos_antes/depois/parametros_atuais em uma
    # unica chamada -- le os 3 .TXT da pasta uma vez e roda 8+ calculos
    # contra os mesmos buffers (vs chamar calc_* individualmente que
    # re-le os .TXT cada vez). Retorna metricas numericas + a string
    # ganhos_totais consumida pelo Resumo.
    # ------------------------------------------------------------------
    def _ganhos_resolve_pasta(self, pasta: Any = "") -> str:
        """Resolve pasta de ganhos: parametro -> config.caminho_pasta_ganhos
        -> config.caminho_pasta_arquivos. Retorna '' se nada valido."""
        s = str(pasta or "").strip()
        if s and os.path.isdir(s):
            return s
        cfg = self._config or {}
        for key in ("caminho_pasta_ganhos", "caminho_pasta_arquivos"):
            p = str(cfg.get(key) or "").strip()
            if p and os.path.isdir(p):
                return p
        return ""

    def _ganhos_load_files(
        self, pasta: str, files: list[str],
    ) -> tuple[dict[str, Any], str]:
        """Le N arquivos tecnicos de uma pasta. Retorna ({arquivo: lines}, '')
        ou ({}, motivo_erro)."""
        if not pasta or not os.path.isdir(pasta):
            return {}, "pasta tecnica nao configurada"
        missing = [f for f in files if not os.path.isfile(os.path.join(pasta, f))]
        if missing:
            return {}, f"arquivos ausentes: {', '.join(missing)}"
        try:
            from runtime.file_io import carregar_arquivos
            dados = carregar_arquivos(pasta, files)
        except Exception as exc:  # noqa: BLE001
            return {}, f"carregar: {exc}"
        return dados or {}, ""

    @staticmethod
    def _ganhos_extrair_ano(lines: Any) -> str:
        """Extrai o ano do cabecalho de um arquivo do Interplan
        (ex.: linha 'Ano: 2025' no FlowMT.TXT). Retorna '' se nao achar."""
        import re  # noqa: PLC0415
        for line in (lines or []):
            m = re.search(r"Ano:\s*(\d{4})", str(line))
            if m:
                return m.group(1)
        return ""

    def _ganhos_validar_ano(
        self, data_flow: Any, ano_obra: Any,
    ) -> tuple[str, str]:
        """Compara o ano do cabecalho dos arquivos do Interplan com o ano
        da obra. Retorna (ano_arquivo, msg_erro). So bloqueia (msg_erro
        nao-vazio) quando AMBOS estao presentes e divergem."""
        ano_obra_s = str(ano_obra or "").strip()
        ano_arq = self._ganhos_extrair_ano(data_flow)
        if not ano_obra_s or not ano_arq:
            return ano_arq, ""
        if ano_arq != ano_obra_s:
            return ano_arq, (
                f"O ano dos arquivos do Interplan (Ano: {ano_arq}) e diferente "
                f"do ano da obra ({ano_obra_s}). Gere os ganhos no Interplan "
                f"para o ano {ano_obra_s} e selecione a pasta correta antes de "
                f"inserir os ganhos."
            )
        return ano_arq, ""

    @staticmethod
    def _ganhos_filter_alims(
        alimentadores: list[str], buffers: list[Any],
    ) -> list[str]:
        """Filtra alimentadores que nao aparecem em nenhum dos buffers
        (replica alimentadores_nos_arquivos do desktop)."""
        out = []
        for alim in alimentadores:
            if not alim:
                continue
            a_proc = alim.lower().replace(" ", "")
            encontrado = False
            for buf in buffers:
                lines = buf if isinstance(buf, list) else [buf]
                for line in lines:
                    if a_proc in str(line).lower().replace(" ", ""):
                        encontrado = True
                        break
                if encontrado:
                    break
            if encontrado:
                out.append(alim)
        return out

    @staticmethod
    def _ganhos_normalize_alims(alimentadores: Any) -> list[str]:
        if not alimentadores:
            return []
        if isinstance(alimentadores, str):
            return [a.strip() for a in alimentadores.split(",") if a.strip()]
        return [str(a).strip() for a in alimentadores
                if str(a or "").strip()]

    def _ganhos_gerar_totais_string(
        self, cm: Any, alimentadores: list[str],
        data_flow: Any, data_topo: Any, data_conf: Any,
        projeto_investimento: str, etapa: str,
    ) -> str:
        """Replica gerar_ganhos_totais do desktop: monta uma string
        'alim_metric_valor' separada por ';'. Consumida pelo Resumo
        (popular_quadro_resumo_from_ganhos_depois) -- formato deve
        bater com o que o legado emite, senao parsing falha."""
        try:
            demanda_max_por_alim = cm.calcular_demanda_maxima(
                data_flow, alimentadores) or {}
        except Exception:  # noqa: BLE001
            demanda_max_por_alim = {}
        partes: list[str] = []
        for alim in alimentadores:
            try:
                tensao_min, tensao_media = cm.calcular_tensoes(data_flow, [alim])
            except Exception:  # noqa: BLE001
                tensao_min, tensao_media = None, None
            try:
                tensao_min_linha = cm.calcular_tensao_linha_minima(
                    data_flow, [alim])
            except Exception:  # noqa: BLE001
                tensao_min_linha = None
            try:
                tensao_max, _t = cm.calcular_tensoes_max(data_flow, [alim])
            except Exception:  # noqa: BLE001
                tensao_max = None
            try:
                carreg = cm.calcular_carregamento(data_topo, [alim])
            except Exception:  # noqa: BLE001
                carreg = None
            try:
                _patamares, perda = cm.calcular_perdas(data_flow, [alim])
            except Exception:  # noqa: BLE001
                perda = None
            try:
                cont_antes, cont_depois = cm.calcular_contas_contratos(
                    data_conf, [alim])
            except Exception:  # noqa: BLE001
                cont_antes, cont_depois = None, None
            try:
                chi, ci = cm.calcular_chi_ci(data_conf, [alim])
            except Exception:  # noqa: BLE001
                chi, ci = None, None

            if etapa == "antes":
                try:
                    benef = cm.calcular_contas_contratos_beneficiadas(
                        data_topo, data_conf, [alim], projeto_investimento)
                except Exception:  # noqa: BLE001
                    benef = 0
                partes.extend([
                    f"{alim}_contas_{cont_antes}",
                    f"{alim}_contasbenef_{benef}",
                ])
            else:
                partes.append(f"{alim}_contas_{cont_depois}")
            partes.extend([
                f"{alim}_carregamento_{round(carreg or 0, 2)}",
                f"{alim}_perdas_{round(perda or 0, 2)}",
                f"{alim}_tensaomedia_{round(tensao_media or 0, 4)}",
                f"{alim}_tensaominima_{round(tensao_min or 0, 4)}",
                f"{alim}_tensaolinhaminima_{round(tensao_min_linha or 0, 4)}",
                f"{alim}_tensaomax_{round(tensao_max or 0, 4)}",
                f"{alim}_chi_{round(chi or 0, 4)}",
                f"{alim}_ci_{round(ci or 0, 4)}",
            ])
            d_max = demanda_max_por_alim.get(alim)
            if d_max is not None:
                partes.append(f"{alim}_Demand_MAX_{float(d_max):.2f}")
        return ";".join(partes)

    def ganhos_compute_antes(
        self,
        alimentadores: Any = None,
        projeto_investimento: Any = "",
        pasta: Any = "",
        ano_obra: Any = "",
    ) -> dict[str, Any]:
        """Calcula as 10 metricas + ganhos_totais 'antes' para uma obra.
        Equivalente a preencher_campos_antes do desktop, mas em uma
        unica chamada (le os 3 .TXT 1x e roda os 8 calculos contra os
        mesmos buffers). Devolve numeros prontos pra popular o form."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "error": "calc indisponivel"}
        alims = self._ganhos_normalize_alims(alimentadores)
        if not alims:
            return {"ok": False, "error": "alimentadores vazio"}
        pi = str(projeto_investimento or "").strip()
        pasta_resolved = self._ganhos_resolve_pasta(pasta)
        if not pasta_resolved:
            return {"ok": False, "error": "pasta de ganhos nao configurada"}
        dados, err = self._ganhos_load_files(
            pasta_resolved,
            ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"])
        if err:
            self._data_state_set(
                "tecnico_txt", "INVALIDADO", path=pasta_resolved, error=err)
            return {"ok": False, "error": err}
        data_flow = dados.get("FlowMT.TXT") or []
        data_topo = dados.get("Topologia.TXT") or []
        data_conf = dados.get("Confiabilidade.TXT") or []
        # Ano do arquivo do Interplan deve coincidir com o ano da obra.
        ano_arq, ano_err = self._ganhos_validar_ano(data_flow, ano_obra)
        if ano_err:
            return {"ok": False, "error": ano_err, "ano_mismatch": True,
                    "ano_arquivo": ano_arq,
                    "ano_obra": str(ano_obra or "").strip()}
        # Filtra alimentadores ausentes nos arquivos
        alims_validos = self._ganhos_filter_alims(
            alims, [data_flow, data_topo, data_conf])
        if not alims_validos:
            return {"ok": False, "alims_filtrados": alims,
                    "error": "nenhum alimentador encontrado nos arquivos"}
        ignorados = [a for a in alims if a not in alims_validos]
        # Calculos agregados (8 metricas)
        try:
            tensao_min, tensao_media = cm.calcular_tensoes(data_flow, alims_validos)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"calcular_tensoes: {exc}"}
        try:
            tensao_min_linha = cm.calcular_tensao_linha_minima(
                data_flow, alims_validos)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"tensao_linha: {exc}"}
        try:
            tensao_max, _ = cm.calcular_tensoes_max(data_flow, alims_validos)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"tensoes_max: {exc}"}
        try:
            carreg = cm.calcular_carregamento(data_topo, alims_validos)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"carregamento: {exc}"}
        try:
            _patamares, maior_perda = cm.calcular_perdas(
                data_flow, alims_validos)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"perdas: {exc}"}
        try:
            contas_antes, _contas_depois = cm.calcular_contas_contratos(
                data_conf, alims_validos)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"contas_contratos: {exc}"}
        try:
            total_benef = cm.calcular_contas_contratos_beneficiadas(
                data_topo, data_conf, alims_validos, pi) if pi else 0
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"contas_benef: {exc}"}
        try:
            chi_total, ci_total = cm.calcular_chi_ci(data_conf, alims_validos)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"chi_ci: {exc}"}
        # String agregada
        ganhos_totais = self._ganhos_gerar_totais_string(
            cm, alims_validos, data_flow, data_topo, data_conf, pi, "antes")
        # Marca tecnico_txt como VALIDADO (lemos com sucesso)
        try:
            tokens = [
                str(int(os.path.getmtime(os.path.join(pasta_resolved, f))))
                for f in ("FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT")
            ]
            self._data_state_set(
                "tecnico_txt", "CARREGADO_VALIDADO",
                path=pasta_resolved,
                version_token="-".join(tokens))
        except OSError:
            pass
        return {
            "ok": True,
            "alimentadores_validos": alims_validos,
            "alimentadores_ignorados": ignorados,
            "tensao_min": tensao_min,
            "tensao_media": tensao_media,
            "tensao_min_linha": tensao_min_linha,
            "tensao_max": tensao_max,
            "carregamento": carreg,
            "perdas": maior_perda,
            "contas_antes": contas_antes,
            "contas_benef": total_benef,
            "chi": chi_total,
            "ci": ci_total,
            "ganhos_totais": ganhos_totais,
            "pasta": pasta_resolved,
            "error": "",
        }

    def ganhos_compute_depois(
        self,
        alimentadores: Any = None,
        projeto_investimento: Any = "",
        pasta: Any = "",
        ano_obra: Any = "",
    ) -> dict[str, Any]:
        """Calcula as 7 metricas + ganhos_totais 'depois' para uma obra.
        Equivalente a preencher_campos_depois do desktop. Igual ao
        antes, mas usa contas_depois (nao antes) e nao soma beneficiadas."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "error": "calc indisponivel"}
        alims = self._ganhos_normalize_alims(alimentadores)
        if not alims:
            return {"ok": False, "error": "alimentadores vazio"}
        pi = str(projeto_investimento or "").strip()
        pasta_resolved = self._ganhos_resolve_pasta(pasta)
        if not pasta_resolved:
            return {"ok": False, "error": "pasta de ganhos nao configurada"}
        dados, err = self._ganhos_load_files(
            pasta_resolved,
            ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"])
        if err:
            self._data_state_set(
                "tecnico_txt", "INVALIDADO", path=pasta_resolved, error=err)
            return {"ok": False, "error": err}
        data_flow = dados.get("FlowMT.TXT") or []
        data_topo = dados.get("Topologia.TXT") or []
        data_conf = dados.get("Confiabilidade.TXT") or []
        # Ano do arquivo do Interplan deve coincidir com o ano da obra.
        ano_arq, ano_err = self._ganhos_validar_ano(data_flow, ano_obra)
        if ano_err:
            return {"ok": False, "error": ano_err, "ano_mismatch": True,
                    "ano_arquivo": ano_arq,
                    "ano_obra": str(ano_obra or "").strip()}
        alims_validos = self._ganhos_filter_alims(
            alims, [data_flow, data_topo, data_conf])
        if not alims_validos:
            return {"ok": False, "alims_filtrados": alims,
                    "error": "nenhum alimentador encontrado nos arquivos"}
        ignorados = [a for a in alims if a not in alims_validos]
        try:
            tensao_min, tensao_media = cm.calcular_tensoes(data_flow, alims_validos)
            tensao_min_linha = cm.calcular_tensao_linha_minima(
                data_flow, alims_validos)
            tensao_max, _ = cm.calcular_tensoes_max(data_flow, alims_validos)
            carreg = cm.calcular_carregamento(data_topo, alims_validos)
            _patamares, maior_perda = cm.calcular_perdas(
                data_flow, alims_validos)
            _contas_antes, contas_depois = cm.calcular_contas_contratos(
                data_conf, alims_validos)
            chi_total, ci_total = cm.calcular_chi_ci(data_conf, alims_validos)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"calc: {exc}"}
        ganhos_totais = self._ganhos_gerar_totais_string(
            cm, alims_validos, data_flow, data_topo, data_conf, pi, "depois")
        try:
            tokens = [
                str(int(os.path.getmtime(os.path.join(pasta_resolved, f))))
                for f in ("FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT")
            ]
            self._data_state_set(
                "tecnico_txt", "CARREGADO_VALIDADO",
                path=pasta_resolved,
                version_token="-".join(tokens))
        except OSError:
            pass
        return {
            "ok": True,
            "alimentadores_validos": alims_validos,
            "alimentadores_ignorados": ignorados,
            "tensao_min": tensao_min,
            "tensao_media": tensao_media,
            "tensao_min_linha": tensao_min_linha,
            "tensao_max": tensao_max,
            "carregamento": carreg,
            "perdas": maior_perda,
            "contas_depois": contas_depois,
            "chi": chi_total,
            "ci": ci_total,
            "ganhos_totais": ganhos_totais,
            "pasta": pasta_resolved,
            "error": "",
        }

    def ganhos_compute_atual(
        self,
        alimentadores: Any = None,
        pasta: Any = "",
    ) -> dict[str, Any]:
        """Calcula 4 metricas + ganhos_totais_atual.
        Equivalente a preencher_parametros_atuais do desktop.
        Usa apenas FlowMT.TXT + Topologia.TXT (Confiabilidade nao
        e necessario)."""
        cm = self._ensure_calc_manager()
        if cm is None:
            return {"ok": False, "error": "calc indisponivel"}
        alims = self._ganhos_normalize_alims(alimentadores)
        if not alims:
            return {"ok": False, "error": "alimentadores vazio"}
        pasta_resolved = self._ganhos_resolve_pasta(pasta)
        if not pasta_resolved:
            return {"ok": False, "error": "pasta de ganhos nao configurada"}
        dados, err = self._ganhos_load_files(
            pasta_resolved, ["FlowMT.TXT", "Topologia.TXT"])
        if err:
            return {"ok": False, "error": err}
        data_flow = dados.get("FlowMT.TXT") or []
        data_topo = dados.get("Topologia.TXT") or []
        try:
            tensao_min, _ = cm.calcular_tensoes(data_flow, alims)
            tensao_min_linha = cm.calcular_tensao_linha_minima(data_flow, alims)
            tensao_max, _ = cm.calcular_tensoes_max(data_flow, alims)
            carreg = cm.calcular_carregamento(data_topo, alims)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"calc: {exc}"}
        # Replica gerar_ganhos_totais_atual: per-alim com prefixo _atual.
        partes: list[str] = []
        for alim in alims:
            partes.extend([
                f"{alim}_carrg_atual_{round(carreg or 0, 4)}",
                f"{alim}_tensao_min_atual_{round(tensao_min or 0, 4)}",
                f"{alim}_tensao_linha_min_atual_{round(tensao_min_linha or 0, 4)}",
                f"{alim}_tensao_max_atual_{round(tensao_max or 0, 4)}",
            ])
        ganhos_atual = ";".join(partes)
        return {
            "ok": True,
            "tensao_min": tensao_min,
            "tensao_min_linha": tensao_min_linha,
            "tensao_max": tensao_max,
            "carregamento": carreg,
            "ganhos_atual": ganhos_atual,
            "tensao_reg_atual": (
                f"{round(tensao_min or 0, 4)}/{round(tensao_max or 0, 4)}"),
            "pasta": pasta_resolved,
            "error": "",
        }

    def ganhos_apply_to_obra(
        self,
        cod: Any = "",
        etapa: Any = "antes",
        alimentadores: Any = None,
        projeto_investimento: Any = "",
        pasta: Any = "",
    ) -> dict[str, Any]:
        """Calcula + persiste em uma chamada para uma obra: chama
        ganhos_compute_(antes|depois) e atualiza
        ganhos_totais_(antes|depois) na linha do banco via
        DatabaseManager.update_obra (passando dict so com a coluna
        alterada e skip_blank=True para nao zerar outros campos)."""
        cod_s = str(cod or "").strip()
        if not cod_s:
            return {"ok": False, "error": "cod vazio"}
        etapa_s = str(etapa or "antes").strip().lower()
        if etapa_s not in ("antes", "depois"):
            return {"ok": False, "error": "etapa deve ser 'antes' ou 'depois'"}
        if etapa_s == "antes":
            r = self.ganhos_compute_antes(
                alimentadores, projeto_investimento, pasta)
        else:
            r = self.ganhos_compute_depois(
                alimentadores, projeto_investimento, pasta)
        if not r.get("ok"):
            return r
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel"}
        col = "ganhos_totais_antes" if etapa_s == "antes" else "ganhos_totais_depois"
        ganhos_str = str(r.get("ganhos_totais") or "")
        try:
            # update_obra recebe dict + cod + skip_blank. Passamos so a
            # coluna que muda; skip_blank=True garante que strings vazias
            # nao sobrescrevam outras colunas (paranoid: o dict so tem 1
            # chave aqui, mas mantemos o flag).
            db.update_obra({col: ganhos_str}, cod_s, skip_blank=True)
        except Exception as exc:  # noqa: BLE001
            friendly = self._friendly_busy_error(exc)
            out: dict[str, Any] = {
                "ok": False,
                "error": friendly or f"update_obra: {exc}",
                "computed": r,
            }
            if friendly:
                out["blocked"] = "db_busy"
            return out
        return {
            "ok": True,
            "cod": cod_s,
            "etapa": etapa_s,
            "ganhos_totais": ganhos_str,
            "alimentadores_validos": r.get("alimentadores_validos") or [],
            "alimentadores_ignorados": r.get("alimentadores_ignorados") or [],
            "metricas": {k: v for k, v in r.items()
                         if k not in ("ok", "error", "ganhos_totais",
                                      "alimentadores_validos",
                                      "alimentadores_ignorados", "pasta")},
        }

    def ganhos_apply_massa(
        self,
        cods: Any = None,
        etapa: Any = "antes",
        pasta: Any = "",
    ) -> dict[str, Any]:
        """Aplica ganhos em massa para uma lista de cods.
        Para cada obra: le alimentadores + projeto da linha, computa
        e persiste. Equivalente a preencher_ganhos_massa do desktop."""
        cods_list = cods or []
        if not isinstance(cods_list, list):
            cods_list = [cods_list]
        cods_list = [str(c).strip() for c in cods_list if str(c or "").strip()]
        if not cods_list:
            return {"ok": False, "error": "cods vazio"}
        etapa_s = str(etapa or "antes").strip().lower()
        if etapa_s not in ("antes", "depois"):
            return {"ok": False, "error": "etapa deve ser 'antes' ou 'depois'"}
        db, err = self._ensure_db_connected()
        if err or db is None:
            return {"ok": False, "error": err or "db indisponivel"}
        try:
            cols = list(db.get_column_names() or [])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"cols: {exc}"}
        i_cod = cols.index("cod") if "cod" in cols else -1
        i_alim = cols.index("alimentador_principal") if "alimentador_principal" in cols else -1
        i_alim_benef = cols.index("alimentadores_beneficiados") if "alimentadores_beneficiados" in cols else -1
        i_pi = cols.index("projeto_investimento") if "projeto_investimento" in cols else -1
        if i_cod < 0 or i_alim < 0 or i_pi < 0:
            return {"ok": False, "error": "schema incompativel (cod/alim/pi)"}
        try:
            rows = list(db.fetch_by_cods(cods_list) or [])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"fetch_by_cods: {exc}"}
        sucesso = 0
        falhas: list[dict[str, str]] = []
        ignoradas: list[str] = []
        for row in rows:
            cod_v = str(row[i_cod]).strip() if 0 <= i_cod < len(row) else ""
            alim_p = str(row[i_alim]).strip() if 0 <= i_alim < len(row) else ""
            alim_b_raw = (str(row[i_alim_benef]).strip()
                          if 0 <= i_alim_benef < len(row) else "")
            pi = str(row[i_pi]).strip() if 0 <= i_pi < len(row) else ""
            alims = [a for a in [alim_p] if a]
            if alim_b_raw:
                alims.extend([a.strip() for a in alim_b_raw.split(",")
                              if a.strip()])
            if not alims:
                ignoradas.append(cod_v)
                continue
            r = self.ganhos_apply_to_obra(
                cod_v, etapa_s, alims, pi, pasta)
            if r.get("ok"):
                sucesso += 1
            else:
                falhas.append({"cod": cod_v,
                               "error": r.get("error") or "?"})
        return {
            "ok": True,
            "sucesso": sucesso,
            "falhas": falhas,
            "ignoradas_sem_alim": ignoradas,
            "total": len(cods_list),
        }
