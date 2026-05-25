# COPLAN — Handoff de UI

Documento de referência para reimplementar a interface visual do mock
`Coplan UI.html` em cima do código existente. Use junto com o Claude Code.

---

## 1. Visão geral

Aplicação interna de planejamento de obras elétricas. A interface é
organizada em **5 áreas principais** acessíveis por uma sidebar fixa,
com um header global de status de fontes de dados e uma barra inferior
com informações da sessão.

**Stack visual sugerida** (independente de framework):
- Tipografia: Inter (UI), JetBrains Mono (códigos, valores numéricos, paths)
- Densidade: confortável-densa (linhas de tabela ~32px, base 13px)
- Paleta: azul institucional profundo + neutros + accents semânticos

---

## 2. Tokens de design

```css
/* Cores */
--bg:           oklch(0.985 0.003 250);   /* fundo da página */
--surface:      #ffffff;                  /* cards, header */
--surface-2:    oklch(0.975 0.004 250);   /* hover suave, header de tabela */
--surface-3:    oklch(0.955 0.006 250);   /* hover de botão ghost */
--border:       oklch(0.91 0.01 250);
--border-strong:oklch(0.85 0.012 250);

--text:         oklch(0.22 0.02 255);
--text-muted:   oklch(0.5 0.02 255);
--text-soft:    oklch(0.62 0.015 255);

--primary:      oklch(0.32 0.07 255);     /* sidebar, header titles */
--primary-2:    oklch(0.27 0.075 255);
--accent:       oklch(0.55 0.13 250);     /* ações primárias, links */

--success:      oklch(0.62 0.13 155);
--warning:      oklch(0.75 0.14 85);
--danger:       oklch(0.58 0.18 25);
--info:         oklch(0.6 0.13 230);

/* Forma */
--radius:    8px;
--radius-sm: 6px;
--radius-lg: 12px;

/* Sombra */
--shadow-sm: 0 1px 2px rgba(15,23,42,.04);
--shadow-md: 0 4px 12px rgba(15,23,42,.06);
--shadow-lg: 0 12px 32px rgba(15,23,42,.12);
```

**Equivalentes em Qt (PySide6) / outras stacks**:
copie os hex resolvidos do `Coplan UI.html` (use o devtools do navegador
para extrair, ou peça ao Claude Code: "converta os tokens oklch deste
arquivo para hex").

---

## 3. Estrutura do shell

```
┌──────────┬───────────────────────────────────────────────┐
│          │  HEADER (52px)                                │
│ SIDEBAR  │  toggle | breadcrumb · título | source-pills  │
│ (240px)  │         | ações globais | Salvar              │
│          ├───────────────────────────────────────────────┤
│ logo     │                                               │
│          │                MAIN (scroll)                  │
│ Operação │                                               │
│ • Visual │   conteúdo da aba ativa                       │
│ • Cadast │                                               │
│ • Ganhos │                                               │
│ • Resumo │                                               │
│          │                                               │
│ Sistema  │                                               │
│ • Config │                                               │
│ • PI     │                                               │
│ • Ajuda  ├───────────────────────────────────────────────┤
│          │ STATUS BAR (32px)                             │
│ user     │ conexão · banco · apoio · usuário · versão    │
└──────────┴───────────────────────────────────────────────┘
```

- Sidebar **colapsável** (toggle no header) → 240px ↔ 64px
- Source pills no header com 3 estados: `ok` (verde), `warn` (amarelo),
  `err` (vermelho). Mostram nome do arquivo/conexão.
- Status bar fixa: pulso verde de conexão, paths em mono, contador de
  seleção, versão.

---

## 4. Telas (abas)

### 4.1 Visualizar Obras
**Função**: listar e filtrar obras do banco.

Componentes:
- 4 stat cards (obras, aprovadas, pendentes, valor planejado)
- Filter bar com busca global (atalho `Ctrl+F`) + botão "Filtros avançados" + "Colunas" + "Limpar"
- Filter chips ativos (clicáveis para remover)
- Tabela densa com colunas: `[ ]` checkbox, COD, Ano, PI, Projeto,
  Alimentador, SE, Regional, Pacote, Valor (R$), Critérios, Aprovada,
  Téc. (snapshot), `⋮`
- Toolbar da tabela: Atualizar, Detalhamento, Relatório Critérios,
  Nota de Colapso, Excluir
- Linhas em vermelho quando obra não atendeu critérios
- Paginação com seletor de itens por página

**Ações que precisam virar handlers reais**:
| UI | Backend |
|---|---|
| Busca global | full-text nos campos visíveis |
| Filtros avançados (modal) | WHERE composto na query |
| Detalhamento | export para Excel da seleção |
| Relatório Critérios | gera PDF/XLSX com obras que falharam |
| Nota de Colapso | gera doc baseado em template |
| Excluir (linha selecionada) | DELETE com confirmação |

### 4.2 Cadastro de Obras
**Função**: criar/editar uma obra completa.

Layout 2 colunas: formulário (esquerda) + painel lateral (direita)
com Validação, Última modificação, Atalhos.

Seções do formulário (cards separados):
1. **Dados Básicos** — Ano, Projeto de Investimento, Item, Projeto, Nome do Projeto, Observações
2. **Informações Técnicas** — Alimentador Obra, Tensão Obra/Operação, Regional, Superintendência, SE, Coordenadas De/Para, Quantidade (km), Manobra, Características, Novo Bay?, Criticidade, Pacote
3. **Dados Financeiros** — Aprovada (NÃO/SIM), Valor da Obra, COD_PEP gerado (readonly)
4. **Alimentadores e Subestações Beneficiadas** — multi-select com chips, SE derivada automaticamente

Atalho: `Ctrl+B` salva.

### 4.3 Ganhos
**Função**: comparar parâmetros antes/depois para validar critérios.

- Card com path da pasta de ganhos do alimentador (selecionar/recarregar)
- Tabela editável: Parâmetro | Antes | Depois | Δ | Critério
  - Parâmetros: Contas, Carregamento, Perdas, Tensão Média, Tensão Min, Tensão Linha Min, CHI, CI, Tensão Máxima, Ganhos Totais
  - Δ calculado automaticamente
  - Status (OK/Falhou) lido do critério vigente em Configurações
- Card "Ganhos Atuais" com mín/máx tensão, carregamento, ganhos totais
- Card lateral "Critérios de Planejamento" (snapshot do que está sendo aplicado) com recomendações

**Ações**: Inserir Ganhos Antes/Depois (lê arquivo), Ganhos em Massa
(modal para várias obras), Preencher parâmetros atuais.

### 4.4 Resumo / Volumetria
**Função**: visão executiva agregada.

Subnav: Volumetria & Financeiro · Resumo Regional · Detalhamento

- Linha de 5 KPIs: CAPEX, Obras planejadas, Km de rede, Contas beneficiadas, Postergações
- Bar chart (Volumetria por Regional)
- Lista de Pacotes com %
- Tabela completa com totais por regional + footer agregado

### 4.5 Configurações
Subnav: Geral · Critérios de Planejamento · Templates · PI_BASE · Regional Map

- Empresa (sigla, razão social, paths de banco e apoio)
- Preferências de UI (toggles)
- Critérios de Planejamento (8 campos numéricos: tensão min/max, carregamento, CHI, CI, piora mercado, horizonte, postergação)
- Mapa Regional (tabela com Regional, Superintendência, prefixos SE, cor)

---

## 5. Convenções de copy

- **Booleanos** em UI: `SIM` / `NÃO` (caixa alta) — não use checkmarks soltos.
- **Códigos** sempre em mono: COD, PI, SE, alimentador.
- **Valores monetários**: `R$ 2.487.500,00` (pt-BR).
- **Tensão**: `0,93 pu`. **Carregamento**: `78,4%`.
- **Critérios**: usar o operador (`≥ 0,93`, `≤ 80%`).

---

## 6. Roteiro sugerido para o Claude Code

Cole isso no Claude Code, **um passo por vez**:

### Passo 1 — Tokens e tema
> Olhando `Coplan UI.html`, extraia o sistema de design (cores, tipografia,
> raio, sombras) e crie um arquivo de tema no formato adequado ao meu
> projeto ([Qt stylesheet / CSS / styled-components / etc]). Não toque
> em nenhuma lógica ainda.

### Passo 2 — Shell
> Implemente o shell (sidebar + header + status bar) no meu app,
> idêntico ao `Coplan UI.html`. As abas podem ficar vazias por enquanto.
> Mantenha a navegação funcional (clicar troca de aba).

### Passo 3 — Visualizar Obras
> Implemente a aba Visualizar Obras conectada ao banco real
> (`[caminho do arquivo .db]`, tabela `obras`). Replique colunas,
> filtros e badges do mock. A busca e os filtros avançados devem
> gerar SQL real, não filtrar em memória se a tabela for grande.

### Passo 4 — Cadastro
> Implemente a aba Cadastro replicando o formulário do mock. Os campos
> devem mapear para a tabela `obras` (faça o mapeamento explícito comigo
> antes de implementar). Inclua validações: campos obrigatórios,
> coordenadas no formato lat,lng, COD_PEP gerado a partir de Sigla+Ano+PI+Item.

### Passo 5 — Ganhos
> Implemente a aba Ganhos. A pasta de arquivos do alimentador deve ser
> lida real ([describe formato dos arquivos: xlsx, csv, etc]).
> Os critérios devem vir das configurações.

### Passo 6 — Resumo
> Implemente a aba Resumo com queries agregadas no banco. Não invente
> dados — se algo não existe ainda, marque com TODO.

### Passo 7 — Configurações
> Implemente Configurações persistindo num arquivo local
> (`config.json` ou tabela `config` no banco — o que for mais alinhado
> ao projeto).

---

## 7. O que **não** trazer do mock

- Os dados de exemplo (ATB-204, MA-26-DI-047, etc) são fictícios.
- A geração aleatória de obras (`generateObras`) é só para demo.
- Toasts e modais de exemplo: replique a UI mas conecte às ações reais.

---

## 8. Quando voltar a iterar visualmente

- Edite `Coplan UI.html` (ou peça novas variantes aqui)
- Exporte de novo
- Diga ao Claude Code: "atualize o visual do app conforme o novo
  `Coplan UI.html`, mantendo a lógica intacta"

A separação **mock visual ↔ código real** mantém as iterações de design
rápidas sem mexer em backend.
