param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue) {
    $global:PSNativeCommandUseErrorActionPreference = $false
}

function Write-Log {
    param([Parameter(Mandatory = $true)][string]$Message)
    $Message | Tee-Object -FilePath $script:LogFile -Append
}

function Read-BuildInfo {
    param([Parameter(Mandatory = $true)][string]$Path)

    $info = @{}
    if (Test-Path -LiteralPath $Path) {
        foreach ($line in Get-Content -LiteralPath $Path) {
            if ($line -match '^(?<key>[^=]+)=(?<value>.*)$') {
                $info[$matches.key] = $matches.value
            }
        }
    }
    return $info
}

function Set-BuildInfoValue {
    param(
        [Parameter(Mandatory = $true)][hashtable]$Info,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$DefaultValue
    )

    if ($Info.ContainsKey($Key) -and -not [string]::IsNullOrWhiteSpace($Info[$Key])) {
        return [string]$Info[$Key]
    }
    return $DefaultValue
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
Set-Location -LiteralPath $ProjectRoot

$script:LogFile = Join-Path $ProjectRoot "NETO_10.37_DERLEME_AYRINTI_LOGU.txt"
if (Test-Path -LiteralPath $script:LogFile) {
    Remove-Item -LiteralPath $script:LogFile -Force
}

$distDir = Join-Path $ProjectRoot "dist_pyapp"
$buildRoot = Join-Path $ProjectRoot ".pyapp_build"
$wheelProjectDir = Join-Path $buildRoot "wheel_project"
$wheelhouseDir = Join-Path $buildRoot "wheelhouse"
$pyappSourceDir = Join-Path $buildRoot "pyapp-source"
$distributionSourceCopy = Join-Path $buildRoot "distribution_source.tar.gz"
$pyappExe = Join-Path $pyappSourceDir "target\release\pyapp.exe"
$distExe = Join-Path $distDir "Neto Asistan.exe"
$distSha = Join-Path $distDir "SHA256SUMS.txt"
$distBuildInfo = Join-Path $distDir "NETO_AGENT_BUILD.txt"

$distributionPath = Join-Path $pyappSourceDir "src\embed\distribution"
$uvSource = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"

$existingBuildInfo = Read-BuildInfo -Path $distBuildInfo
$appVersion = Set-BuildInfoValue -Info $existingBuildInfo -Key "APP_VERSION" -DefaultValue "10.37"
$agentVersion = Set-BuildInfoValue -Info $existingBuildInfo -Key "AGENT_VERSION" -DefaultValue "10.37.13"
$runtimeVersion = Set-BuildInfoValue -Info $existingBuildInfo -Key "PYAPP_RUNTIME_VERSION" -DefaultValue "10.37.13"

Write-Log "=== NETO PYAPP BUILD START ==="
Write-Log "ProjectRoot: $ProjectRoot"

if (Test-Path -LiteralPath $distDir) {
    Write-Log "Cleaning dist_pyapp"
    Remove-Item -LiteralPath $distDir -Recurse -Force
}

if (Test-Path -LiteralPath $wheelhouseDir) {
    Write-Log "Cleaning stale wheelhouse"
    Remove-Item -LiteralPath $wheelhouseDir -Recurse -Force
}

Write-Log "Building wheel with build_wheel.py"
python.exe "$ProjectRoot\build_wheel.py" --project-root "$ProjectRoot" --work-dir "$buildRoot" 2>&1 | Tee-Object -FilePath $script:LogFile -Append
if ($LASTEXITCODE -ne 0) {
    throw "build_wheel.py failed with exit code $LASTEXITCODE"
}

if (Test-Path -LiteralPath $distributionSourceCopy) {
    Remove-Item -LiteralPath $distributionSourceCopy -Force
}
Copy-Item -LiteralPath $distributionPath -Destination $distributionSourceCopy -Force

$wheel = Get-ChildItem -LiteralPath $wheelhouseDir -Filter "neto_assistant-*.whl" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $wheel) {
    throw "Wheel bulunamadi: $wheelhouseDir"
}

Write-Log "Wheel: $($wheel.FullName)"

$env:PYAPP_PROJECT_PATH = $wheel.FullName
$env:PYAPP_DISTRIBUTION_PATH = $distributionSourceCopy
$env:PYAPP_DISTRIBUTION_FORMAT = "tar|gzip"
$env:PYAPP_DISTRIBUTION_PYTHON_PATH = "python\python.exe"
$env:PYAPP_DISTRIBUTION_SITE_PACKAGES_PATH = "python\Lib\site-packages"
$env:PYAPP_DISTRIBUTION_PIP_AVAILABLE = "1"
$env:PYAPP_EXEC_CODE = "import neto_bootstrap;neto_bootstrap.main()"
$env:PYAPP_EXEC_MODULE = ""
$env:PYAPP_IS_GUI = "1"
$env:PYAPP_FULL_ISOLATION = "1"
$env:PYAPP_UPGRADE_VIRTUALENV = "0"
$env:PYAPP_PIP_EXTERNAL = "0"
$env:PYAPP_PIP_VERSION = "latest"
$env:PYAPP_PROJECT_FEATURES = ""
$env:PYAPP_PIP_EXTRA_ARGS = ""
$env:PYAPP_PIP_ALLOW_CONFIG = "0"
$env:PYAPP_UV_ENABLED = "1"
$env:PYAPP_UV_ONLY_BOOTSTRAP = "0"
$env:PYAPP_UV_SOURCE = $uvSource
$env:PYAPP_ALLOW_UPDATES = "0"
$env:PYAPP_PASS_LOCATION = "1"
$env:PYAPP_SELF_COMMAND = "self"
$env:PYAPP_SKIP_INSTALL = "0"

Write-Log "Cleaning PyApp target directory"
Push-Location $pyappSourceDir
try {
    $cleanStdOut = [System.IO.Path]::GetTempFileName()
    $cleanStdErr = [System.IO.Path]::GetTempFileName()
    $cleanProc = Start-Process -FilePath "cargo.exe" -ArgumentList @("clean") `
        -WorkingDirectory $pyappSourceDir -NoNewWindow -PassThru -Wait `
        -RedirectStandardOutput $cleanStdOut -RedirectStandardError $cleanStdErr
    Get-Content -LiteralPath $cleanStdOut, $cleanStdErr | Tee-Object -FilePath $script:LogFile -Append
    Remove-Item -LiteralPath $cleanStdOut, $cleanStdErr -Force -ErrorAction SilentlyContinue
    if ($cleanProc.ExitCode -ne 0) {
        throw "cargo clean failed with exit code $($cleanProc.ExitCode)"
    }

    Write-Log "Running cargo build --release"
    $buildStdOut = [System.IO.Path]::GetTempFileName()
    $buildStdErr = [System.IO.Path]::GetTempFileName()
    $buildProc = Start-Process -FilePath "cargo.exe" -ArgumentList @("build", "--release") `
        -WorkingDirectory $pyappSourceDir -NoNewWindow -PassThru -Wait `
        -RedirectStandardOutput $buildStdOut -RedirectStandardError $buildStdErr
    Get-Content -LiteralPath $buildStdOut, $buildStdErr | Tee-Object -FilePath $script:LogFile -Append
    Remove-Item -LiteralPath $buildStdOut, $buildStdErr -Force -ErrorAction SilentlyContinue
    if ($buildProc.ExitCode -ne 0) {
        throw "cargo build failed with exit code $($buildProc.ExitCode)"
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $pyappExe)) {
    throw "PyApp exe bulunamadi: $pyappExe"
}

New-Item -ItemType Directory -Path $distDir -Force | Out-Null
Copy-Item -LiteralPath $pyappExe -Destination $distExe -Force

$exeHash = (Get-FileHash -LiteralPath $distExe -Algorithm SHA256).Hash.ToLowerInvariant()
$wheelHash = (Get-FileHash -LiteralPath $wheel.FullName -Algorithm SHA256).Hash.ToLowerInvariant()

@(
    "Neto Asistan $appVersion"
    "EXE_SHA256=$exeHash"
    "WHEEL_SHA256=$wheelHash"
    "PYAPP_VERSION=0.29.0"
    "PYTHON_VERSION=3.13"
) | Set-Content -LiteralPath $distSha -Encoding utf8

$buildFinished = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
@(
    "APP_VERSION=$appVersion"
    "AGENT_VERSION=$agentVersion"
    "PYAPP_RUNTIME_VERSION=$runtimeVersion"
    "BUILD_FINISHED=$buildFinished"
) | Set-Content -LiteralPath $distBuildInfo -Encoding utf8

Write-Log "EXE: $distExe"
Write-Log "SHA256: $exeHash"
Write-Log "Wheel SHA256: $wheelHash"
Write-Log "Build info written: $distBuildInfo"
Write-Log "=== NETO PYAPP BUILD END ==="
