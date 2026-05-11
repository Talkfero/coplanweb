"""Mixins da MainWindow, separados por sub-feature.

Cada mixin assume estar misturado em ``MainWindow(QMainWindow, *mixins)``
e nao declara ``__init__``. Atributos como ``self.db_manager``,
``self.config``, ``self.table_obras`` etc. sao herdados via composicao
da MainWindow.

Estrategia de imports: usar ``legacy_module()`` (definido abaixo) para
acessar simbolos do ``codigo5_coplan``. Isso funciona tanto quando o
arquivo e executado como ``__main__`` (``python codigo5_coplan.py``)
quanto quando importado como modulo (em testes ou ``python -m``).
Late imports diretos (``from codigo5_coplan import X``) NAO funcionam
quando o app e executado como script -- carregam o arquivo de novo,
criando classes duplicadas com state desconectado.
"""
from __future__ import annotations

import sys
from types import ModuleType


def legacy_module() -> ModuleType:
    """Retorna o modulo ``codigo5_coplan`` ou ``__main__``.

    Quando o app e executado via ``python codigo5_coplan.py``, o modulo
    fica em ``sys.modules['__main__']`` e NAO em
    ``sys.modules['codigo5_coplan']``. Mixins que precisam acessar
    simbolos top-level (``PlanoObrasDialog``, ``DataStateManager``,
    funcoes ``require_*``, etc.) devem usar este helper:

        from ui.main_window import legacy_module
        ...
        legacy = legacy_module()
        dialog = legacy.PlanoObrasDialog(...)

    Funciona em todos os modos de execucao (script, ``python -m``,
    importacao em testes).
    """
    mod = sys.modules.get('codigo5_coplan')
    if mod is not None:
        return mod
    main = sys.modules.get('__main__')
    if main is not None and str(getattr(main, '__file__', '')).endswith('codigo5_coplan.py'):
        return main
    # Ultima tentativa: import explicito (caso o modulo ja esteja
    # carregado em outro nome ou nao tenha sido carregado ainda)
    import codigo5_coplan  # type: ignore[import-not-found]
    return codigo5_coplan
