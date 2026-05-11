from __future__ import annotations

from math import ceil
import re
from typing import Sequence, TypeVar

T = TypeVar("T")


def paginate_items(items: Sequence[T], page: int, page_size: int) -> tuple[list[T], int, int, int]:
    """Paginate a sequence and return (page_items, total_items, total_pages, normalized_page)."""
    total_items = len(items)
    if page_size <= 0:
        page_size = 1
    total_pages = max(1, ceil(total_items / page_size))
    normalized_page = max(1, min(page, total_pages))
    start = (normalized_page - 1) * page_size
    end = start + page_size
    return list(items[start:end]), total_items, total_pages, normalized_page


def should_use_overflow_menu(window_width: int, threshold: int = 1260) -> bool:
    """Returns True when footer actions should collapse into overflow menu."""
    return window_width < threshold


def matches_filter_value(cell_value: str, filter_value: str) -> bool:
    """Supports multiple terms separated by ';' or ',' using contains semantics."""
    if not filter_value:
        return True
    normalized_cell = (cell_value or "").lower()
    terms = [t.strip().lower() for t in re.split(r"[;,]", filter_value) if t.strip()]
    return any(term in normalized_cell for term in terms)


def matches_cod_terms(cod_value: str, cod_filter: str) -> bool:
    """Cod filter keeps exact matching for numbers and contains for alpha terms."""
    if not cod_filter:
        return True
    normalized_cod = (cod_value or "").lower()
    terms = [t.strip().lower() for t in re.split(r"[;,]", cod_filter) if t.strip()]
    return any(
        (term.isalpha() and term in normalized_cod)
        or (not term.isalpha() and normalized_cod == term)
        for term in terms
    )
