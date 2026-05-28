---
name: test-mixin-endpoint
description: Exercita um endpoint de mixin de `backend/domains/*.py` headless (sem pywebview/display), contra um SQLite temporario. Use para validar mudancas em qualquer mixin da `CoplanApi`, especialmente apos editar `backend/domains/*.py` ou para investigar bugs de concorrencia (threads do pywebview disparam endpoints em paralelo ao abrir uma aba). Roda a chamada uma vez OU sob estresse concorrente para pegar regressoes thread-safety.
---

# Test Mixin Endpoint

A `CoplanApi` e composta por mixins de dominio. Cada metodo publico vira
endpoint exposto ao JS. Esta skill instancia a API em processo, conecta a
um SQLite temporario com schema completo (via `DatabaseManager.connect`) e
chama o(s) metodo(s) — sem precisar de display/pywebview/config.json.

## Pre-requisitos

```bash
pip install pandas openpyxl -q
```

O `_ensure_managers()` da `CoreMixin` importa `pandas` (do
`runtime.calc`/`runtime.database`). Sem isso, retorna
`"DatabaseManager indisponivel"`.

## Padrao 1 — Chamada unica

Substitua `MIXIN_METHOD` pelo metodo a testar e ajuste os argumentos:

```bash
python -c "
import sqlite3, tempfile, os
from backend.api import CoplanApi
from runtime.database import DatabaseManager

# 1. cria SQLite temp com schema completo (DatabaseManager faz CREATE TABLE)
d = tempfile.mkdtemp()
dbp = os.path.join(d, 'obras.db')
dm = DatabaseManager()
dm.connect(dbp)

# 2. popula obras de exemplo (campos minimos para o endpoint sob teste)
con = sqlite3.connect(dbp)
def ins(**kw):
    keys = ','.join(kw); q = ','.join('?'*len(kw))
    con.execute(f'INSERT INTO obras ({keys}) VALUES ({q})', tuple(kw.values()))
ins(cod='MA-26-DI-001', ano_='2026', projeto_investimento='DISTRIBUICAO',
    nome_projeto='PROJ A', valor_obra='1.234,56', quantidade_material='12,5',
    contas_contratos_beneficiadas='100', tipo_pacote='OBRA',
    nome_regional='REGIONAL A', alimentador_principal='ATB-204')
con.commit(); con.close()

# 3. instancia API, aponta para o db temp, chama o endpoint
api = CoplanApi()
api._config = {'obras': dbp}
print(api.MIXIN_METHOD(''))  # <-- ajuste o nome e os args
" 2>/dev/null
```

## Padrao 2 — Estresse concorrente (thread-safety)

Usado para reproduzir corridas como a que causou o crash da aba Resumo
(varios endpoints abrindo a mesma conexao SQLite ao mesmo tempo):

```bash
python -c "
import sqlite3, tempfile, os, threading
from backend.api import CoplanApi
from runtime.database import DatabaseManager
d = tempfile.mkdtemp(); dbp = os.path.join(d,'obras.db')
DatabaseManager().connect(dbp)
con = sqlite3.connect(dbp)
for i in range(50):
    con.execute('INSERT INTO obras (cod,ano_,projeto_investimento,nome_projeto,'
                'valor_obra,quantidade_material,contas_contratos_beneficiadas,'
                'tipo_pacote,nome_regional,alimentador_principal) '
                'VALUES (?,?,?,?,?,?,?,?,?,?)',
      (f'MA-26-DI-{i:03d}','2026','DISTRIBUICAO','PROJ A','1.234,56','12,5',
       '100','OBRA','REGIONAL A','ATB-204'))
con.commit(); con.close()

api = CoplanApi(); api._config = {'obras': dbp}; api._ensure_db_connected()

errs = []
def call(m, *a):
    try:
        r = getattr(api, m)(*a)
        assert r.get('ok'), (m, r)
    except Exception as e:
        errs.append((m, repr(e)))

# Ajuste a lista de (metodo, args) que voce quer disparar em paralelo:
jobs = [
    ('resumo_kpis', ('',)),
    ('resumo_volumetria_regional', ('',)),
    ('pacotes_distribution', ('',)),
    ('resumo_regional_table', ('',)),
    ('resumo_volumetria_financeiro', ('',)),
]
for _ in range(30):  # 30 rodadas concorrentes
    ts = [threading.Thread(target=call, args=(m, *a)) for m, a in jobs]
    [t.start() for t in ts]; [t.join() for t in ts]
print('errors:', errs or 'none')
" 2>/dev/null
```

## Notas

- **Suprima logs** com `2>/dev/null` — o `DatabaseManager.connect` emite
  muitos `WARNING:codigo5_coplan:[DB-CONNECT-DEBUG]` no stderr que poluem
  a saida.
- O contrato da `CoplanApi` exige `{"ok": bool, ...}`. Assert
  `r.get('ok')` no harness de teste — falha silenciosa de endpoint
  retorna `ok=False` com `error` descritivo.
- **Crash do processo** (vs. excecao Python) indica corrupcao C-level
  (ex.: SQLite cross-thread). Rode o padrao 2 para reproduzir.
- Para testar logica de `cenario_ativo`, edite `api._config` antes da
  chamada: `api._config = {'obras': dbp, 'cenario_ativo': 'X'}`.
- Schema completo (66 colunas) e criado por
  `DatabaseManager.connect` automaticamente — nao precisa do `config.json`
  nem do banco de producao.
