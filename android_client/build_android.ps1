$ErrorActionPreference = 'Stop'

$gradleCommand = Get-Command gradle -ErrorAction SilentlyContinue
if ($gradleCommand) {
    $gradle = $gradleCommand.Source
} else {
    $gradle = Join-Path $env:LOCALAPPDATA 'Gradle\gradle-8.9\bin\gradle.bat'
    if (-not (Test-Path $gradle)) {
        throw 'Gradle bulunamadı. Android Studio veya Gradle kurulumu sonrası tekrar çalıştırın.'
    }
}

$sdk = $env:ANDROID_HOME
if ([string]::IsNullOrWhiteSpace($sdk)) {
    $sdk = Join-Path $env:LOCALAPPDATA 'Android\Sdk'
}
if (-not (Test-Path $sdk)) {
    throw "Android SDK bulunamadı: $sdk"
}

$env:ANDROID_HOME = $sdk
$env:ANDROID_SDK_ROOT = $sdk
if (-not (Test-Path (Join-Path $sdk 'platforms\android-35'))) {
    throw 'Android API 35 platformu bulunamadı. sdkmanager ile kurulmalı.'
}
if (-not (Test-Path (Join-Path $sdk 'build-tools\35.0.0'))) {
    throw 'Android build-tools 35.0.0 bulunamadı. sdkmanager ile kurulmalı.'
}

Push-Location $PSScriptRoot
try {
    & $gradle ':app:assembleDebug' '--no-daemon'
} finally {
    Pop-Location
}
