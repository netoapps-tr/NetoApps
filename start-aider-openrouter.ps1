$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot
$env:GIT_CEILING_DIRECTORIES = Split-Path -Parent $ProjectRoot

$AiderBin = Join-Path $env:USERPROFILE ".local\bin"
if (Test-Path -LiteralPath $AiderBin) {
    $env:PATH = "$AiderBin;$env:PATH"
}

if (-not $env:OPENROUTER_API_KEY) {
    Write-Host "OPENROUTER_API_KEY yok. Once bunu calistir:" -ForegroundColor Yellow
    Write-Host 'setx OPENROUTER_API_KEY "or_xxxxx"' -ForegroundColor Cyan
    Write-Host "Sonra PowerShell'i kapatip yeniden ac." -ForegroundColor Yellow
    exit 1
}

$Model = "openrouter/openrouter/free"

Write-Host "NetOps Aider basliyor: OpenRouter fallback" -ForegroundColor Green
Write-Host "Model: $Model" -ForegroundColor DarkGray

aider --config ".aider.conf.yml" --model $Model
