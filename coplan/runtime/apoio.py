"""SupportFileManager + cache de Excel (planilha de apoio).

Extraidos de codigo5_coplan.py. Sem Qt direto (delega show_user_error
via lazy import a codigo5_coplan).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from runtime.config import APP_DIRS

LOGGER = logging.getLogger("codigo5_coplan")

# ---------------------------------------------------------------------------
# Excel cache (wrappers em core/repositories/excel_cache)
# ---------------------------------------------------------------------------
_EXCEL_CACHE_DIR = Path(APP_DIRS["cache"])


def cache_key_for_file(path: str) -> str:
    """Wrapper -- delega ao core/repositories/excel_cache."""
    from core.repositories.excel_cache import cache_key_for_file as _impl
    return _impl(path)


def cache_get_df(key: str) -> Optional[pd.DataFrame]:
    """Wrapper -- delega ao core/repositories/excel_cache."""
    from core.repositories.excel_cache import cache_get_df as _impl
    return _impl(key, cache_dir=_EXCEL_CACHE_DIR)


def cache_set_df(key: str, df: pd.DataFrame) -> None:
    """Wrapper -- delega ao core/repositories/excel_cache."""
    from core.repositories.excel_cache import cache_set_df as _impl
    _impl(key, df, cache_dir=_EXCEL_CACHE_DIR)


def read_excel_cached(
    filepath: str,
    sheet_name: str | int,
    use_cache: bool = True,
    **kwargs: Any,
) -> pd.DataFrame:
    """Wrapper -- delega ao core/repositories/excel_cache, injetando cache_dir."""
    from core.repositories.excel_cache import read_excel_cached as _impl
    return _impl(
        filepath,
        sheet_name,
        cache_dir=_EXCEL_CACHE_DIR,
        use_cache=use_cache,
        **kwargs,
    )


def _clean_excel_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Remove colunas lixo do pandas (ex.: "Unnamed: 64") e colunas vazias."""
    clean_cols = []
    rename_map = {}
    for c in df.columns:
        s = str(c).strip()
        if not s:
            continue
        if s.lower().startswith("unnamed:"):
            continue
        rename_map[c] = s
        clean_cols.append(s)
    df = df.rename(columns=rename_map).loc[:, clean_cols]
    return df, clean_cols


# ---------------------------------------------------------------------------
# SupportFileManager (gestor da planilha de apoio)
# ---------------------------------------------------------------------------
class SupportFileManager:
    """Gestor da planilha de apoio.

    State-unified (Passo 8): em vez de 5 atributos avulsos duplicando dados,
    guarda uma única instância de ``DadosApoio`` em ``self.dados``. Os 5
    atributos legados (``alimentadores_pre_definidos``, etc.) continuam
    expostos como ``@property`` para preservar a superfície pública usada
    pelos callers da UI.
    """

    def __init__(self):
        self.dados = None  # type: ignore[assignment]  # Optional[DadosApoio]

    def clear_data(self):
        """Limpa os dados antes de carregar um novo arquivo."""
        self.dados = None

    # ------------------------------------------------------------------
    # Propriedades retro-compatíveis (delegam ao state unificado)
    # ------------------------------------------------------------------
    @property
    def alimentadores_pre_definidos(self) -> list[str]:
        if not self.dados:
            return []
        return list(self.dados.alimentadores)

    @property
    def projetos_investimento_pre_definidos(self) -> list[str]:
        if not self.dados:
            return []
        return list(self.dados.projetos_investimento)

    @property
    def caracteristicas_pre_definidas(self) -> list[str]:
        if not self.dados:
            return []
        return list(self.dados.caracteristicas)

    @property
    def nomes_projetos_pre_definidos(self) -> list[str]:
        if not self.dados:
            return []
        return list(self.dados.nomes_projetos)

    @property
    def dados_alimentador(self) -> dict:
        """Dict PT-BR esperado pela UI legada (chaves TENSÃO/REGIONAL/...)."""
        if not self.dados:
            return {}
        return {
            nome: {
                "TENSÃO": d.tensao,
                "REGIONAL": d.regional,
                "SUPERINTENDÊNCIA": d.superintendencia,
                "SE": d.se,
            }
            for nome, d in self.dados.dados_alimentador.items()
        }

    def _validate_minimum_support(self, filepath: str) -> tuple[bool, str, str]:
        """Valida presença de abas e colunas mínimas da planilha de apoio."""
        if not os.path.isfile(filepath):
            return (
                False,
                f"Arquivo não encontrado: {filepath}",
                "Selecione uma planilha de apoio válida.",
            )
        try:
            xls = pd.ExcelFile(filepath)
        except Exception as exc:
            LOGGER.exception("Falha ao abrir planilha de apoio.")
            return (
                False,
                f"Erro ao abrir planilha: {exc}",
                "Verifique se o arquivo está acessível e não está corrompido.",
            )

        abas = {str(aba).lower(): aba for aba in xls.sheet_names}
        missing_tabs = [tab for tab in ("apoio", "modulo") if tab not in abas]
        if missing_tabs:
            return (
                False,
                f"Abas ausentes: {', '.join(missing_tabs)}.",
                "Inclua as abas 'Apoio' e 'MODULO' na planilha.",
            )

        try:
            df_apoio = read_excel_cached(filepath, abas["apoio"])
            cols_apoio = {col.lower(): col for col in df_apoio.columns}
        except Exception as exc:
            LOGGER.exception("Falha ao ler aba Apoio.")
            return (
                False,
                f"Erro ao ler aba Apoio: {exc}",
                "Verifique o formato e a codificação da planilha.",
            )

        required_apoio = {
            "alimentador": ["alimentador"],
            "projeto de investimento": ["projeto de investimento"],
            "regional": ["regional"],
            "superintendência": ["superintendência", "superintendencia"],
            "tensão": ["tensão", "tensao"],
            "se": ["se", "subestação_cod", "subestacao_cod"],
        }
        missing_cols = [
            label
            for label, aliases in required_apoio.items()
            if not any(alias in cols_apoio for alias in aliases)
        ]
        if missing_cols:
            return (
                False,
                "Colunas ausentes na aba 'Apoio': " + ", ".join(missing_cols),
                "Ajuste a planilha para conter as colunas mínimas exigidas.",
            )

        try:
            df_modulo = read_excel_cached(filepath, abas["modulo"])
            cols_modulo = {col.lower(): col for col in df_modulo.columns}
        except Exception as exc:
            LOGGER.exception("Falha ao ler aba MODULO.")
            return (
                False,
                f"Erro ao ler aba MODULO: {exc}",
                "Verifique o formato da aba MODULO e tente novamente.",
            )

        required_modulo = ["carac+modulo", "regional", "valor_item"]
        missing_modulo = [col for col in required_modulo if col not in cols_modulo]
        if missing_modulo:
            return (
                False,
                "Colunas ausentes na aba 'MODULO': " + ", ".join(missing_modulo),
                "Ajuste a aba MODULO para conter as colunas mínimas exigidas.",
            )

        return True, "", ""

    def load_support_file(self, filepath):
        """Wrapper de compatibilidade — delega ao core/services/apoio_service.

        A leitura, validação e parsing da planilha de apoio foram extraídos
        para ``core.services.apoio_service.carregar_dados_apoio``. Este
        método mantém os mesmos atributos públicos
        (``alimentadores_pre_definidos``, ``dados_alimentador`` com chaves
        PT-BR ``"TENSÃO"``/``"REGIONAL"``/``"SUPERINTENDÊNCIA"``/``"SE"``,
        etc.) e o mesmo retorno ``(True, dict)`` ou ``(False, {})``.
        """
        from core.exceptions import ApoioFileError
        from core.services.apoio_service import carregar_dados_apoio
        # Lazy import para evitar circular -- show_user_error abre QMessageBox.
        from codigo5_coplan import show_user_error

        self.clear_data()
        try:
            dados = carregar_dados_apoio(filepath, read_excel=read_excel_cached)
        except ApoioFileError as exc:
            if exc.codigo == "DADOS_VAZIOS":
                titulo = "Erro ao carregar planilha de apoio"
            else:
                titulo = "Erro ao validar planilha de apoio"
            show_user_error(titulo, exc.detalhes, exc.hint)
            return False, {}
        except Exception as e:
            LOGGER.exception("Erro ao carregar o arquivo de apoio.")
            show_user_error(
                "Erro ao carregar planilha de apoio",
                f"Erro ao carregar o arquivo de apoio: {str(e)}",
                "Verifique o arquivo e tente novamente.",
            )
            return False, {}

        # State unificado: guarda apenas o DadosApoio tipado.
        self.dados = dados
        modulos_dict = {chave: m.valor for chave, m in dados.modulos.items()}

        LOGGER.debug("Dados dos alimentadores carregados: %s", self.dados_alimentador)
        return True, {
            "alimentadores": self.alimentadores_pre_definidos,
            "dados_alimentador": self.dados_alimentador,
            "projetos_investimento": self.projetos_investimento_pre_definidos,
            "caracteristicas": self.caracteristicas_pre_definidas,
            "nomes_projetos_pre_definidos": self.nomes_projetos_pre_definidos,
            "modulos": modulos_dict,
        }
