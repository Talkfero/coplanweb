# Diretrizes do projeto Coplan Web

## Busca inteligente (Visualizar)

A "Busca inteligente em todos os campos" deve cobrir **todos** os campos
relevantes da obra. Ao adicionar/alterar a busca textual global, garanta que o
campo de **alimentadores beneficiados** (`alim_benef` / coluna
`alimentadores_beneficiados`) esteja incluído no haystack.

- Web: `CoplanApi.search_obras` em `main_web.py` — a função `_haystack`
  precisa listar `alim_benef` junto dos demais campos.
- Desktop: `filter_table` em `ui/main_window/filtros_paginacao_mixin.py` —
  `global_string` precisa incluir `item_alimentadores_benef`.

## Campo de alimentadores beneficiados

O campo `alimentadores_beneficiados` armazena **múltiplos alimentadores
separados por `;`** (vírgula `,` também é aceita como separador). Sempre que
for parsear ou validar esse campo, use `re.split(r"[;,]", valor)` (ou
`[,;|\n]+` quando precisar tolerar pipe/quebra de linha, como na importação).
Não trate o conteúdo como um único alimentador.
