"""Camada de dominio (core) do Coplan.

Este pacote e estritamente agnostico de UI: nenhum modulo aqui dentro pode
importar PySide6, PyQt5, PyQt6 ou shiboken, direta ou indiretamente. Essa
regra e verificada pelo teste tests/test_core_purity.py.

Estrutura:

- core.models        : dataclasses de dominio (dados puros).
- core.repositories  : acesso a Oracle, SQLite, Excel, Parquet.
- core.services      : regras de negocio coordenando modelos e repositorios.
- core.exceptions    : excecoes de dominio (sem textos de UI).
"""
