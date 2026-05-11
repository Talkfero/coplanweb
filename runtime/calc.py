"""PI metadata helpers + CalculationManager + diff_fields + descricao_template.

Extraidos de codigo5_coplan.py. Inclui:
- Wrappers leves de core.services.pi_metadata_service
- diff_fields (wrapper)
- get_descricao_obra_from_template
- CalculationManager (~1000 linhas) -- toda a logica de calculos
  de tensao, carregamento, perdas, demanda maxima, CHI/CI, contas
  contratos beneficiadas, COD generation, descricao por template,
  e wrapper de nota colapso (delega ao core.services).

Os helpers que mexem em PI_BASE_MAP/PI_BASE_CUSTOM (mutaveis)
PERMANECEM em codigo5_coplan porque o boot sequence depende deles.
"""
from __future__ import annotations

import logging
import os
import re
import textwrap
from typing import Any, Dict

import pandas as pd
from PySide6 import QtWidgets

from runtime.apoio import SupportFileManager, read_excel_cached
from runtime.config import REGIONAL_MAP, ORDERED_COLUMNS, ConfigManager
from runtime.text_utils import render_template

LOGGER = logging.getLogger("codigo5_coplan")


# ---------------------------------------------------------------------------
# PI metadata wrappers (delegam a core.services.pi_metadata_service)
# ---------------------------------------------------------------------------
def _normalize_pi_metadata_entry(entry: dict) -> dict | None:
    """Wrapper de compatibilidade -- delega ao core/services/pi_metadata_service.

    Reproduz o formato dict legado (nome, abreviacao, tipo_base,
    descricao_template, calculo, flags) usando ``PIMetadata.from_config_entry``
    + ``to_dict()``.
    """
    from core.models import PIMetadata
    metadata = PIMetadata.from_config_entry(entry)
    return metadata.to_dict() if metadata else None


def get_pi_metadata_entries(config: dict | None = None) -> list[dict]:
    """Wrapper -- delega ao core/services/pi_metadata_service.listar_pi_metadata."""
    from core.services.pi_metadata_service import listar_pi_metadata
    if config is None or not isinstance(config, dict):
        config = ConfigManager.load_config()
    return [m.to_dict() for m in listar_pi_metadata(config)]


def get_pi_metadata_map(config: dict | None = None) -> dict[str, dict]:
    """Wrapper -- mapa por nome normalizado E por tipo_base.

    Reproduz fielmente a logica do legado (que usa ``setdefault`` para nao
    sobrescrever entrada por nome com a entrada por tipo_base).
    """
    from texto_utils import normalize_key
    mapping: dict[str, dict] = {}
    for entry in get_pi_metadata_entries(config):
        nome_key = normalize_key(str(entry.get("nome") or ""))
        if nome_key:
            mapping[nome_key] = entry
        tipo_base = entry.get("tipo_base") or entry.get("nome") or ""
        base_key = normalize_key(str(tipo_base))
        if base_key:
            mapping.setdefault(base_key, entry)
    return mapping


def get_pi_metadata(pi: str, config: dict | None = None) -> dict | None:
    """Wrapper -- busca PI e retorna como dict legado."""
    from core.services.pi_metadata_service import buscar_pi_metadata
    if config is None or not isinstance(config, dict):
        config = ConfigManager.load_config()
    metadata = buscar_pi_metadata(pi, config)
    return metadata.to_dict() if metadata else None


def get_pi_tipo_base(pi: str, config: dict | None = None) -> str:
    """Wrapper -- delega ao core service."""
    from core.services.pi_metadata_service import obter_tipo_base
    if config is None or not isinstance(config, dict):
        config = ConfigManager.load_config()
    return obter_tipo_base(pi, config)


def get_pi_abreviacao(pi: str, config: dict | None = None) -> str:
    """Wrapper -- delega ao core service."""
    from core.services.pi_metadata_service import obter_abreviacao
    if config is None or not isinstance(config, dict):
        config = ConfigManager.load_config()
    return obter_abreviacao(pi, config)


def get_pi_default_description_template(pi: str, config: dict | None = None) -> str:
    """Wrapper -- delega ao core service."""
    from core.services.pi_metadata_service import obter_descricao_template
    if config is None or not isinstance(config, dict):
        config = ConfigManager.load_config()
    return obter_descricao_template(pi, config)


def get_pi_extra_module_keys(pi_base: str, config: dict | None = None) -> list[str]:
    """Wrapper -- delega ao core service."""
    from core.services.pi_metadata_service import obter_modulos_extras
    if config is None or not isinstance(config, dict):
        config = ConfigManager.load_config()
    return obter_modulos_extras(pi_base, config)


# ---------------------------------------------------------------------------
# diff_fields (wrapper)
# ---------------------------------------------------------------------------
def diff_fields(old: dict, new: dict, fields: list[str]) -> list[str]:
    """Wrapper -- delega ao core/services/obra_rules."""
    from core.services.obra_rules import diff_fields as _impl
    return _impl(old, new, fields)


# ---------------------------------------------------------------------------
# get_descricao_obra_from_template
# ---------------------------------------------------------------------------
def get_descricao_obra_from_template(pi_base: str, data: dict) -> str | None:
    config = ConfigManager.load_config()
    templates = config.get("descricao_obra_templates", {})
    pi_normalizado = (pi_base or "").strip().upper()
    template = ""
    if isinstance(templates, dict) and pi_normalizado:
        template = templates.get(pi_normalizado, "") or ""
    if not template:
        template = get_pi_default_description_template(pi_base, config)
    if template:
        return render_template(template, data)
    return None


# ---------------------------------------------------------------------------
# CalculationManager (~1000 linhas) -- extraido de codigo5_coplan.py
# ---------------------------------------------------------------------------
class CalculationManager:
    def __init__(self, support_manager: SupportFileManager, prompt_pi_base: bool = True):
        self.support_manager = support_manager
        # Controla se get_pi_base deve exibir diálogos para PIs desconhecidos
        self.prompt_pi_base = prompt_pi_base

    @staticmethod
    def build_module_key(pi_base, tensao, caracteristica, codigo_regional):
        return f"{pi_base.strip().upper()}-{tensao.strip().replace(',', '.').upper()}-{caracteristica.strip().upper()}_{codigo_regional.strip().upper()}"

    def gerar_cod(self, pacote, alimentador, projeto_investimento, quantidade, caracteristica, coord_final, pi_base=None):
        """Gera o código da obra.

        O parâmetro ``pi_base`` é opcional. Quando ``None`` o PI base é obtido a
        partir de ``projeto_investimento``. Esse ajuste evita múltiplas
        solicitações ao usuário em fluxos onde ``get_pi_base`` já foi invocado
        anteriormente.
        """
        # get_pi_base permanece em codigo5_coplan (depende de PI_BASE_MAP/Qt prompt).
        from codigo5_coplan import get_pi_base

        pacote_str = pacote.strip().upper()
        mapping = {
            "MERCADO": "MCD",
            "CONFIABILIDADE": "CON",
            "INTERLIGAÇÃO DE UDE": "UDE",
            "SOLICITAÇÃO REGIONAL": "SOL",
            "ORÇAMENTO DE CONEXÃO": "ORC",
            "PLPT": "PLPT"
        }
        pacote_resumido = mapping.get(pacote_str, pacote_str[:3])

        if pi_base is None:
            pi_base = get_pi_base(projeto_investimento, prompt_user=self.prompt_pi_base)
        else:
            pi_base = pi_base.strip().upper()
        tipo = get_pi_abreviacao(pi_base)

        if not all([pacote, alimentador, tipo, quantidade, caracteristica, coord_final]):
            raise ValueError("Campos obrigatórios para geração do código estão vazios.")

        cod = f"{pacote_resumido}|{alimentador}|{tipo}|{quantidade}x{caracteristica}|{coord_final}"
        return cod

    def gerar_descricao_obra(
        self,
        pi_base: str,
        data_map: dict | None = None,
    ) -> str:
        if data_map is None:
            data_map = {}
        descricao = get_descricao_obra_from_template(pi_base, data_map)
        if descricao:
            return descricao
        return "- DESCRIÇÃO NÃO DEFINIDA PARA ESTE TIPO DE PROJETO"

    def calcular_valor_obra(self, pi_base, tensao, caracteristica, regional_nome, quantidade):
        try:
            quantidade_val = float(quantidade.replace(",", ".")) if quantidade else 1.0
        except ValueError:
            quantidade_val = 1.0

        tensao_corrigida = tensao.strip().replace(",", ".").upper()
        chave_modulo = f"{pi_base.strip().upper()}-{tensao_corrigida}-{caracteristica.strip().upper()}"

        regional_map = REGIONAL_MAP
        codigo_regional = regional_map.get(regional_nome.strip().upper())

        if not codigo_regional:
            QtWidgets.QMessageBox.warning(None, "Aviso", f"Regional '{regional_nome}' não encontrada no mapeamento fixo.")
            return None

        chave_completa = f"{chave_modulo}_{codigo_regional}"

        config = ConfigManager.load_config()
        caminho_planilha = config.get("apoio", "")

        if not os.path.exists(caminho_planilha):
            QtWidgets.QMessageBox.critical(None, "Erro", "O caminho da planilha de apoio não foi definido corretamente.")
            return None

        try:
            xls = pd.ExcelFile(caminho_planilha)
            abas = {str(aba).lower(): aba for aba in xls.sheet_names}

            if "modulo" not in abas:
                QtWidgets.QMessageBox.warning(None, "Erro", "A aba 'MODULO' não foi encontrada na planilha de apoio.")
                return None

            df_modulo = read_excel_cached(caminho_planilha, abas["modulo"])
            colunas = {col.lower(): col for col in df_modulo.columns}

            if "carac+modulo_regional" not in colunas or "valor_item" not in colunas:
                QtWidgets.QMessageBox.warning(None, "Erro", "A aba 'MODULO' não possui as colunas necessárias.")
                return None

            mask = (
                df_modulo[colunas["carac+modulo_regional"]]
                .astype(str)
                .str.strip()
                .str.upper()
                == chave_completa
            )
            valores = df_modulo.loc[mask, colunas["valor_item"]]

            if valores.empty:
                QtWidgets.QMessageBox.warning(
                    None,
                    "Aviso",
                    f"Chave '{chave_completa}' não encontrada na aba 'MODULO' da planilha de apoio.",
                )
                return None

            try:
                valores_float = pd.to_numeric(
                    valores.astype(str).str.replace(",", "."), errors="raise"
                )
            except Exception:
                QtWidgets.QMessageBox.warning(
                    None,
                    "Erro",
                    f"Valor inválido encontrado para a chave '{chave_completa}' na aba 'MODULO'.",
                )
                return None

            valor_unitario_total = valores_float.sum()

            extra_keys = get_pi_extra_module_keys(pi_base, config)
            for key in extra_keys:
                chave_extra = f"{key.strip().upper()}_{codigo_regional}"
                mask_extra = (
                    df_modulo[colunas["carac+modulo_regional"]]
                    .astype(str)
                    .str.strip()
                    .str.upper()
                    == chave_extra
                )
                valores_extra = df_modulo.loc[mask_extra, colunas["valor_item"]]

                if valores_extra.empty:
                    QtWidgets.QMessageBox.warning(
                        None,
                        "Aviso",
                        f"Chave '{chave_extra}' não encontrada na aba 'MODULO' da planilha de apoio.",
                    )
                    continue

                try:
                    valores_extra_float = pd.to_numeric(
                        valores_extra.astype(str).str.replace(",", "."), errors="raise"
                    )
                    valor_unitario_total += valores_extra_float.sum()
                except Exception:
                    QtWidgets.QMessageBox.warning(
                        None,
                        "Erro",
                        f"Valor inválido encontrado para a chave '{chave_extra}' na aba 'MODULO'.",
                    )
                    continue

            valor_total = valor_unitario_total * quantidade_val
            return round(valor_total, 2)

        except Exception as e:
            QtWidgets.QMessageBox.critical(None, "Erro", f"Erro ao acessar a aba 'MODULO' da planilha: {str(e)}")
            return None

    def calcular_despacho_vt(self, obras):
        if not obras:
            return "Nenhuma obra encontrada."
        try:
            obras.sort(key=lambda x: int(x[4]))
        except Exception:
            pass
        despacho = "------------------------- OBRAS E CONDICIONANTES -----------------------\n"
        numero = 1
        index_desc = self.get_index("descricao_obra")
        for obra in obras:
            descricao = obra[index_desc]
            linhas = textwrap.wrap(descricao or "", width=67, break_long_words=False, break_on_hyphens=False)
            if linhas:
                despacho += f"{numero}. {linhas[0]}\n"
                for l in linhas[1:]:
                    despacho += l + "\n"
            else:
                despacho += f"{numero}. \n"
            numero += 1
        despacho += "------------------------------------------------------------------------\n"
        despacho += "------- POTÊNCIA DISPONIBILIZADA (PARA CÁLCULO DE ERD): XX.XXX kW ------\n\n"
        despacho += "CÓDIGOS DAS OBRAS PARA USO INTERNO DO PLANEJAMENTO DA EXPANSÃO:\n"
        numero = 1
        index_cod = self.get_index("cod")
        for obra in obras:
            cod = obra[index_cod]
            despacho += f"{numero}. {cod}\n"
            numero += 1
        return despacho

    def get_index(self, column_name):
        try:
            return ORDERED_COLUMNS.index(column_name)
        except ValueError:
            return -1

    def calcular_tensoes(self, data_flow_mt, alimentadores_considerados):
        if not data_flow_mt:
            return None, None

        tensoes_por_patamar = {"Madrugada": [], "Manhã": [], "Tarde": [], "Noite": []}
        tensao_minima = float('inf')
        for alimentador in alimentadores_considerados:
            in_section = False
            for i, line in enumerate(data_flow_mt):
                if alimentador.lower() in line.lower():
                    in_section = True
                elif in_section and line.startswith('*'):
                    break
                elif in_section and "Período :" in line:
                    periodo = line.split(":", 1)[1].strip()
                    if periodo in tensoes_por_patamar:
                        period_start_index = i + 2
                        for trafos_line in data_flow_mt[period_start_index:]:
                            if trafos_line.startswith(' Período') or trafos_line.startswith('-'):
                                break
                            trafos_data = trafos_line.split()
                            if len(trafos_data) >= 20:
                                try:
                                    vd_pu = float(trafos_data[17].replace(",", "."))
                                    ve_pu = float(trafos_data[18].replace(",", "."))
                                    vf_pu = float(trafos_data[19].replace(",", "."))
                                    for tensao in [vd_pu, ve_pu, vf_pu]:
                                        if tensao > 0:
                                            tensao_minima = min(tensao_minima, tensao)
                                            tensoes_por_patamar[periodo].append(tensao)
                                except ValueError:
                                    continue
        medias_por_patamar = {}
        for patamar, tensoes in tensoes_por_patamar.items():
            tensoes_validas = [t for t in tensoes if t > 0]
            if tensoes_validas:
                medias_por_patamar[patamar] = sum(tensoes_validas) / len(tensoes_validas)
            else:
                medias_por_patamar[patamar] = None
        menor_media = min([media for media in medias_por_patamar.values() if media is not None], default=None)
        if tensao_minima == float('inf'):
            tensao_minima = None
        return (
            round(tensao_minima, 4) if tensao_minima is not None else None,
            round(menor_media, 4) if menor_media is not None else None,
        )

    def calcular_tensao_linha_minima(self, data_flow_mt, alimentadores_considerados):
        """Calcula a menor tensão DE LINHA (pu) entre VDE/VEF/VFD para todos os alimentadores."""
        if not data_flow_mt:
            return None

        tensao_min_linha = float("inf")

        for alimentador in alimentadores_considerados:
            in_section = False
            for i, line in enumerate(data_flow_mt):
                if alimentador.lower() in line.lower():
                    in_section = True
                    continue
                if in_section and line.startswith("*"):
                    break

                if in_section and "Período :" in line:
                    period_start_index = i + 1
                    idx_vde_pu = idx_vef_pu = idx_vfd_pu = None

                    for trafos_line in data_flow_mt[period_start_index:]:
                        if trafos_line.startswith(" Período") or trafos_line.startswith("-"):
                            break

                        line_stripped = trafos_line.strip()
                        if not line_stripped:
                            continue

                        trafos_data = line_stripped.split()

                        if idx_vde_pu is None:
                            try:
                                idx_vde_pu = next(
                                    k for k, c in enumerate(trafos_data)
                                    if "VDE(pu" in c or c == "VDE(pu)"
                                )
                                idx_vef_pu = next(
                                    k for k, c in enumerate(trafos_data)
                                    if "VEF(pu" in c or c == "VEF(pu)"
                                )
                                idx_vfd_pu = next(
                                    k for k, c in enumerate(trafos_data)
                                    if "VFD(pu" in c or c == "VFD(pu)"
                                )
                                continue
                            except StopIteration:
                                if len(trafos_data) >= 23:
                                    idx_vde_pu, idx_vef_pu, idx_vfd_pu = 20, 21, 22
                                else:
                                    continue

                        try:
                            if idx_vde_pu is None or idx_vef_pu is None or idx_vfd_pu is None:
                                continue
                            if (
                                idx_vde_pu < len(trafos_data)
                                and idx_vef_pu < len(trafos_data)
                                and idx_vfd_pu < len(trafos_data)
                            ):
                                vde_pu = float(trafos_data[idx_vde_pu].replace(",", "."))
                                vef_pu = float(trafos_data[idx_vef_pu].replace(",", "."))
                                vfd_pu = float(trafos_data[idx_vfd_pu].replace(",", "."))
                            else:
                                continue
                        except ValueError:
                            continue

                        for tensao in (vde_pu, vef_pu, vfd_pu):
                            if tensao > 0:
                                tensao_min_linha = min(tensao_min_linha, tensao)

        if tensao_min_linha == float("inf"):
            return None
        return round(tensao_min_linha, 4)

    def calcular_tensoes_max(self, data_flow_mt, alimentadores_considerados):
        """Calcula maior tensão de fase em pu + menor média por patamar."""
        if not data_flow_mt:
            return None, None

        tensoes_por_patamar = {"Madrugada": [], "Manhã": [], "Tarde": [], "Noite": []}
        tensao_maxima = float("-inf")

        for alimentador in alimentadores_considerados:
            in_section = False
            for i, line in enumerate(data_flow_mt):
                if alimentador.lower() in line.lower():
                    in_section = True
                elif in_section and line.startswith('*'):
                    break
                elif in_section and "Período :" in line:
                    periodo = line.split(":", 1)[1].strip()
                    if periodo in tensoes_por_patamar:
                        period_start_index = i + 2
                        idx_vd_pu = idx_ve_pu = idx_vf_pu = None
                        header_encontrado = False
                        for trafos_line in data_flow_mt[period_start_index:]:
                            if trafos_line.startswith(' Período') or trafos_line.startswith('-'):
                                break
                            trafos_data = trafos_line.split()
                            if not trafos_data:
                                continue

                            if not header_encontrado:
                                try:
                                    idx_vd_pu = next(
                                        k for k, c in enumerate(trafos_data)
                                        if "VD(pu" in c or c == "VD(pu)"
                                    )
                                    idx_ve_pu = next(
                                        k for k, c in enumerate(trafos_data)
                                        if "VE(pu" in c or c == "VE(pu)"
                                    )
                                    idx_vf_pu = next(
                                        k for k, c in enumerate(trafos_data)
                                        if "VF(pu" in c or c == "VF(pu)"
                                    )
                                    header_encontrado = True
                                    continue
                                except StopIteration:
                                    if len(trafos_data) >= 20:
                                        idx_vd_pu, idx_ve_pu, idx_vf_pu = 17, 18, 19
                                    else:
                                        continue

                            try:
                                if idx_vd_pu is None or idx_ve_pu is None or idx_vf_pu is None:
                                    continue
                                if (
                                    idx_vd_pu < len(trafos_data)
                                    and idx_ve_pu < len(trafos_data)
                                    and idx_vf_pu < len(trafos_data)
                                ):
                                    vd_pu = float(trafos_data[idx_vd_pu].replace(",", "."))
                                    ve_pu = float(trafos_data[idx_ve_pu].replace(",", "."))
                                    vf_pu = float(trafos_data[idx_vf_pu].replace(",", "."))
                                else:
                                    continue
                            except ValueError:
                                continue

                            for tensao in (vd_pu, ve_pu, vf_pu):
                                if 0 < tensao < 2.0:
                                    tensao_maxima = max(tensao_maxima, tensao)
                                    tensoes_por_patamar[periodo].append(tensao)

        medias_por_patamar = {}
        for patamar, tensoes in tensoes_por_patamar.items():
            tensoes_validas = [t for t in tensoes if t > 0]
            if tensoes_validas:
                medias_por_patamar[patamar] = sum(tensoes_validas) / len(tensoes_validas)
            else:
                medias_por_patamar[patamar] = None

        menor_media = min(
            (media for media in medias_por_patamar.values() if media is not None),
            default=None,
        )

        if tensao_maxima == float("-inf"):
            tensao_maxima = None

        return (
            round(tensao_maxima, 4) if tensao_maxima is not None else None,
            round(menor_media, 4) if menor_media is not None else None,
        )

    def calcular_carregamento(self, data_topologia, alimentadores_considerados):
        if not data_topologia:
            return None

        carregamento_pior_trecho = 0
        for alimentador in alimentadores_considerados:
            in_section = False
            for line in data_topologia:
                if f"circuito: {alimentador.lower()}" in line.lower():
                    in_section = True
                elif in_section and line.strip() == "":
                    in_section = False
                elif in_section and "Carregamento no Pior Trecho:" in line:
                    try:
                        value_str = line.split(":", 1)[1].strip().replace("%", "").replace(",", ".")
                        valor = float(value_str)
                        carregamento_pior_trecho = max(carregamento_pior_trecho, valor)
                    except Exception:
                        continue
        return carregamento_pior_trecho

    def calcular_perdas(self, data_flow_mt, alimentadores_considerados):
        """Calcula as perdas por patamar para os alimentadores fornecidos."""
        if not data_flow_mt:
            return {
                "Madrugada": 0.0,
                "Manhã": 0.0,
                "Tarde": 0.0,
                "Noite": 0.0,
            }, 0.0

        perdas_por_patamar = {"Madrugada": 0.0, "Manhã": 0.0, "Tarde": 0.0, "Noite": 0.0}

        for alimentador in alimentadores_considerados:
            in_section = False
            patamar_atual = None

            for i, line in enumerate(data_flow_mt):
                if alimentador.lower() in line.lower():
                    in_section = True
                elif in_section and line.startswith('*'):
                    break
                elif in_section:
                    if "Período :" in line:
                        patamar_atual = line.split(":", 1)[1].strip()
                    elif "Período" in line and "Perda(kW)" in line:
                        for j in range(1, 5):
                            try:
                                perda_data = data_flow_mt[i + j].strip().split()
                                if len(perda_data) >= 2:
                                    periodo = perda_data[0].strip()
                                    perda_kW = perda_data[1].strip()
                                    if periodo in perdas_por_patamar:
                                        perdas_por_patamar[periodo] += float(perda_kW.replace(",", "."))
                            except Exception:
                                continue

        maior_perda = max(perdas_por_patamar.values(), default=0.0)
        return perdas_por_patamar, maior_perda

    def calcular_demanda_maxima(self, data_flow_mt, alimentadores_considerados) -> Dict[str, float]:
        """Retorna {alimentador: demanda_maxima_em_MW} (coincidente)."""
        demanda_por_alim_e_periodo: Dict[str, Dict[str, float]] = {}

        if not data_flow_mt:
            LOGGER.info("Cálculo baseado no arquivo FlowMT.TXT... (arquivo vazio)")
            return {}

        LOGGER.info("Cálculo baseado no arquivo FlowMT.TXT...")

        for alimentador in alimentadores_considerados:
            in_feeder_block = False
            in_carreg = False
            header_found = False
            periodos_vals: Dict[str, float] = {}

            for line in data_flow_mt:
                line_lower = line.lower()

                if not in_feeder_block:
                    if "alimentador:" in line_lower and alimentador.lower() in line_lower:
                        in_feeder_block = True
                    continue

                if "subestação:" in line_lower:
                    break

                if not in_carreg:
                    if "carregamento do alimentador" in line_lower:
                        in_carreg = True
                    continue

                if in_carreg and not header_found:
                    header_lower = line_lower
                    if (
                        "período" in header_lower
                        and "pot. ativa" in header_lower
                        and "kw" in header_lower
                    ):
                        header_found = True
                    continue

                if in_carreg and header_found:
                    if not line.strip():
                        break
                    if "barra de tensão" in line_lower or "perdas no alimentador" in line_lower:
                        break

                    partes = re.split(r"\s+", line.strip())
                    if len(partes) < 2:
                        continue

                    periodo = partes[0].strip()

                    try:
                        valor_kw = float(partes[1].replace(",", "."))
                    except ValueError:
                        continue

                    valor_mw = valor_kw / 1000.0

                    atual = periodos_vals.get(periodo)
                    if atual is None or valor_mw > atual:
                        periodos_vals[periodo] = valor_mw

            if periodos_vals:
                demanda_por_alim_e_periodo[alimentador] = periodos_vals
            else:
                LOGGER.warning(
                    "Alimentador '%s': nenhuma demanda encontrada no FlowMT.TXT.",
                    alimentador,
                )

        if not demanda_por_alim_e_periodo:
            LOGGER.warning(
                "Nenhuma Demanda Máxima foi extraída do FlowMT.TXT para os alimentadores informados."
            )
            return {}

        periodo_referencia: str | None = None
        valor_ref: float | None = None

        if alimentadores_considerados:
            alim_ref = alimentadores_considerados[0]
            periodos_ref = demanda_por_alim_e_periodo.get(alim_ref, {})
            for periodo, valor_mw in periodos_ref.items():
                if valor_ref is None or valor_mw > valor_ref:
                    valor_ref = valor_mw
                    periodo_referencia = periodo

        demanda_max_por_alim: Dict[str, float] = {}

        if periodo_referencia is not None:
            LOGGER.info(
                "Período de referência para máxima coincidente: '%s' (alimentador %s)",
                periodo_referencia,
                alimentadores_considerados[0],
            )
            for alim, mapa_periodos in demanda_por_alim_e_periodo.items():
                if periodo_referencia in mapa_periodos:
                    val = mapa_periodos[periodo_referencia]
                else:
                    val = max(mapa_periodos.values())
                demanda_max_por_alim[alim] = round(val, 2)
                LOGGER.info(
                    "Alimentador '%s': Demanda máxima COINCIDENTE = %.2f MW (período %s)",
                    alim,
                    demanda_max_por_alim[alim],
                    periodo_referencia,
                )
        else:
            LOGGER.warning(
                "Não foi possível determinar período de referência, usando máximas individuais."
            )
            for alim, mapa_periodos in demanda_por_alim_e_periodo.items():
                val = max(mapa_periodos.values())
                demanda_max_por_alim[alim] = round(val, 2)
                LOGGER.info(
                    "Alimentador '%s': Demanda máxima = %.2f MW",
                    alim,
                    demanda_max_por_alim[alim],
                )

        LOGGER.info(
            "Total de alimentadores com Demanda Máxima extraída (coincidente): %s",
            len(demanda_max_por_alim),
        )
        return demanda_max_por_alim

    def calcular_chi_ci(self, data_confiabilidade, alimentadores_considerados):
        if not data_confiabilidade:
            return 0, 0

        chi_total = 0
        ci_total = 0
        linha_cabecalho = None
        for i, line in enumerate(data_confiabilidade):
            if "CHI" in line and "CI" in line:
                linha_cabecalho = i
                break
        if linha_cabecalho is None:
            return 0, 0
        headers = [h.strip() for h in data_confiabilidade[linha_cabecalho].split("\t")]
        chi_index = None
        ci_index = None
        for i, header in enumerate(headers):
            if "CHI" in header and "Cons." in header:
                chi_index = i
            if "CI" in header and "Cons." in header:
                ci_index = i
        if chi_index is None or ci_index is None:
            return 0, 0
        for alimentador in alimentadores_considerados:
            for line in data_confiabilidade[linha_cabecalho + 1:]:
                if alimentador.lower() in line.lower():
                    try:
                        parts = line.split("\t")
                        chi_val = float(parts[chi_index].replace(",", "."))
                        ci_val = float(parts[ci_index].replace(",", "."))
                        chi_total += chi_val
                        ci_total += ci_val
                    except Exception:
                        continue
        return round(chi_total, 4), round(ci_total, 4)

    def calcular_contas_contratos(self, data_confiabilidade, alimentadores_considerados):
        if not data_confiabilidade:
            return 0, 0

        contas_antes = 0
        contas_depois = 0
        linha_cabecalho = None
        for i, line in enumerate(data_confiabilidade):
            if "Qtd Consumidores" in line:
                linha_cabecalho = i
                break
        if linha_cabecalho is None:
            return 0, 0
        headers = [h.strip() for h in data_confiabilidade[linha_cabecalho].split("\t")]
        consumidores_index = None
        for i, header in enumerate(headers):
            if "Qtd Consumidores" in header:
                consumidores_index = i
                break
        if consumidores_index is None:
            return 0, 0
        for alimentador in alimentadores_considerados:
            for line in data_confiabilidade[linha_cabecalho + 1:]:
                if alimentador.lower() in line.lower():
                    try:
                        parts = line.split("\t")
                        consumidores = int(parts[consumidores_index].strip())
                        contas_antes = max(contas_antes, consumidores)
                        contas_depois = max(contas_depois, consumidores)
                    except Exception:
                        continue
        return contas_antes, contas_depois

    def calcular_contas_contratos_beneficiadas(self, data_topologia, data_confiabilidade, alimentadores_considerados, projeto_investimento):
        """Calcula somatório das Contas Contratos Beneficiadas para todos os alimentadores."""
        from codigo5_coplan import get_pi_base

        total_contas_beneficiadas = 0

        projeto_base = get_pi_base(projeto_investimento, prompt_user=self.prompt_pi_base)
        if "distribuição" in projeto_base.lower():
            if not data_confiabilidade:
                return 0
            LOGGER.info("Cálculo baseado no arquivo Confiabilidade.TXT...")
            for alimentador in alimentadores_considerados:
                for line in data_confiabilidade:
                    if alimentador.lower() in line.lower():
                        try:
                            line_data = [col.strip() for col in line.split("\t")]
                            while len(line_data) < 12:
                                line_data.append("")

                            consumidores = int(line_data[10]) if line_data[10].isdigit() else 0
                            total_contas_beneficiadas += consumidores
                            LOGGER.debug(
                                "Alimentador '%s': %s consumidores somados.",
                                alimentador,
                                consumidores,
                            )
                        except (ValueError, IndexError) as e:
                            LOGGER.debug(
                                "Erro ao processar linha: %s - %s",
                                line.strip(),
                                e,
                            )
                            continue
        else:
            if not data_topologia:
                return 0
            LOGGER.info("Cálculo baseado no arquivo Topologia.TXT...")
            for alimentador in alimentadores_considerados:
                in_section = False
                soma_local = 0

                for line in data_topologia:
                    if f"circuito: {alimentador.lower()}" in line.lower():
                        in_section = True
                        soma_local = 0

                    elif in_section and (line.strip() == "" or "circuito:" in line.lower()):
                        in_section = False
                        total_contas_beneficiadas += soma_local
                        LOGGER.debug(
                            "Alimentador '%s': %s somados nesta seção.",
                            alimentador,
                            soma_local,
                        )

                    elif in_section:
                        keywords = [
                            "Quantidade de Clientes em Tensão Precária:",
                            "Quantidade de Clientes em Tensão Crítica:",
                            "Quantidade de Clientes pós Carregamento maior que 80%:",
                            "Quantidade de Clientes pós Carregamento maior que 100%:"
                        ]
                        for keyword in keywords:
                            if keyword in line:
                                try:
                                    valor = int(line.split(":")[1].strip())
                                    soma_local += valor
                                    LOGGER.debug("%s %s somados.", keyword, valor)
                                except (ValueError, IndexError) as e:
                                    LOGGER.debug(
                                        "Erro ao processar linha: %s - %s",
                                        line.strip(),
                                        e,
                                    )
                                    continue

        LOGGER.info(
            "Total de Contas Contratos Beneficiadas: %s",
            total_contas_beneficiadas,
        )
        return total_contas_beneficiadas

    def calcular_nota_carregamento(self, carreg_inicial, carreg_max):
        try:
            if carreg_inicial == 0 or carreg_max == 0:
                return 0, "Carregamento: Dados insuficientes"

            if carreg_max < 67 and carreg_inicial < 67:
                return 1, "Carregamento: <67"
            elif 67 <= carreg_max < 80 and 67 <= carreg_inicial < 80:
                return 3, "Carregamento: 67-80"
            elif 67 <= carreg_max < 80 and 80 <= carreg_inicial < 90:
                return 4, "Carregamento: 67-80 e 80-90"
            elif 80 <= carreg_max < 90 and 80 <= carreg_inicial < 90:
                return 5, "Carregamento: 80-90"
            elif 80 <= carreg_max < 90 and 95 <= carreg_inicial <= 100:
                return 6, "Carregamento: 80-90 e 95-100"
            elif 90 <= carreg_max < 100 and 90 <= carreg_inicial < 100:
                return 7, "Carregamento: 90-100"
            elif 90 <= carreg_max < 100 and carreg_inicial >= 100:
                return 8, "Carregamento: 90-100 e >=100"
            elif carreg_max >= 100 and carreg_inicial >= 100:
                return 9, "Carregamento: >=100"
            else:
                return 0, "Carregamento: Não definido"
        except Exception:
            return None, "Erro no carregamento"

    def calcular_nota_tensao_min(self, tensao_min_atual, tensao_min_inicial):
        """Aplica a tabela verdade completa para faixas de tensão mínima."""
        try:
            if tensao_min_atual == 0 or tensao_min_inicial == 0:
                return 0, "Tensão Mínima: Dados insuficientes"

            def get_faixa(valor):
                if valor < 0.90:
                    return 4
                elif valor < 0.93:
                    return 3
                elif valor < 0.95:
                    return 2
                elif valor <= 1.03:
                    return 1
                else:
                    return 0

            faixa_atual = get_faixa(tensao_min_atual)
            faixa_inicial = get_faixa(tensao_min_inicial)

            tabela_verdade = {
                (1, 1): (1,  "0,95-1,03 / 0,95-1,03"),
                (2, 1): (1,  "0,93-0,95 / 0,95-1,03"),
                (3, 1): (1,  "0,90-0,93 / 0,95-1,03"),
                (4, 1): (1,  "<0,90 / 0,95-1,03"),
                (1, 2): (4,  "0,95-1,03 / 0,93-0,95"),
                (1, 3): (5,  "0,95-1,03 / 0,90-0,93"),
                (2, 2): (5,  "0,93-0,95 / 0,93-0,95"),
                (3, 2): (5,  "0,90-0,93 / 0,93-0,95"),
                (4, 2): (5,  "<0,90 / 0,93-0,95"),
                (2, 3): (6,  "0,93-0,95 / 0,90-0,93"),
                (3, 3): (7,  "0,90-0,93 / 0,90-0,93"),
                (4, 3): (7,  "<0,90 / 0,90-0,93"),
                (3, 4): (8,  "0,90-0,93 / <0,90"),
                (4, 4): (9,  "<0,90 / <0,90"),
            }

            if (faixa_atual, faixa_inicial) in tabela_verdade:
                nota, descricao = tabela_verdade[(faixa_atual, faixa_inicial)]
                return nota, f"Tensão Mínima: {descricao}"
            else:
                return 0, "Tensão Mínima: Não definido"

        except Exception:
            return None, "Erro na tensão mínima"

    def calcular_nota_tensao_max(self, tensao_min_atual, tensao_max_inicial):
        try:
            if tensao_min_atual == 0 or tensao_max_inicial == 0:
                return 0, "Tensão Máxima: Dados insuficientes"
            if 0.95 <= tensao_min_atual <= 1.03 and 0.95 <= tensao_max_inicial <= 1.03:
                return 1, "Tensão Máxima: 0.95-1.03"
            elif 1.03 < tensao_min_atual <= 1.05 and 1.05 <= tensao_max_inicial <= 1.07:
                return 6, "Tensão Máxima: 1.03-1.05 e 1.05-1.07"
            elif 1.05 < tensao_min_atual <= 1.07 and 1.05 <= tensao_max_inicial <= 1.07:
                return 7, "Tensão Máxima: 1.05-1.07"
            elif 1.05 < tensao_min_atual <= 1.07 and tensao_max_inicial > 1.07:
                return 8, "Tensão Máxima: 1.05-1.07 e >1.07"
            elif tensao_min_atual > 1.07 and tensao_max_inicial > 1.07:
                return 9, "Tensão Máxima: >1.07"
            else:
                return 0, "Tensão Máxima: Não definido"
        except Exception:
            return None, "Erro na tensão máxima"

    def safe_float(self, valor_str):
        valor_str = str(valor_str).strip()
        if valor_str == "":
            return 0.0
        try:
            return float(valor_str.replace(",", "."))
        except Exception as e:
            raise ValueError(f"Não foi possível converter '{valor_str}' para float: {str(e)}")

    def calcular_nota_colapso_obra(self, obra):
        """Wrapper de compatibilidade — delega ao core/services/nota_colapso_service.

        A lógica de cálculo da Nota de Colapso foi extraída para
        ``core.services.nota_colapso_service.calcular_nota_colapso``. Esta
        função preserva a assinatura legada (recebe ``obra`` como tupla/row
        do SQLite, retorna ``(nota, criterio)``).
        """
        from core.models import Obra as _CoreObra, PIMetadata as _CorePIMetadata
        from core.services.nota_colapso_service import (
            calcular_nota_colapso as _calc_nota_colapso_core,
        )

        try:
            row_dict = {
                col: obra[idx]
                for idx, col in enumerate(ORDERED_COLUMNS)
                if idx < len(obra)
            }
        except Exception as e:
            return None, f"Erro na conversão dos valores: {str(e)}"

        obra_core = _CoreObra.from_row_dict(row_dict)
        projeto = obra_core.ident.projeto_investimento.strip().upper()
        pi_meta_dict = get_pi_metadata(projeto)
        pi_meta = (
            _CorePIMetadata.from_config_entry(pi_meta_dict)
            if isinstance(pi_meta_dict, dict)
            else None
        )
        resultado = _calc_nota_colapso_core(obra_core, pi_metadata=pi_meta)
        return resultado.valor, resultado.criterio