# Diretrizes do projeto Coplan Web

> Escopo deste arquivo: a **aplicação WEB** (`main_web.py` + `backend/`,
> `runtime/`, `core/`, `shared/`, e a pasta `frontend/`).
> O desktop (`legacy_desktop/codigo5_coplan.py`, `legacy_desktop/ui/*_mixin.py`,
> PySide6) é legado e **não** é mais importado pela web; não é o foco aqui.
>
> **Layout de pastas**: a raiz contém só `main_web.py` (entrypoint) + pastas:
> `backend/` (`api.py`, `_state.py`, `domains/*.py`), `core/`, `runtime/`,
> `shared/` (utils puros: `ui_helpers.py`, `texto_utils.py`,
> `visualizar_pagination.py`), `frontend/` (`index.html`, `js/coplan_bridge.js`,
> `assets/`), `legacy_desktop/` (desktop Qt legado), `docs/`, `scripts/build/`.

## Arquitetura (web)

- **Framework**: `pywebview` (não é Flask/FastAPI). Entrypoint em
  `main_web.py:main()`, que cria a janela (`webview.create_window`) e inicia com
  `webview.start(debug=debug)`.
- **Front-end**: `frontend/index.html` (HTML/CSS + JS de UX básico). A camada de
  UI em JavaScript fica em `frontend/js/coplan_bridge.js` e é injetada em memória
  por `build_html()` (lê o HTML + o JS do disco e anexa o JS antes de `</body>`;
  nunca modifica os arquivos). O JS chama o backend via
  `window.pywebview.api.<metodo>()`.
- **Backend**: classe `CoplanApi` em `backend/api.py`, **composta por mixins de
  domínio** em `backend/domains/*.py` (`core`, `obras`, `apoio`, `valor`,
  `cadastro`, `tecnico`, `ganhos`, `criterios`, `resumos`, `config`, `banco`,
  `calc`, `nota_colapso`, `cenarios`, `validacoes`). `CoreMixin` (vem primeiro no
  MRO) tem o `__init__`, o estado de sessão e as constantes de classe. Estado de
  módulo compartilhado (progress `_OP_*`, `APP_VERSION`, `HERE`) está em
  `backend/_state.py`. Todos os métodos públicos (sem `_`) são expostos ao JS via
  `js_api` — **os nomes são o contrato com o front; não renomeie ao reorganizar**.
  Managers do legado (`DatabaseManager`, `SupportFileManager`,
  `CalculationManager`, `ConfigManager`) são carregados de forma **lazy** em
  `_ensure_managers()` (`backend/domains/core.py`), com locks para thread-safety.
  Mantenha o padrão lazy/local import dentro dos métodos.
- **Banco**: SQLite. Tabela principal `obras`. Caminho vem de `config.json`
  (`["obras"]`). A camada de acesso é `core/repositories/obra_read_repo.py`
  (`ObraReadRepo`, aliased como `DataAccessLayer`): cache em memória das obras
  (`load_cache`, `get_rows`, `get_by_cod`, `count_tecnico_dirty`, etc.),
  ordenando por `ano_, nome_projeto, codigo_item`.

## Como rodar

```bash
pip install -r requirements-web.txt   # pywebview, pandas, openpyxl (SEM PySide6)
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
- **Imports locais/lazy** dentro dos métodos para os managers/helpers do
  legado. Importe **direto de `runtime.*`/`core.*`** (a origem real), não de
  `codigo5_coplan` — ex.: `from runtime.config import ConfigManager`,
  `from runtime.database import DatabaseManager`, `from runtime.pi_base import
  get_pi_base`, `from runtime.calc import CalculationManager` (todos com
  `# noqa: PLC0415`). A web **não** importa mais `codigo5_coplan` (esse shim só
  serve ao desktop). Evita custo no import e quebra de dependência opcional.
- **Helpers compartilhados** (reaproveite, não reimplemente):
  - `shared.ui_helpers.matches_filter_value` — multi-termo (`;`/`,`), semântica
    "contém".
  - `shared.ui_helpers.matches_cod_terms` — COD: match exato para números, "contém"
    para termos alfabéticos.
  - `shared.ui_helpers.paginate_items` — paginação.
  - `shared.texto_utils.normalize_key` / `normalize_text` — remove acento, uppercase.
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

- Web: `CoplanApi.search_obras` em `backend/domains/obras.py` — a função `_haystack` precisa
  listar `alim_benef` junto dos demais campos (`cod, ano, pi, projeto, alim,
  alim_benef, se, regional, pacote`).
- Desktop (legado): `filter_table` em
  `legacy_desktop/ui/main_window/filtros_paginacao_mixin.py` — `global_string` precisa incluir
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
  `shared.texto_utils.EMPRESA_SIGLAS_VALIDAS = {MA, PA, PI, AL, RS, AP, GO}`.
- **YY**: dois últimos dígitos de `ano_`.
- **PI**: `pi_base` informado ou derivado de `projeto_investimento` via
  `get_pi_base`; uppercase.
- **ITEM**: zero-padded a 3 dígitos se totalmente numérico.

Este é o COD da coluna `obras.cod`, **não** o COD_PEP sequencial pós-aprovação.

### Campos obrigatórios no `save_obra`
`_CAMPOS_OBRIGATORIOS_SAVE` (constante de classe em `backend/domains/core.py`): `ano_`,
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
