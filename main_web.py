# -*- coding: utf-8 -*-
"""COPLAN main_web -- entry point da aplicacao web (pywebview).

Responsabilidades deste arquivo (mantido minimo):
  * resolver os caminhos do front-end (`frontend/`),
  * montar o HTML servido (HTML do disco + bridge JS injetado em memoria),
  * criar a janela pywebview expondo `CoplanApi` como `js_api`.

A logica de backend vive em `backend/` (`CoplanApi` em `backend.api`, composta
por mixins de dominio em `backend.domains.*`; estado compartilhado em
`backend._state`). O front-end vive em `frontend/` (`index.html` +
`js/coplan_bridge.js`). Nenhum arquivo em disco e' modificado em runtime.

Uso:
    pip install -r requirements-web.txt
    python main_web.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Garante que `backend`, `core/`, `runtime/`, `codigo5_coplan` sejam
# importaveis tanto via "python main_web.py" quanto via PyInstaller frozen.
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend._state import APP_VERSION, HERE  # noqa: E402,F401  (HERE == raiz do repo)
from backend.api import CoplanApi  # noqa: E402

# Caminhos do front-end. Em build frozen, coplan_launcher.py reaponta estes
# globais (e FRONTEND_DIR) para a pasta extraida em sys._MEIPASS.
FRONTEND_DIR = HERE / "frontend"
HTML_FILE = FRONTEND_DIR / "index.html"
BRIDGE_JS_FILE = FRONTEND_DIR / "js" / "coplan_bridge.js"


def build_html() -> str:
    """Le o mock do disco e devolve uma copia em memoria com o bridge JS
    anexado antes de ``</body>``. Nunca modifica o arquivo no disco."""
    html = HTML_FILE.read_text(encoding="utf-8")
    bridge = BRIDGE_JS_FILE.read_text(encoding="utf-8")
    if "</body>" in html:
        return html.replace("</body>", bridge + "\n</body>", 1)
    return html + bridge


def main() -> None:
    try:
        import webview  # type: ignore[import-not-found]
    except ImportError:
        print(
            "ERRO: pywebview nao instalado. Instale com:\n"
            "    pip install pywebview\n",
            file=sys.stderr,
        )
        sys.exit(1)

    if not HTML_FILE.exists():
        print(f"ERRO: nao encontrei {HTML_FILE}", file=sys.stderr)
        sys.exit(1)

    api = CoplanApi()
    html = build_html()

    webview.create_window(
        title="COPLAN -- Cadastro e Visualizacao de Obras Eletricas",
        html=html,
        js_api=api,
        width=1440,
        height=860,
        min_size=(1100, 720),
    )
    # debug=True habilita o DevTools (F12 ou clique direito -> Inspect)
    # do Edge WebView2/WebKit. Util pra ver console.log e network.
    debug = (not getattr(sys, "frozen", False)) or os.environ.get("COPLAN_DEBUG") == "1"
    webview.start(debug=debug)


if __name__ == "__main__":
    main()
