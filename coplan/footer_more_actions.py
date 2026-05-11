from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FooterActionEntry:
    attr_name: str
    label: str


DEFAULT_COLLAPSED_ACTIONS: tuple[FooterActionEntry, ...] = (
    FooterActionEntry("btn_exportar_relatorio_criterios", "Relatório Critérios"),
    FooterActionEntry("btn_gerar_nota", "Nota Colapso"),
    FooterActionEntry("btn_exportar_banco", "Exportar Banco"),
    FooterActionEntry("btn_backup", "Backup Banco"),
    FooterActionEntry("btn_atualizar_plano", "Plano de Obras"),
)


def should_show_more_actions_button(window_width: int, threshold: int = 1260) -> bool:
    return window_width < threshold


def get_collapsed_action_keys(window_width: int, threshold: int = 1260) -> set[str]:
    if not should_show_more_actions_button(window_width, threshold):
        return set()
    return {entry.attr_name for entry in DEFAULT_COLLAPSED_ACTIONS}


def iter_default_entries() -> Iterable[FooterActionEntry]:
    return DEFAULT_COLLAPSED_ACTIONS
