# Plano exaustivo — Migração da aba "Ganhos" (codigo5_coplan.py → main_web.py)

> Documento gerado em 2026-05-06.
> Fonte canônica desktop: `codigo5_coplan.py` + `ui/main_window/ganhos_mixin.py` + `ui/main_window/cadastro_mixin.py:843-987` (campos de ganhos vivem no Cadastro mas o cálculo de labels mora aqui) + `core/services/relatorio_criterios_service.py` + `core/services/resumo_service.py` + `core/services/obra_rules.py` + `runtime/calc.py`.
> Alvo: `main_web.py` (CoplanApi + JS embarcado em `COPLAN_BRIDGE_JS`) + `Coplan UI.html` (`#tab-ganhos`).
> Restrição (memória `project_coplan_main_web.md`): NÃO editar `codigo5_coplan.py`. Edits ficam em `main_web.py` e quando inevitável em `Coplan UI.html`.
> **Diferencial vs. Cadastro:** a aba Ganhos no web já está ~85% pronta (Passos 5.1-5.6 do HANDOFF). O foco aqui é fechar gaps, não reconstruir.

---

## 0. Como o usuário/loop usa este arquivo

1. Carregar `MIGRACAO_GANHOS_STATE.md`, pegar próximo `G###` com dependências satisfeitas.
2. Executar (editar `main_web.py` e/ou `Coplan UI.html`); validar via grep/leitura sem abrir o app pywebview (memória `feedback_auditoria_cadastro_web_sem_abrir.md`).
3. Atualizar `MIGRACAO_GANHOS_STATE.md` (concluídos, cursor, bloqueios, desvios).
4. **SEM CRON** — usuário comanda iteração ("proximo", "go", "vá").

---

## 1. Inventário canônico do desktop (CONGELADO — não editar)

### 1.1 Layout da aba Ganhos (ordem visual)

`ganhos_mixin.py:135-318`

```
QScrollArea (vertical AsNeeded)
└─ QWidget (ganhos_layout = QVBoxLayout)
   ├─ QGroupBox "Parâmetros" (group_param)            ─ ganhos_mixin:150-230
   │  ├─ QGridLayout
   │  │  ├─ Row 0: QLabel "Parâmetro" | "Antes" | "Depois"
   │  │  └─ Rows 1-10: 10 pares (label, field_*_antes, field_*_depois)
   │  ├─ Row 11: "Contas Contratos Beneficiadas" + field_contas_benef
   │  ├─ Row 12: "CC_benef_CHI_CI" + field_cc_benef_chi_ci
   │  └─ Row 13: btn_limpar_ganhos (oculto por default)
   ├─ HBox: btn_seta_antes (Inserir Ganhos Antes ↑) + btn_seta_depois (Inserir Ganhos Depois ↑)
   ├─ HBox:
   │   QGroupBox "Ganhos Atuais" (group_ganhos_atuais) com QFormLayout:
   │   ├─ "Mín/Máx Tensão Registrada Atual:"  → edit_tensao_reg_atual
   │   ├─ "Carregamento Registrado Atual:"     → edit_carreg_reg_atual
   │   └─ "Ganhos Totais (Atual):"              → edit_ganhos_totais_atual
   │   + btn_preencher_atuais (Preencher parâmetros atuais ↑)
   ├─ HBox: QLabel "Caminho da Pasta dos Arquivos" + field_caminho_pasta + btn_selecionar_pasta (📁)
   ├─ QLabel label_planejamento  (✅/❌/⚠️ "Atendeu/Não atendeu/Dados insuficientes")
   ├─ QLabel label_posterga      (✅/❌/⚠️ "Suficiente/Insuficiente/Dados insuficientes")
   ├─ stretch
   └─ QPushButton btn_ganhos_massa "Ganhos em Massa" (no rodapé)
```

### 1.2 Campos (atributos da MainWindow)

**ANTES** (`ganhos_mixin:154-178`):

| Atributo | Coluna SQLite |
|---|---|
| `field_contas_antes` | `contas_contratos_previos` |
| `field_carregamento_antes` | `carregamento_inicial` |
| `field_perdas_antes` | `perdas_iniciais` |
| `field_tensao_media_antes` | `tensao_media_inicial` |
| `field_tensao_min_antes` | `tensao_min_inicial` |
| `field_tensao_min_linha_antes` | `tensao_min_linha_inicial` |
| `field_chi_antes` | `chi_inicial` |
| `field_ci_antes` | `ci_inicial` |
| `field_tensao_max_antes` | `tensao_max_inicial` |
| `field_ganhos_totais_antes` | `ganhos_totais_antes` |

**DEPOIS** (mesma estrutura; sufixo `_depois` / coluna `_final`):

| Atributo | Coluna SQLite |
|---|---|
| `field_contas_depois` | `contas_contratos_posteriores` |
| `field_carregamento_depois` | `carregamento_final` |
| `field_perdas_depois` | `perdas_finais` |
| `field_tensao_media_depois` | `tensao_media_final` |
| `field_tensao_min_depois` | `tensao_min_final` |
| `field_tensao_min_linha_depois` | `tensao_min_linha_final` |
| `field_chi_depois` | `chi_final` |
| `field_ci_depois` | `ci_final` |
| `field_tensao_max_depois` | `tensao_max_final` |
| `field_ganhos_totais_depois` | `ganhos_totais_depois` |

**ATUAL** (`ganhos_mixin:256-258`):

| Atributo | Coluna SQLite |
|---|---|
| `edit_tensao_reg_atual` | `tensao_min_registrada_atual` |
| `edit_carreg_reg_atual` | `carregamento_max_registrado_atual` |
| `edit_ganhos_totais_atual` | `ganhos_totais_atual` |

**BENEFICIADAS** (`ganhos_mixin:174-175`):

| Atributo | Coluna SQLite |
|---|---|
| `field_contas_benef` | `contas_contratos_beneficiadas` |
| `field_cc_benef_chi_ci` | `cc_benef_chi_ci` |

### 1.3 Botões e handlers

| Botão | Atributo | Handler | Arquivo:linha |
|---|---|---|---|
| Inserir Ganhos Antes ↑ | `btn_seta_antes` | `preencher_campos_antes` | `ganhos_mixin:234-239 + 417-582` |
| Inserir Ganhos Depois ↑ | `btn_seta_depois` | `preencher_campos_depois` | `ganhos_mixin:241-246 + 584-733` |
| Preencher parâmetros atuais ↑ | `btn_preencher_atuais` | `preencher_parametros_atuais` | `ganhos_mixin:268-273 + 735-814` |
| Selecionar Pasta 📁 | (sem atributo) | `selecionar_pasta_arquivos` | `ganhos_mixin:287-294 + cadastro_mixin:668-680` |
| Ganhos em Massa | `btn_ganhos_massa` | `preencher_ganhos_massa` | `ganhos_mixin:305-317 + 816-1081` |
| Limpar Ganhos (oculto) | `btn_limpar_ganhos` | `limpar_campos_ganhos` | `ganhos_mixin:219-230 + 329-355` |

### 1.4 Diálogos modais

| Diálogo | Origem |
|---|---|
| `GanhosMassaDialog` | `runtime/dialogs.py:143-174` — 3 checkboxes (Antes/Depois/Atual) + Help button + OK/Cancel |
| `QFileDialog.getExistingDirectory` | `cadastro_mixin.py:673` |
| QMessageBox warnings/critical/info/question | ver Seção 1.7 |

### 1.5 Regras de negócio canônicas

| Regra | Implementação | Arquivo:linha |
|---|---|---|
| **Cálculo de Δ por parâmetro** | Δ = Depois − Antes (visual, não persistido). Tensão/carreg: redução desejável. Contas: depende de contexto. | `cadastro_mixin.py:892-974` |
| **`obra_atende(row, idx, criterios, conv_float, conv_int)`** | Avalia critérios. Retorna `(bool|None, list[motivos])`. Falhas: tensão/carregamento/clientes. | `core/services/relatorio_criterios_service.py:149-205` |
| **DEFAULT_CRITERIOS** | `tensao_min=0.95, tensao_max=1.03, carregamento_limite_sim_ou_vazio=67.0, carregamento_limite_nao=100.0, clientes_maximo=6000` | `runtime/config.py:339-345` |
| **`_obra_suficiente(row, idx, criterios, piora_mercado, ...)`** | Projeta degradação ao longo de N anos do horizonte; verifica se em todos os anos a obra ainda atende. | `visualizar_mixin.py:545-622 + cadastro_mixin.py:948-974` |
| **DEFAULT_PIORA_MERCADO** | `carregamento_percentual=3.0, tensao_delta=0.005, anos_horizonte=3` | `runtime/config.py:347-351` |
| **`atualizar_labels_planejamento_desde_tela()`** | Recalcula `label_planejamento` e `label_posterga` lendo valores DEPOIS da tela; reconecta ao carregar obra. | `cadastro_mixin.py:892-987` |
| **Triggers da reavaliação live** | textChanged em `field_tensao_min_depois`, `field_tensao_max_depois`, `field_carregamento_depois`, `field_contas_depois` | `cadastro_mixin.py:981-987` |
| **Geração de `ganhos_totais_*`** | string `;`-separada formato `"{alim}_{metrica}_{valor};..."`. 8 ou 11 partes por alimentador. | `ganhos_mixin.py:357-403` |
| **Snapshot técnico (`tecnico_dirty`)** | Marca obra "SIM" quando ganhos críticos mudam. Campos críticos em `obra_rules.py:35-46`: `pi_base, ano_, tipo_pacote, alimentador_principal, municipio, ganhos_totais_*, criterios_status, descricao_obra` | `core/services/obra_rules.py:134-136` |
| **Pré-requisito: 3 arquivos técnicos** | FlowMT.TXT, Topologia.TXT, Confiabilidade.TXT (Atual usa só FlowMT+Topologia) | `ganhos_mixin.py:417+` |
| **Estado da fonte ganhos** | `_set_data_state("ganhos", VALIDADO/INVALIDADO, ...)` controla habilitação de botões | `ganhos_mixin.py` (RB-1.1, RB-RESTORE-OLD) |

### 1.6 Mapeamento UI → coluna SQLite

(Mesma tabela das seções 1.2 acima — todos os 25 campos cobertos; nenhuma divergência observada.)

### 1.7 Mensagens (catálogo desktop)

| Contexto | Tipo | Texto |
|---|---|---|
| Pasta inexistente | warning | `"Aviso: Selecione uma pasta válida para os arquivos."` |
| Pasta não encontrada (config) | warning | `"Pasta não encontrada: {pasta}. Selecione uma nova pasta."` |
| Arquivos técnicos ausentes | warning | `"Pré-requisito ausente: Arquivos técnicos obrigatórios não encontrados: {lista}"` |
| Erro ao ler arquivo | warning | `"Erro ao ler arquivos técnicos: {detalhes}"` |
| Nenhum alimentador | warning | `"Selecione ao menos um alimentador para preencher os ganhos 'Antes'."` |
| Nenhum encontrado | info | `"Nenhum dos alimentadores informados foi encontrado nos arquivos."` |
| Sucesso Antes | info | `"Ganhos 'Antes' inseridos com sucesso!"` |
| Sucesso Depois | info | `"Ganhos 'Depois' inseridos com sucesso!"` |
| Nenhuma opção (massa) | info | `"Nenhuma opção de ganho selecionada."` |
| Erro TXT alim. (massa) | warning | `"Erro ao gerar o TXT: {erro}"` |
| Confirmação massa | question | `"Deseja prosseguir com a execução?"` (Atualizar / Cancelar) |
| Resumo massa | info | `_format_processing_summary()` — Processadas/Ignoradas/Falhas |

### 1.8 Persistência colateral

- `config.json["caminho_pasta_ganhos"]` (string).
- `config.json["criterios_planejamento"]` (dict 5 chaves).
- `config.json["piora_mercado"]` (dict 3 chaves).

### 1.9 Atalhos

- Nenhum específico da aba Ganhos.

---

## 2. Estado atual do `main_web.py` (CONGELADO — referência inicial)

### 2.1 Métodos `CoplanApi` JÁ presentes

| Método | Local | O que faz |
|---|---|---|
| `list_ganhos_files(alimentador="")` | `main_web.py:2715-2751` | Lista xlsx/csv/txt da pasta + subpasta resolvida |
| `pick_ganhos_folder()` | `main_web.py:2780-2830` | File dialog + persiste `caminho_pasta_ganhos` |
| `read_ganhos_file(path, max_rows=200)` | `main_web.py:2841-2961` | Parser xlsx/csv/txt → headers/rows/parametros |
| `pick_ganhos_file()` | `main_web.py:3213-3239` | File dialog + read_ganhos_file |
| `validate_tecnico_files(pasta="")` | `main_web.py:2963-3011` | Verifica os 3 .TXT obrigatórios |
| `get_criterios()` | `main_web.py:3019-3062` | Lê critérios + piora + 7 regras declarativas |
| `get_ganhos_atuais(alimentador="")` | `main_web.py:3091-3173` | Agrega tensão/carreg/ganhos atual filtrando por alim |
| `apply_ganhos_to_obra(cod, slot, parametros)` | `main_web.py:3273-3302` | Persiste parâmetros[] em colunas (slot=antes/depois) |
| `ganhos_em_massa(cods, slot, parametros)` | `main_web.py:3304-3327` | Aplica em vários cods |
| `ganhos_compute_antes(alims, pi, pasta)` | `main_web.py:5926-6032` | Lê 3 .TXT + calcula 10 métricas + ganhos_totais |
| `ganhos_compute_depois(alims, pi, pasta)` | `main_web.py:6034-6111` | Idem para "depois" |
| `ganhos_compute_atual(alims, pasta)` | `main_web.py:6113-6165` | 4 métricas atuais (FlowMT+Topologia apenas) |
| `ganhos_apply_to_obra(cod, etapa, alims, pi, pasta)` | `main_web.py:6167-6219` | Calcula + persiste em 1 chamada |
| `ganhos_apply_massa(cods, etapa, pasta)` | `main_web.py:6221-6280+` | Massa: lê alim+pi de cada cod, computa, persiste |
| `validate_ganhos(payload, tolerancia=None)` | `main_web.py:6537-6558` | Consistência antes/depois/total |
| `criterios_check_alim_por_ganhos(metrics, manobra)` | `main_web.py:6782-6802` | Avalia critérios para 1 alim com dict {tensaominima, tensaomax, carregamento, contas} |
| `resumo_ganhos_projeto(nome_projeto)` | `main_web.py:3753-3816` | Linha por alimentador agregando obras do projeto |
| `quadro_resumo_ganhos(cod / payload)` | `main_web.py:3970-4035` | Quadro por obra |

### 2.2 IDs HTML JÁ presentes em `Coplan UI.html` (`#tab-ganhos`)

`tab-ganhos`, `ganhos-tbody`, `btn-ganhos-antes`, `btn-ganhos-depois`, `btn-ganhos-massa`, `ganhos-atual-tensao-reg`, `ganhos-atual-carreg`, `ganhos-atual-totais`, `btn-ganhos-atual`.

### 2.3 JS bridge atual (resumo dos blocos)

- **Passo 5.1** (~main_web.py:12882): card "pasta de arquivos" — botões Selecionar/Recarregar.
- **Passo 5.2** (~15313+): Inserir Ganhos Antes/Depois — abre file dialog + read_ganhos_file + popula tbody via `coplanRenderGanhosTbody`.
- **Passo 5.3** (~15983+): card "Critérios de Planejamento" — `loadCriterios()` no evento `coplan:tab='ganhos'` ou `coplan:ganhos:loaded`.
- **Passo 5.4** (~16087+): card "Ganhos Atuais" — `loadAtual()` + botão "Preencher parâmetros atuais".
- **Passo 5.5** (~16215+): botão "Ganhos em Massa" — listener pendente de modal.

Eventos custom: `coplan:tab` (dispatcher de aba) e `coplan:ganhos:loaded`.

Helper global: `window.coplanRenderGanhosTbody(headers, rows, parametros)`.

### 2.4 Lacunas identificadas pelos inventários

1. **Modal "Ganhos em Massa"** — botão `#btn-ganhos-massa` existe mas modal não está no HTML; backend pronto.
2. **Captura do alimentador atual** — card "Parâmetros de Ganhos" mostra "ATB-204" hardcoded. Precisa ler do estado/obra ativa do Cadastro.
3. **Δ calculado e Critério OK/Falhou** — `coplanRenderGanhosTbody` calcula Δ automaticamente, mas a coluna "Critério" precisa ser cruzada com `get_criterios()` regras.
4. **Labels Planejamento / Postergação** — não existe equivalente no HTML web (só info box estática "Obra atende a 3 de 4 critérios"). Precisa virar dinâmico chamando `criterios_check_alim_por_ganhos` ou similar com valores DEPOIS da tela.
5. **Edição inline da tabela** — desktop tem campos individuais editáveis para cada par (label, antes, depois). Web mostra parametros lidos do arquivo, mas se o usuário quiser editar Antes/Depois manualmente (ex.: ajustar valor depois de calcular), o JS atual não suporta.
6. **Validação `_` em alimentador** — não aplicável aqui (input de alim é elsewhere).
7. **Snapshot técnico (`tecnico_dirty`) ao mudar ganhos** — backend precisa marcar `tecnico_dirty=SIM` quando user altera ganhos antes/depois/atual; conferir se já é tratado em `apply_ganhos_to_obra` ou se precisa hook adicional.
8. **Mensagens** — usar texto canônico do desktop (catálogo 1.7) em toasts/banners.
9. **Pré-requisitos visuais** — quando os 3 .TXT não estão validados, os botões Antes/Depois/Atual deveriam estar disabled (estado UI). Hoje o JS só chama e trata erro.
10. **Reuso de motivo crítico em ganhos em massa** — ainda não tem fluxo de motivo; não-aplicável a Ganhos no desktop original (motivo é da aba Cadastro).

---

## 3. Roadmap de migração (itens G001–G050)

### 3.A — IDs e markup que faltam no `Coplan UI.html`

#### G001 — IDs estáveis nos campos do card "Pasta de arquivos"
- **O que fazer:** dar `id="ganhos-input-pasta"` ao input do path, `id="ganhos-badge-arquivos"` ao badge "N arquivos lidos", `id="ganhos-btn-selecionar"` e `id="ganhos-btn-recarregar"` aos botões.
- **Critério:** grep retorna ≥1 ocorrência por id.
- **Depende de:** —

#### G002 — ID estável no card "Parâmetros de Ganhos"
- **O que fazer:** `id="ganhos-card-parametros"` no card; `id="ganhos-card-parametros-title"` no `<div class="card-title">` (para JS atualizar com nome do alim).
- **Depende de:** —

#### G003 — Coluna "Critério" da tabela de parâmetros
- **O que fazer:** garantir que cada `<tr data-param="…">` tem `<td class="ganhos-criterio">` para JS preencher OK/Falhou.
- **Depende de:** —

#### G004 — Inputs editáveis Antes/Depois na tabela
- **O que fazer:** trocar células de Antes/Depois para `<input data-col="antes|depois" data-param="…">` (paridade com QLineEdit do desktop). Editar dispara `coplan:ganhos:dirty` no JS.
- **Depende de:** G003.

#### G005 — Card "Avaliação" novo (ou seção dentro do card de Critérios)
- **O que fazer:** adicionar 2 contêineres com IDs estáveis para os labels do desktop:
  - `<div id="ganhos-label-planejamento" data-state="pending">…</div>`
  - `<div id="ganhos-label-posterga" data-state="pending">…</div>`
- **Critério:** existem como elementos vazios; CSS herda de pills.
- **Depende de:** —

#### G006 — Modal "Ganhos em Massa"
- **O que fazer:** criar `<div class="modal-backdrop" id="modal-ganhos-massa" style="display:none;">` com 3 checkboxes (Antes/Depois/Atual) + lista de cods selecionados (vinda da aba Visualizar via custom event) + botões OK/Cancel + Help (paridade com `GanhosMassaDialog`).
- **Critério:** modal existe; IDs estáveis para JS.
- **Depende de:** —

#### G007 — Toggle "Limpar Ganhos" (oculto por default)
- **O que fazer:** adicionar `<button id="ganhos-btn-limpar" style="display:none;">Limpar Ganhos</button>` no rodapé do card Parâmetros — só aparece em modo edição.
- **Depende de:** —

---

### 3.B — Métodos `CoplanApi` faltando ou a ajustar

> Quase tudo já existe. Esta seção é principalmente **confirmação + adições cirúrgicas**.

#### G020 — `ganhos_form_state(cod="")` agregador
- **Origem desktop:** carregamento atômico do estado da aba.
- **O que fazer:** novo método que retorna `{ok, criterios, piora_mercado, regras, atual, parametros}` para o JS popular tudo num call (similar ao `cadastro_form_metadata`). Reusa `get_criterios`, `get_ganhos_atuais`, e — se `cod` informado — `quadro_resumo_ganhos(cod=cod)`.
- **Critério:** chamada com `cod` válido devolve dict completo.
- **Depende de:** —

#### G021 — `avaliar_ganhos_planejamento(payload)`
- **Origem desktop:** `_obra_atende` em `cadastro_mixin.py:920-933`.
- **O que fazer:** método que recebe valores DEPOIS da tela (`tensao_min, tensao_max, carregamento, contas, manobra`) + critérios (default ou customizado) e retorna `{ok, atende:bool|null, motivos:[]}`.
- **Critério:** com payload válido retorna avaliação; com vazio retorna `atende=null`.
- **Depende de:** —

#### G022 — `avaliar_ganhos_postergacao(payload, anos?)`
- **Origem desktop:** `_obra_suficiente` em `visualizar_mixin.py:545-622`.
- **O que fazer:** projeta degradação ao longo de N anos (DEFAULT_PIORA_MERCADO + override) e retorna `{ok, suficiente:bool|null, anos_alcancados:int, motivos:[]}`.
- **Critério:** caso "atende ano 1 mas falha ano 2" retorna `suficiente=false, anos_alcancados=1`.
- **Depende de:** —

#### G023 — `tecnico_dirty_set(cod, valor="SIM")` opcional
- **Origem desktop:** `obra_rules.py:134-136`.
- **O que fazer:** método que marca `tecnico_dirty='SIM'` para um cod (UPDATE direto). Usado quando user edita ganhos sem clicar Salvar — registra a intenção. Pode também ser deixado para o save_obra subseqüente.
- **Critério:** se aplicado, `get_obra(cod).tecnico_dirty == 'SIM'`.
- **Depende de:** —
- **Status:** **OPCIONAL** — `apply_ganhos_to_obra` já persiste e o save_obra subseqüente cuida do dirty.

#### G024 — `ganhos_resolver_alimentador(cod="")`
- **Origem desktop:** ganhos_mixin lê do field do Cadastro.
- **O que fazer:** dado `cod`, devolve `{principal, beneficiados:[], todos:[]}`. Usa `get_obra(cod)`.
- **Critério:** com cod válido devolve listas corretas.
- **Depende de:** —

---

### 3.C — JS bridge: helpers + listeners

> Toda mudança fica dentro da string `COPLAN_BRIDGE_JS` em `main_web.py`. Confirmar idempotência (`__ganhosBound` etc.).

#### G040 — Helper `coplanGanhos` IIFE
- **O que fazer:** criar `window.coplanGanhos` expondo:
  - `state` (cod ativo, alimentador ativo, parametros[], pasta atual, criterios cache).
  - `loadFor(cod)`: chama `ganhos_form_state(cod)` + popula tudo.
  - `clear()`: limpa tabela e cards.
  - `serializeParametros()`: lê inputs Antes/Depois (G004) e devolve array.
  - `setLabel(planejamento|posterga, state, text)`.
  - `showModal(id)/hideModal(id)`.
  - `MSG` catálogo (Seção 1.7).
- **Critério:** `window.coplanGanhos` existe após `coplanReady`.
- **Depende de:** G001-G005, G020.

#### G041 — Reagir a mudança de aba (`coplan:tab='ganhos'`)
- **O que fazer:** listener que dispara `coplanGanhos.loadFor(cod_atual)` onde `cod_atual = window.coplanCadastro && coplanCadastro.state.obraEmEdicao || ''`.
- **Critério:** trocar para aba Ganhos popula tabela e cards.
- **Depende de:** G040.

#### G042 — Listener "Inserir Ganhos Antes"
- **O que fazer:** `#btn-ganhos-antes.click` → confirma pasta + arquivos via `validate_tecnico_files`; resolve alim via `ganhos_resolver_alimentador(cod)`; chama `ganhos_compute_antes(alims, pi, pasta)`; popula tabela coluna "Antes" + atualiza `field_ganhos_totais_antes`. Toast `MSG.sucesso.antes` ou `MSG.erro.*`.
- **Critério:** clique em pasta válida preenche Antes; em pasta vazia mostra warning correto.
- **Depende de:** G040, G024.

#### G043 — Listener "Inserir Ganhos Depois"
- **O que fazer:** análogo a G042 com `ganhos_compute_depois`.
- **Critério:** idem.
- **Depende de:** G042.

#### G044 — Listener "Preencher parâmetros atuais"
- **O que fazer:** `#btn-ganhos-atual.click` → `ganhos_compute_atual(alims, pasta)` → preencher `#ganhos-atual-tensao-reg`, `#ganhos-atual-carreg`, `#ganhos-atual-totais` com `tensao_reg_atual` (formato `min/max`), `carregamento`, `ganhos_atual` (string).
- **Critério:** clique preenche os 3 inputs.
- **Depende de:** G040, G024.

#### G045 — Cálculo de Δ + coluna Critério
- **O que fazer:** ao popular tabela (G042/G043) ou ao editar input (G004), calcular Δ = Depois − Antes e preencher `<td class="ganhos-criterio">` aplicando regras de `get_criterios()`. `OK` verde, `Falhou` vermelho, `—` neutro se vazio.
- **Critério:** linhas com Antes/Depois preenchidos mostram OK/Falhou; sem dados mostra `—`.
- **Depende de:** G003, G020.

#### G046 — Re-avaliação live de Planejamento e Postergação
- **Origem desktop:** `atualizar_labels_planejamento_desde_tela` em `cadastro_mixin.py:892-987`.
- **O que fazer:** ao editar inputs Depois (G004) ou ao calcular ganhos (G042/G043), debounced 250ms, montar payload com `{tensao_min, tensao_max, carregamento, contas, manobra}` (manobra vem do form do Cadastro) e chamar `avaliar_ganhos_planejamento` + `avaliar_ganhos_postergacao`. Atualizar `#ganhos-label-planejamento` e `#ganhos-label-posterga` com texto + estado (`ok|err|warn|pending`).
- **Critério:** alterar valor "Tensão Min Depois" muda o label de Planejamento em < 500ms.
- **Depende de:** G005, G021, G022.

#### G047 — Botão "Selecionar Pasta"
- **O que fazer:** `#ganhos-btn-selecionar.click` → `pick_ganhos_folder()` → atualiza `#ganhos-input-pasta` com path retornado + dispara `validate_tecnico_files` para refresh do badge.
- **Critério:** após selecionar pasta válida, badge mostra contagem correta de arquivos.
- **Depende de:** G001.

#### G048 — Botão "Recarregar"
- **O que fazer:** `#ganhos-btn-recarregar.click` → `list_ganhos_files()` + atualizar badge.
- **Critério:** clique re-conta arquivos.
- **Depende de:** G001.

#### G049 — Modal "Ganhos em Massa"
- **O que fazer:** `#btn-ganhos-massa.click` → coletar cods selecionados via custom event `coplan:ganhos:massa-cods` (aba Visualizar dispara) ou via state global; abrir `#modal-ganhos-massa`. Botão OK chama `ganhos_apply_massa(cods, etapa)` para cada checkbox marcado em série. Toast resumo (paridade com `_format_processing_summary`).
- **Critério:** com 1+ checkbox marcado, OK aplica; sem checkbox, info "Nenhuma opção de ganho selecionada.".
- **Depende de:** G006, G040.

#### G050 — Habilitação dos botões conforme pré-requisitos
- **O que fazer:** ao mudar pasta ou ao receber resultado de `validate_tecnico_files`, marcar `disabled` em `#btn-ganhos-antes/depois/atual/massa` se algum dos 3 .TXT estiver faltando. Tooltip "Arquivos técnicos ausentes: …".
- **Critério:** botões disabled quando arquivos faltam; habilitam ao validar.
- **Depende de:** G047.

---

### 3.D — Integração com a aba Cadastro

#### G060 — Sincronizar alim ativo e cod ativo entre Cadastro ↔ Ganhos
- **O que fazer:** `coplanCadastro.applyObra(obra)` (já existente) dispara evento `coplan:obra-active` com `{cod, alim_principal, alim_benef[], pi}`. `coplanGanhos` escuta e atualiza title do card + recarrega `loadFor(cod)`.
- **Critério:** abrir obra na aba Cadastro reflete na aba Ganhos.
- **Depende de:** G040.

#### G061 — Marcar `tecnico_dirty=SIM` quando user edita ganhos
- **O que fazer:** quando user altera input Antes/Depois/Atual sem salvar, `state.tecnico_dirty_local = true`. Quando dispara save_obra (M053 do Cadastro), incluir `tecnico_dirty='SIM'` no payload.
- **Critério:** após editar e salvar, coluna `tecnico_dirty` da obra = `SIM`.
- **Depende de:** G040.

---

### 3.E — Verificações finais

#### G080 — Lint MSG (catálogo)
- **O que fazer:** garantir que `coplanGanhos.MSG` tem todas as 11 strings da Seção 1.7 e que JS consome cada uma pelo menos uma vez.
- **Critério:** zero órfãs declaradas mas não usadas (ou registradas como "vocabulário disponível").

#### G081 — Lint IDs `ganhos-*`
- **O que fazer:** grep cada id no JS; reportar IDs declarados mas não consumidos.
- **Critério:** zero órfãos funcionais (wrappers visuais OK).

#### G082 — Cross-check parâmetros UI ↔ coluna SQLite
- **O que fazer:** comparar tabela 1.2 (25 colunas) com `apply_ganhos_to_obra`/`ganhos_compute_*` para garantir que os 25 campos têm mapping coerente.
- **Critério:** 25/25 cobertos.

#### G083 — Cross-check critérios (4 regras)
- **O que fazer:** confirmar que `get_criterios().regras[]` cobre os 4 checks que o desktop avalia: tensão (min+max), carregamento (com manobra), CHI (≥), CI (≥).
- **Critério:** lista de regras = lista do desktop.

#### G084 — Documentar desvios
- **O que fazer:** registrar em STATE itens "intencionalmente diferente" — ex.: tabela web mostra parametros lidos do arquivo (ricos), enquanto desktop tem grade fixa de 10 pares.

---

## 4. Ordem de execução sugerida

1. **Markup faltante:** G001, G002, G003, G005, G006, G007. (G004 fica para depois — mexe na tabela já em uso.)
2. **Backend:** G020, G021, G022, G024.
3. **Helpers JS:** G040, G041.
4. **Auto-fill e cálculo:** G042, G043, G044, G045.
5. **Avaliação ao vivo:** G046.
6. **Pasta e validação:** G047, G048, G050.
7. **Massa:** G049.
8. **Edição inline:** G004 (depende de G003 e G045).
9. **Sincronia entre abas:** G060, G061.
10. **Verificações:** G080-G084.

---

## 5. Convenções

- **Nunca** editar `codigo5_coplan.py` (memória `project_coplan_main_web.md`).
- **Sem cron neste plano** — usuário comanda iteração ("proximo", "vá", "go").
- Validação por leitura/grep/`python -m py_compile main_web.py` — não abrir o app pywebview (memória `feedback_auditoria_cadastro_web_sem_abrir.md`).
- Atualizar `MIGRACAO_GANHOS_STATE.md` ao final de cada iteração.
- Em caso de dúvida, consultar a Seção 1 deste documento — referência canônica do desktop.
