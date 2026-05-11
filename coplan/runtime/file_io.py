"""Helpers de leitura de arquivo + relatorios CSV.

Extraidos de codigo5_coplan.py:
- ler_arquivo_com_codificacoes: tenta varias codificacoes
- carregar_arquivos: le multiplos arquivos de uma pasta
- exportar_relatorio_csv: dump das obras em CSV
- carregar_relatorio_csv: importa CSV para o banco
"""
from __future__ import annotations

import csv
import logging
import os
import re
from typing import Tuple


LOGGER = logging.getLogger("codigo5_coplan")


def ler_arquivo_com_codificacoes(filepath, codificacoes=None):
    if codificacoes is None:
        codificacoes = ["utf-8", "latin1", "ISO-8859-1", "cp1252"]
    ultimo_erro = None
    for cod in codificacoes:
        try:
            with open(filepath, "r", encoding=cod) as f:
                return f.readlines()
        except Exception as e:
            ultimo_erro = e
    raise ValueError(f"Não foi possível ler o arquivo {filepath}. Último erro: {ultimo_erro}")


def carregar_arquivos(pasta, nomes):
    """Carrega arquivos de texto de uma pasta.

    Parameters
    ----------
    pasta : str
        Caminho da pasta contendo os arquivos.
    nomes : list[str]
        Lista com os nomes dos arquivos a serem carregados.

    Returns
    -------
    dict
        Mapeamento ``nome -> linhas`` com o conteúdo de cada arquivo.

    Raises
    ------
    FileNotFoundError
        Se algum arquivo não for encontrado.
    ValueError
        Se a leitura falhar em todas as codificações.
    """
    dados = {}
    for nome in nomes:
        caminho = os.path.join(pasta, nome)
        if os.path.isfile(caminho):
            dados[nome] = ler_arquivo_com_codificacoes(caminho)
        else:
            logging.warning(f"Arquivo {nome} não encontrado em {pasta}.")
            dados[nome] = []
    return dados


def exportar_relatorio_csv(db_manager, destino_csv: str, pacotes=None) -> bool:
    """Exporta todos os registros da tabela 'obras' para um arquivo CSV."""
    try:
        if not db_manager or not getattr(db_manager, "db_path", None):
            return False
        if pacotes is None:
            pacotes = db_manager.allowed_pacotes
        rows = db_manager.fetch_all(pacotes)
        col_names = db_manager.get_column_names()

        with open(destino_csv, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(col_names)
            for row in rows:
                new_row = [
                    v.replace(".", ",") if isinstance(v, str) and re.fullmatch(r"-?\d+\.\d+", v.strip()) else v
                    for v in row
                ]
                writer.writerow(new_row)
        return True
    except Exception:
        LOGGER.exception("Erro ao exportar relatório CSV.")
        return False


def carregar_relatorio_csv(db_manager, origem_csv: str, parent=None) -> Tuple[bool, int]:
    """Lê um arquivo CSV e insere/atualiza os dados na tabela 'obras'.

    Retorna ``(sucesso, ignorados)`` indicando se o carregamento ocorreu
    e quantos registros foram ignorados por conter sublinhado.
    """
    # Lazy import: find_duplicate_in_db ainda mora em codigo5_coplan
    # (depende de wrappers row_helpers que ainda nao foram extraidos).
    from codigo5_coplan import find_duplicate_in_db

    try:
        if not db_manager or not getattr(db_manager, "db_path", None):
            return False, 0

        db_manager.add_column_if_missing("empresa")
        db_manager.add_column_if_missing("cod_pep")
        db_manager.update_columns()

        with open(origem_csv, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=";")
            col_names = [str(col).strip() for col in next(reader, [])]
            required_cols = db_manager.get_column_names()
            col_names_set = {col for col in col_names if col}

            if not set(db_manager.root_columns).issubset(col_names_set):
                LOGGER.warning("CSV sem colunas raiz obrigatórias para importação.")
                return False, 0

            for col in col_names:
                if col and col not in required_cols:
                    db_manager.add_column_if_missing(col)
            db_manager.update_columns()

            ignorados = 0
            for row in reader:
                if not row:
                    continue
                dados_row = {col: row[i] if i < len(row) else "" for i, col in enumerate(col_names)}
                alim = str(dados_row.get("alimentador_principal", ""))
                benef = str(dados_row.get("alimentadores_beneficiados", ""))
                if "_" in alim or any("_" in b for b in re.split(r'[,;|\n]+', benef)):
                    ignorados += 1
                    continue
                cod = dados_row.get("cod")
                try:
                    duplicate = find_duplicate_in_db(db_manager, dados_row)
                    if duplicate:
                        merged = db_manager.build_merge_updates(duplicate, dados_row)
                        if merged:
                            db_manager.update_obra(merged, duplicate.get("cod"), skip_blank=True)
                        else:
                            ignorados += 1
                        continue
                    db_manager.insert_obra(dados_row)
                except PermissionError:
                    continue
        db_manager.update_columns()
        refresh_cache = getattr(db_manager, "_refresh_cache", None)
        if callable(refresh_cache):
            refresh_cache()
        return True, ignorados
    except Exception:
        LOGGER.exception("Erro ao carregar relatório CSV.")
        return False, 0
