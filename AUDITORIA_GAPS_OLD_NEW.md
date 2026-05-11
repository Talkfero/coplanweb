# AUDITORIA — Gaps OLD (PyQt6) → NEW (web pywebview) — COPLAN

> Gerado em 2026-05-06 a partir de análise paralela de 6 áreas (Visualizar, Resumo, Configurações, Infra, Plano/Atualizar/Técnico, Shell global).
>
> **Migração das abas Cadastro de Obras (M001-M124) e Ganhos (G001-G084) já fechadas** — ver [MIGRACAO_CADASTRO_STATE.md](MIGRACAO_CADASTRO_STATE.md) e [MIGRACAO_GANHOS_STATE.md](MIGRACAO_GANHOS_STATE.md).
>
> Este arquivo cataloga **tudo que ainda falta** comparando com o desktop (`codigo5_coplan.py` + `ui/main_window/*.py` + `runtime/*.py`) frente ao web (`main_web.py` + `Coplan UI.html`).

## Resumo executivo

| Área | Críticos | Médios | Cosméticos | Total | Fechados |
|---|---:|---:|---:|---:|---:|
| Visualizar Obras | 6 | 9 | 5 | 20 | **8** (#1/#3/#5/#6 + M3/M4/M5/M27) |
| Resumo / Volumetria / Regional | 4 | 6 | 4 | 14 | 0 |
| Configurações + COD_PEP | 13 | 8 | 3 | 24 | **3** (#11/#12/#13) |
| Infra (Import/Export/Banco/Apoio/Pills) | 12 | 13 | 6 | 31 | **6** (#24-#28 + M20) |
| Plano / Atualizar / Técnico / Outros | 7 | 6 | 2 | 15 | **2** (#41/#42) |
| Shell / Status bar / Ajuda / CLI / Erro | 3 | 7 | 4 | 14 | **2** (#44/#45) |
| **TOTAL** | **45** | **49** | **24** | **118** | **21** |

## Cenários DB-backed (Sprint A) — FECHADO ✓ (2026-05-08)

Refactor arquitetural para suporte a cenários isolados, sem mexer na tabela `obras`. Quando um cenário está ativo no COPLAN, edições ficam confinadas em `cenario_obras_overrides`; obra original permanece intocada.

**Schema (criado lazy pelo COPLAN no `obras.db`):**
```sql
cenario_obras_overrides (
  cenario_nome TEXT NOT NULL,
  cod          TEXT NOT NULL,
  coluna       TEXT NOT NULL,
  valor        TEXT,
  atualizado_em  TEXT,
  atualizado_por TEXT,
  PRIMARY KEY (cenario_nome, cod, coluna)
)
```

Tabelas pré-existentes do CAPEX (consumidas, não modificadas): `cenarios_meta`, `cenarios_obras`.

**Helpers Python em [main_web.py](apps/coplan/main_web.py):**
- `_cenario_ensure_overrides_table(db)` — cria tabela se não existe
- `_cenario_active_name()` — lê `config['cenario_ativo']`
- `_cenario_cod_set(db, nome)` — `({cod1, ...}, {cod -> {ano_final, ano_origem}})` de `cenarios_obras`
- `_cenario_overrides_map(db, nome)` — `{cod -> {coluna -> valor}}` de `cenario_obras_overrides`
- `_cenario_apply_to_row(row, cols, cod, cen_info, overrides)` — devolve cópia da row com `ano_final` + overrides aplicados
- `_cenario_save_overrides(db, nome, cod, diff_pairs)` — INSERT OR REPLACE em batch

**Bridges públicas:**
- `cenario_list()` — lista de `cenarios_meta`
- `cenario_active_get()` — `{ativo, ano_final_count, overrides_count}`
- `cenario_active_set(nome)` — persiste em `config['cenario_ativo']` (`""` desativa)
- `cenario_get_overrides(nome, cod=None)` — lista para inspeção
- `cenario_clear_overrides(nome, cod, coluna)` — reset granular

**Hooks de leitura:**
- `list_obras` — filtra `cod IN cenarios_obras.cod` + aplica `ano_final` + overrides
- `get_obra` — aplica overrides quando cenário ativo

**Hook de escrita:**
- `save_obra` em modo cenário:
  - Se cod NOVO → bloqueia (`blocked: cenario_no_create`)
  - Se cod fora do escopo do cenário → bloqueia (`blocked: cenario_out_of_scope`)
  - Senão: computa diff `(coluna, valor)` vs (obras + overrides anteriores) e INSERT em `cenario_obras_overrides`. **`obras` jamais é tocada.**
  - Retorna `mode: cenario_override` + lista `campos_alterados_no_cenario`

**Bloqueios de operações em massa:**
- `delete_obras` → bloqueia
- `marcar_obras_correcao` → bloqueia
- `atualizar_obras_valores` → bloqueia
- Mensagem padrão: `Operacao bloqueada: cenario '<X>' ativo. Saia do cenario para ...`

**Frontend** ([Coplan UI.html](apps/coplan/Coplan UI.html) + IIFE `coplanCenario`):
- Combo `#header-cenario` no header (entre pills e botões), opções `[— Sem cenário —, ...nome (N obras)]`
- Banner amarelo `#cenario-banner` abaixo do header: `Cenário ativo: <nome> · N obra(s) · X override(s)` + botão "Sair do cenário"
- Botão Salvar muda visualmente quando cenário ativo: laranja + texto "Salvar no cenário"
- Eventos custom: `coplan:cenario-changed` (cascata para `coplan:obras-changed`)
- Helpers expostos: `window.coplanCenarioReload()`, `window.coplanCenarioRefreshActive()`

**Decisão de prioridade (override > ano_final):**
Se `cenario_obras_overrides` tem `(cod, 'ano_')` E `cenarios_obras` tem `ano_final`, o override prevalece (mais recente). Sem override em `ano_`, `ano_final` do CAPEX entra como valor exibido.

**Sprint B (próximo, fora deste sprint):**
- Badge ⚡ "no cenário" em cada campo do form Cadastro mostrando se o valor é override
- Resumo/Volumetria respeitar cenário ativo
- View de diff entre cenário e original
- Audit trail de quem mudou o que (já gravamos `atualizado_por`/`atualizado_em` na tabela)
- Suporte a remover obra do cenário (sem afetar `obras`)

**Sem mudanças no CAPEX necessárias** — toda a infra adicional vive no COPLAN.

## Apoio DB-backed — FECHADO ✓ (2026-05-07)

Refactor arquitetural fora do plano original: a planilha de apoio agora é **importada para tabelas dentro do `obras.db`** na primeira carga. Sessões seguintes hidratam direto do banco sem precisar reabrir o Excel — uma só conexão por usuário. Desktop intacto (legado, continua lendo Excel direto).

**Esquema novo no `obras.db`** (todas com prefixo `apoio_*`):
- `apoio_meta` — singleton (`id=1`) com `last_path`, `last_mtime`, `last_imported_at`, `last_user`, `sheet_count`, `sheets_json`, `version`
- `apoio_apoio` — aba "Apoio" da planilha (colunas dinâmicas, nomes originais via SQLite quoting)
- `apoio_modulo` — aba "MODULO"
- `apoio_<X>` — qualquer aba adicional (sanitização ASCII para nome de tabela; nomes de coluna preservam original PT-BR)

**Helpers Python adicionados em [main_web.py](apps/coplan/main_web.py):**
- `_apoio_table_name(sheet)` — sanitiza nome de aba para tabela ASCII safe (NFKD → ascii → lowercase → snake_case com prefixo `apoio_`)
- `_apoio_quote_ident(name)` — escapa identificador SQL com aspas duplas (preserva PT-BR)
- `_apoio_ensure_meta_table(db)` — cria `apoio_meta` (idempotente)
- `_apoio_meta_dict(db)` — leitura tipada da meta
- `_apoio_import_xlsx_to_db(db, xlsx_path)` — DROP+CREATE+INSERT em transação; cada aba do Excel vira tabela
- `_apoio_load_from_db(db)` — reconstrói `_apoio_cache` no shape original (`alimentadores`, `dados_alimentador`, etc.) sem reler xlsx

**Refator do parser** ([core/services/apoio_service.py](apps/coplan/core/services/apoio_service.py)):
- Nova função pública `carregar_dados_apoio_from_dfs(df_apoio, df_modulo)` — recebe DataFrames diretamente (usado pelo reader DB)
- `carregar_dados_apoio(filepath, ...)` agora é wrapper fino que abre Excel e delega para `from_dfs` (zero duplicação, desktop continua intocado)

**Mudança em `_load_apoio_into_manager`:**
- Ordem nova: cache hit → DB-backed → xlsx fallback (com import automático para o banco após sucesso)
- `force_reload=True` para botão "Atualizar apoio"

**Bridges novas:**
- `apoio_meta()` — info da última importação para JS (`last_path`, `last_imported_at`, `sheet_count`, `hidratado`)
- `apoio_reload_from_xlsx(path)` — síncrono, força reimport
- `apoio_reload_from_xlsx_async(path)` — worker thread + progress (reusa `_OP_STATE` do Bloco 5)

**Frontend** (IIFE `__coplanApoioReloadIIFE`):
- Box injetado no card "Empresa" de Configurações > Geral mostrando: `<arquivo>.xlsx · N aba(s) · importado em DD/MM HH:MM por <user>`
- Botão "Atualizar apoio" que pergunta usar a mesma planilha ou escolher outra → dispara import async com modal de progresso
- Evento custom `coplan:apoio-changed` para outros consumidores reagirem

**Fluxo do usuário:**
1. **Primeira sessão**: Pill `Apoio` em `warn` → user vai em Config > Geral → clica "Atualizar apoio" → escolhe planilha → import → tabelas criadas → pill `ok`
2. **Sessões seguintes**: boot detecta `apoio_meta` → hidrata cache do banco em milissegundos → pill `ok` imediato sem abrir Excel
3. **Mudou de banco**: tabelas ficam no banco antigo; novo banco começa sem apoio até o user reimportar
4. **Atualização**: clique no botão pergunta usar mesma vs nova planilha → importa novamente

**Não migrado** (out of scope desta rodada):
- Histórico de imports (cada import sobrescreve `apoio_meta` — sem audit trail)
- Diff entre apoio antigo e novo (toast só mostra contagem total)
- Compactação após DROP/CREATE em loop (o SQLite já reaproveita páginas, mas `VACUUM` periódico não está automatizado)

## Visualizar Obras / Sprint 1 — FECHADO ✓ (2026-05-06)

8 gaps fechados em 1 iteração (~80 linhas Python + ~140 linhas JS + ~5 linhas CSS/HTML).

**Críticos:**
- #1 ✓ Resumo respeita filtros do Visualizar — helper `_build_resumo_where(ano, cods)` na classe `CoplanApi`; 5 endpoints (`resumo_kpis`, `resumo_volumetria_regional`, `pacotes_distribution`, `resumo_regional_table`, `resumo_volumetria_financeiro`) ganharam parâmetro `cods=None`. JS expõe `window.coplanFilteredCods()` (lista de cods se há filtros ativos, `null` se banco inteiro). Os 5 loaders (`coplanLoadKpis`/`coplanLoadVol`/`coplanLoadPacotes`/`coplanLoadVolTable`/`coplanLoadVolPi`) chamam o helper e propagam.
- #3 ✓ Plano de Obras: destaque persiste — novo `window.coplanReplayPlanoState()` invocado no fim de `coplanRenderObras`. Replays `applyHighlight(pacote, tIni, tFim)` se `__coplanPlanoActive` ativo. Idempotente.
- #5 ✓ `coplanPromptCriteriosScope` wirado — botão "Relatório Critérios" agora pergunta escopo (Todas/Filtradas/Selecionadas) e passa `cods` para `export_relatorio_criterios(cods)` (bridge ganhou parâmetro opcional + filtro client-side por COD).
- #6 ✓ Ctrl+C formato planilha — varre `tr[data-cod]` com checkbox marcado, extrai `<td>` (skip checkbox/actions), gera TSV (cabeçalho + linhas, `\t` entre colunas, `\n` entre linhas). Toast `N linha(s) copiada(s) (TSV)`.

**Médios:**
- M3 ✓ Esc limpa busca global — IIFE `__coplanVisShortcutsIIFE` adicionado: `Escape` quando `tab-visualizar` ativa limpa `#filter-input` (com ou sem foco no input).
- M4 ✓ Cor vermelha em todas as células — confirmou que regra `tr.failed td { color: var(--danger);}` (linha 448) já existia; removeu redundância da regra `td.cod, td.projeto`.
- M5 ✓ Right-click → "Atualizar Projeto" — auditoria estava desatualizada; entrada já existe no menu (`act:'projeto'`, linha 15923) chamando `coplanIniciarAtualizacaoProjetoByCod(cod)`. Catalogado como já-coberto.
- M27 ✓ Ctrl+L foca busca — mesmo IIFE M3: troca para Visualizar se necessário + foca + select() no `#filter-input`.

**HTML:**
- Adicionado `id="filter-input"` ao input de busca da Visualizar para selector estável dos atalhos.

**Não migrado neste sprint** (Sprint 2 ou futuro):
- #2 + #10 Pipeline Detalhamento (TXT despacho VT + XLSX + status DESPACHADA) — bloco próprio, requer port de `calcular_despacho_vt`.
- #4 Salvar/Exportar Banco com integridade campo-a-campo — refatorar `db_export_to`.

## Bloco 5 — UX longa-duração (progress + erro fatal) — FECHADO ✓ (2026-05-06)

Sistema genérico de progress+cancel para operações longas + global error handlers. Aplicado a `import_excel`; demais ops podem adotar via mesmo padrão.

**Gaps fechados:**
- #44 ✓ Diálogo de progresso com Cancelar (paridade `QProgressDialog`):
  - Singleton `_OP_STATE` + `threading.Lock` em [main_web.py](apps/coplan/main_web.py) (escopo de módulo).
  - Helpers `_op_reset(label)`, `_op_set_progress(processed, total, label)`, `_op_check_cancel()`, `_op_finish(result, error)`, `_op_snapshot()`.
  - Bridges `progress_state()` (retorna snapshot atual) e `progress_cancel()` (seta flag).
  - Bridge `import_excel_async(path, strategy)` dispara `threading.Thread` (daemon) e retorna imediatamente.
  - `_import_excel_from_path` agora chama `_op_set_progress` no scan de duplicadas (a cada 25 linhas) e no loop principal (a cada 5 linhas), e checa `_op_check_cancel()` (a cada 50 / a cada 10 linhas respectivamente). Cancel mid-loop devolve `cancelled=True` com contagem real do progresso.
  - HTML modal `#coplan-progress-modal` com label dinâmico, barra `<div id="coplan-progress-bar">` (% transition), counter `processed/total`, elapsed em segundos/minutos, botão `#coplan-progress-cancel`.
  - IIFE `window.coplanProgress` com API `start(label, onComplete)` / `open()` / `close()`. Polling 200ms via `progress_state()`. Quando `finished=true`, fecha modal e chama `onComplete(result, errorStr, cancelled)`.
  - Wrap do flow de import em [main_web.py:20413](apps/coplan/main_web.py:20413) usa async + modal quando `coplanProgress` disponível; fallback para chamada síncrona antiga (`import_excel_apply`).

- #45 ✓ Global error handlers:
  - IIFE `__coplanErrorHandlers` adiciona `window.addEventListener('error')` e `unhandledrejection`.
  - Filtra ruído benigno: `ResizeObserver loop` é ignorado.
  - Resto vira `coplanToast(msg, 'error')` + `console.warn('[coplan] window.onerror:', ...)`.
  - Sem recursão: se o próprio toast falhar, swallowed silenciosamente.

**Não migrado** (out of scope, sistema fica disponível para adoção):
- `cod_pep_gerar_lote`, `export_relatorio_criterios`, `export_resumo_detalhamento`, etc — adotar `_op_set_progress` + chamada via `import_excel_async`-like pattern. Tarefa por op.
- Queue de múltiplas operações (rejeita 2ª op enquanto 1ª roda — design intencional, `_OP_STATE` é singleton).
- `RotatingFileHandler` para logs JS persistentes (`runtime/cli.py:78-108` desktop) — demanda infra mais ampla.

## Bloco 4 — Técnico dirty automático — FECHADO ✓ (2026-05-06)

Refatoração de `tecnico_snapshot()` em [main_web.py:2840](apps/coplan/main_web.py:2840) (era STUB do M029) + nova bridge `tecnico_check_dirty()` + IIFE `coplanTecnicoCheck` no JS. ~190 linhas Python + ~90 linhas JS.

**Gaps fechados:**
- #41 ✓ Token técnico real: `db + apoio + ganhos + tecnico_paths` (paridade `_compute_tecnico_snapshot_token` desktop). Helpers `_compute_file_token(path)` e `_compute_folder_token(folder, required)` portados 1:1 do `tecnico_snapshot_mixin.py`. Reusa `runtime.config.TECNICO_REQUIRED_FILES`.
- #42 ✓ Trigger automático: bridge `tecnico_check_dirty()` compara token atual vs `config['tecnico_last_token']`; se mudou E há obras no banco, chama `db.mark_tecnico_dirty_all()` (fallback simples — mesmo fallback do `_apply_tecnico_token_change_db` desktop quando não há evidência de escopo). Persiste novo token no config para próxima checagem.

**Frontend:**
- IIFE `window.coplanTecnicoCheck` hookado em 3 eventos: boot (via `coplanReady`), `coplan:state` (com debounce 250ms), `coplan:obras-changed` (recount após save).
- Pill `#pill-tecnico` no header reflete contagem: `ok`/sincronizado quando count=0, `warn` quando count>0 com tooltip `N obra(s) com snapshot desatualizado`.
- Toast warn quando dirty é aplicado: `Fontes técnicas mudaram - N obra(s) marcadas como desatualizadas. Use "Atualizar snapshot tec." nas obras revisadas.`
- Novo evento custom `coplan:tecnico-snapshot-updated` (consumidores podem disparar após `tecnico_snapshot_update(cods)` para forçar recount).

**Não migrado** (out of scope, refino futuro):
- Lógica de escopo do `_apply_tecnico_token_change_db` desktop que tenta marcar dirty só para obras afetadas (por pacote/regional/etc) em vez de todas. Nosso fallback é `mark_tecnico_dirty_all()` — seguro porém amplo.
- Label visual `label_tecnico_status` permanente na UI ("Dados técnicos atualizados após consolidação: SIM/NÃO (N)") — nosso pill+toast cobre o sinal essencial.

## Bloco 3 — Importação Excel robusta — FECHADO ✓ (2026-05-06)

Refatoração de `_import_excel_from_path` em [main_web.py:5331](apps/coplan/main_web.py:5331) para paridade com [importar_excel_mixin.py:151](apps/coplan/ui/main_window/importar_excel_mixin.py:151) do desktop. ~150 linhas modificadas, sem novos arquivos.

**Gaps fechados:**
- #24 ✓ Regra do `_` em `alimentador_principal`/`alimentadores_beneficiados` por linha (com mensagem específica no log).
- #25 ✓ `_clean_excel_columns` (reuso do helper em `runtime/apoio.py`) aplicado após `pd.read_excel`/`pd.read_csv`.
- #26 ✓ `add_column_if_missing("empresa")` + `("cod_pep")` + loop para colunas novas do Excel ausentes no banco.
- #27 ✓ Gate `set(db.root_columns).issubset(set(df.columns))` retorna erro com lista de faltantes (até 10 colunas).
- #28 ✓ Branch `merge` agora reaplica `empresa` da config (se Excel não trouxer) + recalcula `cod_pep` via `cod_pep(db, obra, empresa)` quando ausente.
- M20 ✓ Grava arquivo `.txt` ao lado do importado: `<base>_log_importacao_<YYYYMMDD_HHMMSS>.txt` com sumário (insert/merge/skip/underscore/permissao) + detalhes por linha.

**Mudanças adicionais:**
- `pd.read_excel(path, dtype=str) + fillna("")` (paridade desktop, evita NaN→0.0 silencioso).
- `try/except PermissionError` separado de `Exception` (categoriza pacote bloqueado).
- Retorno enriquecido: `log_path`, `ignorados_underscore`, `ignorados_permissao`, `missing_columns` (sem quebrar consumers JS atuais).

**Não migrado neste bloco** (out of scope, pertencem a outros blocos):
- `QProgressDialog` com Cancelar (gap #44 → Bloco 5 UX longa-duração).
- `db.backup_database(label="pre_import")` antes de importar (M-bonus, requer extensão do `db_backup` existente).

## Bloco 2 — Templates de Descrição — FECHADO ✓ (2026-05-06)

Implementado em uma iteração: 4 bridges Python novas + card HTML com 10 IDs estáveis + IIFE JS `window.coplanTemplates` + `applyView` atualizado para emitir `coplan:config-subview`.

**Gaps fechados:**
- #11 ✓ Editor de template com PI Base + textarea + lista de campos clicável + Pré-visualizar.
- #12 ✓ Botão "Restaurar padrão do PI" (`delete_pi_template`).
- #13 ✓ Botão "Restaurar todos" (`restore_all_templates`).

**Bridges adicionadas em `main_web.py`:**
- `delete_pi_template(pi)` — pop de chave (com `overwrite=True` no save).
- `restore_all_templates()` — zera dict.
- `get_template_field_candidates()` — `ORDERED_COLUMNS ∪ db.columns`.
- `template_preview_render(pi, template)` — render server-side com 1ª obra do banco para o PI (fallback dict vazio).

**Desvios assumidos (não mexem na funcionalidade):**
- **D001-Templates**: sem autocomplete `{...}` ao digitar (desktop usa `TemplatePlainTextEdit` Qt). Substituído por painel lateral clicável + hint inline.
- **D002-Templates**: Pré-visualizar usa **primeira obra do banco** com pi_base correspondente (no desktop usa o form de Cadastro aberto, não disponível na aba Configurações). Se não houver obra, renderiza com placeholders vazios.
- **D003-Templates**: botão `+ PI_BASE` abre `#modal-pi` (M080) que edita `pi_base_map`. O desktop edita `pi_base_custom` (gap #14, ainda aberto). Não regrediu.

## Recomendação de priorização

1. **Bloco 1 — paridade funcional Visualizar** (gaps #1, #2, #3 + Detalhamento). Corrige a rota crítica `filtrar → detalhar → despachar → marcar DESPACHADA`, sem a qual o app não fecha o ciclo de planejamento.
2. **Bloco 2 — Templates de Descrição** (gap #11). Sub-aba inteira sem UI; vitória visível e isolada.
3. **Bloco 3 — Importação Excel robusta** (gaps #24-#28). Hoje aceita planilhas inválidas em silêncio.
4. **Bloco 4 — Técnico dirty automático** (gaps #41, #42). M029 do roadmap original ficou stub.
5. **Bloco 5 — UX longa-duração** (gaps #44, #45). Crítico para imports grandes.

---

## CRÍTICOS (45)

### A. Visualizar Obras (6)

1. ~~**Resumo não respeita filtros do Visualizar**~~ ✓ FECHADO no Sprint 1 — helper `_build_resumo_where(ano, cods)` + 5 endpoints aceitam `cods=None` + JS `coplanFilteredCods()` propaga.

2. **Botão "Detalhamento de obras"** (`visualizar_mixin.py:237` + `resumo_volumetria_mixin.py:430+`) — pendente, Sprint 2.
   - Desktop: gera **despacho VT TXT** (`calcular_despacho_vt`) + abre, gera **resumo XLSX** + abre, marca obras como `despacho_status='DESPACHADA'` + grava `despacho_em`/`despacho_ref`.
   - Web (`main_web.py:9372-9388`): só `export_detalhamento` (xlsx em ~/Downloads). Sem TXT, sem `DESPACHADA`. **Toda a maquinaria de bloqueio de save em DESPACHADA fica órfã.**

3. ~~**Plano de Obras: destaque não persiste entre re-renders**~~ ✓ FECHADO no Sprint 1 — `coplanReplayPlanoState()` invocado no fim de `coplanRenderObras`.

4. **Salvar Banco / Exportar para Banco** — pendente, Sprint 2.
   - Desktop: gates de integridade campo-a-campo, ganhos OK, lock detection.
   - Web: bridges `db_save_as`/`db_export_to` existem mas (a) sem binding na toolbar Visualizar e (b) `db_export_to` admite no docstring que "NAO replica toda a logica de _exportar_para_banco_write_phase".

5. ~~**`coplanPromptCriteriosScope` órfão**~~ ✓ FECHADO no Sprint 1 — toolbar pergunta escopo e passa `cods` para `export_relatorio_criterios(cods)`.

6. ~~**Ctrl+C copia só CODs**~~ ✓ FECHADO no Sprint 1 — handler reescrito para gerar TSV (cabeçalho + linhas, `\t`/`\n`).

### B. Resumo / Volumetria / Regional (4)

7. **Quadrante 4 do Resumo Regional ausente**
   - Desktop (`resumo_regional_mixin.py:53-192`): tabela de 8 colunas (PI / Regional / Alimentador / Subestação / Tensão / Quantidade / Coordenadas / Observação), agrupada por `(projeto_investimento × alimentador_principal)`.
   - Web: `resumo_regional_table` (L3905) tem outra coisa (Regional / Obras / Km / Tensão / CHI / CI / Carregamento / Contas / Valor) — agregação por regional.

8. **Export "Quadrante 4" Excel/CSV** (`resumo_regional_mixin.py:194-202`, `:221`, `:259`)
   - Desktop: context menu com "Exportar Quadrante 4 para Excel" e "para CSV".
   - Web: nenhum dos dois.

9. **Export consolidado de 4 abas** (`resumo_volumetria_mixin.py:242-304`)
   - Desktop: 1 XLSX com 4 sheets (Resumo de Ganhos / Ganhos-Projeto / Volumetria-Financeiro / Regional-SE).
   - Web: só `export_resumo_detalhamento` (1 sheet flat).

10. **Pipeline Detalhamento (TXT + XLSX + status DESPACHADA)** — duplica #2 acima.

### C. Configurações + COD_PEP (13)

11. ~~**Template de Descrição: UI inteira ausente**~~ ✓ FECHADO no Bloco 2 (2026-05-06): card `#tpl-card` com editor + lista clicável + preview + 4 botões.

12. ~~**Restaurar padrão do PI**~~ ✓ FECHADO no Bloco 2 — bridge `delete_pi_template(pi)` + botão `#tpl-btn-restore-pi`.

13. ~~**Restaurar todos**~~ ✓ FECHADO no Bloco 2 — bridge `restore_all_templates()` + botão `#tpl-btn-restore-all`.

14. **`pi_base_custom` vs `pi_base_map`** (`cod_pep_mixin.py:182-189`, `pi_base.py:148-149`)
    - Desktop: dois conceitos — `pi_base_custom` (lista mutável de novas BASES) e `pi_base_map` (dict pi → base).
    - Web M080 (`main_web.py:21257-21311`): edita só `pi_base_map`. **Usuário web não cria base nova, só mapeia.**

15. **`PI_BASE_MAP` no combo de Templates** (`cod_pep_mixin.py:103-110`)
    - Desktop: combo da sub-aba Templates inclui `pi_metadata` + `pi_base_custom` + chaves de `PI_BASE_MAP`.
    - Web `list_pi_base_custom` (L4682-4704): só `pi_metadata` + `pi_base_custom`.

16. **`carregamento_limite_nao`** (manobra=NÃO) — backend aceita (L4597), HTML não tem input.

17. **`clientes_maximo`** (Contas Contratos posteriores `<`) — backend aceita (L4600), HTML não tem input.

18. **`CodPepBatchDialog` ausente** (`cod_pep_mixin.py:301-323`)
    - Desktop: dialog com 3 escopos (selected/visible/packages) + checkbox "incluir aprovadas" + "somente vazios" + `QProgressDialog` granular + modal final com resumo.
    - Web: bridge `cod_pep_gerar_lote` (L5772) existe mas **nenhum botão na UI a invoca**, sem progresso, sem resumo.

19. **`preencher_cod_pep_pendentes` automático ao salvar empresa** (`config_mixin.py:97`, `:174-186`)
    - Desktop: dispara após salvar empresa, mostra quantas obras foram preenchidas.
    - Web `save_config_empresa` (L4483-4539): não chama. Bridge `cod_pep_preencher_pendentes` (L5818) existe mas órfã.

20. **Sigla empresa: dropdown de 7 valores** (`config_mixin.py:33-43`, `EMPRESA_SIGLAS_VALIDAS`)
    - Desktop: `QComboBox` com `MA, PA, PI, AL, RS, AP, GO`.
    - Web (HTML L1434): `<input value="MA"/>` texto livre. Backend valida no save mas usuário não tem orientação.

21. **REGIONAL_TO_COD** (`config.py:121-143`) — mapa de 3 letras (NDE/NRO/CEN) usado na geração de COD_PEP — sem CRUD em nenhum lado, hardcoded.

22. **Web introduziu CRUD de `REGIONAL_MAP` com `superintendencia`/`se_prefixos`/`cor`** que o desktop nunca lê — risco de dessincronização (web salva, desktop ignora).

23. **Backup automático de `config.json`** — não existe (cadastro_viabilidades tem; COPLAN não).

### D. Infra (Import/Export/Banco/Apoio) (12)

24. ~~**Regra do `_` em alimentador**~~ ✓ FECHADO no Bloco 3 — by-line check com mensagem específica no log + contador `ignorados_underscore`.

25. ~~**`_clean_excel_columns`**~~ ✓ FECHADO no Bloco 3 — reuso de `runtime.apoio._clean_excel_columns`. (Nota: o helper desktop também não normaliza acentos — a auditoria estava imprecisa nesse ponto; paridade total preservada.)

26. ~~**`add_column_if_missing`**~~ ✓ FECHADO no Bloco 3 — `empresa`/`cod_pep` garantidas + loop para colunas novas do Excel.

27. ~~**Validação `root_columns ⊆ df.columns`**~~ ✓ FECHADO no Bloco 3 — gate retorna `{ok:false, missing_columns: [...]}` com mensagem clara.

28. ~~**`_merge_duplicate_record` recalcula `cod_pep`**~~ ✓ FECHADO no Bloco 3 — `_build_merge_updates_with_pep()` reaplica `empresa` + chama `cod_pep(db, obra, empresa)` quando ausente.

29. **Diálogo "Selecionadas vs Visíveis" no Export Excel** (`exportar_excel_mixin.py:97-118`) — web `header_export_excel` (L5161-5164) sempre exporta todas.

30. **`_prompt_export_columns_mode`** (`exportar_excel_mixin.py:140`, `:209-243`) — perfis `DEFAULT_EXPORT_PROFILES` + escolha de colunas. Web ignora.

31. **`exportar_para_banco` com integridade + lock detection** (`banco_mixin.py:111-244`) — gate aprovadas + `_row_integrity_reasons` + `require_ganhos_ok_or_confirm` + `is_database_busy_exception` + `build_database_busy_message`. Web `db_export_to` admite no código que "NAO replica".

32. **Mensagens UX para `database is locked`** (`banco_mixin.py:259-271`) — desktop usa `build_database_busy_message` com info do lock holder. Web mostra `sqlite3.OperationalError` cru.

33. **`os.access(W_OK)` com mensagens dedicadas** (`banco_mixin.py:54`, `estado_fontes_mixin.py:160-179`) — web `_validate_db_minimum` só retorna string genérica.

34. **`apoio_service.py:107-112,132-154` validação de aba MODULO** — desktop tem `ApoioFileError(codigo='DADOS_VAZIOS')` distinguindo aba ausente vs aba sem dados. Web só "planilha de apoio invalida".

35. **`buscar_projetos`/`ProjectSelectionDialog`** (`apoio_mixin.py:316-325`) — modal de seleção de projeto existente. Web não tem; só combo `nome_projeto` populado por `apoio_get_nomes_projetos`.

### E. Plano / Atualizar / Técnico / Outros (7)

36. **Plano: gates `require_integrity_or_block` + `require_ganhos_ok_or_confirm`** (`plano_obras_mixin.py:34-77`) — web só `db_only` guard.

37. **Geração PDF/Excel do Plano** — não existe. Procurei `plano_pdf|plano_excel|gerar_plano`: nada (também não há no desktop — confirmar se é esperado).

38. **Botão "atualizar Descrição da Obra"** (`atualizar_obra_mixin.py:49-56`)
    - Desktop pergunta "Deseja atualizar também a Descrição da Obra?".
    - Web (`main_web.py:2173-2174`): comentário admite que ficaria para botão dedicado. **Botão nunca foi feito.**

39. **Fluxo de chaves extras (`extra_key_map`)** (`atualizar_obra_mixin.py:59-105`)
    - Desktop: pede chaves separadas por `;` + dialog de seleção de PIs por chave.
    - Web `atualizar_obras_valores` (L2163): hardcoda `extra_key_map={}`.

40. **Relatório TXT de chaves inexistentes** (`atualizar_obra_mixin.py:229-257`) — desktop abre notepad com lista; web só toast de count.

41. ~~**Token técnico real**~~ ✓ FECHADO no Bloco 4 — helpers `_compute_file_token`/`_compute_folder_token` portados; `tecnico_snapshot()` agora hash sha1 de `db|apoio|ganhos|tecnico_paths`.

42. ~~**`_handle_tecnico_token_change` automático**~~ ✓ FECHADO no Bloco 4 — bridge `tecnico_check_dirty()` + hook JS no `coplan:state` event marca dirty automaticamente quando token muda.

### F. Shell / Status bar / Ajuda (3)

43. **Ctrl+B na aba Ganhos** (`codigo5_coplan.py:670-674`) — desktop salva; web só salva se aba ativa = Cadastro.

44. ~~**Diálogo de progresso**~~ ✓ FECHADO no Bloco 5 — sistema genérico (`_OP_STATE` + `progress_state` + `progress_cancel` + `import_excel_async` em thread). Modal `#coplan-progress-modal` com barra/counter/elapsed/cancel. Aplicado a `import_excel`; demais ops podem adotar.

45. ~~**`window.onerror` / `unhandledrejection`**~~ ✓ FECHADO no Bloco 5 — IIFE `__coplanErrorHandlers` toasta `Erro inesperado: <msg>` e loga `console.warn`. Filtra ruído benigno (`ResizeObserver loop`).

---

## MÉDIOS (49) — top 20

### Visualizar Obras
- M1. **`returnPressed` na busca global** (`visualizar_mixin.py:147`) — Enter dispara filtro imediato. Web só tem debounce 180ms.
- M2. **11 campos de filtro inline** (`visualizar_mixin.py:51-86`) — desktop tem barra horizontal com filter_cod/ano/pi/nome_projeto/alim/alim_benef/regional/superintendencia/subestacao/pacote/tecnico_dirty. Web: tudo dentro de modal "Filtros avançados" (~3 cliques a mais).
- M3. ~~**Esc limpa busca global**~~ ✓ FECHADO no Sprint 1 — IIFE `__coplanVisShortcutsIIFE` adicionado.
- M4. ~~**Cor vermelha em obras falhadas**~~ ✓ FECHADO no Sprint 1 — regra CSS `tr.failed td` já existia; removeu redundância.
- M5. ~~**Right-click → "Atualizar Projeto"**~~ ✓ FECHADO (já existia) — entrada `act:'projeto'` no menu chamando `coplanIniciarAtualizacaoProjetoByCod`.
- M6. **Double-click em modo "Plano ativo"** (`visualizar_mixin.py:624-689`) — desktop dispara `iniciar_atualizacao_projeto`; web sempre abre edição.
- M7. **"Marcar como CORREÇÃO" pede motivo no momento** (`visualizar_mixin.py:241-243`, `excluir_obra_mixin.py:179-185`) — web adia para o save (`PENDENTE - informar no salvamento`).
- M8. **Web `pi` filtro mapeia para campo curado `pi_base-codigo_item`** — desktop usa `projeto_investimento` puro. Pode rejeitar buscas que casavam só com PI base.
- M9. **`clear_all_filters`** (`filtros_paginacao_mixin.py:32-52`) — verifica se zera TUDO incluindo chips e selects do modal.

### Resumo / Volumetria / Regional
- M10. **`parse_number` pt-BR/en-US misto** (`resumo_regional_mixin.py:93-122`) — desktop usa parser permissivo. Web `_sql_to_real` (L3699) `REPLACE('.','')+REPLACE(',','.')` pode dar 100x errado em valores com ponto decimal en-US (`12.5` → `125`).
- M11. **`coplan:obras-changed` vs `coplan:obras`** — Resumo escuta o segundo, save dispara o primeiro. Verificar bridge.
- M12. **Quadro "Volumetria por PI × Ano"** — backend retorna shape correto, mas a tabela `vol-tbody` mostra só Regional. Card extra injetado por JS substitui ou complementa?

### Configurações + COD_PEP
- M13. **2 sub-abas (Critérios / Piora de Mercado) fundidas em 1 card** — UX divergente.
- M14. **`postergacao_max_anos`/`chi_min`/`ci_min`** — chaves novas só do web; desktop ignora ao ler config.json.
- M15. **`open_manage_pi_base_dialog` chamado direto da sub-aba Templates** — web exige passar pelo "Abrir Gerenciador" da sub-aba PI_BASE.
- M16. **Prompt local para PI desconhecido** — desktop tem `+ Criar novo PI_BASE...`; web `resolver_pi_base` retorna `{conhecido: false}` mas JS não dispara `add_pi_base_custom`.
- M17. **`_warn_external_db_update`** (`estado_fontes_mixin.py:454-466`) — desktop modal "Banco atualizado por outro usuário; recarregue". Web só `console.warn`.
- M18. **`refresh_action_availability`** (`estado_fontes_mixin.py:482-540`) — desktop habilita/desabilita ~15 botões conforme estado. Web só checa no clique (descobre erro depois).

### Infra
- M19. **Última pasta usada nos diálogos de arquivo** — `pywebview.create_file_dialog` parece não persistir; cada chamada começa do zero.
- M20. ~~**Log de importação**~~ ✓ FECHADO no Bloco 3 — arquivo `<base>_log_importacao_<YYYYMMDD_HHMMSS>.txt` com sumário + detalhes por linha.

### Plano / Técnico
- M21. **Histórico completo da obra** — não há viewer; só `db_last_modification_info` (última entrada).
- M22. **`projeto_novo_ano`/`projeto_novo_nome`** travados nas obras 2..N do modo Atualizar Projeto (`atualizar_obra_mixin.py:388-397`) — não propagado no web.

### Shell / Status bar / Ajuda
- M23. **Diálogo de erro com stacktrace expandível** (`runtime/dialogs.py:50-86`, `setDetailedText`) — web só `toast(error)` curto.
- M24. **Diálogo "Sobre/Versão"** — ausente em ambos (mas desktop pelo menos tem `show_help_main`).
- M25. **Footer "Mais ações"** (`footer_more_actions.py`, `status_bar_chrome_mixin.py:217-247`) — desktop QToolButton com popup (Relatório Critérios / Nota Colapso / Exportar Banco / Backup Banco / Plano de Obras). Web `<button>more-horizontal</button>` (HTML L856) sem handler.
- M26. **F1 → Ajuda** — sem atalho em nenhum dos lados (esperado pela maioria).
- M27. ~~**Ctrl+L (foco busca)**~~ ✓ FECHADO no Sprint 1 — IIFE `__coplanVisShortcutsIIFE`: troca para Visualizar se necessário + foca + select() no `#filter-input`.
- M28. **Persistência sidebar colapsada** — não persiste entre sessões.
- M29. **Toggle "Rodapé compacto" desconectado** (HTML L1448-1451) — switch puro `data-toggle`, sem bridge para `applyStatusbarCompact`.

---

## COSMÉTICOS (24) — resumo

- Recolher coluna calculada por `QFontMetrics` vs `COMPACT_PX = 120` hardcoded.
- Seleção `SelectItems` desktop vs só checkbox web.
- `freeze_panes`/`Font(bold=True)`/auto-width — formatação simplificada no export web.
- 4 toggles do card "Preferências de UI" sem bridge (`Coplan UI.html:1450-1463`).
- "Abrir pasta" ao lado de paths do Explorer (`subprocess.Popen(['explorer', '/select,', path])`).
- Ícone `more-horizontal` sem handler na toolbar Visualizar.
- "Snapshot timestamp" (`label_tecnico_status`) não migrado para o header do Resumo.
- (demais cosméticos nos relatórios completos por agente.)

---

## Suspeitas / Verificação manual

1. **Sub-aba "Templates de descrição"** — confirmar visualmente que placeholder não tem editor.
2. **Sub-aba "PI_BASE"** — confirmar que modal #modal-pi atua sobre `pi_base_map` (não `pi_base_custom`).
3. **PI Extra (config-card-pi-extra)** — fica permanentemente visível porque não está em `applyView` mapping.
4. **`carregamento_limite_nao` + `clientes_maximo`** — confirmar que JS não envia essas chaves.
5. **`SupportFileManager.load_support_file` shape** — confirmar que web e desktop consomem o mesmo retorno.
6. **`_sql_to_real`** com valores en-US misturados — verificar dados reais em `tensao_media_final`, `chi_final`, `ci_final`, `carregamento_final`.
7. **Cores `var(--success)`/`var(--danger)`** definidas nos CSS vars — verificar visualmente.
8. **Botão `more-horizontal`** na table-toolbar (HTML L856) sem handler — testar clique.
9. **`apply_windows_selection_color`** — paleta azul Windows; verificar consistência em tabelas/listas.
10. **`Detalhes da obra`** (commit `ec02b6d`) — verificar se já mostra histórico completo.

---

## Apêndice — relatórios completos por área

Cada agente devolveu inventário detalhado com `arquivo:linha`. Para retomar trabalho em uma área específica, reabrir o agente correspondente via `SendMessage` com o ID:

| Área | Agent ID | Tamanho |
|---|---|---|
| Visualizar Obras | `ad2fd6fb58aa470ab` | ~600 linhas |
| Resumo / Volumetria | `ae1ca93db5005d669` | ~500 linhas |
| Configurações + COD_PEP | `ad2c3ab171fda753f` | ~500 linhas |
| Infra (Import/Export/Banco/Apoio) | `a8b80f708ef5fcc40` | ~600 linhas |
| Plano / Atualizar / Técnico | `a8708a9279e9baa50` | ~500 linhas |
| Shell / Status bar / CLI | `a3ac030df273786ae` | ~450 linhas |

> **Nota:** os IDs acima são da sessão `2026-05-06`. Em sessão futura, lançar nova auditoria comparando contra este arquivo.
