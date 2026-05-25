# -*- coding: utf-8 -*-
"""CoplanApi: superficie exposta ao JS via pywebview (`js_api`).

Composta por mixins de dominio. O __init__ vem de CoreMixin. Os nomes
publicos dos metodos sao o contrato com o front (window.pywebview.api.<m>),
portanto NAO devem mudar ao reorganizar os mixins.
"""
from __future__ import annotations

from backend.domains.core import CoreMixin
from backend.domains.obras import ObrasMixin
from backend.domains.apoio import ApoioMixin
from backend.domains.valor import ValorMixin
from backend.domains.cadastro import CadastroMixin
from backend.domains.tecnico import TecnicoMixin
from backend.domains.ganhos import GanhosMixin
from backend.domains.criterios import CriteriosMixin
from backend.domains.resumos import ResumosMixin
from backend.domains.config import ConfigMixin
from backend.domains.banco import BancoMixin
from backend.domains.calc import CalcMixin
from backend.domains.nota_colapso import NotaColapsoMixin
from backend.domains.cenarios import CenariosMixin
from backend.domains.validacoes import ValidacoesMixin


class CoplanApi(
    CoreMixin,
    ObrasMixin,
    ApoioMixin,
    ValorMixin,
    CadastroMixin,
    TecnicoMixin,
    GanhosMixin,
    CriteriosMixin,
    ResumosMixin,
    ConfigMixin,
    BancoMixin,
    CalcMixin,
    NotaColapsoMixin,
    CenariosMixin,
    ValidacoesMixin,
):
    """API exposta ao JS via ``window.pywebview.api.<metodo>``."""
