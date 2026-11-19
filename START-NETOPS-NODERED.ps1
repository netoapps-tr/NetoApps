[CmdletBinding()]
param(
    [int]$Port = 1880
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$flowSource = Join-Path $root "tools\nodered\netops-flow.json"
$localAppData = $env:LOCALAPPDATA
if ([string]::IsNullOrWhiteSpace($localAppData)) {
    $localAppData = Join-Path $HOME "AppData\Local"
}
$userDir = Join-Path $localAppData "NetOps\NodeRed"
New-Item -ItemType Directory -Force -Path $userDir | Out-Null
$flowTarget = Join-Path $userDir "flows.json"
if (-not (Test-Path -LiteralPath $flowTarget)) {
    Copy-Item -LiteralPath $flowSource -Destination $flowTarget
}

$nodeRed = Get-Command node-red.cmd -ErrorAction SilentlyContinue
if ($null -eq $nodeRed) { $nodeRed = Get-Command node-red -ErrorAction SilentlyContinue }
if ($null -eq $nodeRed) {
    $npmPrefix = npm prefix --global 2>$null
    if ($LASTEXITCODE -eq 0) {
        $candidate = Join-Path ($npmPrefix | Select-Object -Last 1) "node-red.cmd"
        if (Test-Path -LiteralPath $candidate) {
            $nodeRed = Get-Item -LiteralPath $candidate
        }
    }
}
if ($null -eq $nodeRed) { throw "Node-RED bulunamadı. npm install --global --omit=optional node-red çalıştırın." }

Write-Host "NetOps yerel Node-RED akışı başlatılıyor: http://127.0.0.1:$Port"
$nodeRedPath = if ($nodeRed.PSObject.Properties.Name -contains "Source") { $nodeRed.Source } else { $nodeRed.FullName }
& $nodeRedPath --userDir $userDir --port $Port
