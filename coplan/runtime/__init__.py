"""Pacote runtime/ -- modulos extraidos de codigo5_coplan.py.

Este pacote consolida funcoes utilitarias, managers de estado (Config,
Database, Apoio, Calculation) e dialogs Qt que originalmente viviam todos
no monolito codigo5_coplan.py.

Mantemos compat 100% via re-exports em codigo5_coplan.py: qualquer
``from codigo5_coplan import X`` continua funcionando.
"""
