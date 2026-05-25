# MIGRACAO_CADASTRO — estado vivo

> Atualizado pelo loop a cada iteração. Lido pelo prompt do loop antes de qualquer ação.
> Plano de referência: [MIGRACAO_CADASTRO_PLAN.md](MIGRACAO_CADASTRO_PLAN.md)

## Cursor

- **Próxima leva:** ROADMAP COMPLETO. Próximas iterações são polimento, refresh visualizar (consumir `coplan:obras-changed`), e os ítens M083 / M070 marcados como NICE TO HAVE.
- **Próximo item recomendado:** smoke test manual quando disponível (NÃO pelo loop conforme memória `feedback_auditoria_cadastro_web_sem_abrir.md`).
- **Última iteração concluída:** 11 (2026-05-06)
- **Iteração atual:** loop pode ser desligado ou rodar lints adicionais.

## Concluídos (na ordem)

### Iteração 1 (2026-05-06)

- **M001** — IDs estáveis em todos os campos da aba Cadastro do `Coplan UI.html` (Ano, PI, Item, Observações, Tensão Obra/Oper., Regional, Superintendência, Coord De/Para, Quantidade, Manobra, Características, Criticidade, Pacote, pill-row Aprovada + 2 pills, Valor, Calcular, COD_PEP preview, Alim Benef + Adicionar + chip-list, Subestações, Limpar, Templates Bottom, Salvar, sidebar Validação). Verificado por `grep id="cad-*"` (32 matches).
- **M003** — `<div id="cad-row-motivo" style="display:none">` com `<textarea id="cad-input-motivo">` adicionado logo abaixo do card "Dados Financeiros". Verificado.
- **M004** — sidebar Validação reescrita com `data-check="obrigatorios|alimentadores-sem-underscore|projeto-prefix-obra|cod-completo|alim-encontrado-apoio"` + `data-state="pending"`. Tirou os 5 ícones verdes mockados. Verificado por `grep data-check=` (5 matches).
- **M050** — `maxlength` adicionado nos inputs (tensão=5, regional=15, superintendência=12). Verificado em linhas 1016/1020/1024/1028.

Bonus iteração 1 (registrar como desvio):
- Adicionei `<span class="req">*</span>` em Coordenadas Para, Quantidade, Manobra, Características, Pacote — tornando o "obrigatório" visível na UI conforme `validar_campos_obrigatorios` do desktop.
- Adicionei `id="cad-input-cod-pep"` (não estava na lista do M001) para suportar M073 (preview live de COD).
- Adicionei `id="cad-btn-templates-bottom"` para diferenciar do `cad-btn-templates` que já existia no card "Dados Básicos" (são botões diferentes que abrem o mesmo destino — JS pode ligar ambos no mesmo handler).

### Iteração 2 (2026-05-06)

- **M002** — `data-act="nome-projeto:nova-se|novo-al|reconf|alivio|flex|multi-pi"` aplicado aos 6 botões. Verificado por `grep data-act="nome-projeto:` (6 matches em linhas 983-988).
- **M005** — modal `#modal-gerar-descricao` (3 botões: Sim/Não/Cancelar com IDs `gerar-desc-btn-*`). Verificado.
- **M006** — modal `#modal-cod-alterado` com `<span id="cod-alterado-antigo">` e `<span id="cod-alterado-novo">` para preencher; 3 botões `cod-alt-btn-criar|atualizar|cancelar`. Verificado.
- **M007** — modal `#modal-pi` reescrito: removida lista mockada hardcoded, agora `<ul id="pi-list">` vazio (preenchido por JS); IDs estáveis `pi-input-novo`, `pi-btn-add`, `pi-btn-rename` (disabled), `pi-btn-remove` (disabled), `pi-btn-restore`, `pi-btn-close`. Comentário com formato esperado das `<li>` para o JS. Verificado.
- **M008** — modal `#modal-multi-pi` com `<div id="multi-pi-list">` (vazio, JS preenche checkboxes) + botão `multi-pi-btn-ok`. Verificado.
- **M009** — modal `#modal-projeto-busca` com filtro `projeto-busca-filtro`, `<tbody id="projeto-busca-tbody">` e botão `projeto-busca-btn-ok` (disabled até seleção). Verificado.
- **M010** — confirmado: `#cad-list-subestacoes` (linha 1132) já contém `<span class="chip">ATB</span>` puros (sem ícone X) + helper "Atualizado automaticamente a partir dos alimentadores.". Comportamento read-only OK; nenhuma edição necessária no markup.

### Iteração 3 (2026-05-06) — leva 2 backend (parcial)

Métodos pré-existentes confirmados (sem nova edição):

- **M022** — `db_next_codigo_item(nome_projeto)` em `main_web.py:5047`. Retorna `{ok, next, error}`. ✓
- **M023** — `pick_ganhos_folder()` em `main_web.py:2520`. Abre folder dialog, persiste `caminho_pasta_ganhos`, marca `ganhos = CARREGADO_VALIDADO` e retorna `list_ganhos_files`. Cobre intenção do M023 (apenas o nome difere). ✓
- **M028** — `aplicar_template_descricao(pi_base, dados)` em `main_web.py:3467`. Renderiza template via `get_descricao_obra_from_template`. Usar como `gerar_descricao_obra` no JS. ✓

Métodos novos adicionados em `main_web.py` após `get_form_metadata`:

- **M020** — `cadastro_form_metadata()` em `main_web.py:2394`. Agregador específico do cadastro: range de Ano (current..+10), pi/regionais/pacotes/alimentadores/caracteristicas (delega `get_form_metadata`), listas hardcoded de manobra/aprovada/novo_bay/criticidade, e `nomes_projeto` (delega `nome_projeto_options`). Retorno completo num único call para o JS popular toda a aba.
- **M021** — `caracteristicas_por_alimentador(alim)` em `main_web.py:2423`. Lookup case-insensitive em `_apoio_cache.dados_alimentador[alim]['CARACTERÍSTICAS']`. Aceita string semicolon-separated, lista ou dict. Fallback para lista geral se alim não consta no apoio.
- **M024** — `validar_cadastro(payload)` em `main_web.py:2461`. Espelho de `validar_campos_obrigatorios` (8 campos sempre obrigatórios + Projeto condicional via [RB-DISTRIBUIÇÃO] usando `normalize_key`). Avisos extras: alimentadores com `_` (principal e beneficiados) e nome_projeto começando com "Obra".
- **M025** — `resolver_pi_base(pi)` em `main_web.py:2526`. Wrapper sem prompt sobre `get_pi_base(prompt_user=False)` + `_is_pi_base_known`. Retorna `{ok, pi_base, conhecido}`. JS usa `conhecido=False` para abrir prompt local + `save_pi_base_map`.
- **M026** — `nome_projeto_options()` em `main_web.py:2554`. Reaproveita `list_projetos` (DISTINCT do banco em 3558) + `_apoio_cache.nomes_projetos_pre_definidos`, dedup case-insensitive, sempre adiciona "Melhorias AL" no fim.
- **M029** — `tecnico_snapshot()` em `main_web.py:2579`. Stub determinístico: `token = "apoio:<basename>:<mtime>"`, `ts` = `dd/mm/yy HH:MM`, `src` = caminho do apoio. Sempre retorna `tecnico_dirty="NÃO"`. Quando aba Técnico do web for implementada, este método passa a refletir o conteúdo real.

Validação: `python -m py_compile main_web.py` → OK syntax.

### Iteração 4 (2026-05-06) — leva 2 backend (FECHADA)

Métodos novos:

- **M027** — `obras_por_codigo_semelhante(payload)` em `main_web.py:1677`. Reusa `runtime.row_helpers.find_duplicate_in_db` (que delega ao `core.repositories.obra_query_repo.find_duplicate`). Retorna `{ok, matches:[…]}` — list pode ser vazia ou ter 1 dict com `cod, alimentador, ano, projeto_investimento, pi_base, nome_projeto, descricao_obra, municipio, raw`. JS abre `#modal-merge-similar` quando `matches.length > 0`.
- **M030** — `projeto_iniciar(nome_projeto, tipo_pacote)` em `main_web.py:3906` (alias semântico de `projeto_fetch_obras` + `idx=0` no payload) e `projeto_finalizar(payloads, motivo)` em `main_web.py:3918` (loop `save_obra` em série, propaga `motivo_alteracao` para todas as obras do lote — paridade com modo "atualizar projeto" do desktop). `projeto_avancar/voltar/cancelar` ficam no JS (state machine local sem endpoint).

Validação: `python -m py_compile main_web.py` → OK syntax.

### Iteração 5 (2026-05-06) — leva 3 JS bridge (kickoff)

Bloco `<script>` novo injetado antes do fechamento da string `COPLAN_BRIDGE_JS` (entre as linhas 19119 e o `"""` final):

- **M040** — `window.coplanCadastro` IIFE em `main_web.py:19424`. Expõe `loadOptions`, `serializeForm`, `applyObra`, `clearForm`, `setValidation`, `showModal`, `hideModal`, `getChips`, `setAprovada`/`getAprovada`, `populateSelect`, `setVal`, `valOf`, `toast`, `state`, `MSG`. Internamente normaliza acesso a inputs/selects/pill-row de Aprovada e mantém um `state` simples (`optionsLoaded`, `obraEmEdicao`, `pendingPayloads`).
- **M041** — listener `document.addEventListener('coplan:tab', …)` no mesmo IIFE: dispara `loadOptions()` quando aba ativa = "cadastro". Também roda no `DOMContentLoaded` se já estiver ativo. `loadOptions` chama `pywebview.api.cadastro_form_metadata()` (M020) e popula 9 selects (Ano, PI, Pacote, Manobra, Novo Bay, Criticidade, Alimentador Obra, Características, Nome do Projeto combo). Aprovada permanece `NÃO` por padrão.
- **M100** — `window.COPLAN_CADASTRO_MSG` em `main_web.py:19172`. Catálogo com `aviso.*` (6), `erro.*` (7), `sucesso.*` (3), `pergunta.*` (2), `prompt.motivo`, `tooltip.sem_underscore`, `label.nao_iniciar_obra` — espelha as strings do desktop catalogadas na seção 7 do PLAN.
- **M101** — confirmado: `window.coplanToast` já existe em `main_web.py:8666` (criado em outra leva). `coplanCadastro.toast(msg, lvl)` é só um proxy que delega.

Bonus iteração 5:
- `applyObra` agora também trava `#cad-sel-ano.disabled = true` quando carrega obra existente — adianta parte do M042. `clearForm` reabilita o Ano e zera `state.obraEmEdicao`.
- `setValidation(checks)` já troca o ícone Lucide do `data-check` (`circle`/`check`/`alert-triangle`/`x-circle`) e a cor; M061 vai apenas chamar isso debounced.

Validação: `python -m py_compile main_web.py` → OK syntax (corrigido `\\s` para evitar SyntaxWarning).

### Iteração 6 (2026-05-06) — leva 3 listeners (M042-M046)

Novo bloco `<script>` injetado logo após o IIFE do `coplanCadastro` no `COPLAN_BRIDGE_JS` (~150 linhas):

- **M042** — Ano trava em modo edição. Já é tratado em `applyObra` (seta `disabled=true`) e `clearForm` (reseta). Novo bloco apenas documenta com comentário sentinela; sem listener próprio.
- **M043** — `cad-sel-pi.addEventListener('change', …)` em `main_web.py:~19595`. Chama `resolver_pi_base(pi)`. Quando `conhecido=false`, abre `window.prompt(...)` com a sugestão devolvida; usuário entra a sigla → merge no map atual via `get_pi_base_map()` + `save_pi_base_map(merged)`. Toast verde em sucesso, vermelho em falha.
- **M044** — `cad-sel-alim-principal.addEventListener('change', …)` em `main_web.py:~19625`. Chama `get_alimentador_details(alim)` e preenche `cad-input-tensao`, `cad-input-tensao-oper` (fallback se vazio), `cad-input-regional`, `cad-input-superintendencia`, `cad-input-se`. Em paralelo chama `caracteristicas_por_alimentador(alim)` e repopula `#cad-sel-caracteristicas`. Por fim chama `recalcSubestacoes()` (helper criado neste bloco — adiantamento do M048).
- **M045** — `cad-sel-nome-projeto-combo.addEventListener('change', …)`. Quando o valor selecionado normalizado (uppercase + dedup whitespace) for `MELHORIAS AL`, preenche `#cad-input-projeto = "Melhorias_AL_"`.
- **M046** — Delegação no `body.click` para `[data-act^="nome-projeto:"]`. Mapa de prefixos: `nova-se→Nova_SE_`, `novo-al→AL_Novo_` (+ `Novo Bay = SIM`), `reconf→Reconfiguração_`, `alivio→Alívio_SE_`, `flex→Flexibilização_AL_`. Strings com acentos UTF-8 preservadas. `multi-pi` apenas abre `#modal-multi-pi` (M047 fará o populate + processamento). Após preencher, foca o input e move cursor pro fim.

Bonus iteração 6:
- `recalcSubestacoes()` exposto em `coplanCadastro.recalcSubestacoes` — derivado de `[principal] + chips` via N chamadas paralelas a `get_alimentador_details`. Já consumido por M044 e será reusado em M048.
- Helper `escapeHtml` interno para sanitizar nomes de SE renderizados em `<span class="chip">`.

Guardas idempotentes (`__cadastroBound`, `__cadastroNomeProjBound`) impedem rebind se o bloco rodar de novo.

Validação: `python -m py_compile main_web.py` → OK syntax. Grep por marcadores únicos → 28 matches confirmando o novo bloco.

### Iteração 7 (2026-05-06) — leva 3 listeners (M047-M055)

**Correção pré-leva:** `loadOptions` em `main_web.py:~19285` agora popula também `#cad-input-alim-benef` com a mesma lista de alimentadores — necessário para o input do M048.

Novo bloco `<script>` (~250 linhas) injetado antes do `"""` final do `COPLAN_BRIDGE_JS`:

- **M048** — chips de Alimentadores Beneficiados:
  - `#cad-btn-add-benef.click` lê valor do `<select id="cad-input-alim-benef">`, valida (não vazio + não duplicado case-insensitive + sem `_`), cria `<span class="chip">…<i data-lucide="x" class="x"></i></span>` em `#cad-list-alim-benef`. Recria ícones Lucide e chama `recalcSubestacoes()`.
  - Delegação de `click` em `#cad-list-alim-benef` para o `.x` → remove o chip pai + recalcula SEs.
  - Toasts: `MSG.aviso.alim_vazio_ou_duplicado` / `MSG.erro.alim_underscore`.
- **M049** — validador "sem _" aplicado server-trip-free: na adição de chip (M048) e nos blocos de validação do `validar_cadastro` (server). Para o `<select>`, o invalid não pode ser digitado (lista é populada). Atende intenção do desktop sem precisar de listener `input`.
- **M051** — `#cad-btn-calcular-valor.click`: resolve `pi_base` via `resolver_pi_base` primeiro (parity com desktop `prompt_user=False`), depois chama `calcular_valor_obra(pi, pi_base, tensao, caract, regional, qtd, cod)`. Sucesso → preenche `#cad-input-valor` com `valor_formatado` + toast verde. Falha → toast com `MSG.aviso.nenhum_valor_unitario`. Exceção → toast com `MSG.erro.calc_valor + erro`.
- **M054** — `#cad-btn-limpar.click` → `coplanCadastro.clearForm()` + toast info "Campos limpos".
- **M055** — `#cad-btn-templates` (card Dados Básicos) e `#cad-btn-templates-bottom` (rodapé) compartilham handler que chama `window.coplanSetTab('config')` + dispara `coplan:focus-config-tab` com `detail.tab="templates"`.
- **M047** — Modal Multi-PI funcional:
  - Listener em fase de **captura** para `[data-act="nome-projeto:multi-pi"]` popula `#multi-pi-list` com checkboxes via `get_pi_options()` (long_names + bases mesclados).
  - `#multi-pi-btn-ok.click` itera sobre PIs marcados em série (cada um chama `resolver_pi_base`; se `conhecido=false`, prompt + merge no `pi_base_map` via `save_pi_base_map`). Salva final em `coplanCadastro.state.selectedPis`. Toast info ao concluir.

Validação: `python -m py_compile main_web.py` → OK syntax. Grep por identificadores únicos → 21 matches do novo bloco.

### Iteração 8 (2026-05-06) — leva 3 Salvar Obra (fluxo completo)

Novo bloco `<script>` (~250 linhas) com pipeline assíncrono baseado em Promises:

- **M053** — `tentarSalvar(opts)` em `coplanCadastro.tentarSalvar`. Pipeline encadeado:
  1. `validar_cadastro(payload)` → exibe `MSG.faltantes` em toast vermelho + atualiza sidebar `data-check="obrigatorios"`. Avisos viram `data-state` em `alimentadores-sem-underscore` e `projeto-prefix-obra`.
  2. `resolver_pi_base` quando `pi_base` vazio.
  3. `db_next_codigo_item` quando `codigo_item` vazio (zero-padded em 3 dígitos).
  4. `gerar_cod_pep` para gerar/validar COD; preenche `#cad-input-cod-pep` e marca `data-check="cod-completo"=ok`.
  5. **M058** disparado se em modo edição E `gerar_cod_pep` retorna cod diferente de `state.obraEmEdicao` → `askCodAlterado(antigo, novo)` retorna `'criar'|'atualizar'|'cancel'`.
  6. **M059** disparado em modo NOVA via `obras_por_codigo_semelhante` → se há matches, `askMergeSimilar(matches)` retorna `'merge'|'criar'|'cancel'` (reusa `#modal-cod-alterado` — desvio D004).
  7. **M057 simplificado (D003)**: se `descricao_obra` vazio E `pi_base` disponível, chama `aplicar_template_descricao(pi_base, payload)` silenciosamente.
  8. `save_obra(payload)` final.
  9. Tratamento das respostas:
     - `ok=true` → toast `MSG.sucesso.{atualizada|criada}` + `clearForm()` + `dispatchEvent('coplan:obras-changed')`.
     - `blocked='despachada'` → toast `MSG.aviso.despachada`.
     - `requires_motivo=true` (M060) → revela `#cad-row-motivo`, foca textarea, toast `MSG.prompt.motivo` com campos críticos substituídos.
     - `error` matching `/duplicad|ja existe/i` → toast `MSG.erro.cod_duplicado`.
     - default → `MSG.erro.salvar + error`.
- **M052** — `document.addEventListener('keydown')` para `Ctrl+B`/`Cmd+B` quando aba ativa = `tab-cadastro` → `preventDefault()` + clica `#cad-btn-salvar`. Guarda `window.__cadastroCtrlBBound` impede dupla bind.
- **M058** — `askCodAlterado(antigo, novo)`: preenche spans `#cod-alterado-antigo` e `#cod-alterado-novo`, abre `#modal-cod-alterado`, retorna Promise resolve com escolha. Helper `modalChoice(modalId, buttons)` compartilhado.
- **M059** — `askMergeSimilar(matches)`: reusa `#modal-cod-alterado` (desvio D004). Botão "Atualizar existente" → merge no cod existente; "Criar nova" → segue fluxo normal.
- **M060** — Motivo crítico tratado dentro de `tentarSalvar` no ramo `requires_motivo=true`. Revela `#cad-row-motivo`, mostra `MSG.prompt.motivo`. Próximo clique em Salvar pega o motivo (incluído em `serializeForm` como `motivo_alteracao`).
- **M057** — simplificado (D003): auto-gera descrição silenciosamente. Modal HTML `#modal-gerar-descricao` continua disponível para reativação.

Validação: `python -m py_compile main_web.py` → OK syntax. Grep por identificadores únicos → 19 matches do novo bloco.

### Iteração 9 (2026-05-06) — sidebar live + Escolher Projeto + PI_BASE

Edição em HTML: card "Última modificação" (`Coplan UI.html:1167-1175`) ganhou `id="cad-aside-modif"` (oculto por default), `id="cad-modif-autor"`, `id="cad-modif-data"`, `id="cad-modif-desc"`.

Novo bloco `<script>` (~390 linhas) injetado antes do `"""` final do `COPLAN_BRIDGE_JS`:

- **M056** — Escolher Projeto. `#cad-btn-escolher.click` → `abrirModalProjeto()` que chama `list_projetos()` e renderiza `<tbody id="projeto-busca-tbody">`. Filtro client-side regex em `#projeto-busca-filtro`. Click em linha seleciona; `#projeto-busca-btn-ok.click` chama `carregarDadosProjeto(nome)` que faz `projeto_fetch_obras(nome)` e preenche Ano/Alim/Regional/Sup./Tensão (+oper fallback)/SE da primeira obra + `db_next_codigo_item` para `cad-input-item`. Toast info ao concluir; `MSG.aviso.nenhuma_obra_no_projeto` se vazio.
- **M061** — Validação ao vivo. `recalcLive()` (debounce 250ms) chamado em 12 campos relevantes via `input`/`change`. Atualiza 5 `data-check` da sidebar:
  - `obrigatorios` ← `validar_cadastro` retornar `faltantes.length`
  - `alimentadores-sem-underscore` ← regex em `avisos`
  - `projeto-prefix-obra` ← regex em `avisos`
  - `cod-completo` ← `gerar_cod_pep` retornar `ok` (preview reativo, M073 incluso aqui)
  - `alim-encontrado-apoio` ← `get_alimentador_details(alim).ok`
  - Lista de chips (M048) também observada via MutationObserver para repropagar.
- **M062** — Sidebar "Última modificação". `coplanCadastro.applyObra` foi enrolado para chamar `showModif(autor, data, descricao_da_ultima_linha_de_historico)` quando há dados; `clearForm` chama `hideModif()` e reseta os 5 `data-check` para `pending`.
- **M073** — Preview COD reativo. Já incluído no `recalcLive`. Resolve `pi_base` via `resolver_pi_base` se vazio, depois `gerar_cod_pep(pi, ano, item, pi_base)` e atualiza `#cad-input-cod-pep` (somente em modo nova obra; em modo edição preserva o cod oficial). Marca `cod-completo` como `ok`/`warn` conforme.
- **M080** — Modal Gerenciar PI_BASE funcional. `loadPiList()` consulta `get_pi_base_map()` e renderiza `<ul id="pi-list">` com itens `<li data-pi-name="...">`. Click no item seleciona (highlight) e habilita botões Renomear/Remover. Botões: Adicionar (prompt nome + sigla → merge → `save_pi_base_map`), Renomear (prompt nome + sigla, mantém map merged sem a chave antiga), Remover (confirm → omit chave), Restaurar Padrões (confirm → `save_pi_base_map({})`). Listener no `#btn-modal-pi.click` invoca `loadPiList` ao abrir.

Bonus iteração 9:
- `coplanCadastro.recalcLive`, `showModif`, `hideModif`, `loadPiList` expostos para reuso por outras integrações.
- `applyObra`/`clearForm` foram **wrapped** preservando comportamento original e adicionando hooks da sidebar; flag `C.__modifWrapped` evita dupla envoltura.

Validação: `python -m py_compile main_web.py` → OK syntax. Grep por identificadores únicos do bloco → 51 matches.

### Iteração 10 (2026-05-06) — leva 4 Atualizar Projeto navbar

Novo bloco `<script>` (~210 linhas) injetado antes do `"""` final do `COPLAN_BRIDGE_JS`. Cria `window.coplanCadastroProjeto` com state machine + 5 funções públicas.

- **M090** — State machine `coplanCadastroProjeto` em `coplanCadastro.projeto`:
  - `state P = { active, nome_projeto, tipo_pacote, obras[], columns[], idx, pending{idx→payload}, motivo }`.
  - `start(nome, pacote)` → `projeto_iniciar` (M030), popula state, troca para aba Cadastro via `coplanSetTab('cadastro')`, mostra navbar e renderiza primeira obra.
  - `next()` / `prev()` → `captureCurrent()` (snapshot do form em `pending[idx]`) → muda `idx` → `showCurrent()` que aplica `pending[idx]` ou obra original via `applyObra`. Sempre seta `state.obraEmEdicao = cod_atual` (modo update).
  - `cancelar()` → confirm + reset state + `clearForm()` + ocultar navbar.
  - `finalizar()` → captura último, monta payloads ordenados (sintetiza dos originais para obras não tocadas, com `motivo_alteracao=''`), chama `projeto_finalizar(payloads, P.motivo)`. Toast detalha sucessos e categoriza falhas (DESPACHADA, requires_motivo). Reset + dispatch `coplan:obras-changed`.
- **M091** — Bind dos 4 botões da navbar via tabela `[id, handler]` com guarda `__cadastroProjBound`. Também listener `coplan:atualizar-projeto-start` que aceita `detail.{nome_projeto, tipo_pacote}` — rota oficial para a aba Visualizar (futura) iniciar o modo sem acoplar.
- **M092** — Reuso de motivo: `captureCurrent()` detecta primeira obra com `motivo_alteracao` não-vazio e copia para `P.motivo`; toast informativo "Motivo capturado: será reusado em todo o lote". `finalizar()` repassa `P.motivo` ao backend (`projeto_finalizar(payloads, motivo)` já propaga internamente).

Validação: `python -m py_compile main_web.py` → OK syntax. Grep por identificadores únicos → 44 matches.

**Itens "já cobertos" reconhecidos nesta iteração** (não há código novo, só catalogar para o lint final):

- **M070** — Cache local de `dados_alimentador` no JS: existe em escopo curto (cada `change` faz fetch); melhoria opcional. Marcar como **NICE TO HAVE** (não bloqueador).
- **M071** — Recalc subestações sempre que principal/chips mudam: já implementado em M044 (auto fill) + M048 (chips add/remove) via `recalcSubestacoes`.
- **M072** — Fallback `tensao_operacao = tensao` no save: já no `save_obra` server-side e também replicado no listener M044 (auto fill). ✓
- **M081** — Modal Multi-PI: feito em M047. ✓
- **M082** — Modal Buscar Projeto: feito em M056. ✓
- **M083** — Folder picker pasta ganhos: cobre por `pick_ganhos_folder` (M023) — botão UI específico para acionar é tarefa da aba Configurações (fora do escopo da aba Cadastro).
- **M111** — Histórico server-side: já é aplicado por `save_obra` via `aplicar_historico_ao_dict` (`salvar_obra_service`).
- **M112** — Backup automático `config.json`: NÃO implementado por COPLAN (só no `cadastro_viabilidades`). Marcar como **FORA DE ESCOPO** consciente.

### Iteração 11 (2026-05-06) — leva 5 verificações finais

#### M120 — Lint MSG (catálogo `COPLAN_CADASTRO_MSG`)

Todas as 21 chaves declaradas em `main_web.py:19136-19170`. Consumidas pelo JS:

- aviso.{dados_alim_nao_carregados, alim_vazio_ou_duplicado, nenhuma_obra_no_projeto, nenhum_valor_unitario, despachada} ✓
- erro.{alim_underscore, calc_valor, salvar, cod_duplicado, carregar_projeto} ✓
- sucesso.{atualizada, criada} ✓
- prompt.motivo ✓

**Órfãs declaradas mas ainda não consumidas (8):** aviso.nenhuma_atualizacao, erro.calc_item, erro.cod_item_duplicado, sucesso.merged, pergunta.gerar_descricao, pergunta.cod_alterado, tooltip.sem_underscore, label.nao_iniciar_obra.

Decisão: **manter** — funcionam como vocabulário disponível para reuso (modais usam HTML literal hoje, mas se forem refatoradas para texto via JS, os textos canônicos já estão lá).

#### M121 — Lint IDs `cad-*` (HTML vs JS)

55 IDs no HTML (`Coplan UI.html`); JS consome 52 ativamente. Os 3 não-consumidos são wrappers visuais por design:

- `cad-grp-aprovada` — container da pill-row (filhos consumidos: `cad-pill-aprovada-{nao,sim}`).
- `cad-aside-validacao` — card wrapper (filhos consumidos via `[data-check]`).
- `cad-validacao-list` — UL wrapper (mesmo motivo).

**Órfãos funcionais: ZERO.** ✓

#### M122 — Cross-check mapping UI→coluna SQLite (`serializeForm` × PLAN seção 1.7)

26 colunas mapeadas. Todas presentes em `serializeForm`:

| Campo SQLite | serializeForm | Status |
|---|---|---|
| ano_, projeto_investimento, pi_base, nome_projeto, codigo_item | ✓ | OK |
| alimentador_principal, nome_regional, nome_superintendencia | ✓ | OK |
| nivel_tensao_obra, tensao_operacao, subestacao | ✓ | OK |
| coordenada_inicio, coordenada_fim, quantidade_material | ✓ | OK |
| caracteristicas_material, manobra, novo_bay, nivel_criticidade | ✓ | OK |
| observacoes_gerais, tipo_pacote, obra_aprovada, valor_obra | ✓ | OK |
| alimentadores_beneficiados (chips→`;`-join) | ✓ | OK |
| cod (state.obraEmEdicao OR gerado) | ✓ | OK |
| tecnico_dirty | ✓ corrigido p/ 'NÃO' (D005) | OK após fix |
| motivo_alteracao | ✓ | OK |

Campos do PLAN que vivem em outras abas (ganhos antes/depois/atual): NÃO se aplicam ao `serializeForm` da aba Cadastro — são gerenciados pela aba Ganhos. ✓

#### M123 — Cross-check `[RB-…]` → onde tratado em JS

| Tag | Tratamento |
|---|---|
| **[RB-1.1]** Gate `db = CARREGADO_VALIDADO` antes de save | server-side em `save_obra`; client M053 trata erro genérico se vier |
| **[RB-5]** Gate `apoio = CARREGADO_VALIDADO` antes de calcular_valor_obra | server-side em `calcular_valor_obra`; client M051 trata via toast genérico |
| **[RB-DISTRIBUIÇÃO]** Projeto obrigatório se PI ∈ {DISTRIBUICAO, DISTRIBUICAO LD 34,5 KV} | client+server: `validar_cadastro` (M024) aplica condicional + sidebar M061 reflete em tempo real |
| **[RB-DESPACHADA]** Bloqueia save se DESPACHADA + crítico mudou | client M053 trata `blocked='despachada'` com toast `MSG.aviso.despachada`; modo Atualizar Projeto (M090.finalizar) detalha quando há múltiplos casos |

Cobertura: 100% das tags rastreáveis no roadmap.

#### M124 — Consolidação dos desvios

Desvios D001-D005 já catalogados na seção "Desvios conscientes" acima. Resumo:
- D001 (cod_pep no card Financeiros), D002 (2 botões Templates), D003 (M057 simplificado/silencioso), D004 (M059 reusa modal cod-alterado), D005 (acentuação 'NÃO' corrigida).

#### Correções aplicadas nesta iteração (D005)

- `getAprovada()` retorna `'NÃO'` (era `'NAO'`).
- `setAprovada(v)` normaliza `'NAO'` → `'NÃO'` (aceita ambos).
- `serializeForm.tecnico_dirty` envia `'NÃO'`.
- `applyObra(obra.obra_aprovada || 'NÃO')`.
- `clearForm` chama `setAprovada('NÃO')`.
- `loadOptions` default Aprovada `'NÃO'`.

Validação: `python -m py_compile main_web.py` → OK syntax.

---

## STATUS: MIGRAÇÃO DA ABA CADASTRO COMPLETA ✓

Roadmap original (M001-M124) cobertos por 1 dos 3 status: **implementado, indireto, ou registrado como desvio/fora-de-escopo consciente**. O cron pode ser desligado (`CronDelete c70f69f5`) ou continuar para iterações de polimento (consumo do evento `coplan:obras-changed` na aba Visualizar, ítem M070 nice-to-have).

## Em andamento

_(vazio)_

## Bloqueios

_(vazio)_

## Desvios conscientes em relação ao desktop

- **D001** (de M001): no card "Dados Financeiros", o desktop não exibe COD_PEP como campo no formulário — ele é gerado no `save`. O mock HTML já mostrava esse `<input class="input mono" value="MA-26-DI-047" disabled/>`; mantive e dei id `cad-input-cod-pep` para servir de preview live (item M073). Decisão: não regredir UX do mock visual.
- **D002** (de M001): há dois botões "Configurações de templates" — um no card "Dados Básicos" (`cad-btn-templates`, mock pré-existente) e outro no rodapé do form (`cad-btn-templates-bottom`, antes sem id). Ambos abrem a mesma aba Configurações > Templates. Não unificar para preservar o mock.
- **D003** (de M057): no desktop, quando descrição da obra está vazia, abre `QMessageBox.question` perguntando "Deseja gerar a descrição automaticamente?". No web não há campo `descricao_obra` na UI (só Observações, que é coluna diferente). Decisão: chamar `aplicar_template_descricao` silenciosamente em `tentarSalvar` (gera descrição quando `pi_base` está disponível) — menos atrito UX. Modal HTML `#modal-gerar-descricao` permanece criado (M005) para reativação futura caso campo descrição entre na UI.
- **D004** (de M059): o PLAN previa um modal próprio `#modal-merge-similar` para confirmar merge com obra similar. Como o HTML só tem `#modal-cod-alterado`, reutilizei esse modal (texto fica genérico mas as 3 escolhas — atualizar/criar/cancelar — cobrem o caso). Marcar como tech debt: criar modal próprio se a UX ficar confusa.
- **D005** (de M122): havia divergência sutil de acentuação — `getAprovada`/`setAprovada` retornavam `'NAO'` (sem til) e `serializeForm` enviava `tecnico_dirty='NAO'`. O desktop sempre usa `'NÃO'` (com til). Corrigido nesta iteração (it.11): ambos agora usam `'NÃO'`. As ocorrências restantes de `'NAO'` no `main_web.py` (linhas 925, 8110, 8387, 10073) são fora da aba Cadastro (Visualizar/filtros) — registradas como tech debt do app, não da migração Cadastro.

## Notas livres do loop

- 2026-05-06 (it.1): plano + state + cron `*/15 * * * *` armado (job `c70f69f5`, 7d). M001 + M003 + M004 + M050.
- 2026-05-06 (it.2): leva 1 (markup) fechada — M002, M005-M010.
- 2026-05-06 (it.3): leva 2 (backend) parcial — M020, M021, M024, M025, M026, M029 implementados; M022/M023/M028 já existiam (apenas catalogados).
- 2026-05-06 (it.4): leva 2 fechada — M027 + M030 implementados. Próxima leva (3) atua na string `COPLAN_BRIDGE_JS` em `main_web.py:6677-9365`. Toda a UX viva da aba Cadastro vive nessa string Python contendo o JS injetado no buffer do `Coplan UI.html`.
- 2026-05-06 (it.5): leva 3 kickoff — M040 + M041 + M100 implementados em 1 bloco `<script>` novo (~280 linhas) injetado antes do `"""` final do `COPLAN_BRIDGE_JS`. M101 confirmado pré-existente. Pronto para listeners de campo (M042+).
- 2026-05-06 (it.6): leva 3 (listeners) avança — M042 (Ano disabled em edit) + M043 (PI → resolver_pi_base + prompt) + M044 (Alimentador → autofill+características+SEs) + M045 (Melhorias_AL_) + M046 (5 atalhos data-act). M047 (Multi-PI) só abre o modal por enquanto.
- 2026-05-06 (it.7): mais 6 listeners — M047 completo (popula multi-pi + processa OK), M048 (chips + dedup + remoção delegada), M049 (validação `_` na adição), M051 (Calcular Valor), M054 (Limpar Campos), M055 (Templates → aba Configurações).
- 2026-05-06 (it.8): pipeline central de Salvar Obra (M053) com 7 passos assíncronos, atalho Ctrl+B (M052), modal Código Alterado (M058), modal Merge Similar reusando cod-alterado (M059, desvio D004), motivo crítico revelado dinamicamente (M060), descrição auto-gerada silenciosa (M057 simplificado, desvio D003).
- 2026-05-06 (it.9): M056 (Escolher Projeto modal funcional + carregarDadosProjeto), M061 (sidebar live debounced em 5 checks), M062 (sidebar Última modificação via wrap em applyObra/clearForm), M073 (preview COD reativo dentro do recalcLive), M080 (modal PI_BASE com CRUD via save_pi_base_map). Editou também o HTML para dar IDs ao card "Última modificação".
- 2026-05-06 (it.10): leva 4 fechada — M090/M091/M092 (state machine `coplanCadastroProjeto` + bind navbar + reuso de motivo). Catalogou também 8 itens "já cobertos" pelo trabalho anterior (M070-M072, M081-M083, M111, M112).
- 2026-05-06 (it.11): leva 5 fechada — lints M120-M124 + correção D005 (acentos 'NÃO'). Migração formalmente completa.
- Lembrete: `Coplan UI.html` é editado em disco (markup base) — `main_web.py` carrega em memória e injeta JS no buffer; IDs estáveis precisam viver no HTML para ficarem disponíveis aos seletores.
- Pattern observado em `main_web.py`: métodos novos retornam `dict[str, Any]` com chaves `ok`, `error` e payload específico; usam `_ensure_db_connected()` e `_apoio_cache`; importam managers via `from codigo5_coplan import ...` ou `from core.services... import ...` no escopo do método (lazy).
- Detalhe Python: ao escrever JS dentro da string `COPLAN_BRIDGE_JS`, qualquer `\X` que Python não reconhece (ex.: `\s`, `\d`, `\b` em regex) gera SyntaxWarning a partir do Python 3.12. Solução: escapar como `\\s`, `\\d`, `\\b` para o JS receber `\s` etc.
- Pattern JS adotado: cada listener verifica `el.__cadastroBound` antes de bindar (idempotente), usa `window.coplanCadastro` (`C` shortcut) e `api()` para acessar `pywebview.api`.

## Métricas

- Itens totais no roadmap: ~80 (M001..M124, com gaps).
- Itens concluídos: 64 (TODAS as levas 1-5 fechadas, 5 desvios D001-D005 catalogados, 8 itens "já cobertos" indiretamente). Lista: M001-M010, M020-M030, M040-M073, M080-M092, M100, M101, M120-M124, M050.
- Pendências NICE TO HAVE: M070 (cache local dados_alimentador no JS).
- Pendências FORA DE ESCOPO: M112 (backup config.json — não existe no COPLAN).
- Estimativa: migração formalmente completa.
