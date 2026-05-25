# Plano exaustivo — Migração da aba "Cadastro" (codigo5_coplan.py → main_web.py)

> Documento gerado em 2026-05-06.
> Fonte canônica do desktop: `codigo5_coplan.py` + `ui/main_window/cadastro_mixin.py` + `ui/main_window/apoio_mixin.py` + `ui/main_window/visualizar_mixin.py` + `core/services/salvar_obra_service.py`.
> Alvo da migração: `main_web.py` (CoplanApi + JS embarcado em `COPLAN_BRIDGE_JS`) + `Coplan UI.html` (mock visual carregado em memória).
> Restrição imposta pelo usuário (memória `project_coplan_main_web.md`): NÃO editar `codigo5_coplan.py` nem o HTML em disco — toda mudança fica em `main_web.py` (que injeta JS no buffer do HTML em memória) e, quando inevitável, no próprio `Coplan UI.html`.

---

## 0. Como o loop de 15 min lê este arquivo

1. O loop carrega `MIGRACAO_CADASTRO_STATE.md`, pega o `cursor` e a lista de itens `feitos`.
2. Procura o próximo bloco `M###` que ainda não está em `feitos` e cujas dependências (`Depende de:`) já estão.
3. Executa o item: lê os arquivos citados, faz a edição em `main_web.py` (e/ou `Coplan UI.html`), valida o critério de pronto.
4. Atualiza `MIGRACAO_CADASTRO_STATE.md` (move para `feitos`, atualiza `cursor`, anota observações).
5. Encerra a iteração (sem abrir o app — auditoria por análise de código, conforme memória `feedback_auditoria_cadastro_web_sem_abrir.md`).

Cada iteração pega entre 1 e 5 itens dependendo do tamanho. Se algo travar, registra em `bloqueios` no STATE e segue o próximo item independente.

---

## 1. Inventário canônico do desktop (CONGELADO — não editar)

### 1.1 Layout (ordem visual de cima para baixo)

`cadastro_mixin.py:225-547`

```
QScrollArea (vertical+horizontal AsNeeded)
└─ QWidget (cadastro_layout = QVBoxLayout)
   └─ QGroupBox group_dados
      ├─ QGroupBox "Dados Básicos da Obra"          (cadastro_mixin.py:242-303)
      │  ├─ QComboBox  field_ano                    (linha de combo + label "Ano")
      │  ├─ HBox: QComboBox field_projeto_investimento + QLabel "Item" + QLineEdit field_item
      │  ├─ HBox: QComboBox combo_nome_projeto + QLineEdit field_projeto + QLabel instrução + QPushButton "Nome de projetos"(QMenu) + QPushButton "Escolher Projeto"
      │  └─ QPlainTextEdit field_observacoes (height fixo 60)
      ├─ QGroupBox "Informações Técnicas"           (cadastro_mixin.py:309-383)
      │  ├─ Linha "Alimentador Obra":
      │  │   QComboBox(editable) field_alimentador
      │  │   + label "Tensão Obra"  + QLineEdit field_tensao (maxlen 5)
      │  │   + label "Tensão Oper." + QLineEdit field_tensao_operacao (maxlen 5)
      │  │   + label "Regional"     + QLineEdit field_regional (maxlen 15)
      │  │   + label "Superintendência" + QLineEdit field_superintendencia (maxlen 12)
      │  │   + label "SE"           + QLineEdit field_se
      │  ├─ Linha "Coordenadas De":
      │  │   QLineEdit field_coord_inicio
      │  │   + label "Coordenadas Para" + QLineEdit field_coord_fim
      │  │   + label "Quantidade" + QLineEdit field_quantidade
      │  │   + label "Características" + QComboBox(editable) field_caracteristicas
      │  │   + label "Manobra" + QComboBox field_manobra (SIM/NÃO)
      │  └─ Linha extra:
      │      label "Novo Bay?" + QComboBox field_novo_bay (NÃO/SIM)
      │      + label "Criticidade" + QComboBox field_criticidade (Baixa/Média/Alta)
      ├─ QGroupBox "Dados Financeiros"              (cadastro_mixin.py:389-416)
      │  ├─ QComboBox field_pacote (Mercado/Confiabilidade/Interligação de UDE/Solicitação Regional/Orçamento de Conexao/PLPT)
      │  ├─ QComboBox field_obra_aprovada (NÃO/SIM, default NÃO)
      │  └─ HBox: QLineEdit field_valor_obra + QPushButton "Calcular Valor da Obra"
      ├─ QGroupBox "Ações"                          (cadastro_mixin.py:421-450)
      │  ├─ ToolButton "Salvar Obra" (Ctrl+B) → save_data
      │  ├─ ToolButton "Limpar Campos" → limpar_campos_cadastro
      │  └─ QPushButton "⚙ Configurações" → open_descricao_template_dialog
      └─ QGroupBox "Alimentadores e Subestações"    (cadastro_mixin.py:453-505)
         ├─ HBox: QComboBox(editable) field_alimentador_benef + ToolButton "Adicionar à Lista"
         └─ HBox:
             CopyListWidget list_alimentadores_benef (h=120, wrapping TopToBottom, ExtendedSelection, ContextMenu Copiar/Remover)
             VBox: QLabel "Subestações Consideradas" + CopyListWidget list_subestacoes (h=100, ContextMenu Copiar)
   └─ HBox nav_layout (oculto até modo "Atualizar Projeto"):
      btn_prev_proj "◀" | label_nav_proj "X de Y" | btn_next_proj "▶" | btn_cancelar_proj "Cancelar" | label_msg_proj | btn_finalizar_proj "Salvar no banco de dados"
```

### 1.2 Combos com itens fixos

| Combo | Itens (na ordem) | Default |
|---|---|---|
| `field_ano` | `current_year` … `current_year+10` (11 anos) | índice 0 |
| `field_projeto_investimento` | DISTRIBUIÇÃO; MELHORAMENTOS; TRIFASEAMENTO; INSTALAÇÃO DE BANCOS DE REGULADORES DE TENSÃO EM RD; INSTALAÇÃO DE BANCOS DE CAPACITORES EM RD; INSTALAÇÃO DE BANCOS DE REATORES EM RD; DISTRIBUIÇÃO LD 34,5 KV | sem seleção (-1) |
| `field_pacote` | Mercado; Confiabilidade; Interligação de UDE; Solicitação Regional; Orçamento de Conexao; PLPT | sem seleção (-1) |
| `field_obra_aprovada` | NÃO; SIM | NÃO |
| `field_manobra` | SIM; NÃO | sem seleção (-1) |
| `field_novo_bay` | NÃO; SIM | sem seleção (-1) |
| `field_criticidade` | Baixa; Média; Alta | sem seleção (-1) |
| `combo_nome_projeto` | dinâmico: extras + `support_manager.nomes_projetos_pre_definidos` + DISTINCT do banco; sempre adiciona "Melhorias AL" no fim se ausente | sem seleção (-1) |
| `field_alimentador` (editable) | dinâmico: chaves de `support_manager.dados_alimentador` | sem seleção (-1) |
| `field_caracteristicas` (editable) | dinâmico: `dados_alimentador[alim]['CARACTERÍSTICAS']` | sem seleção (-1) |
| `field_alimentador_benef` (editable) | igual a `field_alimentador` | sem seleção (-1) |

### 1.3 Validadores e tooltips

- `field_alimentador` e `field_alimentador_benef`: `QRegularExpressionValidator(r'^[^_]+$')` + tooltip "Não use sublinhado (_) neste campo".
- `field_tensao` e `field_tensao_operacao`: maxLength 5.
- `field_regional`: maxLength 15.
- `field_superintendencia`: maxLength 12.
- `instruction_label` ao lado de `field_projeto`: texto fixo `Não pode iniciar com "Obra"` (informativo).

### 1.4 Sinais e handlers

| Widget | Sinal | Handler | Arquivo:linha |
|---|---|---|---|
| `field_projeto_investimento` | `currentTextChanged` | `verificar_pi_padrao` | `cadastro_mixin.py:270, 702-714` |
| `combo_nome_projeto` | `currentTextChanged` | `_preencher_nome_projeto_auto` | `cadastro_mixin.py:276`; impl `apoio_mixin.py:307-314` |
| `field_alimentador` | `currentIndexChanged` | `alimentador_selecionado` | `cadastro_mixin.py:314`; impl `apoio_mixin.py:175-192` |
| btn "Escolher Projeto" | `clicked` | `buscar_projetos` | `apoio_mixin.py:316-325` |
| btn "Calcular Valor da Obra" | `clicked` | `calcular_valor_obra_handler` | `cadastro_mixin.py:549-578` |
| btn "Salvar Obra" (Ctrl+B) | `clicked` | `save_data` | `codigo5_coplan.py:1075-1425` |
| btn "Limpar Campos" | `clicked` | `limpar_campos_cadastro` | `cadastro_mixin.py:611-665` |
| btn "⚙ Configurações" | `clicked` | `open_descricao_template_dialog` | `cod_pep_mixin.py:274-275` → `config_mixin.py:206-221` |
| btn "Adicionar à Lista" | `clicked` | `adicionar_alimentador_benef` | `apoio_mixin.py:194-200` |
| `list_alimentadores_benef` | `customContextMenuRequested` | `mostrar_menu_contexto_alimentadores` (Copiar; Remover) | `visualizar_mixin.py:281-291` |
| `list_subestacoes` | `customContextMenuRequested` | `mostrar_menu_contexto_subestacoes` (Copiar) | `visualizar_mixin.py:300-307` |
| Menu "Nome de projetos" | actions | `nova_se` / `novo_al` / `reconfiguracao` / `alivio_se` / `flexibilizacao` | `cadastro_mixin.py:282-289, 682-700`; `preencher_novo_al` em `apoio_mixin.py:202-205` |
| `btn_prev_proj`/`btn_next_proj`/`btn_cancelar_proj`/`btn_finalizar_proj` | `clicked` | `prev_projeto_obra` / `next_projeto_obra` / `cancelar_atualizacao_projeto` / `finalizar_atualizacao_projeto` | `atualizar_obra_mixin.py` |

### 1.5 Diálogos abertos a partir da aba

| Diálogo | Origem | Função |
|---|---|---|
| Gerenciar PI_BASE (QDialog c/ Adicionar/Renomear/Remover/Restaurar/Fechar) | `cadastro_mixin.py:18-218` | CRUD da lista custom de PI_BASE; usa QInputDialog.getText, QInputDialog.getItem (substituto), QMessageBox.question (restaurar), atualiza `PI_BASE_CUSTOM`, `PI_BASE_MAP`, `descricao_obra_templates` no `config.json` |
| Templates de descrição | `open_descricao_template_dialog` → `config_mixin.py:206-221` | Abre aba "Configurações" com sub-aba "Template" |
| ProjectSelectionDialog | `apoio_mixin.py:316-325` (`runtime/dialogs.py`) | Seleciona projeto existente; preenche `field_projeto` e chama `carregar_dados_projeto` |
| Multi-select de PIs | `cadastro_mixin.py:716-754` (`selecionar_pis`) | QDialog c/ QListWidget MultiSelection; resolve PI_BASE para cada item |
| QFileDialog pasta | `cadastro_mixin.py:668-679` (`selecionar_pasta_arquivos`) | Salva `caminho_pasta_ganhos` no config |
| QInputDialog "Adicionar PI_BASE" | `cadastro_mixin.py:93-95` | texto novo |
| QInputDialog "Renomear PI_BASE" | `cadastro_mixin.py:113-117` | texto pré-preenchido |
| QInputDialog "Substituir PI_BASE" | `cadastro_mixin.py:163-176` | escolha em lista |
| QMessageBox "Restaurar padrões?" | `cadastro_mixin.py:195-202` | Yes/No (default No) |
| QInputDialog "Mudança crítica" (motivo) | `codigo5_coplan.py:1303-1306` | obrigatório quando campos críticos mudam fora de modo "atualizar projeto" |
| QMessageBox "Descrição da Obra (gerar?)" | `codigo5_coplan.py:1151-1157` | sim/não |
| QMessageBox "Código Alterado" | `codigo5_coplan.py:1184-1189` | "Nova obra" vs "Atualizar obra existente" |
| QMessageBox "Já existe obra com este código" | `codigo5_coplan.py:1384` | erro INSERT duplicado |
| QMessageBox "Já existe obra com este código de item para o projeto" | `codigo5_coplan.py:1337-1338, 1351` | erro projeto_obras |
| QMessageBox "Sucesso – nova obra criada" / "atualizada" / "registro existente atualizado" | `codigo5_coplan.py:1380, 1416, 1394-1396` | info |
| QMessageBox "Aviso – nenhuma atualização aplicável" | `codigo5_coplan.py:1402-1403` | info |
| QMessageBox "Aviso – obra já DESPACHADA" | `codigo5_coplan.py:1286-1287` | bloqueio |

### 1.6 Regras de negócio (tags `[RB-…]`)

- **[RB-1.1]** Gate `db = CARREGADO_VALIDADO` antes de `save_data` (`codigo5_coplan.py:1075-1077`).
- **[RB-5]** Gate `apoio = CARREGADO_VALIDADO` antes de `calcular_valor_obra_handler` (`cadastro_mixin.py:553-557`).
- **[RB-DISTRIBUIÇÃO]** Campo `Projeto` obrigatório SOMENTE quando `normalize_key(pi) ∈ {"DISTRIBUICAO", "DISTRIBUICAO LD 34,5 KV"}` (`cadastro_mixin.py:596-606`).
- **[RB-DESPACHADA]** Bloqueia salvamento se obra estava em status DESPACHADA e algum campo crítico mudou; oferece marcar como CORREÇÃO (`codigo5_coplan.py:1286-1287`; `salvar_obra_service.py`).
- **Campos sempre obrigatórios para salvar**: Ano, Projeto de Investimento, Alimentador Obra, Quantidade, Coordenadas Para, Pacote, Características, Manobra (`cadastro_mixin.py:585-594`).
- **Validador alimentador sem `_`** aplicado também na persistência via `aplicar_alimentador_validations` (`salvar_obra_service.py:31-52`).
- **Geração automática de `codigo_item`** quando `field_projeto` preenchido e `field_item` vazio (via `db_manager.get_next_codigo_item(nome_projeto)` em `cadastro_mixin.py:756-763`).
- **Geração de COD** via `calc_manager.gerar_cod(pacote, alimentador, pi, quantidade, caracteristica, coord_fim, pi_base)` (`codigo5_coplan.py:1127-1135`).
- **Resolução de PI_BASE**: `get_pi_base(pi, prompt_user)` com `prompt_user=True` em `save_data` e `verificar_pi_padrao`, `False` em `calcular_valor_obra_handler`.
- **Auto-preenchimento ao escolher alimentador**: tensão, tensão operação, regional, superintendência, SE; depois `update_subestacoes_list()`.
- **Fallback** `tensao_operacao = tensao_operacao or nivel_tensao_obra` no save (`codigo5_coplan.py:1137-1140`; `salvar_obra_service.py:183`).
- **Histórico**: ao alterar campos, monta string `[YYYY-MM-DD HH:MM] Campos: a, b, c | Motivo: …` e grava em coluna `historico` (ou `observacoes` se não houver) (`salvar_obra_service.py:298-359`).
- **Detecção de duplicidade na criação**: por código (`cod`) e por chave semântica (alimentador+município+descrição+pi+ano).
- **Refresh pós-save**: chama `load_obras_into_table()` + `limpar_campos_cadastro()`.
- **`enable_cadastro_fields(bool)`**: liga/desliga `group_dados` e `group_param` em conjunto (`cadastro_mixin.py:765-767`).
- **`combo_nome_projeto` "Melhorias AL"**: ao selecionar, preenche `field_projeto = "Melhorias_AL_"` (`apoio_mixin.py:307-314`).
- **`preencher_novo_al`**: preenche `field_projeto = "AL_Novo_"` e marca `field_novo_bay = "SIM"` (`apoio_mixin.py:202-205`).
- **Recálculo dos labels Planejamento/Postergação** ao carregar obra; reconecta sinais nos campos "Depois" da aba Ganhos (`cadastro_mixin.py:892-987`). (Esses labels vivem na aba Ganhos, mas dependem de `preencher_campos_obra`.)

### 1.7 Mapeamento UI → coluna SQLite

`cadastro_mixin.py:799-820` (campos básicos) e `843-867` (ganhos):

| Coluna SQLite | Widget Qt |
|---|---|
| `ano_` | `field_ano` |
| `projeto_investimento` | `field_projeto_investimento` |
| `pi_base` | derivado por `get_pi_base` |
| `nome_projeto` | `field_projeto` |
| `codigo_item` | `field_item` |
| `alimentador_principal` | `field_alimentador` |
| `nome_regional` | `field_regional` |
| `nome_superintendencia` | `field_superintendencia` |
| `nivel_tensao_obra` | `field_tensao` |
| `tensao_operacao` | `field_tensao_operacao` |
| `subestacao` | `field_se` |
| `coordenada_inicio` | `field_coord_inicio` |
| `coordenada_fim` | `field_coord_fim` |
| `quantidade_material` | `field_quantidade` |
| `caracteristicas_material` | `field_caracteristicas` |
| `manobra` | `field_manobra` |
| `novo_bay` | `field_novo_bay` |
| `nivel_criticidade` | `field_criticidade` |
| `observacoes_gerais` | `field_observacoes` |
| `tipo_pacote` | `field_pacote` |
| `obra_aprovada` | `field_obra_aprovada` |
| `valor_obra` | `field_valor_obra` |
| `alimentadores_beneficiados` | `list_alimentadores_benef` (join `;`) |
| `cod` | derivado por `calc_manager.gerar_cod` |
| `tecnico_dirty` | sempre `"NÃO"` ao salvar |
| (ganhos antes/depois/atual) | mapeamento em `cadastro_mixin.py:843-867` (não fica na aba Cadastro, mas é zerado por `limpar_campos_cadastro`) |

### 1.8 Mensagens visíveis ao usuário (catálogo)

(Lista completa nas seções 7.1 a 7.5 do relatório do agente; reproduzida abaixo no roadmap por item.)

### 1.9 Atalhos de teclado

- `Ctrl+B` → "Salvar Obra" (`cadastro_mixin.py:431`).

### 1.10 Persistência colateral

- `config.json["caminho_pasta_ganhos"]` ← `selecionar_pasta_arquivos`.
- `config.json["pi_base_custom"]`, `config.json["pi_base_map"]`, `config.json["descricao_obra_templates"]` ← diálogo Gerenciar PI_BASE.
- Histórico em coluna `historico`/`observacoes` da obra ao salvar com mudanças.

---

## 2. Estado atual do `main_web.py` (CONGELADO — referência inicial)

### 2.1 Métodos `CoplanApi` que JÁ existem e são usáveis pela aba Cadastro

| Método | Local | Para quê serve |
|---|---|---|
| `get_obra(cod)` | `main_web.py:1503-1539` | Carrega obra completa para edição |
| `save_obra(payload, motivo?)` | `main_web.py:1552-1670` | Insert/Update; faz fallback de tensão; aplica histórico; bloqueia DESPACHADA |
| `delete_obras(cods)` | `main_web.py:1038-1058` | (visualizar) |
| `gerar_cod_pep(pi, ano, item, pi_base)` | `main_web.py:1679-1734` | Constrói COD `<SIGLA>-<YY>-<PI>-<ITEM>` |
| `calcular_valor_obra(pi, pi_base, tensao, caract, regional, qtd, cod)` | `main_web.py:1881-1975` | Cálculo via `atualizar_obra_service._core_calc` |
| `atualizar_obras_valores(cods)` | `main_web.py:1986-2122` | bulk |
| `list_alimentadores()` | `main_web.py:2152-2243` | catálogo (BD ∪ apoio) |
| `get_alimentador_details(alim)` | `main_web.py:2114-2150` | retorna tensao/regional/se a partir do apoio |
| `get_pi_options()` | `main_web.py:2252-2303` | bases + long_names |
| `get_regionais()` | `main_web.py:2305-2321` | lista ordenada |
| `get_pacotes()` | `main_web.py:2323-2357` | defaults + vistos no banco |
| `get_form_metadata()` | `main_web.py:2359-2384` | agregador de pi/regionais/pacotes/alimentadores/caracteristicas em 1 chamada |
| `projeto_fetch_obras(nome_projeto, tipo_pacote)` | `main_web.py:3584-3633` | obras de um projeto (Atualizar Projeto) |
| `db_next_codigo_item(nome_projeto)` | `main_web.py:5047-5059` | próximo código |
| `load_apoio(path)` | `main_web.py:1798-1822` | (re)carrega planilha de apoio |
| `pick_and_load_apoio()` | `main_web.py:1824-1831` | file dialog + load |
| `pick_apoio_file()` | `main_web.py:3861-3863` | file dialog |
| `get_config_empresa()` / `save_config_empresa(payload)` | `main_web.py:3783-3854` | sigla + paths |
| `pick_db_file()` | `main_web.py:3856-3859` | file dialog |
| `get_pi_base_map()` / `save_pi_base_map(payload)` | `main_web.py:4067-4127` | CRUD do PI_BASE custom |

### 2.2 IDs HTML já presentes em `Coplan UI.html` (`#tab-cadastro`)

`tab-cadastro`, `cad-projeto-nav-bar`, `cad-projeto-nav-info`, `cad-projeto-nav-prev`, `cad-projeto-nav-next`, `cad-projeto-nav-finalizar`, `cad-projeto-nav-cancelar`, `cad-input-projeto`, `cad-btn-escolher`, `cad-btn-templates`, `cad-btn-nova-se`, `cad-btn-novo-al`, `cad-btn-reconf`, `cad-btn-alivio`, `cad-btn-flex`, `cad-btn-multi-pi`, `cad-sel-nome-projeto-combo`, `cad-sel-alim-principal`, `cad-input-se`, `cad-sel-novo-bay`, `modal-pi`, `btn-modal-pi`.

### 2.3 Lacunas críticas identificadas no inventário (resumo)

1. JS bridge não tem listener nenhum para os campos/botões do Cadastro.
2. Auto-preenchimento (SE / Regional / Superintendência / Tensão / Características) ao escolher alimentador não está plugado.
3. "Adicionar à Lista" (chips de alimentadores beneficiados) não cria chips nem dispara recálculo de SEs.
4. Validação dos obrigatórios é mock estática na sidebar.
5. `Ctrl+B` não dispara salvar (só `Ctrl+1..5` para abas).
6. Nav "Atualizar Projeto" tem HTML mas zero state machine.
7. IDs faltam em vários `<input>` / `<select>` do Coplan UI.html (Ano, Item, Tensão Obra, Regional, etc.) — JS não consegue endereçar.
8. Modal "Templates de descrição" sem implementação (botão `cad-btn-templates` solto).
9. Confirmação de descrição automática, "Código Alterado", motivo de alteração crítica, "Restaurar padrões PI_BASE" — todos sem JS.
10. Persistência colateral de `caminho_pasta_ganhos` via `pick_export_dir` parcialmente plugada (commit `7b2a025`) mas não para o cenário do cadastro.

---

## 3. Roadmap de migração (itens M001–M120)

> Cada item é independente o suficiente para ser executado numa fatia do loop. As dependências (`Depende de:`) são as mínimas — só o que precisa estar pronto antes.

### 3.A — IDs e markup que faltam no `Coplan UI.html`

> Edição mínima de IDs/`data-*`. Nada de alterar layout visual sem necessidade.

#### M001 — Adicionar `id`/`name` aos campos sem identificador
- **Origem desktop:** `cadastro_mixin.py:245-302, 312-380, 391-415`
- **Estado web:** `Coplan UI.html` linhas 945-1141 — vários `<input>`/`<select>` sem `id`.
- **O que fazer:** Adicionar IDs estáveis para todos os campos da aba cadastro:
  - Ano → `cad-sel-ano`
  - Projeto de Investimento → `cad-sel-pi`
  - Item → `cad-input-item`
  - Observações → `cad-input-observacoes`
  - Tensão Obra → `cad-input-tensao`
  - Tensão Operação → `cad-input-tensao-oper`
  - Regional → `cad-input-regional`
  - Superintendência → `cad-input-superintendencia`
  - Coordenadas De → `cad-input-coord-inicio`
  - Coordenadas Para → `cad-input-coord-fim`
  - Quantidade → `cad-input-quantidade`
  - Manobra → `cad-sel-manobra`
  - Características → `cad-sel-caracteristicas`
  - Criticidade → `cad-sel-criticidade`
  - Pacote → `cad-sel-pacote`
  - Obra Aprovada (pill row) → `cad-grp-aprovada` no container e `cad-pill-aprovada-nao` / `cad-pill-aprovada-sim` nos botões
  - Valor da Obra → `cad-input-valor`
  - Botão Calcular Valor → `cad-btn-calcular-valor`
  - Alimentador Beneficiado input → `cad-input-alim-benef`
  - Botão Adicionar (chip) → `cad-btn-add-benef`
  - Container chips → `cad-list-alim-benef`
  - Container subestações → `cad-list-subestacoes`
  - Botão Limpar Campos → `cad-btn-limpar`
  - Botão Salvar Obra → `cad-btn-salvar`
  - Sidebar Validação container → `cad-aside-validacao`
  - Sidebar Última modif. container → `cad-aside-modif`
- **Critério de pronto:** `grep "cad-input-tensao\|cad-sel-pi\|…"` retorna ≥ 1 ocorrência por id.
- **Depende de:** —

#### M002 — Padronizar atributo `data-act` nos botões de atalho do Projeto
- **Origem desktop:** menu "Nome de projetos" (`cadastro_mixin.py:282-289`).
- **O que fazer:** garantir que `cad-btn-nova-se`, `cad-btn-novo-al`, `cad-btn-reconf`, `cad-btn-alivio`, `cad-btn-flex`, `cad-btn-multi-pi` carreguem `data-act="nome-projeto:nova-se"` etc., para o JS centralizar via delegação.
- **Critério de pronto:** todos os 6 botões têm `data-act` previsível.
- **Depende de:** M001.

#### M003 — Adicionar campo `<textarea>` "Motivo de Alteração" oculto
- **Origem desktop:** `QInputDialog` em `codigo5_coplan.py:1303-1306` (texto obrigatório quando muda campo crítico).
- **O que fazer:** adicionar bloco no card "Dados Financeiros" com `id="cad-row-motivo"` `style="display:none"` contendo `<textarea id="cad-input-motivo">` e label "Motivo de alteração crítica". JS revela quando `save_obra` retornar `requires_motivo: true`.
- **Critério de pronto:** elemento existe no HTML; CSS não vaza visualmente até JS revelar.
- **Depende de:** M001.

#### M004 — Marcar a sidebar "Validação" como `data-state="pending"` por padrão
- **Origem desktop:** sidebar mock em HTML 1145-1157.
- **O que fazer:** trocar os ícones/classes mock por contêineres `data-check="obrigatorios"`, `data-check="alimentadores-sem-underscore"`, `data-check="projeto-prefix-obra"`, `data-check="cod-completo"`. Cada um inicia neutro; JS atualiza via classes `.ok`/`.warn`/`.err`.
- **Critério de pronto:** os 4 `data-check` existem; sem cor "verde fixa".
- **Depende de:** M001.

#### M005 — Adicionar bloco modal "Gerar descrição automaticamente?"
- **Origem desktop:** `QMessageBox.question` em `codigo5_coplan.py:1151-1157`.
- **O que fazer:** adicionar `<div class="modal" id="modal-gerar-descricao" hidden>` com pergunta + botões "Sim" / "Não" / "Cancelar".
- **Critério de pronto:** marcação presente; sem JS ainda.
- **Depende de:** —

#### M006 — Adicionar bloco modal "Código Alterado: criar nova ou atualizar?"
- **Origem desktop:** `codigo5_coplan.py:1184-1189`.
- **O que fazer:** modal `id="modal-cod-alterado"` com 3 botões: "Criar nova", "Atualizar existente", "Cancelar".
- **Critério de pronto:** marcação presente.
- **Depende de:** —

#### M007 — Estender modal "Gerenciar PI_BASE" com botões reais
- **Origem desktop:** `cadastro_mixin.py:18-218`.
- **Estado web:** `modal-pi` mock estático.
- **O que fazer:** adicionar botões `id="pi-btn-add"`, `pi-btn-rename`, `pi-btn-remove`, `pi-btn-restore`, `pi-btn-close` + `<ul id="pi-list">` para a lista.
- **Critério de pronto:** todos os IDs existem.
- **Depende de:** —

#### M008 — Adicionar modal "Selecionar PIs" (multi-select)
- **Origem desktop:** `selecionar_pis` em `cadastro_mixin.py:716-754`.
- **O que fazer:** modal `id="modal-multi-pi"` com `<select multiple>` (ou checklist) + OK/Cancel.
- **Critério de pronto:** modal existe.
- **Depende de:** —

#### M009 — Adicionar modal "Buscar projeto" (lista de projetos)
- **Origem desktop:** `ProjectSelectionDialog` (`runtime/dialogs.py`).
- **O que fazer:** modal `id="modal-projeto-busca"` com `<input>` filtro + `<table>` de projetos (`<tbody id="projeto-busca-tbody">`) + OK/Cancel.
- **Critério de pronto:** modal existe.
- **Depende de:** —

#### M010 — Tornar a lista "Subestações Consideradas" derivada (read-only visual)
- **Origem desktop:** `update_subestacoes_list`.
- **O que fazer:** garantir que `#cad-list-subestacoes` esteja em modo somente leitura visual (sem botão remover) e com helper "Atualizado automaticamente".
- **Critério de pronto:** sem inputs editáveis nesse contêiner; helper presente.
- **Depende de:** M001.

---

### 3.B — Métodos `CoplanApi` que faltam em `main_web.py`

#### M020 — `cadastro_form_metadata()` — agregador específico do cadastro
- **Origem desktop:** combinação dos auto-preenchimentos de combos.
- **O que fazer:** método que retorna `{ano_range, pis, pacotes, manobra: ["SIM","NÃO"], aprovada: ["NÃO","SIM"], novo_bay: ["NÃO","SIM"], criticidade: ["Baixa","Média","Alta"], regionais, alimentadores, nomes_projeto: [...,"Melhorias AL"]}`. Pode reusar `get_form_metadata` + extras hardcoded.
- **Critério de pronto:** chamada retorna todos esses arrays não vazios (exceto se apoio não carregado, retorna `ok=False` + mensagem).
- **Depende de:** —

#### M021 — `caracteristicas_por_alimentador(alim)`
- **Origem desktop:** `dados_alimentador[alim]['CARACTERÍSTICAS']`.
- **O que fazer:** método que devolve lista de características para um alimentador.
- **Critério de pronto:** retorna lista (vazia se não há); reusa `_apoio_cache`.
- **Depende de:** —

#### M022 — `proximo_codigo_item(nome_projeto)`
- **Origem desktop:** `db_manager.get_next_codigo_item`.
- **Estado web:** já existe `db_next_codigo_item`. Validar que retorna formato esperado pela UI (string zero-padded em 3 casas? confirmar).
- **O que fazer:** apenas garantir interface consistente; aliasar se preciso.
- **Critério de pronto:** chamada `pywebview.api.db_next_codigo_item("ATIBAIA - REC. 2025")` retorna `{ok, next}`.
- **Depende de:** —

#### M023 — `pick_pasta_ganhos()` + `set_pasta_ganhos(pasta)`
- **Origem desktop:** `selecionar_pasta_arquivos` (`cadastro_mixin.py:668-679`).
- **O que fazer:** método que abre folder dialog (reuso de `pick_export_dir`/`pick_db_file`) e/ou recebe path; persiste em `config.json["caminho_pasta_ganhos"]` via `ConfigManager`.
- **Critério de pronto:** após chamada, `config.json` reflete o novo path.
- **Depende de:** —

#### M024 — `validar_cadastro(payload)` — espelho server-side de `validar_campos_obrigatorios`
- **Origem desktop:** `cadastro_mixin.py:580-609`.
- **O que fazer:** método que recebe dict do form e retorna `{ok, faltantes:[…], avisos:[…]}` aplicando regra **[RB-DISTRIBUIÇÃO]** condicional.
- **Critério de pronto:** com payload mínimo, devolve faltantes corretos.
- **Depende de:** —

#### M025 — `resolver_pi_base(pi, prompt=False)` (sem prompt server)
- **Origem desktop:** `get_pi_base`.
- **O que fazer:** método que devolve `{ok, pi_base, conhecido:bool}`. Quando `conhecido=False`, JS deve abrir prompt local; ao confirmar, JS chama `set_pi_base_map(payload)` (já existe).
- **Critério de pronto:** chamadas não escrevem em config sem confirmação.
- **Depende de:** —

#### M026 — `nome_projeto_options()` (DISTINCT do banco + apoio + "Melhorias AL")
- **Origem desktop:** `populate_combo_nome_projeto` (`apoio_mixin.py:247-305`).
- **O que fazer:** método que monta a lista do combo (ordenada, dedup case-insensitive, "Melhorias AL" no fim).
- **Critério de pronto:** lista está deduplicada e contém "Melhorias AL".
- **Depende de:** —

#### M027 — `obras_por_codigo_semelhante(payload)` (detecção semântica de duplicada)
- **Origem desktop:** detecção em `save_data` (`codigo5_coplan.py`).
- **O que fazer:** método que retorna `{matches:[{cod, descricao, alimentador,…}]}` para a UI oferecer merge ou criação.
- **Critério de pronto:** quando houver `obra_em_edicao` mas chave semântica colidir, retorna candidatos.
- **Depende de:** —

#### M028 — `gerar_descricao_obra(payload)`
- **Origem desktop:** "gerar a descrição automaticamente" (`codigo5_coplan.py:1151-1157`).
- **O que fazer:** método que devolve `{descricao:str}` montada via templates `descricao_obra_templates[pi_base]` + dados do payload.
- **Critério de pronto:** retorna string; usa template existente quando há.
- **Depende de:** —

#### M029 — `tecnico_snapshot()` (dummy se não existir ainda no web)
- **Origem desktop:** `_compute_tecnico_snapshot_token`, `_get_tecnico_snapshot_source`, `tecnico_dirty="NÃO"`.
- **O que fazer:** stub que devolve `{token, ts, src}` consistentes para `save_obra` aplicar.
- **Critério de pronto:** `save_obra` continua marcando `tecnico_dirty="NÃO"` (já faz) e ganha `tecnico_snapshot_*` quando disponível.
- **Depende de:** —

#### M030 — `atualizar_projeto_estado()` — endpoints da nav-bar
- **Origem desktop:** `prev_projeto_obra`, `next_projeto_obra`, `cancelar_atualizacao_projeto`, `finalizar_atualizacao_projeto`.
- **O que fazer:** exposer 4 métodos: `projeto_iniciar(nome_projeto, tipo_pacote)`, `projeto_avancar(idx, dirty_payload)`, `projeto_voltar(idx)`, `projeto_cancelar()`, `projeto_finalizar(payloads)`. Reusa `projeto_fetch_obras` + `save_obra`.
- **Critério de pronto:** ciclo iniciar→avançar→finalizar funciona em chamada manual.
- **Depende de:** M027.

---

### 3.C — JS bridge: listeners, atalhos, helpers

> Toda mudança fica dentro da string `COPLAN_BRIDGE_JS` em `main_web.py:6677-9365`.

#### M040 — Helper `coplanCadastro` (módulo IIFE no JS)
- **O que fazer:** criar IIFE que exporta `loadOptions`, `bindAll`, `serializeForm`, `applyObra(payload)`, `clearForm`, `setValidation(state)`, `showModal(id)`, `hideModal(id)` para o resto reusar.
- **Critério de pronto:** `window.coplanCadastro` existe após `coplanReady`.
- **Depende de:** M001.

#### M041 — Popular combos via `cadastro_form_metadata`
- **Origem desktop:** combos fixos + dinâmicos.
- **O que fazer:** ao entrar na aba Cadastro pela primeira vez, chamar `pywebview.api.cadastro_form_metadata()` e popular: `cad-sel-ano`, `cad-sel-pi`, `cad-sel-pacote`, `cad-sel-manobra`, `cad-sel-novo-bay`, `cad-sel-criticidade`, `cad-sel-alim-principal`, `cad-sel-caracteristicas`, `cad-sel-nome-projeto-combo`. Preservar default (Aprovada=NÃO, Ano=primeiro).
- **Critério de pronto:** abrir Cadastro popula todos os selects sem hardcode no HTML.
- **Depende de:** M020, M040.

#### M042 — Listener Ano: travar após edição inicial em modo "edição de obra"
- **Origem desktop:** comentário sobre travar Ano em ediç. (`cadastro_mixin.py:614`).
- **O que fazer:** quando JS detecta carregamento via `applyObra`, marcar `disabled` no `#cad-sel-ano`. `clearForm` reabilita.
- **Critério de pronto:** ao editar uma obra existente, Ano fica disabled; ao limpar, volta a editável.
- **Depende de:** M040.

#### M043 — Listener `change` em PI → `verificar_pi_padrao`
- **Origem desktop:** `cadastro_mixin.py:270, 702-714`.
- **O que fazer:** quando `#cad-sel-pi` muda, chamar `resolver_pi_base(pi)`. Se `conhecido=false`, abrir prompt local pedindo o PI_BASE; salvar via `save_pi_base_map`.
- **Critério de pronto:** PI fora da lista padrão dispara prompt; valor persistido.
- **Depende de:** M025, M040.

#### M044 — Listener `change` em Alimentador → `alimentador_selecionado`
- **Origem desktop:** `apoio_mixin.py:175-192`.
- **O que fazer:** ao mudar `#cad-sel-alim-principal`, chamar `get_alimentador_details(alim)` e preencher `cad-input-tensao`, `cad-input-tensao-oper`, `cad-input-regional`, `cad-input-superintendencia`, `cad-input-se`. Em seguida `caracteristicas_por_alimentador(alim)` para repopular `#cad-sel-caracteristicas`. Por fim, recalcular subestações via M048.
- **Critério de pronto:** trocar alimentador atualiza os 5 campos derivados + características.
- **Depende de:** M021, M040.

#### M045 — Listener `change` em `combo_nome_projeto` → "Melhorias_AL_"
- **Origem desktop:** `apoio_mixin.py:307-314`.
- **O que fazer:** se valor selecionado normalizado = "MELHORIAS AL", preencher `#cad-input-projeto = "Melhorias_AL_"`.
- **Critério de pronto:** efeito visível ao escolher "Melhorias AL".
- **Depende de:** M040.

#### M046 — Botões de atalho do Projeto (Nova SE / Novo AL / Reconf / Alívio / Flex)
- **Origem desktop:** `cadastro_mixin.py:282-289, 682-700`; `preencher_novo_al` em `apoio_mixin.py:202-205`.
- **O que fazer:** delegação no `data-act="nome-projeto:*"`:
  - nova-se → `Nova_SE_`
  - novo-al → `AL_Novo_` + setar `#cad-sel-novo-bay = "SIM"`
  - reconf → `Reconfiguração_`
  - alivio → `Alívio_SE_`
  - flex → `Flexibilização_AL_`
- **Critério de pronto:** clicar cada um preenche o input conforme tabela.
- **Depende de:** M002, M040.

#### M047 — Botão "Multi-PI" (`cad-btn-multi-pi`) → modal multi-select
- **Origem desktop:** `selecionar_pis` (`cadastro_mixin.py:716-754`).
- **O que fazer:** abrir `#modal-multi-pi`; ao confirmar, para cada PI selecionado chamar `resolver_pi_base(pi)`. Armazenar resultado em `window.coplanCadastro.selectedPis`.
- **Critério de pronto:** modal abre, OK persiste seleção.
- **Depende de:** M008, M025, M040.

#### M048 — Botão "Adicionar à Lista" (chip) + dedup + recálculo SEs
- **Origem desktop:** `apoio_mixin.py:194-200, 230-245`.
- **O que fazer:** clicar `#cad-btn-add-benef` adiciona chip em `#cad-list-alim-benef` se input não vazio e não duplicado (case-insensitive). Cada chip tem botão `×`. Após qualquer add/remove, montar lista `[principal] + chips`, chamar `get_alimentador_details` para cada, deduplicar SE e renderizar `#cad-list-subestacoes`.
- **Critério de pronto:** adicionar/remover chip atualiza subestações; duplicado mostra toast/aviso "Alimentador vazio ou já adicionado.".
- **Depende de:** M001, M044.

#### M049 — Validador "sem underscore" nos inputs de alimentador
- **Origem desktop:** regex `^[^_]+$`.
- **O que fazer:** no listener `input` de `#cad-sel-alim-principal` e `#cad-input-alim-benef`, remover `_` em tempo real ou marcar inválido. Tooltip/title = "Não use sublinhado (_) neste campo".
- **Critério de pronto:** digitar `_` é impedido ou highlight de erro.
- **Depende de:** M040.

#### M050 — `maxlength` JS para tensao(5)/regional(15)/superintendencia(12)
- **Origem desktop:** `cadastro_mixin.py:322,324,326,328`.
- **O que fazer:** definir `maxlength` no HTML (ou JS) para `cad-input-tensao`, `cad-input-tensao-oper` (5); `cad-input-regional` (15); `cad-input-superintendencia` (12).
- **Critério de pronto:** atributo presente; digitar acima trunca.
- **Depende de:** M001.

#### M051 — Botão "Calcular Valor da Obra"
- **Origem desktop:** `cadastro_mixin.py:549-578`.
- **O que fazer:** listener em `#cad-btn-calcular-valor` que monta payload (pi, pi_base, tensão, características, regional, quantidade, cod) e chama `calcular_valor_obra`. Sucesso → preenche `#cad-input-valor` (formato pt-BR via `valor_formatado`). Falha → toast/banner "Nenhum valor unitário encontrado para os parâmetros selecionados.". Exceção → toast "Erro no cálculo do valor da obra: …".
- **Critério de pronto:** clique dispara API; resultado popula campo.
- **Depende de:** M040.

#### M052 — Atalho `Ctrl+B` → Salvar Obra
- **Origem desktop:** `cadastro_mixin.py:431`.
- **O que fazer:** adicionar handler global no JS (semelhante ao Ctrl+1..5) que, quando aba ativa = `#tab-cadastro`, dispara click em `#cad-btn-salvar`. Não conflita com browser default em `<input>` se usar `event.preventDefault()`.
- **Critério de pronto:** com aba Cadastro visível, Ctrl+B aciona Salvar.
- **Depende de:** M053.

#### M053 — Botão "Salvar Obra" — fluxo completo
- **Origem desktop:** `save_data` (`codigo5_coplan.py:1075-1425`).
- **O que fazer:** sequência:
  1. Validar via `validar_cadastro` (M024). Se faltantes, exibir banner "Os seguintes campos obrigatórios estão vazios: …" e abortar.
  2. Validar regex underscore localmente (M049).
  3. Resolver PI_BASE via `resolver_pi_base` (M025).
  4. Se `#cad-input-item` vazio e `#cad-input-projeto` preenchido, chamar `db_next_codigo_item` (M022) e preencher.
  5. Construir payload (mapeamento UI→coluna conforme 1.7 + `tecnico_dirty="NÃO"`).
  6. Chamar `save_obra(payload, motivo?)`.
  7. Tratar respostas:
     - `ok=true` → toast verde ("Nova obra criada com sucesso!" / "Obra atualizada com sucesso!"), refresh aba Visualizar (`load_obras` → `clearForm`).
     - `ok=false`/`requires_motivo=true` → revelar `#cad-row-motivo`, focar `#cad-input-motivo`, banner "Mudança crítica: <campos>. Informe motivo (obrigatório)."; reenviar quando preenchido.
     - `blocked="despachada"` → banner amarelo "Obra já DESPACHADA. Para alterar, marque como CORREÇÃO primeiro." (sem reenvio automático).
     - `error` contém "código duplicado" → banner vermelho "Já existe uma obra com este código.".
     - se `error` indicar duplicada por chave semântica → abrir `#modal-cod-alterado` (M058) ou `#modal-merge-similar` (criar M059).
  8. Atualizar sidebar Validação (M061).
- **Critério de pronto:** caso feliz salva e limpa form; caso de erro mostra banner correto.
- **Depende de:** M001, M024, M025, M022, M040, M058, M059.

#### M054 — Botão "Limpar Campos"
- **Origem desktop:** `limpar_campos_cadastro` (`cadastro_mixin.py:611-665`).
- **O que fazer:** zerar 1-a-1 cada campo da aba (lista exata em 1.7 + manter Aprovada=NÃO + reabilitar Ano), limpar chips e subestações, descartar `obra_em_edicao` (variável JS local).
- **Critério de pronto:** após clique, formulário visualmente vazio (Ano=primeiro, Aprovada=NÃO).
- **Depende de:** M040.

#### M055 — Botão "⚙ Configurações" (templates)
- **Origem desktop:** `open_descricao_template_dialog` (`cod_pep_mixin.py:274-275`).
- **O que fazer:** clique em `#cad-btn-templates` muda para aba Configurações + sub-aba "Templates". Reusar handler de mudança de aba (`fireTabEvent`) e disparar evento custom `coplan:focus-config-tab` com `detail="templates"`.
- **Critério de pronto:** clique navega corretamente.
- **Depende de:** —

#### M056 — Botão "Escolher Projeto" → modal busca
- **Origem desktop:** `apoio_mixin.py:316-325, 327-350`.
- **O que fazer:** clique em `#cad-btn-escolher` abre `#modal-projeto-busca` (M009). Filtro client-side. Ao confirmar projeto, chamar `projeto_fetch_obras(nome_projeto)` para preencher Ano/Alim/Regional/Sup./Tensão/SE/Item da PRIMEIRA obra do projeto. Se vazio, banner "Nenhuma obra encontrada para o projeto selecionado.".
- **Critério de pronto:** seleção preenche os campos derivados.
- **Depende de:** M009, M040.

#### M057 — Modal "Gerar descrição automaticamente?"
- **Origem desktop:** `codigo5_coplan.py:1151-1157`.
- **O que fazer:** integrado ao fluxo M053: se descrição vazia ao salvar, abrir `#modal-gerar-descricao`; "Sim" chama `gerar_descricao_obra(payload)` (M028) e injeta no payload; "Não" segue com descrição vazia; "Cancelar" aborta save.
- **Critério de pronto:** os 3 caminhos funcionam.
- **Depende de:** M005, M028, M053.

#### M058 — Modal "Código Alterado"
- **Origem desktop:** `codigo5_coplan.py:1184-1189`.
- **O que fazer:** quando em modo edição e `cod` derivado mudar, abrir `#modal-cod-alterado`. "Criar nova" → tratar como insert; "Atualizar existente" → manter `cod` original; "Cancelar" → aborta.
- **Critério de pronto:** mudança de cod dispara modal antes de gravar.
- **Depende de:** M006, M053.

#### M059 — Modal "Obra similar encontrada — mesclar?"
- **Origem desktop:** detecção semântica em `save_data`.
- **O que fazer:** novo modal `#modal-merge-similar` listando obras retornadas por `obras_por_codigo_semelhante`. Botões: "Mesclar com selecionada", "Criar nova", "Cancelar".
- **Critério de pronto:** modal aparece quando há matches.
- **Depende de:** M027.

#### M060 — Bloqueio DESPACHADA + textarea motivo
- **Origem desktop:** `[RB-DESPACHADA]`.
- **O que fazer:** já tratado em M053 (`blocked="despachada"` mostra banner). Adicionalmente, quando `requires_motivo=true`, garantir que `#cad-row-motivo` fique visível até o usuário enviar texto não vazio (validação client-side antes de reenviar).
- **Critério de pronto:** textarea aparece e re-submit só ocorre com texto.
- **Depende de:** M003, M053.

#### M061 — Sidebar Validação ao vivo (4 checks)
- **Origem desktop:** lista da aba (informativo) + validar_campos_obrigatorios + regex.
- **O que fazer:** atualizar `data-check="*"` (M004) reagindo a `input`/`change` debounced 200 ms:
  - `obrigatorios` ← `validar_cadastro` (sem rede; cliente espelha lista mínima).
  - `alimentadores-sem-underscore` ← regex local.
  - `projeto-prefix-obra` ← warn se `#cad-input-projeto` começa com "Obra " (case-insensitive).
  - `cod-completo` ← `gerar_cod_pep` retorna `ok=true` (debounced).
- **Critério de pronto:** ícones mudam em tempo real conforme edição.
- **Depende de:** M004, M024, M040.

#### M062 — Sidebar "Última modificação"
- **Origem desktop:** N/A no desktop (informativo). No web, é diferencial.
- **O que fazer:** quando `applyObra` carrega, exibir `data_modificacao` + `usuario` da obra (já presentes no payload de `get_obra`). Em modo "nova obra", esconder o card.
- **Critério de pronto:** dados do banco aparecem ao editar.
- **Depende de:** M040.

---

### 3.D — Auto-preenchimento e derivações pesadas

#### M070 — Cache local de `dados_alimentador` no JS
- **O que fazer:** ao carregar Cadastro, chamar 1 vez `get_form_metadata` + lazy `get_alimentador_details` por demanda. Memoizar respostas por sessão.
- **Critério de pronto:** mudar alimentador 2x não dispara 2 chamadas para o mesmo.
- **Depende de:** M040.

#### M071 — Recalcular Subestações sempre que `principal` ou chips mudam
- Já coberto por M048 — fica como subitem se M048 ficar grande, senão merge.

#### M072 — Fallback `tensao_operacao = tensao` no save (server)
- Já implementado em `save_obra` (`main_web.py:1552-1670`). Confirmar e citar no STATE.

#### M073 — Geração de `cod` ao vivo (preview no header da aba)
- **O que fazer:** debounce 300 ms; chamar `gerar_cod_pep` toda vez que (PI, ano, item, pi_base) mudam; mostrar preview em badge "Nova obra"/"Editando COD-XX" no topo do card "Dados Básicos".
- **Critério de pronto:** preview reativo.
- **Depende de:** M040.

---

### 3.E — Modais — fluxo completo

#### M080 — Modal "Gerenciar PI_BASE" — funcional
- **Origem desktop:** `cadastro_mixin.py:18-218`.
- **O que fazer:** ao abrir `#modal-pi`, chamar `get_pi_base_map`. Renderizar lista. Botões:
  - **Adicionar:** prompt → validar (não vazio, não duplicado em padrão nem em custom) → `save_pi_base_map({add:nome})`.
  - **Renomear:** prompt pré-preenchido → mesmas validações → `save_pi_base_map({rename:{from,to}})`.
  - **Remover:** se item está em templates ou em map, abrir prompt secundário "Substituto:" com lista; depois `save_pi_base_map({remove:nome, replace:substituto?})`.
  - **Restaurar padrões:** modal de confirmação `Yes/No` (default No); se Yes → `save_pi_base_map({reset:true})`.
  - **Fechar:** apenas oculta o modal.
- **Critério de pronto:** os 5 fluxos persistem em `config.json` corretamente (verificar via diff do arquivo).
- **Depende de:** M007.

#### M081 — Modal "Selecionar PIs" (multi)
- Coberto por M047.

#### M082 — Modal "Buscar Projeto"
- Coberto por M056.

#### M083 — Folder picker "pasta de ganhos"
- **O que fazer:** botão na aba Configurações OU em "⚙ Configurações" da aba Cadastro (a definir). Ao clicar, chamar `pick_pasta_ganhos` (M023). Mostrar caminho atual em status.
- **Critério de pronto:** novo caminho persistido + visível em status bar.
- **Depende de:** M023.

---

### 3.F — Navegação "Atualizar Projeto"

#### M090 — Estado JS para Atualizar Projeto
- **Origem desktop:** `atualizar_obra_mixin.py` (não lido em detalhe; comportamento conhecido pela navbar).
- **O que fazer:** módulo `coplanCadastroProjeto` com:
  - `start(nome_projeto, tipo_pacote)` → chama `projeto_iniciar` (M030), recebe `obras[]`, `idx=0`, popula form com `obras[0]`, mostra navbar (`display:flex`) e atualiza `#cad-projeto-nav-info` ("1 de N").
  - `next()` → coleta payload atual, valida (`validar_cadastro`), grava em buffer local (`pendingPayloads[idx]`), avança `idx`, popula próxima obra.
  - `prev()` → idem para trás.
  - `cancelar()` → confirma "Descartar alterações?", esconde navbar, `clearForm`.
  - `finalizar()` → para cada `pendingPayloads`, chama `save_obra` em série; se algum falhar, parar, banner com lista. Se tudo OK, fechar navbar e refresh visualizar.
- **Critério de pronto:** ciclo completo testado manualmente em runtime.
- **Depende de:** M030, M053.

#### M091 — Bind dos botões da navbar
- **O que fazer:** `#cad-projeto-nav-prev` → `prev()`; `#cad-projeto-nav-next` → `next()`; `#cad-projeto-nav-cancelar` → `cancelar()`; `#cad-projeto-nav-finalizar` → `finalizar()`.
- **Critério de pronto:** clicar dispara handler correto.
- **Depende de:** M090.

#### M092 — Reuso de motivo ao longo do projeto
- **Origem desktop:** "modo atualizar projeto reutiliza motivo da primeira obra".
- **O que fazer:** quando primeiro `requires_motivo=true` no projeto, capturar motivo e injetar nas próximas chamadas `save_obra` do mesmo lote.
- **Critério de pronto:** segunda obra do projeto não pede motivo de novo.
- **Depende de:** M090.

---

### 3.G — Mensagens, toasts e copy

#### M100 — Catalogar todas as mensagens (i18n-friendly)
- **O que fazer:** centralizar em `coplanCadastro.MSG = {…}` os textos exatos da seção 1.8 do desktop:
  - `MSG.aviso.dados_alim_nao_carregados`
  - `MSG.aviso.alim_vazio_ou_duplicado`
  - `MSG.aviso.nenhuma_obra_no_projeto`
  - `MSG.aviso.nenhum_valor_unitario`
  - `MSG.aviso.despachada`
  - `MSG.aviso.nenhuma_atualizacao`
  - `MSG.erro.alim_underscore`
  - `MSG.erro.calc_item`
  - `MSG.erro.calc_valor`
  - `MSG.erro.carregar_projeto`
  - `MSG.erro.salvar`
  - `MSG.erro.cod_duplicado`
  - `MSG.erro.cod_item_duplicado`
  - `MSG.sucesso.atualizada`
  - `MSG.sucesso.criada`
  - `MSG.sucesso.merged`
  - `MSG.pergunta.gerar_descricao`
  - `MSG.pergunta.cod_alterado`
  - `MSG.prompt.motivo`
  - `MSG.tooltip.sem_underscore`
  - `MSG.label.nao_iniciar_obra`
- **Critério de pronto:** referenciado pelos M-itens; sem strings literais espalhadas.
- **Depende de:** —

#### M101 — Toaster reutilizável (3 níveis)
- **O que fazer:** componente JS `coplan.toast(level, msg)` com níveis `info|warn|error|success`.
- **Critério de pronto:** todos os banners do roadmap usam o toaster.
- **Depende de:** —

---

### 3.H — Persistência colateral

#### M110 — `caminho_pasta_ganhos` no `config.json`
- Coberto por M023 + M083.

#### M111 — Histórico de alterações (server-side)
- **Estado web:** já parcial em `save_obra` (aplica histórico).
- **O que fazer:** verificar que campos críticos disparam histórico no formato do desktop e que o motivo, quando exigido, vai para o histórico.
- **Critério de pronto:** após save com `motivo`, coluna `historico` (ou `observacoes`) contém entrada `[YYYY-MM-DD HH:MM] Campos: a, b, c | Motivo: …`.
- **Depende de:** M053, M060.

#### M112 — Backup automático (snapshot do `config.json` antes de mudanças PI_BASE)
- **Origem desktop:** observado em `_backups/config.<timestamp>.json` em `cadastro_viabilidades` — confirmar se COPLAN tem hábito similar. Se não tiver, item opcional/futuro.
- **Critério de pronto:** decisão registrada (implementar ou marcar fora-de-escopo no STATE).
- **Depende de:** M080.

---

### 3.I — Verificações finais (sem abrir o app)

#### M120 — Lint visual: todas as strings do catálogo M100 estão referenciadas
- **O que fazer:** grep por `MSG.` no JS; comparar com chaves declaradas; reportar órfãs.
- **Critério de pronto:** lista vazia.
- **Depende de:** todos os M040-M101.

#### M121 — Lint visual: todos os IDs de M001 estão referenciados pelo JS
- **O que fazer:** grep por cada id em `COPLAN_BRIDGE_JS`; reportar IDs não usados.
- **Critério de pronto:** zero IDs órfãos (ou registrados como "reserva visual" no STATE).
- **Depende de:** todos os M040-M091.

#### M122 — Cross-check 1.7 (mapeamento UI→coluna) ↔ payload de `save_obra`
- **O que fazer:** comparar dict canônico do desktop (`salvar_obra_service.py:151-219`) com o payload montado em M053. Apontar divergências.
- **Critério de pronto:** lista de divergências = ∅.
- **Depende de:** M053.

#### M123 — Cross-check 1.6 (regras [RB-…]) ↔ JS implementado
- **O que fazer:** para cada `[RB-…]`, indicar onde no JS foi tratado.
- **Critério de pronto:** tabela cobertura 100%.
- **Depende de:** M053, M060.

#### M124 — Documentar desvios conscientes
- **O que fazer:** se algum item do desktop não fizer sentido no web (ex.: enable_cadastro_fields agrupa group_dados+group_param que talvez não exista no web), registrar em STATE como "intencionalmente diferente".
- **Critério de pronto:** seção `desvios:` no STATE com ≥ 0 entradas explicadas.
- **Depende de:** —

---

## 4. Ordem de execução sugerida pelo loop

1. **Primeira leva (markup):** M001, M002, M003, M004, M005, M006, M007, M008, M009, M010.
2. **Segunda leva (backend):** M020, M021, M022, M023, M024, M025, M026, M027, M028, M029, M030.
3. **Terceira leva (helpers e bootstrap):** M040, M041, M100, M101.
4. **Quarta leva (interações simples):** M042, M043, M044, M045, M046, M049, M050, M070, M073.
5. **Quinta leva (chips e subestações):** M048, M072.
6. **Sexta leva (cálculo de valor + atalhos):** M051, M052.
7. **Sétima leva (salvar):** M053, M054, M055, M056, M057, M058, M059, M060.
8. **Oitava leva (sidebar):** M061, M062.
9. **Nona leva (PI_BASE, multi-PI, pasta):** M080, M081, M082, M083.
10. **Décima leva (atualizar projeto):** M090, M091, M092.
11. **Onze (persistência):** M111, M112.
12. **Doze (verificações finais):** M120, M121, M122, M123, M124.

---

## 5. Convenções para o loop

- **Sempre** atualizar `MIGRACAO_CADASTRO_STATE.md` ao terminar uma fatia.
- **Nunca** abrir o app (`pywebview`) durante o loop. Validação é por leitura de código + grep + diff.
- **Nunca** editar `codigo5_coplan.py` (memória `project_coplan_main_web.md`).
- Se um item cresce demais, quebrar em sub-itens `M0xxa`, `M0xxb` no STATE e seguir.
- Em caso de dúvida sobre regra de negócio, consultar a seção 1 deste documento — ela é congelada como referência canônica do desktop.
