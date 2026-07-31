param(
    [int]$Port = 8000,
    [switch]$Reload,
    [switch]$Install,
    [switch]$SkipDoctor
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepositoryRoot

$Candidates = @(
    (Join-Path $RepositoryRoot "venv\Scripts\python.exe"),
    (Join-Path $RepositoryRoot ".venv\Scripts\python.exe")
)
$Python = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) {
    $Python = "python"
}

Write-Host "Python: $Python"

if ($Install) {
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r requirements-dev.txt
}

if (-not $SkipDoctor) {
    & $Python -m commands.doctor --prepare-assets
    if ($LASTEXITCODE -ne 0) {
        throw "O diagnóstico encontrou requisitos obrigatórios pendentes."
    }
}

$Arguments = @("-m", "commands.studio", "--port", "$Port")
if ($Reload) {
    $Arguments += "--reload"
}

& $Python @Arguments
exit $LASTEXITCODE
