# Build Windows -- COPLAN

Build do `Coplan.exe` (PyInstaller, one-folder) para Windows.

## Layout

```
_nina_ceo/builds/
  Coplan.spec               # spec do PyInstaller
  Coplan.exe.config         # .NET runtime config (loadFromRemoteSources)
  coplan_launcher.py        # entrypoint do .exe (chama main_web.main)
  build_windows_exe.ps1     # script principal (PowerShell)
  build_windows_exe.bat     # wrapper .bat (chama o .ps1)
  requirements-build.txt    # deps de build (pyinstaller, pythonnet, clr_loader)
  README.md                 # este arquivo
```

`requirements-web.txt` fica na raiz do repo e cuida das deps de runtime
(`pywebview`, `pandas`, `openpyxl`).

## Como rodar localmente

Em uma maquina Windows, com Python 3.10+ no PATH, a partir da raiz do
repositorio:

```powershell
.\_nina_ceo\builds\build_windows_exe.ps1
```

Ou via .bat:

```cmd
_nina_ceo\builds\build_windows_exe.bat
```

O script:

1. Cria/reaproveita `.venv-build\` na raiz do repo.
2. Instala `requirements-web.txt` (raiz) e `requirements-build.txt`.
3. Limpa `dist\` e `build\`.
4. Roda `pyinstaller _nina_ceo\builds\Coplan.spec`.
5. Copia `Coplan.exe.config` para dentro de `dist\Coplan\`.
6. Roda `Unblock-File` recursivo em `dist\Coplan\` (remove MOTW dos
   arquivos baixados do GitHub Actions / zip de distribuicao).

Bundle final: `dist\Coplan\Coplan.exe`.

## CI

`.github/workflows/build-windows.yml` roda o mesmo script em
`windows-latest` e publica `dist\Coplan\` como artifact.

## Notas tecnicas

### `_unblock_motw`

`coplan_launcher.py` faz `_unblock_motw(sys._MEIPASS)` na inicializacao.
A funcao varre recursivamente o diretorio temporario do PyInstaller e
apaga o ADS `Zone.Identifier` de todo `.dll` / `.exe` / `.pyd`. Sem isso,
em maquinas onde o `.exe` veio de zip baixado do navegador / network
share, o Windows recusa carregar as DLLs nativas do `pythonnet` /
WebView2 e o app trava na inicializacao.

### Paths patch

O launcher tambem reaponta `main_web.HTML_FILE` para o `Coplan UI.html`
extraido em `sys._MEIPASS`. O HTML e empacotado como `datas` no `.spec`.

`ConfigManager.CONFIG_FILE` **nao** e patchado: continua resolvendo via
`%LOCALAPPDATA%\COPLAN\config\config.json` tanto no .exe quanto rodando
do fonte. Esse comportamento e intencional (paridade com o app
desktop). Se um dia quisermos config portatil ao lado do .exe, e nesse
launcher que entra o override.

### `Coplan.exe.config`

Habilita `loadFromRemoteSources` no CLR (necessario quando o .exe esta
em pasta de rede / Zone Internet) e forca `supportedRuntime v4.0`,
exigido pelo `pythonnet`.

### Debug do webview

`main_web.main()` agora liga o DevTools do WebView2 quando:

- nao esta `frozen` (rodando do fonte), ou
- `COPLAN_DEBUG=1` esta setado no ambiente.

Para abrir o devtools em uma build de release, basta:

```cmd
set COPLAN_DEBUG=1
Coplan.exe
```
