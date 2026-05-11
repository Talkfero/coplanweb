from __future__ import annotations

from typing import Any, Optional

from ui_helpers import paginate_items


def paginate_visualizar_rows(
    rows: list[tuple[tuple[Any, ...], Optional[bool]]],
    current_page: int,
    page_size: int,
) -> tuple[list[tuple[tuple[Any, ...], Optional[bool]]], int, int, int]:
    """Pagina linhas da aba Visualizar preservando metadados de avaliação."""
    return paginate_items(rows, current_page, page_size)


def format_pagination_label(current_page: int, total_pages: int, total_items: int) -> str:
    """Gera texto padrão do paginador para a UI."""
    return f"Página {current_page}/{total_pages} • {total_items} resultado(s)"
