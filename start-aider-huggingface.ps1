$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectRoot
$env:GIT_CEILING_DIRECTORIES = Split-Path -Parent $ProjectRoot

$AiderBin = Join-Path $env:USERPROFILE ".local\bin"
if (Test-Path -LiteralPath $AiderBin) {
    $env:PATH = "$AiderBin;$env:PATH"
}

if (-not $env:HUGGINGFACE_API_KEY) {
    Write-Host "HUGGINGFACE_API_KEY yok. Once bunu calistir:" -ForegroundColor Yellow
    Write-Host 'setx HUGGINGFACE_API_KEY "hf_xxxxx"' -ForegroundColor Cyan
    Write-Host "Sonra PowerShell'i kapatip yeniden ac." -ForegroundColor Yellow
    exit 1
}

$env:OPENAI_API_KEY = $env:HUGGINGFACE_API_KEY
$env:OPENAI_API_BASE = "https://router.huggingface.co/v1"

$Model = "openai/Qwen/Qwen2.5-Coder-7B-Instruct"

Write-Host "NetOps Aider basliyor: Hugging Face router" -ForegroundColor Green
Write-Host "Model: $Model" -ForegroundColor DarkGray

aider --config ".aider.conf.yml" --model $Model
