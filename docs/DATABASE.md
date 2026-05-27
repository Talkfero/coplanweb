# Estrutura do banco (COPLAN)

> Fonte desta versão: **código** (`runtime/config.py` `ORDERED_COLUMNS`,
> `runtime/database.py`, `backend/domains/*`). Para a estrutura **real e
> autoritativa** de um banco específico, regenere a partir de um `.db`:
>
> ```bash
> python scripts/dump_db_schema.py /caminho/para/obras.db
> # (sem argumento, usa a chave "obras" do config.json)
> ```
>
> **Regra**: qualquer mudança de esquema (nova coluna em `ORDERED_COLUMNS`,
> novo `add_column_if_missing`, novo `CREATE TABLE`, nova tabela) **deve**
> atualizar este arquivo — rode o gerador acima ou ajuste à mão.

Banco **SQLite**. Caminho vem de `config.json` (chave `["obras"]`). Quase
todas as colunas são `TEXT` (a app normaliza/parseia em Python). Tabela
principal: `obras`.

## Tabela `obras`

PK: `cod`. Criada por `create_table_if_needed` com as colunas de
`ORDERED_COLUMNS`; `empresa`/`cod_pep` e os campos de critérios/despacho são
adicionados por migração no `connect()` (`add_column_if_missing` /
`ensure_schema_business_patch`). Todas `TEXT` salvo indicação.

### Identidade / classificação
| Coluna | Notas |
|---|---|
| `cod` | **PK**. COD da obra `SIGLA-YY-PI-ITEM` (ex.: `MA-26-DI-047`). |
| `ano_` | Ano da obra (4 dígitos). |
| `projeto_investimento` | Nome longo do PI (ex.: DISTRIBUIÇÃO). |
| `pi_base` | Código curto do PI (DI/ME/...), derivado de `get_pi_base`. |
| `nome_projeto` | Nome do projeto. |
| `codigo_item` | Item dentro do projeto. |
| `tipo_pacote` | Pacote (Mercado, Confiabilidade, ...). |
| `nivel_criticidade` | Baixa/Média/Alta. |
| `obra_aprovada` | `'SIM'`/`'NAO'` (default `'NAO'`). |
| `valor_obra` | Valor calculado (pt-BR como texto). |
| `descricao_obra` | Não pode iniciar com "Obra". |
| `observacoes_gerais` | Texto livre. |

### Alimentadores / localização
| Coluna | Notas |
|---|---|
| `alimentador_principal` | Sem `_`. |
| `alimentadores_beneficiados` | Múltiplos separados por `;` (ou `,`). |
| `subestacao` | Derivada do prefixo do alimentador. |
| `coordenada_inicio`, `coordenada_fim` | Coordenadas. |
| `quantidade_material`, `caracteristicas_material`, `novo_bay`, `manobra` | Dados técnicos. |
| `nivel_tensao_obra`, `tensao_operacao` | Tensões. |
| `nome_regional`, `nome_superintendencia` | Regional/Superintendência. |

### Ganhos (antes/depois/atual)
`contas_contratos_previos`, `contas_contratos_posteriores`,
`carregamento_inicial`, `carregamento_final`, `perdas_iniciais`,
`perdas_finais`, `tensao_media_inicial`, `tensao_media_final`,
`tensao_min_inicial`, `tensao_min_final`, `tensao_min_linha_inicial`,
`tensao_min_linha_final`, `chi_inicial`, `chi_final`, `ci_inicial`,
`ci_final`, `tensao_max_inicial`, `tensao_max_final`,
`ganhos_totais_antes`, `ganhos_totais_depois`,
`contas_contratos_beneficiadas`, `cc_benef_chi_ci`,
`tensao_min_registrada_atual`, `carregamento_max_registrado_atual`,
`ganhos_totais_atual`.

### Snapshot técnico
`tecnico_snapshot_token`, `tecnico_snapshot_at`, `tecnico_snapshot_src`,
`tecnico_dirty` (`TEXT DEFAULT 'NÃO'`; `'SIM'` = snapshot desatualizado).

### COD_PEP / empresa (migração)
| Coluna | Notas |
|---|---|
| `empresa` | Sigla da empresa (MA, PA, PI, AL, RS, AP, GO). |
| `cod_pep` | COD_PEP sequencial `EMPRESA-YY-RRR-AAA-SSSS-L`. Veja `cod_pep_emitidos`. |

### Critérios / despacho (migração `ensure_schema_business_patch`)
| Coluna | Default |
|---|---|
| `criterios_status` | — |
| `criterios_motivos` | — |
| `criterios_limite_carreg` | — |
| `despacho_status` | `'NAO_DESPACHADA'` |
| `despacho_em` | — |
| `despacho_ref` | — |

### Auditoria
`data_criacao`, `data_modificacao`, `criado_por`, `modificado_por`.

## Tabela `cod_pep_emitidos`

Registro **permanente** de cada SSSS já emitido — garante que um COD_PEP
nunca seja reaproveitado, mesmo após a obra ser excluída. Escopo por
empresa + ano (YY); a numeração SSSS reinicia a cada ano.

| Coluna | Tipo | Notas |
|---|---|---|
| `empresa` | TEXT | parte da PK |
| `yy` | TEXT | ano (2 dígitos) — parte da PK |
| `seq` | INTEGER | SSSS — parte da PK |
| `cod_pep` | TEXT | COD_PEP completo emitido |
| `obra_cod` | TEXT | COD da obra na emissão |
| `emitido_em` | TEXT | data/hora |

PK: `(empresa, yy, seq)`. Criada/semeada por
`DatabaseManager._ensure_cod_pep_ledger` (backfill das obras no `connect`).

## Tabela `meta`
Chave/valor interno. `key TEXT PRIMARY KEY`, `value TEXT`.

## Tabela `tecnico_scope_tokens`
Tokens de snapshot técnico por escopo. `scope_key TEXT PRIMARY KEY`,
`token TEXT NOT NULL`, `updated_at TEXT`.

## Tabela `apoio_meta`
Metadados da importação da planilha de apoio.

| Coluna | Tipo |
|---|---|
| `id` | INTEGER PK `CHECK (id=1)` |
| `last_path` | TEXT |
| `last_mtime` | INTEGER |
| `last_imported_at` | TEXT |
| `last_user` | TEXT |
| `sheet_count` | INTEGER |
| `sheets_json` | TEXT |
| `version` | TEXT |

## Tabelas `apoio_<aba>` (dinâmicas)
Uma por aba do `apoio.xlsx` (ex.: `apoio_apoio`, `apoio_modulo`), recriadas
a cada importação. Colunas `TEXT` espelhando as colunas da planilha.

## Tabela `cenario_obras_overrides`
Overrides por campo quando há cenário ativo (planejamento CAPEX).

| Coluna | Notas |
|---|---|
| `cenario_nome` | parte da PK |
| `cod` | parte da PK |
| `coluna` | parte da PK |
| `valor` | TEXT |
| `atualizado_em` | TEXT |
| `atualizado_por` | TEXT |

PK: `(cenario_nome, cod, coluna)`.

## Tabelas externas (CAPEX) — somente leitura
`cenarios_meta` e `cenarios_obras` são criadas por outro sistema (CAPEX).
O COPLAN apenas **lê** (`cenarios_obras`: `cod -> ano_final`, membresia do
cenário). Não são criadas/migradas por este app.
