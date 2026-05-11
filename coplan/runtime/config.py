"""ConfigManager + constantes de configuracao + state managers.

Extraidos de codigo5_coplan.py. Sem dependencia de Qt nem de DatabaseManager.
"""
from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

# DEFAULT_PI_METADATA continua morando em core/services/pi_metadata_service.py.
from core.services.pi_metadata_service import DEFAULT_PI_METADATA  # noqa: F401

from runtime.text_utils import normalize_key


# ---------------------------------------------------------------------------
# DataSourceState / DataStateManager (UI-agnostico, mas usado pela UI)
# ---------------------------------------------------------------------------
@dataclass
class DataSourceState:
    state: str = "NAO_CARREGADO"
    path: str = ""
    loaded_at: Optional[datetime.datetime] = None
    validated_at: Optional[datetime.datetime] = None
    error_last: str = ""
    version_token: str = ""


class DataStateManager:
    NAO_CARREGADO = "NAO_CARREGADO"
    CARREGADO_PARCIAL = "CARREGADO_PARCIAL"
    CARREGADO_VALIDADO = "CARREGADO_VALIDADO"
    INVALIDADO = "INVALIDADO"

    _STATE_ORDER = {
        NAO_CARREGADO: 0,
        CARREGADO_PARCIAL: 1,
        CARREGADO_VALIDADO: 2,
        INVALIDADO: -1,
    }

    def __init__(self):
        self.sources: Dict[str, DataSourceState] = {
            "db": DataSourceState(),
            "apoio": DataSourceState(),
            "ganhos": DataSourceState(),
            "tecnico_txt": DataSourceState(),
        }

    def update_source(
        self,
        source: str,
        state: str,
        path: Optional[str] = None,
        error: Optional[str] = None,
        version_token: Optional[str] = None,
    ) -> None:
        info = self.sources.setdefault(source, DataSourceState())
        info.state = state
        if path is not None:
            info.path = path
        if state in (self.CARREGADO_PARCIAL, self.CARREGADO_VALIDADO):
            info.loaded_at = datetime.datetime.now()
        if state == self.CARREGADO_VALIDADO:
            info.validated_at = datetime.datetime.now()
        if error is not None:
            info.error_last = error
        if version_token is not None:
            info.version_token = version_token

    def meets_required(self, source: str, min_state: str) -> bool:
        info = self.sources.get(source)
        if not info:
            return False
        if info.state == self.INVALIDADO:
            return False
        return self._STATE_ORDER.get(info.state, -1) >= self._STATE_ORDER.get(
            min_state, 0
        )

    def get_state(self, source: str) -> DataSourceState:
        return self.sources.get(source, DataSourceState())


# ---------------------------------------------------------------------------
# App dirs (criados na importacao, mantem APP_DIRS como modulo-level)
# ---------------------------------------------------------------------------
def get_app_dirs(app_name: str = "COPLAN") -> Dict[str, str]:
    """Retorna os diretórios padrão do app e garante que eles existam."""
    base_dir = os.environ.get("LOCALAPPDATA")
    if base_dir:
        base_path = Path(base_dir) / app_name
    else:
        base_path = Path.home() / app_name

    dirs = {
        "config": base_path / "config",
        "logs": base_path / "logs",
        "cache": base_path / "cache",
        "backups": base_path / "backups",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    return {key: str(path.resolve()) for key, path in dirs.items()}


APP_DIRS = get_app_dirs()


# ---------------------------------------------------------------------------
# Empresas + Regionais
# ---------------------------------------------------------------------------
EMPRESA_SIGLAS_VALIDAS = {"MA", "PA", "PI", "AL", "RS", "AP", "GO"}

REGIONAL_TO_COD = {
    "NORTE": "NOR",
    "NORDESTE": "NDE",
    "NOROESTE": "NRO",
    "CENTRO": "CEN",
    "LESTE": "LES",
    "OESTE": "OES",
    "SUL": "SUL",
    "PARNAÍBA": "PAR",
    "PICOS": "PIC",
    "FLORIANO": "FLO",
    "METROPOLITANA": "MET",
    "INTERIOR": "INT",
    "FORMOSA": "FOR",
    "GOIÂNIA": "GOI",
    "ANÁPOLIS": "ANA",
    "IPORÁ": "IPO",
    "LUZIÂNIA": "LUZ",
    "MONTES BELOS": "MBL",
    "MORRINHOS": "MOR",
    "RIO VERDE": "RIV",
    "URUAÇU": "URU",
}
REGIONAL_TO_COD = {
    re.sub(r"\s+", " ", normalize_key(k)).strip(): v
    for k, v in REGIONAL_TO_COD.items()
}

REGIONAL_MAP = {
    "EQTL": "REG-0000",
    "FLORIANO": "REG-0021",
    "ANÁPOLIS": "REG-0001",
    "CENTRO": "REG-0002",
    "CORPORATIVO": "REG-0003",
    "FORMOSA": "REG-0004",
    "GOIÂNIA": "REG-0005",
    "INTERIOR": "REG-0006",
    "IPORÁ": "REG-0007",
    "LESTE": "REG-0008",
    "LUZIÂNIA": "REG-0009",
    "METROPOLITANA": "REG-0010",
    "MONTES BELOS": "REG-0011",
    "MORRINHOS": "REG-0012",
    "NORDESTE": "REG-0013",
    "NOROESTE": "REG-0014",
    "NORTE": "REG-0015",
    "PARNAÍBA": "REG-0016",
    "OESTE": "REG-0017",
    "RIO VERDE": "REG-0018",
    "SUL": "REG-0019",
    "URUAÇU": "REG-0020",
    "PICOS": "REG-0022",
}


# ---------------------------------------------------------------------------
# Colunas / schema
# ---------------------------------------------------------------------------
ROOT_COLUMNS = [
    "cod",
    "ano_",
    "projeto_investimento",
    "pi_base",
    "nome_projeto",
    "codigo_item",
    "alimentador_principal",
    "alimentadores_beneficiados",
    "coordenada_inicio",
    "coordenada_fim",
    "quantidade_material",
    "caracteristicas_material",
    "novo_bay",
    "nivel_criticidade",
    "observacoes_gerais",
    "nome_regional",
    "nome_superintendencia",
    "nivel_tensao_obra",
    "tensao_operacao",
    "subestacao",
    "contas_contratos_previos",
    "contas_contratos_posteriores",
    "contas_contratos_beneficiadas",
    "carregamento_inicial",
    "carregamento_final",
    "perdas_iniciais",
    "perdas_finais",
    "tensao_media_inicial",
    "tensao_media_final",
    "tensao_min_inicial",
    "tensao_min_final",
    "tensao_min_linha_inicial",
    "tensao_min_linha_final",
    "chi_inicial",
    "ci_inicial",
    "tensao_max_inicial",
    "tensao_max_final",
    "tensao_min_registrada_atual",
    "carregamento_max_registrado_atual",
    "tipo_pacote",
    "obra_aprovada",
    "valor_obra",
    "cc_benef_chi_ci",
    "chi_final",
    "ci_final",
    "descricao_obra",
    "manobra",
]

CAMPOS_CRITICOS_MUDANCA = [
    "pi_base",
    "ano_",
    "tipo_pacote",
    "alimentador_principal",
    "municipio",
    "ganhos_totais_antes",
    "ganhos_totais_depois",
    "ganhos_totais_atual",
    "criterios_status",
    "descricao_obra",
]

ORDERED_COLUMNS = [
    "cod",
    "ano_",
    "projeto_investimento",
    "pi_base",
    "nome_projeto",
    "codigo_item",
    "alimentador_principal",
    "alimentadores_beneficiados",
    "coordenada_inicio",
    "coordenada_fim",
    "quantidade_material",
    "caracteristicas_material",
    "novo_bay",
    "nivel_criticidade",
    "observacoes_gerais",
    "nome_regional",
    "nome_superintendencia",
    "nivel_tensao_obra",
    "tensao_operacao",
    "subestacao",
    # --- Ganhos ---
    "contas_contratos_previos",
    "contas_contratos_posteriores",
    "carregamento_inicial",
    "carregamento_final",
    "perdas_iniciais",
    "perdas_finais",
    "tensao_media_inicial",
    "tensao_media_final",
    "tensao_min_inicial",
    "tensao_min_final",
    "tensao_min_linha_inicial",
    "tensao_min_linha_final",
    "chi_inicial",
    "chi_final",
    "ci_inicial",
    "ci_final",
    "tensao_max_inicial",
    "tensao_max_final",
    "ganhos_totais_antes",
    "ganhos_totais_depois",
    "contas_contratos_beneficiadas",
    "cc_benef_chi_ci",
    "tensao_min_registrada_atual",
    "carregamento_max_registrado_atual",
    "ganhos_totais_atual",
    # --- Fim Ganhos ---
    "tipo_pacote",
    "obra_aprovada",
    "valor_obra",
    "descricao_obra",
    "manobra",
    "tecnico_snapshot_token",
    "tecnico_snapshot_at",
    "tecnico_snapshot_src",
    "tecnico_dirty",
    "data_criacao",
    "data_modificacao",
    "criado_por",
    "modificado_por",
]

GANHOS_NUMERIC_FIELDS = {
    "quantidade_material",
    "contas_contratos_previos",
    "contas_contratos_posteriores",
    "contas_contratos_beneficiadas",
    "carregamento_inicial",
    "carregamento_final",
    "perdas_iniciais",
    "perdas_finais",
    "tensao_media_inicial",
    "tensao_media_final",
    "tensao_min_inicial",
    "tensao_min_final",
    "tensao_min_linha_inicial",
    "tensao_min_linha_final",
    "chi_inicial",
    "ci_inicial",
    "tensao_max_inicial",
    "tensao_max_final",
    "tensao_min_registrada_atual",
    "carregamento_max_registrado_atual",
    "valor_obra",
    "cc_benef_chi_ci",
    "chi_final",
    "ci_final",
    "ganhos_totais_antes",
    "ganhos_totais_depois",
    "ganhos_totais_atual",
}


# ---------------------------------------------------------------------------
# Defaults de criterios / piora
# ---------------------------------------------------------------------------
DEFAULT_CRITERIOS = {
    "tensao_min": 0.95,
    "tensao_max": 1.03,
    "carregamento_limite_sim_ou_vazio": 67.0,
    "carregamento_limite_nao": 100.0,
    "clientes_maximo": 6000,
}

DEFAULT_PIORA_MERCADO = {
    "carregamento_percentual": 3.0,  # acréscimo percentual ao ano
    "tensao_delta": 0.005,           # redução em pu ao ano
    "anos_horizonte": 3,             # horizonte em anos
}

DEFAULT_GANHOS_TOLERANCIA = 0.01


# ---------------------------------------------------------------------------
# Campos de ganhos (used by validations + UI)
# ---------------------------------------------------------------------------
GANHOS_ANTES_FIELDS = [
    "contas_contratos_previos",
    "carregamento_inicial",
    "perdas_iniciais",
    "tensao_media_inicial",
    "tensao_min_inicial",
    "tensao_min_linha_inicial",
    "chi_inicial",
    "ci_inicial",
    "tensao_max_inicial",
    "ganhos_totais_antes",
]

GANHOS_DEPOIS_FIELDS = [
    "contas_contratos_posteriores",
    "carregamento_final",
    "perdas_finais",
    "tensao_media_final",
    "tensao_min_final",
    "tensao_min_linha_final",
    "chi_final",
    "ci_final",
    "tensao_max_final",
    "ganhos_totais_depois",
]

GANHO_TOTAL_FIELDS = [
    "ganho_total",
    "ganhos_total",
    "ganhos_totais_atual",
]

GANHO_ANTES_TOTAL_FIELDS = [
    "ganho_antes",
    "ganhos_antes",
    "ganho_total_antes",
    "ganhos_totais_antes",
]

GANHO_DEPOIS_TOTAL_FIELDS = [
    "ganho_depois",
    "ganhos_depois",
    "ganho_total_depois",
    "ganhos_totais_depois",
]


# ---------------------------------------------------------------------------
# Profiles + tecnico
# ---------------------------------------------------------------------------
DEFAULT_EXPORT_PROFILES = [
    {
        "id": "visible_only",
        "label": "Somente colunas visíveis",
        "mode": "visible_only",
    },
    {
        "id": "all_db",
        "label": "Todas as colunas do banco",
        "mode": "all_db",
    },
]

TECNICO_REQUIRED_FILES = ["FlowMT.TXT", "Topologia.TXT", "Confiabilidade.TXT"]


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------
class ConfigManager:
    CONFIG_FILE = os.path.join(APP_DIRS["config"], "config.json")

    @staticmethod
    def load_config() -> dict[str, Any]:
        default = {
            "caminho_pasta_arquivos": "",
            "apoio": "",
            "obras": "",
            "caminho_pasta_ganhos": "",
            "empresa_sigla": "MA",
            "modulos": {},
            "regional_map": {},
            "criterios_planejamento": DEFAULT_CRITERIOS.copy(),
            "piora_mercado": DEFAULT_PIORA_MERCADO.copy(),
            "last_pi_extra_map": {},
            "pi_base_map": {},
            "pi_base_custom": [],
            "pi_metadata": DEFAULT_PI_METADATA.copy(),
            "descricao_obra_templates": {},
            "export_profiles": DEFAULT_EXPORT_PROFILES.copy(),
            "ui_state": {},
        }

        if os.path.exists(ConfigManager.CONFIG_FILE):
            try:
                with open(ConfigManager.CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except UnicodeDecodeError:
                with open(ConfigManager.CONFIG_FILE, "r", encoding="latin-1") as f:
                    config = json.load(f)
        else:
            config = default

        if "criterios_planejamento" not in config:
            config["criterios_planejamento"] = DEFAULT_CRITERIOS.copy()
        if "piora_mercado" not in config:
            config["piora_mercado"] = DEFAULT_PIORA_MERCADO.copy()
        else:
            for k, v in DEFAULT_PIORA_MERCADO.items():
                config["piora_mercado"].setdefault(k, v)
        if "ui_state" not in config:
            config["ui_state"] = {}

        for key, val in default.items():
            if key not in config:
                config[key] = val

        return config

    @staticmethod
    def save_config(config, overwrite=False):
        """Salva as configurações no arquivo JSON.

        Quando ``overwrite`` é ``False`` (padrão), mescla o conteúdo a ser
        salvo com o que já estiver presente em ``config.json`` evitando que
        informações existentes sejam perdidas.
        """
        if not overwrite and os.path.exists(ConfigManager.CONFIG_FILE):
            try:
                with open(ConfigManager.CONFIG_FILE, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except UnicodeDecodeError:
                with open(ConfigManager.CONFIG_FILE, "r", encoding="latin-1") as f:
                    current = json.load(f)
        else:
            current = {}

        def merge_dicts(base, updates):
            for k, v in updates.items():
                if isinstance(v, dict) and isinstance(base.get(k), dict):
                    merge_dicts(base[k], v)
                else:
                    base[k] = v

        merge_dicts(current, config)

        with open(ConfigManager.CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=4)
