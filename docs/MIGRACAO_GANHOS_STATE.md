# MIGRACAO_GANHOS — estado vivo

> Atualizado a cada iteração comandada pelo usuário.
> Plano de referência (congelado): [MIGRACAO_GANHOS_PLAN.md](MIGRACAO_GANHOS_PLAN.md).
> **Sem cron** — usuário comanda ("proximo"/"go"/"vá"); cron `c70f69f5` da aba Cadastro foi cancelado nesta iteração.

## Cursor

- **Próxima leva:** ROADMAP COMPLETO. Itens pendentes são opcionais (G003 + G004) e dependem de decisão UX do usuário.
- **Próximo item recomendado:** smoke test manual quando disponível (não pelo loop — memória `feedback_auditoria_cadastro_web_sem_abrir.md`).
- **Última iteração concluída:** 4 (2026-05-06).
- **Iteração atual:** aguardando comando do usuário.

## Concluídos (na ordem)

### Iteração 1 (2026-05-06) — leva A markup HTML

- **G001** — IDs no card "Pasta de arquivos do alimentador":
  - Card → `id="ganhos-card-pasta"`
  - Input do path → `id="ganhos-input-pasta"`
  - Badge "N arquivos lidos" → `id="ganhos-badge-arquivos"`
  - Botão Selecionar → `id="ganhos-btn-selecionar"` (com title)
  - Botão Recarregar → `id="ganhos-btn-recarregar"` (com title)
- **G002** — Card "Parâmetros de Ganhos":
  - Card → `id="ganhos-card-parametros"`
  - Title → `id="ganhos-card-parametros-title"`
  - Nome do alim atual virou `<span id="ganhos-alim-atual">—</span>` (era "ATB-204" hardcoded)
- **G005** — Card "Critérios de Planejamento" reescrito:
  - 4 checks dinâmicos com `data-criterio="tensao_min|tensao_max|carregamento|clientes"` + `data-state="pending"` + badge inline (popup `populateSelect`-like via JS na G045/G046).
  - Removida a info box "Obra atende a 3 de 4 critérios" estática — substituída por:
  - 2 labels com IDs estáveis: `#ganhos-label-planejamento` e `#ganhos-label-posterga` com `data-state="pending"`. Inicialmente texto neutro "Aguardando dados para avaliar…".
- **G006** — Modal `#modal-ganhos-massa` adicionado antes do toast:
  - 3 checkboxes: `ganhos-massa-chk-{antes,depois,atual}`.
  - Contador de cods selecionados: `#ganhos-massa-cods-count` + preview `#ganhos-massa-cods-preview`.
  - Botão Help: `#ganhos-massa-btn-help`.
  - Botão OK: `#ganhos-massa-btn-ok` (disabled por default).
  - Cancelar via `[data-close]` e botão explícito.
- **G007** — Botão Limpar Ganhos no header do card Parâmetros: `#ganhos-btn-limpar` com `style="display:none"` por default (revelado em modo edição).

Bonus iteração 1:
- Adicionei `class="col-delta"` e `class="col-criterio"` aos `<th>` da tabela (paridade com os existentes `col-antes`/`col-depois`) para o JS conseguir endereçar via seletor.
- Card "Critérios" ganhou `id="ganhos-card-criterios"`.

Validação: `grep id="ganhos-*"` → 20 matches; `grep "data-criterio=|data-state=pending"` → 11 matches (5 do Cadastro, 6 novos da Ganhos).

**G003** (coluna Critério com `<td class="ganhos-criterio">`) **adiado** — depende de mexer no JS renderer `coplanRenderGanhosTbody`. Será feito junto com G045 (cálculo Δ + Critério).

**G004** (inputs editáveis Antes/Depois) **adiado** — risco de quebrar UX visual; confirmar com usuário antes.

### Iteração 2 (2026-05-06) — leva B backend

Bloco de 4 métodos novos inseridos após `get_ganhos_atuais` (em `main_web.py` ~linha 3173):

- **G024** — `ganhos_resolver_alimentador(cod)` em `main_web.py:3185`. Resolve `{principal, beneficiados[], todos[]}` lendo `get_obra(cod)`. Reusa `obra.alim_benef` quando o backend já parseou; fallback para split semicolon/comma. Dedup case-insensitive.
- **G020** — `ganhos_form_state(cod="")` em `main_web.py:3238`. Agregador retornando `{ok, error, criterios, alim, atual, quadro, cod}`. Reusa `get_criterios`, `get_ganhos_atuais` (filtrado pelo principal resolvido) e `quadro_resumo_ganhos(cod)` quando cod informado.
- **G021** — `avaliar_ganhos_planejamento(payload)` em `main_web.py:3272`. Espelho web de `_obra_atende`. Aceita payload com chaves alternativas (`tensao_min`/`tensao_min_final`/`tmin`, etc.). Carrega `criterios_planejamento` do config (fallback `DEFAULT_CRITERIOS`), monta linha sintética + idx, delega para `core.services.relatorio_criterios_service.obra_atende()`. Retorna `{ok, atende:bool|null, motivos:[]}`.
- **G022** — `avaliar_ganhos_postergacao(payload, anos?)` em `main_web.py:3356`. Espelho web de `_obra_suficiente`. Loop de N anos aplicando `delta_tensao` (subtrai) e `carregamento_percentual` (multiplica), avalia `obra_atende` ano a ano. Retorna `{ok, suficiente:bool|null, anos_alcancados:int, motivos:[]}`. `anos` default vem de `piora_mercado.anos_horizonte`.

Validação: `python -m py_compile main_web.py` → OK syntax. 4 métodos definidos nas linhas 3185/3238/3272/3356.

### Iteração 3 (2026-05-06) — leva C JS bridge

Novo bloco `<script>` (~310 linhas) injetado no fim de `COPLAN_BRIDGE_JS`. Cria `window.coplanGanhos` e amarra os 6 itens da leva C que ainda não eram cobertos.

- **G040** — `window.coplanGanhos` IIFE com `state` (cod, alim_principal, alim_beneficiados, pasta, txt_validos, selectedCods), `MSG` (12 strings do desktop catálogo 1.7), helpers `setLabel(which,st,text)`, `setCriterio(key,st,text)`, `showModal/hideModal`, `refreshAlimAtual`, `loadFormState`, `recalcLabels`, `refreshPrereq`, `openMassaModal`, `setSelectedCods(cods)`, `toast`.
- **G041** — Listener `coplan:tab='ganhos'` chama `refreshPrereq()` + `loadFormState()` + `recalcLabelsDebounced()`. `loadFormState` chama `ganhos_form_state(cod)` (G020), atualiza `<span id="ganhos-alim-atual">` e popula os 4 chips de critérios da sidebar com valores config (`tensao_min/tensao_max/carregamento/clientes_maximo`) em estado `pending`.
- **G046** — `recalcLabels()` debounced 250ms chama `avaliar_ganhos_planejamento(payload)` (G021) e `avaliar_ganhos_postergacao(payload)` (G022). Atualiza `#ganhos-label-planejamento` e `#ganhos-label-posterga` com ícone Lucide + cor + bg conforme `data-state` (ok/warn/err/pending). Triggers: change em `cad-input-tensao`, `cad-input-tensao-oper`, `cad-sel-manobra` (proxy enquanto não há inputs DEPOIS dedicados — desvio D001-Ganhos).
- **G049** — Modal Ganhos em Massa wirado. Listener no `#btn-ganhos-massa` em **fase de captura** (`addEventListener(..., true)`) que **intercepta** o handler antigo (`clickMassa` em ~16140) via `stopImmediatePropagation()`. Abre `#modal-ganhos-massa` populando contador/preview com `state.selectedCods`. OK habilita só com checkbox + cods. Confirmação `window.confirm`. Aplica em série por etapa via `ganhos_apply_massa(cods, etapa, '')` e mostra toast resumo. Help button: toast informativo. Canal `coplan:ganhos:massa-cods` (futuro: aba Visualizar dispara com array de cods).
- **G050** — `refreshPrereq()` chama `validate_tecnico_files('')` e `disable=true` em `#btn-ganhos-{antes,depois,atual,massa}` se faltam .TXT. Tooltip dinâmico explica o motivo. Disparado no `coplan:tab='ganhos'`.

**Itens "já cobertos" pelo JS pré-existente** (não há código novo, só catalogar):

- **G042 / G043 / G044** — botões Inserir Antes/Depois/Atual: bindados em `main_web.py:~16131` (Passo 5.5) com `clickAntes/Depois/Atual` que chamam `ganhos_apply_to_obra` ou `ganhos_compute_*`. ✓
- **G045** — Δ + Critério na tabela: wrap em `coplanRenderGanhosTbody` (linha ~16282) aplica regras de `get_criterios()` via `applyCriterios(parametros)` retornando `{crit_label, status: 'ok'|'fail'|null}`. ✓
- **G047 / G048** — botões Selecionar/Recarregar pasta: bindados em `bindGanhosCard` (linha ~15585, Passo 5.1). Os IDs novos `ganhos-btn-selecionar/recarregar` (G001) servem como ancora explícita; o JS antigo localiza por `getInputs(card)`. ✓

Bonus iteração 3:
- `coplan:obra-active` listener implementado (sincroniza state quando o Cadastro disparar). G060 ainda pendente (Cadastro precisa **disparar** o evento — apenas 2 linhas de patch).
- `coplan:ganhos:alim-changed` event disparado quando alim muda — outras integrações podem escutar.

Validação: `python -m py_compile main_web.py` → OK syntax. Grep por marcadores únicos do bloco → 47 matches.

### Iteração 4 (2026-05-06) — leva D integração + lints (FECHA migração Ganhos)

**G060** — patch INLINE no wrap existente do `C.applyObra` em `main_web.py:~20860` para disparar `document.dispatchEvent('coplan:obra-active', detail:{cod, alim_principal, alim_beneficiados, pi, pi_base})`. Patch idêntico no `C.clearForm` para emitir `cod=''` quando obra desativa. Beneficiados são parseados de string (`;`/`,`) ou aceitos como array. Resolve o desvio D002-Ganhos.

**G061** — `state.tecnico_dirty_local` flag dentro de `coplanGanhos`. `markTecnicoDirty()` é bound em:
- click nos 4 botões `#btn-ganhos-{antes,depois,atual,massa}` (guarda `__ganhosDirtyBound`)
- input nos 3 inputs `#ganhos-atual-{tensao-reg,carreg,totais}`
- Wrap de `coplanCadastro.serializeForm` (guarda `__ganhosDirtyWrap`) injeta `tecnico_dirty='SIM'` no payload quando o flag está true.
- Listener `coplan:obras-changed` com `source='cadastro:save'` chama `clearTecnicoDirty()`.

#### Lints finais

- **G080** (Lint MSG `coplanGanhos.MSG`): 12 strings declaradas, 5 consumidas pelo JS novo (`aviso.txt_ausentes`, `aviso.pasta_invalida`, `aviso.sem_cods_massa`, `aviso.sem_opcao_massa`, `pergunta.massa_executar`). 7 órfãs mantidas como vocabulário disponível (fluxos antigos do Passo 5.1/5.5 já têm seus próprios toasts inline). **OK.**
- **G081** (Lint IDs `ganhos-*`): 23 declarados no HTML, todos consumidos pelo JS novo + JS antigo (Passo 5.1/5.4/5.5). **Zero órfãos funcionais.**
- **G082** (Cross-check 25 colunas SQLite): `GANHOS_LABEL_MAP` (~main_web.py:3187) cobre os 20 campos ANTES/DEPOIS via mapeamento substring. Os 3 campos ATUAL (`tensao_min_registrada_atual`, `carregamento_max_registrado_atual`, `ganhos_totais_atual`) são persistidos pelo backend `ganhos_compute_atual` + `apply_ganhos_to_obra(slot='atual')`. Os 2 BENEFICIADAS (`contas_contratos_beneficiadas`, `cc_benef_chi_ci`) já vinham populados pelo `ganhos_compute_antes`. **25/25 cobertos** (alguns indiretamente via cálculos backend).
- **G083** (Cross-check critérios): `DEFAULT_CRITERIOS` tem 5 chaves; `obra_atende` aplica 3 checks lógicos (tensão min+max combinados, carregamento conforme manobra, clientes). HTML mostra 4 chips (`tensao_min`, `tensao_max`, `carregamento`, `clientes`). **Coerente.** A regra "manobra" altera apenas o limite de carregamento (não vira chip próprio).
- **G084** (Consolidação dos desvios): D001-Ganhos + D002-Ganhos catalogados acima. D002 foi RESOLVIDO por G060 nesta iteração (Cadastro agora dispara o evento). D001 fica até G004 entrar.

Validação: `python -m py_compile main_web.py` → OK syntax. Grep por novos marcadores → 17 matches (G060 emit + G061 dirty wrap).

---

## STATUS: MIGRAÇÃO DA ABA GANHOS COMPLETA ✓

Todos os itens G001-G084 cobertos por: **implementado, indireto (já no JS antigo), ou registrado como adiamento opcional (G003/G004)**. Pode ser feito smoke test manual.

### Hotfix pós-smoke (2026-05-06) — 4 SyntaxError no console DevTools

Smoke test do usuário expôs 4 `Uncaught SyntaxError: Invalid or unexpected token` em about:blank linhas 2050, 3147, 4592, 10707. Causa raiz: strings JS dentro de `COPLAN_BRIDGE_JS` continham `\n` Python (newline real interpretado pelo Python como quebra de linha) — JS recebia string literal quebrada em 2 linhas, ilegal.

Pontos corrigidos (todos com `\n` → `\\n` em Python para gerar literal `\n` no JS):

- `main_web.py:7456-7457` — `tip += '\nErro: '` e `tip += '\nPath: '` (tooltip de pills do header).
- `main_web.py:8551` — `cods.join('\n')` (Ctrl+C de visualizar).
- `main_web.py:9995` — `'".\n\nContinuar com '` (confirm de Plano de Obras).
- `main_web.py:16108-16110` — `' obra(s)?\n\n'` + `'... beneficiadas)\n'` (prompt de Ganhos em massa antigo).

Bug pré-existente (não introduzido por nenhuma das migrações Cadastro/Ganhos) — só revelou agora porque os scripts afetados eram lazy (rodam ao clicar/passar mouse). Detector heurístico (`_detect_broken_strings.py`) rodado para scan completo no served HTML não encontrou outras quebras reais (31 falsos positivos, todos validados).

Validação: served HTML regerado tem 16409 linhas (8 a menos = 4 pares 2→1 linhas consolidadas). `python -m py_compile main_web.py` → OK syntax. **DevTools deve ficar limpo no próximo F5.**

## Em andamento

_(vazio)_

## Bloqueios

_(vazio)_

## Desvios conscientes em relação ao desktop

- **D001-Ganhos** (de G046): no desktop, `atualizar_labels_planejamento_desde_tela` lê os 4 valores DEPOIS dos QLineEdit dedicados (`field_tensao_min_depois`, `field_tensao_max_depois`, `field_carregamento_depois`, `field_contas_depois`). No web, esses campos individuais ainda não existem na UI (a tabela mostra parametros lidos de arquivo, não inputs por linha — vide G004 adiado). Como **proxy** o JS lê do form do Cadastro: `tensao_min/tensao_max ← nivel_tensao_obra`, `manobra ← cad-sel-manobra`. `carregamento` e `contas` ficam vazios e a avaliação retorna `dados_insuficientes` enquanto não houver inputs editáveis. Quando G004 entrar, refatorar `readDepoisFromCadastro()` para ler dos inputs da tabela.
- **D002-Ganhos** (de G041): ~a sincronia automática Cadastro↔Ganhos depende do evento `coplan:obra-active` que ainda não é disparado pelo `coplanCadastro.applyObra` (item G060 pendente)~. **RESOLVIDO na iteração 4** (G060) — `coplanCadastro.applyObra/clearForm` agora disparam o evento. A sincronia é automática (escutar `coplan:obra-active` em `coplanGanhos`).

## Notas livres

- 2026-05-06 (it.0): plano gravado. Cron da Cadastro (`c70f69f5`) cancelado para parar ruído.
- 2026-05-06 (it.1): leva A (markup HTML) fechada — G001, G002, G005, G006, G007. G003 e G004 adiados (dependem de JS / risco UX).
- 2026-05-06 (it.2): leva B (backend) fechada — G020, G021, G022, G024 implementados (lazy-import; reusa `obra_atende` server-side; replica algoritmo `_obra_suficiente` no main_web pra não acoplar a `visualizar_mixin` Qt).
- 2026-05-06 (it.3): leva C (JS bridge) fechada — G040, G041, G046, G049, G050 implementados; G042-G045/G047/G048 confirmados como já cobertos pelo JS antigo (Passo 5.1/5.3/5.5). 2 desvios registrados (D001-Ganhos: proxy de DEPOIS; D002-Ganhos: sincronia falta `coplan:obra-active` do Cadastro).
- 2026-05-06 (it.4): leva D fechada — G060 patch (Cadastro emite `coplan:obra-active`, resolve D002), G061 (wrap `serializeForm` injeta `tecnico_dirty='SIM'`), lints G080-G084 OK. **Migração da aba Ganhos completa.**
- A aba Ganhos no web já está bem mais avançada que a Cadastro estava no início (~85% pelos relatos dos audits): backend completíssimo (Passos 5.1-5.6 do HANDOFF), HTML com 3 cards principais, JS com bootstrap por aba ativa.
- Foco do roadmap G001-G084: fechar gaps cirúrgicos em vez de reconstruir do zero.
- Riscos:
  - **Edição inline da tabela (G004)**: pode quebrar UX visual; melhor não fazer no início — confirmar com usuário se vale a pena (desktop tem grade editável; web tem tabela read-only).
  - **Sincronização Cadastro↔Ganhos (G060)**: depende do `coplanCadastro.state.obraEmEdicao` (já existe).
  - **`tecnico_dirty=SIM` (G061)**: a leva 5 da Cadastro registrou D005 (acentos NÃO); confirmar que o backend save_obra já normaliza isso para Ganhos também.
- Pattern do JS: usar IIFE `coplanGanhos` análogo ao `coplanCadastro`. Reaproveitar `coplanReady`, `coplanToast`, `coplanSetTab`, custom events `coplan:tab` e `coplan:obras-changed`.

## Métricas

- Itens totais no roadmap: ~30 (G001..G084, com gaps).
- Itens concluídos: 24 (todas as levas A-D fechadas + lints). Lista: G001, G002, G005, G006, G007, G020, G021, G022, G024, G040-G050, G060, G061, G080-G084.
- Adiados: 2 (G003 depende de JS edit-inline, G004 depende de decisão UX). Recomendação: **manter adiados** se decisão for não dar edição inline na tabela web (paridade visual com mock atual basta para dashboard).
- Migração: **completa.**
