#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$NetOpsExePath = ""
)

$ErrorActionPreference = "Stop"
$accountName = "NetOps"
$taskPath = "\NetOps\"
$taskName = "NetOps-AutoStart"

# Resolve from the script location, not from the PowerShell current directory.
# This also works when the script is launched from C:\Windows\System32.
if ([string]::IsNullOrWhiteSpace($NetOpsExePath)) {
    $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
    $NetOpsExePath = Join-Path $scriptRoot "dist\NetOps\NetOps.exe"
}
$NetOpsExePath = [System.IO.Path]::GetFullPath($NetOpsExePath)

if (-not (Test-Path -LiteralPath $NetOpsExePath -PathType Leaf)) {
    throw "NetOps EXE bulunamadı: $NetOpsExePath"
}

$user = Get-LocalUser -Name $accountName -ErrorAction SilentlyContinue
if (-not $user) {
    $password = Read-Host "NetOps hesabı için parola oluştur" -AsSecureString
    New-LocalUser -Name $accountName -Password $password -Description "NetOps akıllı Windows oturumu" -AccountNeverExpires | Out-Null
    Add-LocalGroupMember -Group "Users" -Member $accountName -ErrorAction SilentlyContinue
    Write-Host "NetOps standart hesabı oluşturuldu."
} else {
    Write-Host "NetOps hesabı zaten var; yeni hesap oluşturulmadı."
}

$action = New-ScheduledTaskAction -Execute $NetOpsExePath -WorkingDirectory (Split-Path -Parent $NetOpsExePath) -Argument "--netops-session"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:COMPUTERNAME\$accountName"
$principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$accountName" -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskPath $taskPath -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "NetOps oturumunda uygulamayı otomatik başlatır." -Force | Out-Null
Get-ScheduledTask -TaskPath $taskPath -TaskName $taskName -ErrorAction Stop | Out-Null
Write-Host "NetOps-AutoStart görevi hazırlandı. NetOps oturumuna girince uygulama otomatik açılacak."
