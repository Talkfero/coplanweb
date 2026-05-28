---
name: check-bridge-js
description: Valida a sintaxe dos modulos JS de `frontend/js/bridge/*.js` (que sao HTML-com-script, nao .js puros). Extrai os blocos `<script>...</script>`, concatena na ordem do `build_html()` e roda `node --check`. Use sempre que editar qualquer arquivo em `frontend/js/bridge/` antes de commitar, ou quando o usuario pedir para validar/checar o bundle do bridge.
---

# Check Bridge JS

Os arquivos em `frontend/js/bridge/*.js` sao HTML — cada bloco IIFE vive
dentro de `<script>...</script>`. O `build_html()` (`backend/api.py`) le esses
arquivos em **ordem alfabetica** (o prefixo numerico define a ordem),
concatena **sem separador** e injeta antes de `</body>`.

Validar so o `.js` cru com `node --check` falha porque a sintaxe inclui
`<script>`. A skill extrai os blocos antes de checar.

## Comando

Roda em todos os bridges:

```bash
python3 -c "
import re, glob
files = sorted(glob.glob('frontend/js/bridge/*.js'))
out = []
for f in files:
    s = open(f).read()
    out.extend(re.findall(r'<script>(.*?)</script>', s, re.S))
open('/tmp/_bridge.js','w').write('\n;\n'.join(out))
print('wrote', len(out), 'script block(s) from', len(files), 'file(s)')
" && node --check /tmp/_bridge.js && echo "JS SYNTAX OK"
```

Para validar um arquivo especifico (mais rapido, escopo do diff):

```bash
F=frontend/js/bridge/40-resumo.js
python3 -c "
import re, sys
s = open(sys.argv[1]).read()
blocks = re.findall(r'<script>(.*?)</script>', s, re.S)
open('/tmp/_one.js','w').write('\n;\n'.join(blocks))
" "$F" && node --check /tmp/_one.js && echo "JS SYNTAX OK"
```

## Notas

- Erros do `node --check` mostram linha/coluna do bundle concatenado em
  `/tmp/_bridge.js`, nao do arquivo fonte — abra o `/tmp/_bridge.js` para
  localizar o trecho ofensivo e mapear de volta ao fonte.
- Se `node` nao estiver disponivel, instale via gerenciador do SO
  (`apt-get install nodejs`) ou rode em ambiente que ja tenha.
- A skill nao roda o app — so checa sintaxe. Erros de runtime (uso de
  identificador nao definido, etc.) nao sao pegos aqui.
