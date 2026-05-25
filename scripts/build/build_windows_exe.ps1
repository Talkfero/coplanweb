#requires -Version 5.1
<#
.SYNOPSIS
    Build script para gerar o Coplan.exe (PyInstaller, modo one-folder).

.DESCRIPTION
    1. Cria/usa um virtualenv local em .venv-build/.
    2. Instala requirements-web.txt + requirements-build.txt.
    3. Roda PyInstaller contra Coplan.spec.
    4. Copia Coplan.exe.config para dentro do dist\Coplan\.
    5. Roda Unblock-File recursivo no dist\Coplan\ para remover MOTW.

.NOTES
    Deve ser executado a partir da raiz do repositorio (ou de qualquer
    diretorio -- o script normaliza). Requer Python 3.10+ no PATH.
#>

[CmdletBinding()]
param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir "..\..")
$VenvDir   = Join-Path $RepoRoot ".venv-build"
$DistDir   = Join-Path $RepoRoot "dist"
$BuildDir  = Join-Path $RepoRoot "build"
$SpecFile  = Join-Path $ScriptDir "Coplan.spec"
$ConfigSrc = Join-Path $ScriptDir "Coplan.exe.config"

Write-Host "==> Repo root: $RepoRoot"
Write-Host "==> Spec file: $SpecFile"

Push-Location $RepoRoot
try {
    if (-not (Test-Path $VenvDir)) {
        Write-Host "==> Criando venv em $VenvDir"
        & $Python -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "falha ao criar venv" }
    }

    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        throw "venv python nao encontrado em $VenvPython"
    }

    Write-Host "==> Atualizando pip"
    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "falha ao atualizar pip" }

    $ReqWeb   = Join-Path $RepoRoot "requirements-web.txt"
    $ReqBuild = Join-Path $ScriptDir "requirements-build.txt"

    if (Test-Path $ReqWeb) {
        Write-Host "==> Instalando $ReqWeb"
        & $VenvPython -m pip install -r $ReqWeb
        if ($LASTEXITCODE -ne 0) { throw "falha ao instalar requirements-web" }
    }

    Write-Host "==> Instalando $ReqBuild"
    & $VenvPython -m pip install -r $ReqBuild
    if ($LASTEXITCODE -ne 0) { throw "falha ao instalar requirements-build" }

    if (Test-Path $DistDir)  { Write-Host "==> Limpando $DistDir";  Remove-Item -Recurse -Force $DistDir }
    if (Test-Path $BuildDir) { Write-Host "==> Limpando $BuildDir"; Remove-Item -Recurse -Force $BuildDir }

    Write-Host "==> Rodando PyInstaller"
    & $VenvPython -m PyInstaller --noconfirm --clean $SpecFile
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

    $BundleDir = Join-Path $DistDir "Coplan"
    if (-not (Test-Path $BundleDir)) {
        throw "bundle nao encontrado em $BundleDir"
    }

    Write-Host "==> Copiando Coplan.exe.config para $BundleDir"
    Copy-Item $ConfigSrc (Join-Path $BundleDir "Coplan.exe.config") -Force

    Write-Host "==> Unblock-File recursivo em $BundleDir"
    Get-ChildItem -Path $BundleDir -Recurse -File | Unblock-File

    Write-Host ""
    Write-Host "==> Build OK. Bundle em: $BundleDir"
}
finally {
    Pop-Location
}
