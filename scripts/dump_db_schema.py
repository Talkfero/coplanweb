#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera a documentacao da estrutura do banco (docs/DATABASE.md).

Introspecta um banco SQLite REAL (sqlite_master + PRAGMA) e escreve um
Markdown com todas as tabelas, colunas (tipo, NOT NULL, default, PK) e
indices. E a fonte autoritativa da estrutura -- util para reaproveitar o
banco em outros programas.

Uso:
    python scripts/dump_db_schema.py [caminho_do_banco.db] [-o docs/DATABASE.md]

Sem o caminho, tenta ler a chave "obras" do config.json do app
(ConfigManager.load_config). Abre o banco em modo read-only.
"""
from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _resolve_db_path(arg: str | None) -> str:
    if arg:
        return arg
    # Tenta o config.json do app.
    if str(_ROOT) not in sys.path:
        sys.path.insert(0, str(_ROOT))
    try:
        from runtime.config import ConfigManager  # noqa: PLC0415

        cfg = ConfigManager.load_config() or {}
        return str(cfg.get("obras") or "").strip()
    except Exception as exc:  # noqa: BLE001
        print(f"[dump_db_schema] nao consegui ler config.json: {exc}",
              file=sys.stderr)
        return ""


def _open_ro(db_path: str) -> sqlite3.Connection:
    # Abre read-only via URI; cai para conexao normal se a URI falhar.
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    try:
        return sqlite3.connect(uri, uri=True)
    except Exception:  # noqa: BLE001
        return sqlite3.connect(db_path)


def _tables(cur: sqlite3.Cursor) -> list[str]:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [r[0] for r in cur.fetchall()]


def _columns(cur: sqlite3.Cursor, table: str) -> list[dict]:
    cur.execute(f'PRAGMA table_info("{table}")')
    out = []
    for cid, name, ctype, notnull, dflt, pk in cur.fetchall():
        out.append({
            "name": name, "type": ctype or "", "notnull": bool(notnull),
            "default": dflt, "pk": int(pk or 0),
        })
    return out


def _indexes(cur: sqlite3.Cursor, table: str) -> list[str]:
    cur.execute(f'PRAGMA index_list("{table}")')
    rows = cur.fetchall()
    out = []
    for r in rows:
        idx_name = r[1]
        unique = bool(r[2])
        cur.execute(f'PRAGMA index_info("{idx_name}")')
        cols = [ic[2] for ic in cur.fetchall()]
        if idx_name.startswith("sqlite_autoindex"):
            continue
        out.append(("UNIQUE " if unique else "") + idx_name
                   + " (" + ", ".join(cols) + ")")
    return out


def _row_count(cur: sqlite3.Cursor, table: str) -> int:
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        return int(cur.fetchone()[0] or 0)
    except Exception:  # noqa: BLE001
        return -1


def build_markdown(db_path: str) -> str:
    conn = _open_ro(db_path)
    cur = conn.cursor()
    lines: list[str] = []
    lines.append("# Estrutura do banco (COPLAN)")
    lines.append("")
    lines.append(
        "> **Gerado** por `scripts/dump_db_schema.py` a partir de um banco "
        "SQLite real. Não edite à mão — regenere após mudanças de esquema.")
    lines.append(">")
    lines.append(f"> Origem: `{db_path}`  ")
    lines.append(f"> Gerado em: {datetime.datetime.now():%Y-%m-%d %H:%M}")
    lines.append("")
    tables = _tables(cur)
    lines.append(f"Tabelas ({len(tables)}): "
                 + ", ".join(f"`{t}`" for t in tables))
    lines.append("")
    for t in tables:
        n = _row_count(cur, t)
        lines.append(f"## `{t}`" + (f"  ({n} linha(s))" if n >= 0 else ""))
        lines.append("")
        lines.append("| Coluna | Tipo | NN | PK | Default |")
        lines.append("|---|---|:--:|:--:|---|")
        for c in _columns(cur, t):
            dflt = "" if c["default"] is None else f"`{c['default']}`"
            lines.append(
                f"| `{c['name']}` | {c['type'] or '—'} | "
                f"{'✔' if c['notnull'] else ''} | "
                f"{c['pk'] or ''} | {dflt} |")
        idxs = _indexes(cur, t)
        if idxs:
            lines.append("")
            lines.append("Índices: " + "; ".join(f"`{i}`" for i in idxs))
        lines.append("")
    conn.close()
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Documenta a estrutura do banco.")
    ap.add_argument("db", nargs="?", help="caminho do .db (senão usa config.json)")
    ap.add_argument("-o", "--out", default=str(_ROOT / "docs" / "DATABASE.md"),
                    help="arquivo de saída (default docs/DATABASE.md)")
    ap.add_argument("--stdout", action="store_true", help="imprime no stdout")
    args = ap.parse_args()

    db_path = _resolve_db_path(args.db)
    if not db_path or not os.path.isfile(db_path):
        print(f"[dump_db_schema] banco não encontrado: '{db_path}'.\n"
              "Informe o caminho: python scripts/dump_db_schema.py <db>",
              file=sys.stderr)
        return 2
    md = build_markdown(db_path)
    if args.stdout:
        sys.stdout.write(md)
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"[dump_db_schema] escrito: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
