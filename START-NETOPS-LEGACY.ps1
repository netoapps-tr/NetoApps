$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$legacyRoot = Join-Path $projectRoot "_release_staging_20261024-170109\NetOps-Zenkamind-Merge-v1.42.0"
$entryPoint = Join-Path $legacyRoot "asistan beta.py"

if (-not (Test-Path -LiteralPath $entryPoint)) {
    throw "Eski NetOps giris dosyasi bulunamadi: $entryPoint"
}

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}
if (-not $python) {
    throw "Python bulunamadi. Python 3.12 veya daha yeni bir surum kurulu olmali."
}

# The preserved v1.42 desktop is the product entry point. The native shell is
# kept available only as a separately approved experiment.
$env:NETOPS_QT_UI = "0"
$env:NETOPS_LEGACY_UI = "1"
$env:NETOPS_NATIVE_UI_EXPERIMENTAL = "0"
$env:NETO_ENABLE_STARTUP_UPDATE_CHECK = "1"

Push-Location $legacyRoot
try {
    & $python.Source $entryPoint
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
