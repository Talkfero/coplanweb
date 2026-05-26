# -*- coding: utf-8 -*-
"""Mixin de dominio "cadastro" da CoplanApi (extraido de main_web.py).

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


class CadastroMixin:

    def get_alimentador_details(self, alim: Any) -> dict[str, Any]:
        """Retorna metadados de UM alimentador (TENSAO, REGIONAL,
        SUPERINTENDENCIA, SE) -- replica apoio_mixin.alimentador_selecionado
        do desktop. Vazio se nao houver apoio carregado ou alim nao
        constar nele."""
        a = str(alim or "").strip()
        if not a:
            return {"ok": False, "error": "alim vazio"}
        cache = getattr(self, "_apoio_cache", None) or {}
        dados_alim = cache.get("dados_alimentador") or {}
        # Tenta exato; depois case-insensitive.
        if a in dados_alim:
            d = dados_alim[a]
        else:
            up = a.upper()
            d = None
            for k, v in dados_alim.items():
                if str(k).upper() == up:
                    d = v
                    break
        if not d:
            return {"ok": False, "error": f"alimentador '{a}' nao encontrado no apoio"}
        return {
            "ok": True, "error": "",
            "alim": a,
            "tensao":           str(d.get("TENSÃO") or d.get("TENSAO") or "").strip(),
            "regional":         str(d.get("REGIONAL") or "").strip(),
            "superintendencia": str(d.get("SUPERINTENDÊNCIA")
                                    or d.get("SUPERINTENDENCIA") or "").strip(),
            "se":               str(d.get("SE") or "").strip(),
        }

    # ------------------------------------------------------------------
    # Passo 4.4 (Cadastro / list_alimentadores): catalogo de alimentadores
    # ja cadastrados (alimentador_principal + alimentadores_beneficiados
    # parseados). Usado pelo <select> "Alimentador Beneficiado" do form.
    # Retorna lista unica ordenada alfabeticamente.
    # ------------------------------------------------------------------
    def list_alimentadores(self) -> dict[str, Any]:
        # Importante: o usuario precisa dos alimentadores do APOIO mesmo
        # quando o DB esta vazio ou inacessivel (caso do primeiro setup).
        # Estrategia: tenta DB primeiro mas trata falha como WARN (nao
        # zera resposta) -- sempre mescla com self._apoio_cache no final.
        unique: set[str] = set()
        warnings: list[str] = []

        # 1. DB (alimentadores ja cadastrados em obras).
        db, err = self._ensure_db_connected()
        if err or db is None:
            warnings.append(f"db: {err or 'indisponivel'}")
        else:
            # _get_cursor() retorna None apos _with_connection fechar.
            # Usamos open_sqlite_safe direto + fechamos manualmente, em
            # vez de db._get_cursor() (que so funciona dentro de
            # _with_connection). Replica o que outras APIs fazem (ex.:
            # search_obras) usando cursor fresco.
            try:
                from runtime.database import open_sqlite_safe  # noqa: PLC0415
                db_path = (self._config or {}).get("obras") or ""
                if db_path and os.path.isfile(str(db_path)):
                    conn = open_sqlite_safe(str(db_path))
                    try:
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT alimentador_principal, "
                            "alimentadores_beneficiados FROM obras"
                        )
                        for row in cur.fetchall():
                            principal = str(row[0] or "").strip()
                            if principal:
                                unique.add(principal.upper())
                            benef_raw = str(row[1] or "")
                            for piece in re.split(r"[;,|]+", benef_raw):
                                p = piece.strip().upper()
                                if p:
                                    unique.add(p)
                    finally:
                        try:
                            conn.close()
                        except Exception:  # noqa: BLE001
                            pass
                else:
                    warnings.append("db: path invalido")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"sql: {exc}")

        # 2. Cache do apoio (DB-backed): mais completo que o banco de
        # obras pois inclui alim ainda nao cadastrados. Hidrata via
        # _apoio_cache_dict (le tabela apoio_apoio se cache vazio).
        cache = self._apoio_cache_dict()
        for a in (cache.get("alimentadores") or []):
            s = str(a or "").strip().upper()
            if s:
                unique.add(s)

        items = sorted(unique)
        # Tambem extrai prefixo (SE candidata) de cada alimentador para o
        # JS poder oferecer agrupamento ou validacao.
        ses: list[str] = []
        seen_se: set[str] = set()
        for a in items:
            pref = re.split(r"[-_/]", a, 1)[0].strip().upper()
            if pref and pref not in seen_se:
                seen_se.add(pref)
                ses.append(pref)
        # ok=True sempre que tivermos itens; warnings mostra de onde
        # veio a falha parcial (DB ou apoio) -- nao bloqueia o JS de
        # popular o combo.
        return {
            "ok": bool(items),
            "items": items,
            "ses": ses,
            "warnings": warnings,
            "error": ("; ".join(warnings) if not items and warnings else ""),
        }

    # ------------------------------------------------------------------
    # Passo 4.5 (Cadastro / metadata para selects):
    #   * get_pi_options()   -> projetos de investimento + bases curtas
    #   * get_regionais()    -> chaves de REGIONAL_MAP + extras do config
    #   * get_pacotes()      -> distinct(tipo_pacote) do banco + defaults
    # Tudo em uma so chamada agregada (`get_form_metadata`) para o JS
    # popular os 3 selects de uma vez.
    # ------------------------------------------------------------------
    def get_pi_options(self) -> dict[str, Any]:
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            from runtime.pi_base import PI_BASE_CUSTOM  # noqa: PLC0415
            from core.services.pi_metadata_service import (  # type: ignore[import-not-found]
                listar_todas_bases,
            )
            cfg = ConfigManager.load_config() or {}
            bases = listar_todas_bases(cfg, custom_bases=tuple(PI_BASE_CUSTOM))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "items": [], "error": f"pi_metadata: {exc}"}
        # Tambem busca os nomes longos ja usados em obras (projeto_investimento)
        # para que o select reflita o que ja existe na base do cliente.
        long_names: list[str] = []
        seen_long: set[str] = set()
        # 1) Apoio (replica o que o desktop popula em
        #    field_projeto_investimento.addItems(dados['projetos_investimento'])).
        cache = getattr(self, "_apoio_cache", None) or {}
        for v in (cache.get("projetos_investimento") or []):
            s = str(v or "").strip()
            k = s.upper()
            if s and k not in seen_long:
                seen_long.add(k)
                long_names.append(s)
        # 2) Banco (DISTINCT projeto_investimento das obras existentes).
        try:
            db, err = self._ensure_db_connected()
            if not err and db is not None:
                cursor = db._get_cursor()
                if cursor is not None:
                    cursor.execute(
                        "SELECT DISTINCT projeto_investimento FROM obras "
                        "WHERE projeto_investimento IS NOT NULL "
                        "AND TRIM(projeto_investimento) <> ''"
                    )
                    for row in cursor.fetchall():
                        v = str(row[0] or "").strip()
                        key = v.upper()
                        if v and key not in seen_long:
                            seen_long.add(key)
                            long_names.append(v)
                    long_names.sort()
        except Exception:  # noqa: BLE001
            pass
        return {
            "ok": True,
            "bases": list(bases),
            "long_names": long_names,
            "error": "",
        }

    def get_regionais(self) -> dict[str, Any]:
        try:
            from runtime.config import REGIONAL_MAP, ConfigManager  # noqa: PLC0415
            base = list(REGIONAL_MAP.keys())
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "items": [], "error": f"REGIONAL_MAP: {exc}"}
        # Adiciona regionais extras configuradas no config.json
        # (regional_map = dict { nome: codigo }).
        try:
            cfg = ConfigManager.load_config() or {}
            extras = list((cfg.get("regional_map") or {}).keys())
            for e in extras:
                if e and e not in base:
                    base.append(e)
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "items": sorted(set(base)), "error": ""}

    def get_pacotes(self) -> dict[str, Any]:
        # Defaults vindos do mock + nomes vistos no banco. Mantidos
        # apenas em alfabetico para nao impor ordenacao opinativa.
        defaults = [
            "Mercado", "Confiabilidade", "Interligação UDE",
            "Interligação de UDE", "Solicitação Regional",
            "Orçamento de Conexão", "PLPT",
        ]
        seen_keys: set[str] = set()
        out: list[str] = []
        for v in defaults:
            k = v.strip().upper()
            if k and k not in seen_keys:
                seen_keys.add(k)
                out.append(v.strip())
        try:
            db, err = self._ensure_db_connected()
            if not err and db is not None:
                cursor = db._get_cursor()
                if cursor is not None:
                    cursor.execute(
                        "SELECT DISTINCT tipo_pacote FROM obras "
                        "WHERE tipo_pacote IS NOT NULL "
                        "AND TRIM(tipo_pacote) <> ''"
                    )
                    for row in cursor.fetchall():
                        v = str(row[0] or "").strip()
                        k = v.upper()
                        if v and k not in seen_keys:
                            seen_keys.add(k)
                            out.append(v)
        except Exception:  # noqa: BLE001
            pass
        out.sort()
        return {"ok": True, "items": out, "error": ""}

    def get_form_metadata(self) -> dict[str, Any]:
        """Agregador para o JS popular todos os selects do Cadastro de
        uma vez. Inclui alimentadores (banco+apoio) e caracteristicas
        (apoio) para que os selects nao fiquem so com a opcao do mock."""
        # Alimentadores: list_alimentadores ja mescla banco + apoio.
        alim = self.list_alimentadores()
        # Caracteristicas vem do apoio cache (carregadas pelo
        # SupportFileManager.load_support_file).
        cache = getattr(self, "_apoio_cache", None) or {}
        carac_items = sorted({
            str(c).strip() for c in (cache.get("caracteristicas") or [])
            if str(c or "").strip()
        })
        return {
            "pi": self.get_pi_options(),
            "regionais": self.get_regionais(),
            "pacotes": self.get_pacotes(),
            "alimentadores": {
                "ok": bool(alim.get("ok")),
                "items": list(alim.get("items") or []),
            },
            "caracteristicas": {
                "ok": bool(carac_items),
                "items": carac_items,
            },
        }

    # ------------------------------------------------------------------
    # Cadastro / metodos auxiliares (leva 2 da migracao desktop->web).
    # Origem: ui/main_window/cadastro_mixin.py + apoio_mixin.py.
    # M020 cadastro_form_metadata, M021 caracteristicas_por_alimentador,
    # M024 validar_cadastro, M025 resolver_pi_base, M029 tecnico_snapshot.
    # ------------------------------------------------------------------

    def cadastro_form_metadata(self) -> dict[str, Any]:
        """[M020] Agregador especifico do cadastro: estende
        get_form_metadata com listas hardcoded do desktop
        (manobra/aprovada/novo_bay/criticidade), o range de Ano
        (current..+10). Reaproveita get_form_metadata para os combos
        comuns (PI, regionais, pacotes, alimentadores, caracteristicas)."""
        from datetime import datetime as _dt
        ano_atual = _dt.now().year
        meta = self.get_form_metadata()
        return {
            "ok": True, "error": "",
            "ano_range":     [str(y) for y in range(ano_atual, ano_atual + 11)],
            "pi":            meta.get("pi") or {"ok": False, "bases": [], "long_names": []},
            "regionais":     meta.get("regionais") or {"ok": False, "items": []},
            "pacotes":       meta.get("pacotes") or {"ok": False, "items": [
                "Mercado", "Confiabilidade", "Interligação de UDE",
                "Solicitação Regional", "Orçamento de Conexao", "PLPT",
            ]},
            "alimentadores":   meta.get("alimentadores") or {"ok": False, "items": []},
            "caracteristicas": meta.get("caracteristicas") or {"ok": False, "items": []},
            "manobra":         ["SIM", "NÃO"],
            "aprovada":        ["NÃO", "SIM"],
            "novo_bay":        ["NÃO", "SIM"],
            "criticidade":     ["Baixa", "Média", "Alta"],
        }

    def caracteristicas_por_alimentador(self, alim: Any) -> dict[str, Any]:
        """[M021] Lista CARACTERISTICAS de um alimentador especifico,
        replicando apoio_mixin.alimentador_selecionado (recarrega o combo
        de Caracteristicas conforme escolha). Cai pra lista geral do
        apoio quando o alim nao consta em dados_alimentador."""
        a = str(alim or "").strip()
        if not a:
            return {"ok": False, "items": [], "error": "alim vazio"}
        cache = getattr(self, "_apoio_cache", None) or {}
        dados_alim = cache.get("dados_alimentador") or {}
        d = dados_alim.get(a)
        if d is None:
            up = a.upper()
            for k, v in dados_alim.items():
                if str(k).upper() == up:
                    d = v
                    break
        if not d:
            geral = sorted({
                str(c).strip() for c in (cache.get("caracteristicas") or [])
                if str(c or "").strip()
            })
            return {
                "ok": bool(geral), "items": geral,
                "error": (f"alimentador '{a}' nao encontrado no apoio"
                          " (mostrando lista geral)"),
            }
        raw = d.get("CARACTERÍSTICAS") or d.get("CARACTERISTICAS") or []
        items: list[str] = []
        if isinstance(raw, str):
            items = [s.strip() for s in raw.split(";") if s.strip()]
        elif isinstance(raw, dict):
            items = [str(k).strip() for k in raw.keys() if str(k or "").strip()]
        elif isinstance(raw, (list, tuple, set)):
            items = [str(c).strip() for c in raw if str(c or "").strip()]
        items = sorted(set(items))
        return {"ok": True, "items": items, "error": ""}

    def validar_cadastro(self, payload: Any) -> dict[str, Any]:
        """[M024] Espelho server-side de
        cadastro_mixin.validar_campos_obrigatorios. Aplica
        [RB-DISTRIBUICAO]: 'nome_projeto' so eh obrigatorio quando
        projeto_investimento normalizado for DISTRIBUICAO ou
        DISTRIBUICAO LD 34,5 KV. Tambem reporta avisos: alimentadores
        com '_' (validacao do desktop) e nome_projeto comecando com
        'Obra' (label informativa do desktop)."""
        if not isinstance(payload, dict):
            payload = {}

        def _v(key: str) -> str:
            return str(payload.get(key) or "").strip()

        obrig = {
            "Ano":                       _v("ano_") or _v("ano"),
            "Projeto de Investimento":   _v("projeto_investimento"),
            "Alimentador Obra":          _v("alimentador_principal"),
            "Quantidade":                _v("quantidade_material") or _v("quantidade"),
            "Coordenadas Para":          _v("coordenada_fim"),
            "Pacote":                    _v("tipo_pacote") or _v("pacote"),
            "Caracteristicas":           _v("caracteristicas_material") or _v("caracteristicas"),
            "Manobra":                   _v("manobra"),
        }

        pi_raw = _v("projeto_investimento")
        pi_base_raw = _v("pi_base")
        try:
            from runtime.text_utils import normalize_key  # noqa: PLC0415
        except Exception:  # noqa: BLE001
            def normalize_key(s: str) -> str:  # type: ignore[no-redef]
                return (s or "").strip().upper()
        valores_distribuicao = {"DISTRIBUICAO", "DISTRIBUICAO LD 34,5 KV"}
        if (
            normalize_key(pi_raw) in valores_distribuicao
            or normalize_key(pi_base_raw) in valores_distribuicao
        ):
            obrig["Projeto"] = _v("nome_projeto")

        faltantes = [nome for nome, valor in obrig.items() if not valor]

        avisos: list[str] = []
        alim_principal = _v("alimentador_principal")
        if "_" in alim_principal:
            avisos.append(f"alimentador '{alim_principal}' contem '_'")
        benef_raw = payload.get("alimentadores_beneficiados") or ""
        if isinstance(benef_raw, list):
            benef_list = [str(x).strip() for x in benef_raw if str(x or "").strip()]
        else:
            benef_list = [s.strip() for s in str(benef_raw).split(";")
                          if s.strip()]
        for b in benef_list:
            if "_" in b:
                avisos.append(f"alimentador beneficiado '{b}' contem '_'")
        nome_proj = _v("nome_projeto")
        if nome_proj.lower().startswith("obra"):
            avisos.append("nome_projeto inicia com 'Obra' (informativo)")

        return {
            "ok": (not faltantes) and (not avisos),
            "faltantes": faltantes,
            "avisos": avisos,
            "error": "",
        }

    def resolver_pi_base(self, pi: Any) -> dict[str, Any]:
        """[M025] Devolve {pi_base, conhecido} sem prompt server-side. Se
        nao for conhecido, JS deve abrir prompt local e persistir via
        save_pi_base_map(). Reflete get_pi_base(prompt_user=False)."""
        pi_s = str(pi or "").strip()
        if not pi_s:
            return {"ok": False, "pi_base": "", "conhecido": False,
                    "error": "pi vazio"}
        try:
            from runtime.pi_base import get_pi_base, _is_pi_base_known  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "pi_base": "", "conhecido": False,
                    "error": f"import: {exc}"}
        try:
            conhecido = bool(_is_pi_base_known(pi_s))
        except Exception:  # noqa: BLE001
            conhecido = False
        try:
            base = str(get_pi_base(pi_s, prompt_user=False) or "").strip()
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "pi_base": "", "conhecido": conhecido,
                    "error": f"get_pi_base: {exc}"}
        return {"ok": True, "pi_base": base, "conhecido": conhecido,
                "error": ""}

