"""Utilitarios de texto, logging e timing.

Extraidos de codigo5_coplan.py. Sem dependencia de Qt, ConfigManager,
DatabaseManager etc. Apenas stdlib + re.
"""
from __future__ import annotations

import datetime
import logging
import logging.handlers  # noqa: F401  -- mantido para compat com codigo5
import os
import re
import time
import unicodedata
from typing import Any


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def setup_logging(log_dir: str) -> str:
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, f"app_{datetime.datetime.now():%Y%m%d}.log")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Evita duplicar handlers em reinicializações (Qt / reload / etc.)
    if not any(
        isinstance(h, logging.FileHandler)
        and os.path.abspath(getattr(h, "baseFilename", "")) == os.path.abspath(log_path)
        for h in root.handlers
    ):
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        fh = logging.FileHandler(log_path, encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)

        # Remove StreamHandler (terminal) se existir
        for h in list(root.handlers):
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                root.removeHandler(h)

        root.addHandler(fh)

    logging.info("==== LOG INICIADO ====")
    logging.info("Arquivo de log: %s", log_path)
    return log_path


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
def ts_now() -> float:
    return time.perf_counter()


def ts_log(label: str, start_ts: float) -> None:
    elapsed = time.perf_counter() - start_ts
    logging.info(f"[TIMESTAMP] {label} levou {elapsed:.3f}s")


# ---------------------------------------------------------------------------
# Normalizacao de texto
# ---------------------------------------------------------------------------
def normalize_key(text: str) -> str:
    """Normaliza texto removendo acentos e convertendo para maiúsculas."""
    text = str(text or "")
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ASCII", "ignore").decode("ASCII").upper()


def _compact_key(text: str) -> str:
    """Normaliza e remove separadores para comparação tolerante."""
    return "".join(ch for ch in normalize_key(text) if ch.isalnum())


def normalize_text(s: Any) -> str:
    """Normaliza texto removendo acento, aplicando trim/upper e compactando espaços."""
    normalized = normalize_key(str(s or ""))
    return re.sub(r"\s+", " ", normalized).strip()


# ---------------------------------------------------------------------------
# COD_PEP parsing (puro -- sem dependencia de db)
# ---------------------------------------------------------------------------
def parse_cod_pep(cod: str) -> dict[str, Any] | None:
    cod_s = str(cod or "").strip().upper()
    parts = cod_s.split("-")
    if len(parts) != 6:
        return None
    empresa, yy, regional, aaa, ssss, letra = parts
    if not empresa or not yy.isdigit() or len(yy) != 2:
        return None
    if not regional:
        return None
    if not aaa.isdigit() or len(aaa) != 3:
        return None
    if not ssss.isdigit() or len(ssss) != 4:
        return None
    if not letra or len(letra) != 1:
        return None
    agrup = int(aaa)
    seq = int(ssss)
    if not (0 <= agrup <= 999):
        return None
    if not (0 <= seq <= 9999):
        return None
    return {
        "empresa": empresa,
        "yy": yy,
        "regional": regional,
        "agrup": agrup,
        "seq": seq,
        "letra": letra,
    }


# ---------------------------------------------------------------------------
# Template rendering (puro -- substitui {field} no texto)
# ---------------------------------------------------------------------------
def render_template(template: str, data: dict) -> str:
    def replace_placeholder(match: re.Match) -> str:
        key = match.group(1)
        value = data.get(key, "")
        if value is None:
            return ""
        value_str = str(value).strip()
        return value_str if value_str else ""

    rendered = re.sub(r"\{([a-zA-Z0-9_]+)\}", replace_placeholder, template or "")
    rendered = rendered.replace(" ,", ",")
    rendered = re.sub(r"[ \t]{2,}", " ", rendered)
    return rendered.strip()
