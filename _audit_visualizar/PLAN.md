# Auditoria EXAUSTIVA — Aba Visualizar (COPLAN)

**Data:** 2026-05-05
**Escopo:** Tudo que existe na aba Visualizar do desktop (`ui/main_window/visualizar_mixin.py`, `visualizar_colunas_mixin.py`, `filtros_paginacao_mixin.py`) versus o que está no web (`main_web.py` + `Coplan UI.html` `#tab-visualizar`).

Status: ✅ ok / ⚠️ parcial / ❌ ausente / 🐛 quebrado

---

## A. Top actions (linha superior)

| # | Feature desktop | API Web | UI Web | Status | Gap |
|---|---|---|---|---|---|
| A1 | Botão "Carregar Banco e Apoio" (`_on_load_db_and_apoio_clicked`) | `header_connect_db` + `pick_and_load_apoio` | Botão na header global, não no tab-visualizar | ⚠️ | Falta botão no toolbar da Visualizar |
| A2 | Botão "⚙ Colunas" (`show_visualizar_columns_dialog`) | `visualizar_columns_get_config` / `_save_config` / `_reset` | `coplan-btn-config-cols` injetado | ✅ | Verificar drag-drop reorder funcional |

---

## B. Filtros — barra de inputs

**Desktop:** 12 inputs individuais (linha de filtros) + botão "Filtros…" + busca global + botão "Limpar".

| # | Filtro | Coluna DB | Web | Status |
|---|---|---|---|---|
| B1 | filter_cod (`;` multi) | `cod` | modal-filtros | ✅ |
| B2 | filter_ano (`;` multi) | `ano_` | modal-filtros (select multiple) | ✅ |
| B3 | filter_pi (`;` multi) | `projeto_investimento` | modal-filtros | ✅ |
| B4 | filter_nome_projeto (`;` multi) | `nome_projeto` | modal-filtros | ✅ |
| B5 | filter_alimentador (`;` multi) | `alimentador_principal` | modal-filtros | ✅ |
| B6 | filter_alimentadores_benef (`;` multi) | `alimentadores_beneficiados` | modal-filtros | ⚠️ verificar |
| B7 | filter_regional (`;` multi) | `nome_regional` | modal-filtros (select multiple) | ✅ |
| B8 | filter_superintendencia | `nome_superintendencia` | modal-filtros | ✅ |
| B9 | filter_subestacao | `subestacao` | modal-filtros | ✅ |
| B10 | filter_pacote (`;` multi) | `tipo_pacote` | modal-filtros + `coplan-btn-pkg` | ⚠️ duplicado |
| B11 | filter_tecnico_dirty (SIM/NÃO) | `tecnico_dirty` | modal-filtros (select) | ✅ |
| B12 | filter_global (busca inteligente, `;` multi) | TODAS | `.search-input input` | ✅ |
| B13 | btn_limpar_filtros | — | "Limpar" na filter-bar | ✅ |
| B14 | filter_feedback (label "X resultados / Y filtros") | — | `.badge` "X resultados · Y selecionadas" | ✅ |
| B15 | show_filter_dialog (modal aplicar/cancelar) | — | `#modal-filtros` | ✅ |
| B16 | shortcut Ctrl+L / Ctrl+F (focus busca) | — | Ctrl+F | ⚠️ falta Ctrl+L |
| B17 | shortcut Esc (clear) | — | Esc | ✅ |
| B18 | filter_chips removíveis (chips ativos) | — | `.filter-chip` | ⚠️ mock visual; verificar removal binding |
| B19 | "Tecnico Atualizado": valor confuso (filter SIM mostra `tecnico_dirty=NÃO`) | `tecnico_dirty` invertido | precisa verificar | ⚠️ |

---

## C. Tabela `table_obras` (VisibleRowTableWidget)

| # | Feature desktop | Web | Status |
|---|---|---|---|
| C1 | readonly NoEditTriggers | `<input>` por célula? Verificar | ⚠️ |
| C2 | SelectionBehavior=Items, Mode=Extended | row click + checkboxes | ⚠️ comportamento diferente |
| C3 | NoDragDrop | — | ✅ |
| C4 | customContextMenuRequested → mostrar_menu_linha | right-click → menu (Pass 11) | ✅ |
| C5 | doubleClicked → _on_visualizar_double_click (abre Cadastro / Atualizar Projeto) | Verificar binding | ⚠️ |
| C6 | shortcut Ctrl+C (copy_to_clipboard de seleção) | Botão "Copiar" injetado | ⚠️ falta atalho Ctrl+C |
| C7 | header.customContextMenuRequested → mostrar_menu_cabecalho ("Recolher") | right-click cabeçalho → recolhe direto | ⚠️ falta menu real |
| C8 | header.sectionResized → persist widths em config.ui_state.visualizar.column_widths | Não rastreado | ❌ |
| C9 | apply_visualizar_columns_config (carrega widths + visible no boot) | Carrega visible/order; widths não aplicados | ⚠️ |
| C10 | Cor da linha condicional: vermelho (não atendeu) / preto (atendeu) / **cinza (None=indef)** | Vermelho/preto via `.failed`; **falta cinza** | 🐛 |

---

## D. Paginação

| # | Feature desktop | Web | Status |
|---|---|---|---|
| D1 | btn_prev_page / btn_next_page | `.page-btns` prev/next | ✅ |
| D2 | pagination_label "Página X/Y de N items" | `.mono` "X / Y" | ⚠️ falta total de itens |
| D3 | page_size_combo [100,300,500,1000] | `<select>` em `.pagination` | ✅ |
| D4 | _go_to_previous_page / _go_to_next_page | `coplanPage--/++` | ✅ |
| D5 | shortcut PageUp/PageDown navegando páginas | ✅ | ✅ |
| D6 | format_pagination_label de `visualizar_pagination.py` (compartilhado) | JS próprio | ⚠️ não reutiliza algoritmo |
| D7 | Botões disabled em borda | Habilitação visual via opacity | ✅ |
| D8 | Reset auto para página 1 ao filtrar | `resetToFirstPage()` | ✅ |

---

## E. Footer com botões de ação (10 botões + 1 chk)

| # | Botão desktop | Handler | Web | Status |
|---|---|---|---|---|
| E1 | "Atualizar Obras" | `atualizar_obras` | "Atualizar" + `atualizar_obras_valores` | ✅ |
| E2 | "Excluir Obras Selecionadas" | `delete_selected_obras` | "Excluir" + gating aprovadas (Pass 2) | ✅ |
| E3 | "Detalhamento de obras" | `gerar_detalhamento` | "Detalhamento" + `export_detalhamento` | ✅ |
| E4 | "Marcar como CORREÇÃO" | `marcar_obras_correcao` | `coplan-btn-correcao` | ✅ |
| E5 | "Salvar Banco de Dados" | `salvar_banco_dados` | API `db_save_as` ok, **falta botão UI** | ❌ |
| E6 | "Exportar para Banco" | `exportar_para_banco` | API `db_export_to` ok, **falta botão UI** | ❌ |
| E7 | "Atualizar Plano de Obras" | `abrir_dialogo_plano` | `coplan-btn-plano-obras` | ✅ |
| E8 | "Gerar nota de Colapso" | `gerar_nota_colapso_excel` | "Nota de Colapso" + `export_nota_colapso` | ✅ |
| E9 | "Exportar Relatório de Critérios" | `exportar_relatorio_criterios_excel` | "Relatório Critérios" + `export_relatorio_criterios` | ✅ |
| E10 | "Cancelar Atualização do Plano" (hidden quando inativo) | `cancelar_atualizacao_plano_obras` | `coplan-btn-plano-cancel` | ✅ |
| E11 | chk_incluir_aprovadas (checkbox) | controla _gate_aprovadas | **NÃO existe**; gating sempre pergunta excepcional | ❌ |

---

## F. Lógica/regras de negócio (RB)

| # | Feature desktop | Web | Status |
|---|---|---|---|
| F1 | choose_packages (auto-prompt na 1ª conexão) | `coplan-btn-pkg` manual; sem auto-prompt | ⚠️ |
| F2 | populate_combo_nome_projeto (sync com obras) | Cadastro tem `cad-input-projeto` mas combo não popula com nomes existentes | ❌ |
| F3 | verificar_criterios_planejamento_v2 (avaliação de cor/passou) | `passou_per_row` flag em list_obras | ✅ |
| F4 | _build_criterios_persistencia_updates (persist `criterios_status`) | `criterios_persistir_status` | ✅ |
| F5 | _gate_aprovadas_for_action | `gate_aprovadas_for_action` | ✅ |
| F6 | _confirmar_exclusao_excepcional + _registrar_exclusao_excepcional (auditoria) | `register_exclusao_excepcional` | ✅ |
| F7 | _filtrar_ids_por_anos (backend filter) | Filtro do banco via search_obras | ⚠️ verificar |
| F8 | _filtrar_ids_por_aprovacao | gate_aprovadas + JS filter | ⚠️ |
| F9 | _mark_db_refresh_point | `db_mark_refresh_point` | ✅ |
| F10 | _warn_external_db_update (toast quando outro user grava) | `db_check_external_update` polling 30s | ✅ |
| F11 | update_tecnico_dirty_indicator (DIRTY count) | chip Técnico mostra DIRTY (X) | ✅ |
| F12 | atualizar_snapshot_tecnico_selecionados | `tecnico_snapshot_update` | ✅ |
| F13 | aplicar_atualizacao_plano + blocked_rows (ações bloqueadas em linha cinza) | Pinta linhas; **NÃO bloqueia ações** | 🐛 |
| F14 | _on_visualizar_double_click → abre Cadastro Editar / Atualizar Projeto | Existe? Verificar | ⚠️ |
| F15 | abrir_editar_obra (do menu Linha) | `coplanLoadObraIntoForm(cod)` | ✅ |
| F16 | iniciar_atualizacao_projeto / prev/next/finalizar/cancelar | **NÃO portado** (fluxo navegacional) | ❌ |

---

## G. Stats / KPI

| # | Card desktop | Web | Status |
|---|---|---|---|
| G1 | "Obras no banco" total | `.stat` 1 + `get_obras_stats.total` | ✅ |
| G2 | "Aprovadas" count + % | `.stat` 2 + `aprovadas` | ✅ |
| G3 | "Em análise / pendentes" + delta | `.stat` 3 + `pendentes` | ✅ |
| G4 | "Valor planejado" R$ XM | `.stat` 4 + `valor_total` | ✅ |
| G5 | Stats reagem a filtros aplicados | Verificar reload em search_obras | ⚠️ |

---

## H. Visual / formatação

| # | Feature desktop | Web | Status |
|---|---|---|---|
| H1 | Texto cinza para `atende=None` | Falta cor cinza | 🐛 |
| H2 | Linhas plano_obras: cinza claro / verde claro / sem cor | `.plano-cinza` / `.plano-verde` via inline-style | ✅ |
| H3 | Badges de Pacote com cor | `pacoteBadge()` mapeia cor por pacote | ✅ |
| H4 | Formato R$ pt-BR | `fmtNum` com `pt-BR` | ✅ |
| H5 | Ícone "Téc. Atual" (✓ verde / ⚠ laranja) | Render condicional | ✅ |
| H6 | resizeColumnsToContents após render | CSS `min-width:300px` em Projeto | ⚠️ não dinâmico |
| H7 | Legend "🔴 Não atendeu / ⚫ Atendeu" | `.legend-dot danger` + `text` | ✅ (faltando 🟡 indef) |

---

## I. Atalhos

| # | Atalho | Desktop | Web | Status |
|---|---|---|---|---|
| I1 | Ctrl+F (focus busca) | ✅ | ✅ | ✅ |
| I2 | Ctrl+L (focus busca) | ✅ | ❌ | ❌ |
| I3 | Esc (clear busca) | ✅ | ✅ | ✅ |
| I4 | Ctrl+C (copy seleção) | ✅ via shortcut | ❌ falta atalho (só botão) | ❌ |
| I5 | PageUp/PageDown | — | ✅ | ✅ extra |
| I6 | Ctrl+1 / Ctrl+2... (trocar abas) | — | ✅ | ✅ extra |

---

## J. Eventos / variáveis globais

| Item | Status |
|---|---|
| `window.coplanObras*` (raw, columns, passou) | ✅ |
| `window.coplanFilters` | ✅ |
| `window.coplanPage`/Size | ✅ |
| `window.coplanLoadObras()` | ✅ |
| `window.coplanApplySearch()` | ✅ |
| `coplan:obras` event | ✅ |
| `coplan:tab` event | ✅ |
| `coplanGetSelectedCods()` | ⚠️ existência dependente |

---

## RESUMO CONSOLIDADO DE GAPS (priorizado)

### 🐛 BUGS (quebrados — impacto alto, prioridade 1)
1. **F13** Plano de Obras pinta linhas mas **não bloqueia ações** em linhas cinza (blocked_rows). Usuário pode deletar/marcar correção em obras "em janela bloqueada"
2. **C10/H1** Linhas com `atende=None` (dados insuficientes) deveriam aparecer cinza, **estão pretas** (confunde com "atendeu")

### ❌ AUSENTES (impacto alto, prioridade 2)
3. **E5** Botão "Salvar Banco de Dados" no footer Visualizar (API existe)
4. **E6** Botão "Exportar para Banco" no footer Visualizar (API existe)
5. **E11** Checkbox "Incluir aprovadas" persistente (atualmente só prompt excepcional)
6. **F16** Fluxo "Atualizar Projeto" navegacional (prev/next obras de um pacote)
7. **C8** Persistência de larguras de coluna ao redimensionar
8. **F2** Combo "Nome Projeto" sincronizado com obras carregadas (no Cadastro)

### ❌ AUSENTES (impacto médio, prioridade 3)
9. **F1** Auto-prompt choose_packages na 1ª conexão
10. **I2** Atalho Ctrl+L (focus busca, alias do Ctrl+F)
11. **I4** Atalho Ctrl+C copy seleção
12. **C7** Menu cabeçalho real ("Recolher" + outras ações; hoje só recolhe direto)
13. **D2** Pagination label com total de itens
14. **D6** Reutilizar algoritmo `paginate_visualizar_rows` do desktop (compartilhar)

### ⚠️ PARCIAIS (impacto baixo, prioridade 4)
15. **A1** Botão "Carregar Banco e Apoio" no toolbar Visualizar (atalho)
16. **B6** filter_alimentadores_benef precisa testes
17. **B10** Pacote duplicado (modal + botão Pacotes)
18. **B16** Atalho Ctrl+L
19. **B18** filter_chips ativos hoje são mock; precisam ser reais
20. **B19** filter_tecnico_dirty: confirmar mapeamento "Atualizado SIM" ↔ `tecnico_dirty=NÃO`
21. **C1** readonly da tabela (verificar se há edição inadvertida)
22. **C2** Selection multi: verificar Shift/Ctrl funcionam
23. **C5** Double-click → Editar/Atualizar — verificar
24. **C9** Widths persistidos ao boot — confirmar carregamento
25. **F4** Persistência critérios: confirmar que update_criterios_por_cod roda ao carregar
26. **F5/F8** _filtrar_ids_por_anos / _por_aprovacao em backend para search/export — pode não estar
27. **F7** Stats reagem a filtros — verificar
28. **G5** Stats reagem a filtros aplicados
29. **H6** Auto-resize colunas após render
30. **H7** Legend faltando indef cinza

---

## PARCELAS DE EXECUÇÃO (loop 15min)

Cada parcela deve caber em ~15min de trabalho focado, com validação `python -m py_compile main_web.py` ao fim.

### Parcela 1 — Fix bugs críticos
- [ ] **F13** Plano de Obras bloqueia ações em linhas cinza:
  - Cada handler que opera sobre cods (delete, correcao, snapshot, atualizar valor) deve filtrar `window.__coplanPlanoActive.blocked_rows`
- [ ] **C10/H1** Cor cinza para indef (`atende === null`) na renderização de linha + legend

### Parcela 2 — Botões footer faltantes
- [ ] **E5** Botão "Salvar BD" no toolbar Visualizar → `db_save_as`
- [ ] **E6** Botão "Exportar p/ Banco" → `db_export_to` (com gate aprovadas)
- [ ] **E11** Checkbox "Incluir aprovadas" persistente (em `localStorage` + envia em delete/export)

### Parcela 3 — Persistência de widths
- [ ] **C8** Listener `mouseup` em `<th>` com resize → captura largura → bulk save em `visualizar_columns_save_config({widths})`
- [ ] **C9** No carregamento de obras, aplicar widths salvos a cada `<th>`

### Parcela 4 — Combo Nome Projeto
- [ ] **F2** API `list_nomes_projetos()` (distinct nome_projeto onde não vazio) + popular `<select>` no Cadastro

### Parcela 5 — Atualizar Projeto navegacional
- [ ] **F16** Modal "Atualizar Projeto" com prev/next/finalizar/cancelar:
  - API `projeto_iniciar_atualizacao(nome_projeto)` retorna lista de cods do projeto + dados primeiros
  - JS mantém index local; botões prev/next chamam `get_obra(cod)` para próxima
  - Finalizar = save_obra para todas modificadas

### Parcela 6 — Auto-prompt e atalhos
- [ ] **F1** Após `header_connect_db` ok, dispara `openChoosePackagesDialog()` se 1ª conexão
- [ ] **I2** Adicionar Ctrl+L como alias do Ctrl+F
- [ ] **I4** Atalho Ctrl+C copia CODs selecionados (delegar para botão Copiar)

### Parcela 7 — Menu cabeçalho real
- [ ] **C7** `<th>` contextmenu → menu com:
  - Recolher coluna (~15chars baseado na fonte)
  - Restaurar largura
  - Esconder coluna (toggle visibility, salva no config)
  - Ordenar A-Z / Z-A

### Parcela 8 — Pagination & Visual
- [ ] **D2** Label "Página X / Y · N obras"
- [ ] **D6** Reutilizar `format_pagination_label` via API se possível
- [ ] **H6** Auto-fit colunas após render (janela mínima)
- [ ] **H7** Legend incluir "🟡 Indefinido"

### Parcela 9 — Filtros polidos
- [ ] **B6** Validar filter_alimentadores_benef no backend search_obras
- [ ] **B18** Filter chips ativos: render dinâmico baseado em `coplanFilters` + click no `<i>` remove
- [ ] **B19** Verificar mapping tecnico_dirty correto
- [ ] **B10** Remover botão "Pacotes" duplicado OU manter mas marcar como "Filtro rápido" (mantém modal completo)

### Parcela 10 — Toolbar atalho carregar
- [ ] **A1** Botão "Carregar Banco e Apoio" no toolbar Visualizar (atalho que faz `header_connect_db` + `pick_and_load_apoio`)

### Parcela 11 — Validações finais
- [ ] **C1** Verificar tabela é realmente readonly
- [ ] **C2** Testar selection com Shift/Ctrl
- [ ] **C5** Testar double-click → Editar
- [ ] **F4/F7** Confirmar persistência critérios + filtros backend
- [ ] **G5** Stats reagem a filtros (re-call get_obras_stats com filters)

### Parcela 12 — Smoke test final + checklist
- [ ] Rodar `python main_web.py` no Chrome MCP via preview
- [ ] Validar: connect DB, list obras, search, filter, export, plano, snapshot, gating

---

## ESTADO ATUAL DESTE DOCUMENTO

Auditoria fechada em 2026-05-05.

**Total de itens auditados:** ~30 features/regras
**Total bugs:** 2
**Total ausentes:** 6
**Total ausentes médios:** 6
**Total parciais:** 16

**Plano:** 12 parcelas, ~15 min cada, ~3h de trabalho total estimado.
