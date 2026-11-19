$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$entryPoint = Join-Path $projectRoot "asistan beta.py"

if (-not (Test-Path -LiteralPath $entryPoint)) {
    throw "NetOps giris dosyasi bulunamadi: $entryPoint"
}

$pythonPath = $null
$python312 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
if (Test-Path -LiteralPath $python312) {
    $pythonPath = $python312
}

if (-not $pythonPath) {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            $candidate = (& $pyLauncher.Source -3.12 -c "import sys; print(sys.executable)").Trim()
            if ($candidate -and (Test-Path -LiteralPath $candidate)) {
                $pythonPath = $candidate
            }
        }
        catch {
            $pythonPath = $null
        }
    }
}

if (-not $pythonPath) {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $pythonPath = $python.Source
    }
}

if (-not $pythonPath) {
    throw "Python bulunamadi. Python 3.12 veya daha yeni bir surum kurulu olmali."
}

# This is the default launch path for today's native NetOps interface.
$env:NETOPS_QT_UI = "1"
$env:NETOPS_LEGACY_UI = "0"
$env:NETOPS_NATIVE_UI_EXPERIMENTAL = "1"
$env:NETO_ENABLE_STARTUP_UPDATE_CHECK = "1"

Push-Location $projectRoot
try {
    & $pythonPath $entryPoint
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
