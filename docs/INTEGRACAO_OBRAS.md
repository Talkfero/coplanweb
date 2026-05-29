# Integração: banco de obras compartilhado (capex × coplanweb × sistemadecadastro)

Os três aplicativos web — **capex**, **coplanweb** e **sistemadecadastro** —
operam sobre o **mesmo banco de obras** (`PLANO_DE_OBRAS.db`, SQLite). Eles
serão unificados no futuro; até lá, este documento define o **contrato comum**
para que todos apontem para o mesmo arquivo e leiam as mesmas tabelas de forma
consistente.

## 1. Como cada app resolve o banco de obras

A resolução é padronizada na seguinte ordem de prioridade (igual nos três):

1. **Variável de ambiente `PLANO_DE_OBRAS_DB`** — quando definida e apontando
   para um arquivo existente, **tem prioridade** sobre qualquer config.json.
   É o mecanismo recomendado para forçar os três apps ao mesmo arquivo num
   mesmo ambiente/instalação.
2. **`config.json` → chave `obras`** — chave canônica compartilhada (o caminho
   do `.db`). Cada app também aceita seus aliases legados:
   - capex: `obras` (+ fallback `PLANO_DE_OBRAS.db` ao lado do app);
   - coplanweb: `obras`;
   - sistemadecadastro: `obras`, `obras_path`, `db_obras` e a env legada
     `VIABILIDADES_OBRAS`.

> **Recomendação de deploy:** defina `PLANO_DE_OBRAS_DB` no ambiente
> (apontando para o `PLANO_DE_OBRAS.db` na pasta de rede compartilhada) para os
> três apps. Assim a integração funciona independente do config.json de cada um.

Pontos de código:
- capex: `web/backend/api.py :: Api._ensure_conn`.
- coplanweb: `runtime/config.py :: ConfigManager.load_config` (sobrepõe
  `config["obras"]`; propaga ao DAL/DatabaseManager).
- sistemadecadastro: `main_web/mw_resolve.py :: _resolve_obras_path`.

## 2. Quem escreve o quê (papéis)

| Tabela | Dono (escreve) | Leitores (somente leitura) |
|--------|----------------|----------------------------|
| `obras` | coplanweb (cadastro) | capex, sistemadecadastro |
| `cenarios_meta` | capex | coplanweb, sistemadecadastro |
| `cenarios_obras` | capex | coplanweb, sistemadecadastro |
| `cenario_obras_overrides` | coplanweb (planejamento) | sistemadecadastro |

- **`cenarios_meta`**: metadados do cenário, incluindo `status`
  (`em_defesa`, `aprovado`, `parcial`, `obsoleto`, `arquivado`), `nome`,
  `criado_em`.
- **`cenarios_obras`**: relação obra × ano no cenário
  (`cenario_nome`, `cod`, `ano_origem`, `ano_final`).
- **`cenario_obras_overrides`**: edições campo a campo do COPLAN dentro de um
  cenário (`cenario_nome`, `cod`, `coluna`, `valor`).

## 3. Cenário "em defesa" — invariante

Por regra do capex, **existe no máximo um cenário com `status='em_defesa'` por
vez** (o último criado; ao criar um novo, os anteriores viram `obsoleto`). Os
leitores devem selecionar o cenário em defesa assim:

```sql
SELECT nome FROM cenarios_meta
WHERE COALESCE(status,'em_defesa')='em_defesa'
ORDER BY COALESCE(criado_em,'') DESC, rowid DESC
LIMIT 1;
```

## 4. Compatibilidade retroativa (obrigatória)

- `cenario_obras_overrides` pode **não existir** em bancos antigos (só o COPLAN
  a cria). Leitores detectam via `sqlite_master` e degradam para "sem
  overrides".
- Colunas novas são sempre opcionais; caminhos de leitura toleram ausência
  (`PRAGMA table_info`, `dict.get`, `try/except`).
- Ler `config.json` sempre com `.get(chave, default)`.

## 5. Como o sistemadecadastro reflete o cenário

Ao baixar uma nota **"Com necessidade de obra"** e escolher as obras, o
sistemadecadastro retrata cada obra **como ela está no último cenário em
defesa**, considerando **todas as obras do cenário** (não apenas as
reagendadas):

- substitui `ano_` pelo `ano_final` do cenário (quando não há override de
  `ano_`);
- aplica as edições do COPLAN (`cenario_obras_overrides`);
- expõe a situação (`em_cenario`, `cenario_situacao`, `cenario_ano_origem/final`,
  `cenario_status`) no seletor de obras, nos detalhes e na geração do despacho.

A **seleção continua aberta a todas as obras** do alimentador (não é restrita
às obras do cenário). Código:
`main_web/mw_obras.py :: _load_cenario_em_defesa` / `_aplicar_cenario_em_obra`.
