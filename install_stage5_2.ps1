param(
    [string]$ProjectRoot = (Get-Location).Path
)
$ErrorActionPreference = 'Stop'
$PackageRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Не найден Python виртуального окружения проекта: $Python"
}
& $Python (Join-Path $PackageRoot 'install_stage5_2.py') --project-root $ProjectRoot --package-root $PackageRoot
if ($LASTEXITCODE -ne 0) { throw "Stage 5.2 installer failed with exit code $LASTEXITCODE" }
