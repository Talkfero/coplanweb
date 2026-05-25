# legacy_desktop/

App **desktop legado** (PySide6/Qt). Não é o foco do projeto — a aplicação ativa
é a web (`main_web.py` + `backend/` + `frontend/`). Mantido aqui como referência
e porque ainda compartilha os pacotes `runtime/` e `core/` (na raiz do repo).

Conteúdo:
- `codigo5_coplan.py` — shim/`MainWindow` Qt + re-exports dos managers legados.
- `ui/main_window/*_mixin.py` — mixins da janela principal (desktop).
- `footer_more_actions.py` — helper de UI do rodapé.

## Como rodar (desktop)

Requer **PySide6** (não incluído em `requirements-web.txt`):

```bash
pip install -r requirements-web.txt PySide6
python legacy_desktop/codigo5_coplan.py
```

O `codigo5_coplan.py` ajusta o `sys.path` para incluir tanto esta pasta
(`legacy_desktop/`, para `ui`/`footer_more_actions`) quanto a raiz do repo
(para os pacotes compartilhados `runtime`, `core`, `ui_helpers`,
`texto_utils`, `visualizar_pagination`).

> A app web **não** importa nada daqui (desacoplada na Etapa 1). Alterar este
> diretório não afeta a web.
