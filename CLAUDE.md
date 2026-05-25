# Diretrizes do projeto Coplan Web

> Escopo deste arquivo: a **aplicação WEB** (`main_web.py` + `runtime/`,
> `core/`, `data_access_layer.py`, `ui_helpers.py`, `texto_utils.py`,
> `Coplan UI.html`). O desktop (`codigo5_coplan.py`, `ui/main_window/*_mixin.py`,
> PySide6) é legado reaproveitado como biblioteca de managers; não é o foco aqui.

## Arquitetura (web)

- **Framework**: `pywebview` (não é Flask/FastAPI). Entrypoint em
  `main_web.py:main()` (`main_web.py:29955`), que cria a janela
  (`webview.create_window`, `main_web.py:29973`) e inicia com
  `webview.start(debug=debug)`.
- **Front-end**: `Coplan UI.html` (single-page HTML/CSS/JS). O JS é injetado em
  memória (bridge `window.coplanBridge`) e chama o backend via
  `window.pywebview.api.<metodo>()`.
- **Backend**: classe `CoplanApi` (`main_web.py:126`). Todos os métodos públicos
  são expostos ao JS via `js_api`. Managers do legado (`DatabaseManager`,
  `SupportFileManager`, `CalculationManager`, `ConfigManager`) são carregados de
  forma **lazy** em `_ensure_managers()`, com locks para thread-safety. Não
  importe esses managers no topo do módulo — siga o padrão lazy/local import.
- **Banco**: SQLite. Tabela principal `obras`. Caminho vem de `config.json`
  (`["obras"]`). `data_access_layer.py` provê cache em memória das obras
  (`DataAccessLayer`: `load_cache`, `get_rows`, `get_by_cod`,
  `count_tecnico_dirty`, etc.), ordenando por `ano_, nome_projeto, codigo_item`.

## Como rodar

```bash
pip install -r requirements-web.txt   # pywebview, pandas, openpyxl, PySide6
python main_web.py
```

Debug do pywebview liga se não estiver "frozen" ou se `COPLAN_DEBUG=1`.
Não há suíte de testes nem config de lint no repositório — as supressões são
inline (`# noqa: BLE001`, `# noqa: PLC0415`, `# noqa: E731`).

## Convenções de código (web)

- **Contrato de retorno**: todo método da API devolve um `dict` com no mínimo
  `{"ok": bool, "error": str, ...}`. Mantenha esse formato; o front depende dele.
  Nunca deixe exceção vazar para o bridge — capture e retorne `{"ok": False,
  "error": ...}` (`# noqa: BLE001` é o padrão aceito para o except amplo).
- **Imports locais/lazy** dentro dos métodos para módulos do legado
  (`from codigo5_coplan import ...  # type: ignore[import-not-found]`,
  `# noqa: PLC0415`). Evita custo de Qt/SQLite no import e quebra de
  dependência opcional.
- **Helpers compartilhados** (reaproveite, não reimplemente):
  - `ui_helpers.matches_filter_value` — multi-termo (`;`/`,`), semântica
    "contém".
  - `ui_helpers.matches_cod_terms` — COD: match exato para números, "contém"
    para termos alfabéticos.
  - `ui_helpers.paginate_items` — paginação.
  - `texto_utils.normalize_key` / `normalize_text` — remove acento, uppercase.
- **`@staticmethod`** para utilitários puros (`_row_to_dict`, `_fmt_pi`,
  `_split_terms`, `_to_float_brl`, etc.).
- **Tags de código** usadas em comentários para rastrear paridade/regra:
  `[B6]` (alimentadores beneficiados), `[G0xx]` (ganhos), `[M027]` (duplicidade
  semântica), `[RB-*]` (regra de negócio), `[FIX]`. Mantenha o padrão ao mexer
  nas áreas correspondentes.
- **Operações longas**: estado global `_OP_STATE` + helpers `_op_*`; worker em
  thread atualiza progresso e o JS faz polling em `progress_state()`.

## Busca inteligente (search_obras / Visualizar)

A "Busca inteligente em todos os campos" deve cobrir **todos** os campos
relevantes da obra. Ao adicionar/alterar a busca textual global, garanta que o
campo de **alimentadores beneficiados** (`alim_benef` / coluna
`alimentadores_beneficiados`) esteja incluído no haystack.

- Web: `CoplanApi.search_obras` em `main_web.py` — a função `_haystack` precisa
  listar `alim_benef` junto dos demais campos (`cod, ano, pi, projeto, alim,
  alim_benef, se, regional, pacote`).
- Desktop (legado): `filter_table` em
  `ui/main_window/filtros_paginacao_mixin.py` — `global_string` precisa incluir
  `item_alimentadores_benef`.

## Regras de domínio

### Campo de alimentadores beneficiados
`alimentadores_beneficiados` armazena **múltiplos alimentadores separados por
`;`** (vírgula `,` também é aceita). Sempre parseie com `re.split(r"[;,]",
valor)` (ou `[,;|\n]+` para tolerar pipe/quebra de linha, como na importação).
Não trate o conteúdo como um único alimentador.

### Alimentadores: proibição de `_`
Nem `alimentador_principal` nem os itens de `alimentadores_beneficiados` podem
conter sublinhado (`_`). Mensagem ao usuário: "Alimentador contem '_' (nao
permitido)".

### Derivação de subestação
A subestação é derivada do **prefixo** do alimentador, antes do primeiro `-`,
`_` ou `/`, em uppercase. Ex.: `ATB-204` → `ATB`
(`re.split(r"[-_/]", a, 1)[0].strip().upper()`).

### COD da obra (`gerar_cod_pep`)
Formato `SIGLA-YY-PI-ITEM` (ex.: `MA-26-DI-047`). Componentes:
- **SIGLA**: `config.empresa_sigla` (default `MA`). Siglas válidas:
  `texto_utils.EMPRESA_SIGLAS_VALIDAS = {MA, PA, PI, AL, RS, AP, GO}`.
- **YY**: dois últimos dígitos de `ano_`.
- **PI**: `pi_base` informado ou derivado de `projeto_investimento` via
  `get_pi_base`; uppercase.
- **ITEM**: zero-padded a 3 dígitos se totalmente numérico.

Este é o COD da coluna `obras.cod`, **não** o COD_PEP sequencial pós-aprovação.

### Campos obrigatórios no `save_obra`
`_CAMPOS_OBRIGATORIOS_SAVE` (`main_web.py:445`): `ano_`,
`projeto_investimento`, `alimentador_principal`, `quantidade_material`,
`coordenada_fim`, `tipo_pacote`, `caracteristicas_material`, `manobra`. Além
disso, `nome_projeto` é obrigatório quando `pi_base` ∈ {DISTRIBUIÇÃO,
DISTRIBUIÇÃO LD 34,5 KV}. A validação é refeita no backend mesmo que o JS já
valide (defense-in-depth). `descricao_obra` não pode iniciar com "Obra".

### Flags `obra_aprovada` e `tecnico_dirty`
Strings `'SIM'`/`'NAO'`, default `'NAO'` ao salvar. `tecnico_dirty == 'SIM'`
indica snapshot técnico desatualizado (valor/ganhos precisam recálculo); o
header mostra a contagem via `count_tecnico_dirty()`.

### PI / Projeto de Investimento
Metadados em `core/services/pi_metadata_service.py` (DISTRIBUIÇÃO,
MELHORAMENTOS, TRIFASEAMENTO, BRT, BC, RTO, DISTRIBUIÇÃO LD 34,5 KV, TRAFO RD),
cada um com `abreviacao`, `tipo_base`, `descricao_template`,
`calculo.modulo_extra`, `exige_aterramento`. PI exibido = `pi_base` +
`codigo_item` (`_fmt_pi`).

### Cálculo de `valor_obra` (`calcular_valor_obra`)
Usa tabela de módulos (Excel de preços) + extras do PI (`modulo_extra`,
`ATERRAMENTO` se `exige_aterramento`) + `regional_map`. Delega a
`core.services.atualizar_obra_service`. Retorna `valor`, `valor_formatado`
(pt-BR "1.234,56"), `chave`, `motivos_falha`. Parsing pt-BR via `_to_float_brl`.

### Detecção de duplicidade (`[M027]`)
`obras_por_codigo_semelhante` usa chave semântica alimentador + PI + ano +
município (+ descrição) via `find_duplicate_in_db`.

### Cenários (planejamento CAPEX)
Quando `config["cenario_ativo"]` não é vazio:
- As obras são filtradas às presentes em `cenarios_obras`.
- Overrides por campo aplicados de `cenario_obras_overrides`.
- `ano_final` substitui `ano_` salvo override.
- **Bloqueado**: criar obra nova, excluir obra; edições são redirecionadas para
  `cenario_obras_overrides` (não gravam direto em `obras`).

### Critérios de planejamento / Ganhos
`get_criterios` mescla `DEFAULT_CRITERIOS` com
`config["criterios_planejamento"]` (regras declarativas comparando tensão
min/max, carregamento, CHI, CI). `avaliar_ganhos_planejamento` espelha o
`_obra_atende` do desktop e retorna `{ok, atende, motivos}`. Campos de ganhos
antes/depois/atual definidos em `core/services/obra_rules.py`
(`GANHOS_ANTES_FIELDS`, `GANHOS_DEPOIS_FIELDS`).

### Auditoria de mudanças
`CAMPOS_CRITICOS_MUDANCA` (`core/services/obra_rules.py`): `pi_base`, `ano_`,
`tipo_pacote`, `alimentador_principal`, `municipio`, ganhos totais,
`criterios_status`, `descricao_obra`. Mudanças exigem motivo e vão ao histórico.
Exclusão excepcional de obra aprovada é logada (`register_exclusao_excepcional`).
