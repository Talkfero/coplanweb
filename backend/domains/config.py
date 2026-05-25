# -*- coding: utf-8 -*-
"""Mixin de dominio "config" da CoplanApi (extraido de main_web.py).

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


class ConfigMixin:

    # ------------------------------------------------------------------
    # Fase C1 (set_extra_keys_for_pi):
    # Permite ao usuario salvar (no config) chaves extras adicionais para
    # um PI base. Estas chaves se somam a `metadata.calculo.modulos_extras`
    # (config-driven) na proxima rodada de calcular_valor_obra.
    # ------------------------------------------------------------------
    def set_modulos_extras(
        self, pi_base: Any = "", extras: Any = None,
    ) -> dict[str, Any]:
        pi = str(pi_base or "").strip().upper()
        if not pi:
            return {"ok": False, "error": "pi vazio", "extras": []}
        if not isinstance(extras, (list, tuple)):
            return {"ok": False, "error": "extras nao e lista", "extras": []}
        try:
            from runtime.pi_base import set_extra_keys_for_pi  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}", "extras": []}
        normalized = [str(k).strip().upper() for k in extras if str(k or "").strip()]
        try:
            set_extra_keys_for_pi(pi, normalized)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}", "extras": []}
        # Atualiza nosso cache de config local pra refletir a mudanca.
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            self._config = ConfigManager.load_config() or self._config
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "error": "", "pi": pi, "extras": normalized}

    # ------------------------------------------------------------------
    # Fase A11 (pi_metadata_service.obter_modulos_extras):
    # Retorna a lista de chaves extras (modulo_extra do PI + ATERRAMENTO
    # se exige_aterramento + last_pi_extra_map salvo no config). Util
    # para a UI de Cadastro mostrar as chaves que serao somadas no
    # calculo de valor_obra.
    # ------------------------------------------------------------------
    def get_modulos_extras(self, pi_base: Any = "") -> dict[str, Any]:
        pi = str(pi_base or "").strip()
        if not pi:
            return {"ok": False, "error": "pi vazio", "extras": [], "pi": pi}
        try:
            from core.services.pi_metadata_service import (  # type: ignore[import-not-found]
                obter_modulos_extras,
            )
            from runtime.config import ConfigManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}",
                    "extras": [], "pi": pi}
        try:
            cfg = ConfigManager.load_config() or {}
        except Exception:  # noqa: BLE001
            cfg = {}
        try:
            extras = list(obter_modulos_extras(pi, cfg) or [])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"obter_modulos_extras: {exc}",
                    "extras": [], "pi": pi}
        return {"ok": True, "error": "", "pi": pi, "extras": extras}

    # ------------------------------------------------------------------
    # Fase A10 (pi_metadata_service.obter_descricao_template +
    #           get_descricao_obra_from_template):
    # devolve o template do PI e renderiza com dados do form (placeholder
    # {col} substituidos pelos valores).
    # ------------------------------------------------------------------
    def get_descricao_template(self, pi: Any = "") -> dict[str, Any]:
        pi_s = str(pi or "").strip()
        try:
            from core.services.pi_metadata_service import (  # type: ignore[import-not-found]
                obter_descricao_template,
            )
            from runtime.config import ConfigManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}", "template": "",
                    "pi": pi_s}
        try:
            cfg = ConfigManager.load_config() or {}
        except Exception:  # noqa: BLE001
            cfg = {}
        # Tambem honra o override por PI: config.descricao_obra_templates[PI]
        custom = ""
        try:
            templates = cfg.get("descricao_obra_templates") or {}
            if isinstance(templates, dict):
                custom = str(templates.get(pi_s.upper()) or "")
        except Exception:  # noqa: BLE001
            custom = ""
        try:
            default = obter_descricao_template(pi_s, cfg) or ""
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"obter_template: {exc}",
                    "template": "", "pi": pi_s}
        return {"ok": True, "error": "",
                "pi": pi_s,
                "template_default": default,
                "template_custom": custom,
                "template": custom or default}

    def aplicar_template_descricao(
        self, pi_base: Any = "", dados: Any = None,
    ) -> dict[str, Any]:
        pi = str(pi_base or "").strip()
        if not isinstance(dados, dict):
            dados = {}
        try:
            from runtime.calc import get_descricao_obra_from_template  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}", "descricao": ""}
        try:
            descricao = get_descricao_obra_from_template(pi, dict(dados))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"render: {exc}", "descricao": ""}
        if descricao is None:
            return {"ok": False, "error": "sem template para o PI",
                    "descricao": ""}
        return {"ok": True, "error": "", "descricao": descricao}

    # ------------------------------------------------------------------
    # Passo 7.1 (Config / Empresa): get/save dos campos da empresa.
    #   * sigla            (config.empresa_sigla)
    #   * razao_social     (config.razao_social  -- chave NOVA, nao quebra
    #                       o legado, mas aparece no JSON ao salvar)
    #   * caminho_db       (config.obras)
    # Apoio NAO esta mais aqui: agora e DB-backed (tabelas apoio_*).
    # Use o botao "Atualizar apoio" no card Empresa para reimportar.
    # ------------------------------------------------------------------
    def get_config_empresa(self) -> dict[str, Any]:
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"config: {exc}"}
        return {
            "ok": True, "error": "",
            "sigla":         str(cfg.get("empresa_sigla") or "").strip(),
            "razao_social":  str(cfg.get("razao_social") or "").strip(),
            "caminho_db":    str(cfg.get("obras") or "").strip(),
            "caminho_pasta_ganhos": str(cfg.get("caminho_pasta_ganhos") or "").strip(),
        }

    def save_config_empresa(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"ok": False, "error": "payload nao e dict"}
        try:
            from runtime.config import ConfigManager, EMPRESA_SIGLAS_VALIDAS  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}"}

        partial: dict[str, Any] = {}

        if "sigla" in payload:
            sigla = str(payload.get("sigla") or "").strip().upper()
            if sigla and sigla not in EMPRESA_SIGLAS_VALIDAS:
                return {"ok": False, "error":
                        f"Sigla invalida. Permitidas: "
                        f"{', '.join(sorted(EMPRESA_SIGLAS_VALIDAS))}"}
            partial["empresa_sigla"] = sigla
        if "razao_social" in payload:
            partial["razao_social"] = str(payload.get("razao_social") or "").strip()
        if "caminho_db" in payload:
            partial["obras"] = str(payload.get("caminho_db") or "").strip()
        if "caminho_pasta_ganhos" in payload:
            partial["caminho_pasta_ganhos"] = str(
                payload.get("caminho_pasta_ganhos") or ""
            ).strip()

        if not partial:
            return {"ok": False, "error": "payload sem campos conhecidos"}
        try:
            ConfigManager.save_config(partial)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        # Invalida cache interno -- proxima chamada le do disco.
        self._config = None
        # Se o caminho do banco mudou, esquece o cache de paths
        # conectados (forca reconnect na proxima chamada).
        if "obras" in partial:
            self._connected_paths.clear()
        return {"ok": True, "error": "", "saved": list(partial.keys())}

    def pick_db_file(self) -> dict[str, Any]:
        return self._pick_file_with_filters(
            "Banco SQLite (*.db;*.sqlite;*.sqlite3)",
        )

    def pick_apoio_file(self) -> dict[str, Any]:
        return self._pick_file_with_filters(
            "Planilha de Apoio (*.xlsx;*.xlsm;*.xls;*.csv)",
        )

    # ------------------------------------------------------------------
    # Passo 7.2 (Config / Criterios de Planejamento): persiste os 8
    # campos editaveis do card "Criterios de Planejamento (vigentes)".
    #   Campo no mock                      -> Coluna do config.json
    #   Tensao Min. (pu)                   -> criterios_planejamento.tensao_min
    #   Tensao Max. (pu)                   -> criterios_planejamento.tensao_max
    #   Carregamento Max. (%)              -> criterios_planejamento.carregamento_limite_sim_ou_vazio
    #   CHI Minimo                         -> criterios_planejamento.chi_min  (chave nova)
    #   CI Minimo                          -> criterios_planejamento.ci_min   (chave nova)
    #   Piora Mercado (%)                  -> piora_mercado.carregamento_percentual
    #   Anos de horizonte                  -> piora_mercado.anos_horizonte
    #   Postergacao max. (anos)            -> piora_mercado.postergacao_max_anos (chave nova)
    # As chaves "novas" (chi_min, ci_min, postergacao_max_anos) coexistem
    # com os defaults legados sem quebrar nada, e ficam disponiveis para o
    # get_criterios() do Passo 5.3 aplicar nas regras.
    # ------------------------------------------------------------------
    @staticmethod
    def _to_float(v: Any) -> float | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", ".")
        s = re.sub(r"[^0-9.\-]", "", s)
        try:
            return float(s)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Passo 7.3 (Config / Templates + PI_BASE):
    #   * get_templates / save_templates    -> config.descricao_obra_templates
    #   * list_pi_base_custom               -> config.pi_base_custom + DEFAULT pi_metadata
    #   * add_pi_base_custom / remove        -> mutate pi_base_custom list
    #   * get_pi_base_map / save_pi_base_map -> config.pi_base_map (dict de
    #     mapeamentos PI nao-canonicos -> base curta)
    # ------------------------------------------------------------------
    def get_templates(self) -> dict[str, Any]:
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"config: {exc}", "items": {}}
        items = cfg.get("descricao_obra_templates") or {}
        if not isinstance(items, dict):
            items = {}
        return {"ok": True, "error": "", "items": items}

    def save_templates(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"ok": False, "error": "payload nao e dict"}
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}"}
        clean = {
            str(k).strip().upper(): str(v) for k, v in payload.items()
            if str(k).strip()
        }
        try:
            ConfigManager.save_config({"descricao_obra_templates": clean})
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return {"ok": True, "error": "", "count": len(clean)}

    # Bloco 2 (Templates de Descricao) - Auditoria #11/#12/#13.
    # save_config faz deep merge: para REMOVER chave de templates precisa
    # ler config inteiro, mutar e salvar com overwrite=True.
    def delete_pi_template(self, pi: Any = "") -> dict[str, Any]:
        """Restaura padrao do PI: remove a chave de descricao_obra_templates."""
        pi_s = str(pi or "").strip().upper()
        if not pi_s:
            return {"ok": False, "error": "pi vazio"}
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}"}
        try:
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"load: {exc}"}
        templates_cfg = dict(cfg.get("descricao_obra_templates") or {})
        had = pi_s in templates_cfg
        templates_cfg.pop(pi_s, None)
        cfg["descricao_obra_templates"] = templates_cfg
        try:
            ConfigManager.save_config(cfg, overwrite=True)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return {"ok": True, "error": "", "removed": had, "pi": pi_s}

    def restore_all_templates(self) -> dict[str, Any]:
        """Restaura todos: zera descricao_obra_templates."""
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}"}
        try:
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"load: {exc}"}
        before = len(dict(cfg.get("descricao_obra_templates") or {}))
        cfg["descricao_obra_templates"] = {}
        try:
            ConfigManager.save_config(cfg, overwrite=True)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return {"ok": True, "error": "", "removed": before}

    def template_preview_render(
        self, pi: Any = "", template: Any = "",
    ) -> dict[str, Any]:
        """Renderiza um template (texto editado, NAO salvo) usando dados
        da primeira obra do banco com pi_base = pi. Fallback: dict vazio
        (placeholders viram strings vazias)."""
        pi_s = str(pi or "").strip().upper()
        tpl = str(template or "")
        if not tpl:
            return {"ok": True, "error": "", "rendered": "",
                    "obra_cod": "", "obra_count": 0}
        try:
            from runtime.text_utils import render_template  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}",
                    "rendered": "", "obra_cod": "", "obra_count": 0}
        data: dict[str, Any] = {}
        obra_cod = ""
        obra_count = 0
        db, _err = self._ensure_db_connected()
        if db is not None:
            try:
                cursor = db._get_cursor()
                if cursor is not None:
                    cursor.execute(
                        "SELECT * FROM obras WHERE UPPER(TRIM(COALESCE(pi_base,'')))=?"
                        " LIMIT 1",
                        (pi_s,),
                    )
                    row = cursor.fetchone()
                    if row:
                        cols = [d[0] for d in (cursor.description or [])]
                        data = {cols[i]: row[i] for i in range(len(cols))}
                        obra_cod = str(data.get("cod") or "")
                        obra_count = 1
            except Exception:  # noqa: BLE001
                data = {}
        # Normaliza valores None -> '' para render mais limpo
        clean = {k: ("" if v is None else str(v)) for k, v in data.items()}
        try:
            rendered = render_template(tpl, clean)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"render: {exc}",
                    "rendered": "", "obra_cod": obra_cod,
                    "obra_count": obra_count}
        return {"ok": True, "error": "", "rendered": rendered,
                "obra_cod": obra_cod, "obra_count": obra_count}

    def get_template_field_candidates(self) -> dict[str, Any]:
        """Lista de colunas para inserir como {placeholder} no template.
        Espelho de _get_visualizar_columns_candidates do desktop:
        ORDERED_COLUMNS + colunas reais do banco, deduplicado."""
        try:
            from runtime.config import ORDERED_COLUMNS  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}", "items": []}
        ordered = [str(c) for c in (ORDERED_COLUMNS or []) if c]
        cols_db: list[str] = []
        db, _err = self._ensure_db_connected()
        if db is not None:
            try:
                cols_db = list(db.get_column_names() or [])
            except Exception:  # noqa: BLE001
                cols_db = []
        if not cols_db:
            return {"ok": True, "error": "", "items": ordered}
        seen = set()
        out: list[str] = []
        for c in ordered:
            if c in cols_db and c not in seen:
                out.append(c)
                seen.add(c)
        for c in cols_db:
            if c not in seen:
                out.append(c)
                seen.add(c)
        return {"ok": True, "error": "", "items": out}

    def list_pi_base_custom(self) -> dict[str, Any]:
        """Devolve {ok, custom: [...], all: [...], hidden_defaults: [...]}.
        - custom: lista mutavel salva em config.pi_base_custom.
        - hidden_defaults: defaults que o usuario removeu (config.
          pi_base_hidden_defaults) -- filtrados de `all`.
        - all: defaults visiveis (defaults menos hidden) + custom."""
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"config: {exc}",
                    "custom": [], "all": [], "hidden_defaults": []}
        custom_raw = cfg.get("pi_base_custom") or []
        if not isinstance(custom_raw, list):
            custom_raw = []
        custom = [str(c).strip() for c in custom_raw if str(c).strip()]
        hidden_raw = cfg.get("pi_base_hidden_defaults") or []
        if not isinstance(hidden_raw, list):
            hidden_raw = []
        hidden = [str(h).strip() for h in hidden_raw if str(h).strip()]
        all_bases: list[str] = []
        try:
            from core.services.pi_metadata_service import (  # type: ignore[import-not-found]
                listar_todas_bases,
            )
            all_bases = list(listar_todas_bases(
                cfg,
                custom_bases=tuple(custom),
                hidden_defaults=tuple(hidden),
            ))
        except Exception:  # noqa: BLE001
            all_bases = list(custom)
        return {"ok": True, "error": "", "custom": custom,
                "all": all_bases, "hidden_defaults": hidden}

    def _is_default_pi_base(self, name: str) -> bool:
        """True se `name` (case-insensitive, sem acento) bate com algum
        tipo_base de DEFAULT_PI_METADATA. Usado para distinguir entre
        remover de pi_base_custom vs. ocultar via pi_base_hidden_defaults."""
        try:
            from core.services.pi_metadata_service import (  # type: ignore[import-not-found]
                DEFAULT_PI_METADATA,
                normalize_key,
            )
        except Exception:  # noqa: BLE001
            return False
        target = normalize_key(name)
        if not target:
            return False
        for entry in DEFAULT_PI_METADATA:
            base = entry.get("tipo_base") or entry.get("nome") or ""
            if normalize_key(str(base)) == target:
                return True
        return False

    def add_pi_base_custom(self, name: Any) -> dict[str, Any]:
        s = str(name or "").strip()
        if not s:
            return {"ok": False, "error": "nome vazio"}
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"config: {exc}"}
        # Se `s` corresponde a um default oculto, restauramos (un-hide).
        hidden_raw = cfg.get("pi_base_hidden_defaults") or []
        if not isinstance(hidden_raw, list):
            hidden_raw = []
        upper_s = s.upper()
        new_hidden = [
            h for h in hidden_raw
            if str(h).strip().upper() != upper_s
        ]
        if len(new_hidden) != len(hidden_raw):
            try:
                ConfigManager.save_config(
                    {"pi_base_hidden_defaults": new_hidden}
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"save: {exc}"}
            self._config = None
            return self.list_pi_base_custom()
        existing = cfg.get("pi_base_custom") or []
        if not isinstance(existing, list):
            existing = []
        # Dedupe case-insensitive (mas mantem capitalizacao do usuario).
        upper_set = {str(x).strip().upper() for x in existing}
        if upper_s in upper_set:
            return {"ok": False, "error": "PI ja existe"}
        # Tambem rejeita se ja eh um default visivel (nao oculto).
        if self._is_default_pi_base(s):
            return {"ok": False, "error": "PI ja existe como default"}
        existing.append(s)
        try:
            ConfigManager.save_config({"pi_base_custom": existing})
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return self.list_pi_base_custom()

    def remove_pi_base_custom(self, name: Any) -> dict[str, Any]:
        s = str(name or "").strip()
        if not s:
            return {"ok": False, "error": "nome vazio"}
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"config: {exc}"}
        existing = cfg.get("pi_base_custom") or []
        if not isinstance(existing, list):
            existing = []
        new_list = [x for x in existing if str(x).strip().upper() != s.upper()]
        if len(new_list) != len(existing):
            try:
                ConfigManager.save_config(
                    {"pi_base_custom": new_list}, overwrite=False,
                )
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "error": f"save: {exc}"}
            self._config = None
            return self.list_pi_base_custom()
        # Nao estava em pi_base_custom -- talvez seja um default. Se for,
        # registramos em pi_base_hidden_defaults (mecanismo para "remover"
        # defaults sem alterar DEFAULT_PI_METADATA).
        if self._is_default_pi_base(s):
            hidden_raw = cfg.get("pi_base_hidden_defaults") or []
            if not isinstance(hidden_raw, list):
                hidden_raw = []
            upper_set = {str(x).strip().upper() for x in hidden_raw}
            if s.upper() not in upper_set:
                hidden_raw.append(s)
                try:
                    ConfigManager.save_config(
                        {"pi_base_hidden_defaults": hidden_raw}
                    )
                except Exception as exc:  # noqa: BLE001
                    return {"ok": False, "error": f"save: {exc}"}
                self._config = None
            return self.list_pi_base_custom()
        return {"ok": False, "error": "PI nao encontrada"}

    def get_pi_base_map(self) -> dict[str, Any]:
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"config: {exc}", "items": {}}
        m = cfg.get("pi_base_map") or {}
        if not isinstance(m, dict):
            m = {}
        return {"ok": True, "error": "", "items": m}

    def save_pi_base_map(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"ok": False, "error": "payload nao e dict"}
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}"}
        clean = {
            str(k).strip(): str(v).strip().upper() for k, v in payload.items()
            if str(k).strip()
        }
        try:
            ConfigManager.save_config({"pi_base_map": clean})
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return {"ok": True, "error": "", "count": len(clean)}

    @staticmethod
    def _normalize_regional_entry(raw: Any, fallback_codigo: str = "") -> dict[str, Any]:
        if isinstance(raw, dict):
            return {
                "codigo":          str(raw.get("codigo") or fallback_codigo or "").strip(),
                "superintendencia":str(raw.get("superintendencia") or "").strip(),
                "se_prefixos":     str(raw.get("se_prefixos") or "").strip(),
                "cor":             str(raw.get("cor") or "info").strip().lower(),
            }
        # Legado: regional_map[X] = "REG-0002" (string)
        return {
            "codigo":          str(raw or fallback_codigo or "").strip(),
            "superintendencia": "",
            "se_prefixos":      "",
            "cor":              "info",
        }

    def get_regional_map_full(self) -> dict[str, Any]:
        """Devolve mapa enriquecido { NOME: {codigo, superintendencia,
        se_prefixos, cor, source: 'default'|'config'} }."""
        try:
            from runtime.config import ConfigManager, REGIONAL_MAP  # noqa: PLC0415
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"import: {exc}", "items": {}}
        cfg = ConfigManager.load_config() or {}
        user = cfg.get("regional_map") or {}
        if not isinstance(user, dict):
            user = {}
        merged: dict[str, dict[str, Any]] = {}
        # Defaults primeiro
        for nome, codigo in REGIONAL_MAP.items():
            entry = self._normalize_regional_entry(codigo)
            entry["source"] = "default"
            merged[str(nome).upper()] = entry
        # Overrides + adicionais do usuario
        for nome, raw in user.items():
            key = str(nome or "").strip().upper()
            if not key:
                continue
            base = merged.get(key, {"codigo":"", "superintendencia":"",
                                     "se_prefixos":"", "cor":"info",
                                     "source":"config"})
            normalized = self._normalize_regional_entry(raw, base.get("codigo", ""))
            normalized["source"] = "config"
            merged[key] = normalized
        return {"ok": True, "error": "", "items": merged,
                "cores": list(self.REGIONAL_COR_OPCOES)}

    def save_regional_entry(
        self,
        nome: Any,
        payload: Any = None,
    ) -> dict[str, Any]:
        nome_s = str(nome or "").strip().upper()
        if not nome_s:
            return {"ok": False, "error": "nome vazio"}
        if not isinstance(payload, dict):
            return {"ok": False, "error": "payload nao e dict"}
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"config: {exc}"}
        user = cfg.get("regional_map") or {}
        if not isinstance(user, dict):
            user = {}
        new_entry = self._normalize_regional_entry(payload)
        if new_entry["cor"] not in self.REGIONAL_COR_OPCOES:
            new_entry["cor"] = "info"
        user[nome_s] = new_entry
        try:
            ConfigManager.save_config({"regional_map": user})
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return self.get_regional_map_full()

    def delete_regional_entry(self, nome: Any) -> dict[str, Any]:
        nome_s = str(nome or "").strip().upper()
        if not nome_s:
            return {"ok": False, "error": "nome vazio"}
        try:
            from runtime.config import ConfigManager  # noqa: PLC0415
            cfg = ConfigManager.load_config() or {}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"config: {exc}"}
        user = cfg.get("regional_map") or {}
        if not isinstance(user, dict):
            user = {}
        if nome_s not in {str(k).strip().upper() for k in user.keys()}:
            return {"ok": False,
                    "error": "regional nao esta em config (default nao pode ser removido)"}
        new_user = {
            k: v for k, v in user.items()
            if str(k).strip().upper() != nome_s
        }
        try:
            ConfigManager.save_config({"regional_map": new_user}, overwrite=False)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"save: {exc}"}
        self._config = None
        return self.get_regional_map_full()
