# PyInstaller normal ilerleme bilgisini stderr'e de yazabilir. Native çıkışı
# ErrorAction Stop ile kesmeden, gerçek çıkış kodunu aşağıda açıkça denetle.
$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $PSScriptRoot
$log = Join-Path $PSScriptRoot "BUILD_LOG.txt"
if (Test-Path $log) { Remove-Item $log -Force }
function Log($s) { $s | Tee-Object -FilePath $log -Append }
Log "=== NETOPS BUILD START ==="
$python = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $python) {
    Log "FATAL: Python bulunamadı."
    exit 1
}
$pyinstallerVersion = python -m PyInstaller --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Log "FATAL: PyInstaller çalıştırılamadı."
    Log ($pyinstallerVersion -join [Environment]::NewLine)
    exit 1
}
Log ("PYINSTALLER: " + ($pyinstallerVersion -join " "))
$requirements = Join-Path $PSScriptRoot "requirements_live.txt"
python -m pip install --upgrade pip setuptools wheel | Tee-Object -FilePath $log -Append
if (Test-Path $requirements) {
    python -m pip install -r $requirements | Tee-Object -FilePath $log -Append
} else {
    Log "WARN: requirements_live.txt bulunamadı."
}
if (Test-Path "build") { Remove-Item "build" -Recurse -Force }
if (Test-Path "dist") { Remove-Item "dist" -Recurse -Force }
$argsList = @(
    "--clean","--noconfirm","--windowed","--onedir","--noupx",
    "--name","NetOps",
    "--exclude-module","PyQt5","--exclude-module","PySide2","--exclude-module","PySide6","--exclude-module","PyQt6","--exclude-module","scipy","--exclude-module","av","--exclude-module","onnxruntime","--exclude-module","faster_whisper","--exclude-module","ctranslate2","--exclude-module","soundfile","--exclude-module","torch","--exclude-module","torchvision","--exclude-module","torchaudio","--exclude-module","tensorflow","--exclude-module","tensorboard","--exclude-module","pandas","--exclude-module","matplotlib","--exclude-module","sklearn","--exclude-module","sympy","--exclude-module","datasets",
    "--collect-all","customtkinter","--collect-submodules","neto_weather_engine","--hidden-import","lupa","--hidden-import","lupa.lua54","--hidden-import","ytmusicapi",
    "--hidden-import","flask","--hidden-import","pycaw","--hidden-import","comtypes","--hidden-import","psutil","--hidden-import","requests","--hidden-import","aiohttp","--hidden-import","yt_dlp","--hidden-import","ytmusicapi","--hidden-import","pyautogui","--hidden-import","pygame",
    # Optional browser uses Qt WebEngine in a separate process; the main EXE remains lean.
    "--hidden-import","temalar","--hidden-import","neto_astryx_design","--hidden-import","neto_chat","--hidden-import","ayarlar","--hidden-import","neto_now_playing","--hidden-import","neto_music_search","--hidden-import","netops_one_engine","--hidden-import","neto_ai","--hidden-import","browser_engine","--hidden-import","neto_live_mode","--hidden-import","neto_live_app","--hidden-import","neto_live_commands","--hidden-import","neto_weather","--hidden-import","neto_system_updater",
    "--hidden-import","neto_weather_engine","--hidden-import","neto_weather_engine.engine","--hidden-import","neto_weather_engine.http_client","--hidden-import","neto_weather_engine.cache","--hidden-import","neto_weather_engine.models","--hidden-import","neto_weather_engine.providers","--hidden-import","neto_weather_engine.providers.open_meteo","--hidden-import","neto_weather_engine.providers.met_norway","--hidden-import","neto_weather_engine.providers.rainviewer","--hidden-import","neto_weather_engine.providers.aviation_weather","--hidden-import","neto_weather_engine.providers.nasa_power","--hidden-import","neto_weather_engine.providers.opensensemap","--hidden-import","neto_weather_engine.providers.wttr","--hidden-import","neto_weather_engine.analyzers","--hidden-import","neto_weather_engine.analyzers.snow","--hidden-import","neto_weather_engine.analyzers.consensus","--hidden-import","neto_error_detection_agent",
    "--hidden-import","neto_android_device","--hidden-import","neto_doctor","--hidden-import","neto_sohbet_v2","--hidden-import","neto_sohbet_v3","--hidden-import","neto_settings_page","--hidden-import","neto_window_manager","--hidden-import","neto_autopilot","--hidden-import","neto_autopilot_automation","--hidden-import","neto_operation_loop","--hidden-import","neto_system_twin","--hidden-import","neto_windows_session_bridge","--hidden-import","neto_agent","--hidden-import","neto_agent_worker","--hidden-import","neto_agent_crypto","--hidden-import","neto_local_agent_runner","--hidden-import","neto_automation_ui","--hidden-import","neto_automation_core","--hidden-import","neto_automation_guard","--hidden-import","neto_automation_backup","--hidden-import","neto_automation_draft","--hidden-import","neto_lua_kernel","--hidden-import","neto_lua_memory","--hidden-import","neto_lua_plugins","--hidden-import","neto_wake_bridge","--hidden-import","neto_automation_worker","--hidden-import","neto_scene_engine","--hidden-import","neto_scene_ui","--hidden-import","neto_network_scan"
)
$dynamicModules = Get-ChildItem -LiteralPath $PSScriptRoot -Filter "neto_*.py" -File |
    Select-Object -ExpandProperty BaseName
foreach ($module in $dynamicModules) {
    $argsList += @("--hidden-import", $module)
}
$argsList += @(
    "--hidden-import", "netops_one_engine",
    "--hidden-import", "netops_harbilig_engine",
    "--hidden-import", "netops_ozellik_motoru",
    "--hidden-import", "neto_version"
)
$iconCandidates = @("NetoAsistan.ico","neto_asistan.ico","neto.ico","neto_titlebar_logo.ico","neto_default_logo_v12.ico","Logo.ico")
foreach ($candidate in $iconCandidates) {
    if (Test-Path $candidate) {
        $argsList += @("--icon",$candidate)
        Log "ICON: $candidate"
        break
    }
}
$files = @(
    "config.py","lang.py","temalar.py","neto_chat.py","ayarlar.py","neto_now_playing.py","neto_music_search.py","neto_ai.py","browser_engine.py","neto_live_mode.py","neto_live_app.py","neto_live_commands.py","neto_weather.py",
    "neto_android_device.py","neto_settings_page.py","neto_window_manager.py","neto_autopilot.py","neto_lua_runtime.py","neto_lua_kernel.py","neto_lua_memory.py","neto_lua_plugins.py","neto_wake_bridge.py","neto_windows_session_bridge.py","setup-netops-session.ps1","crash_guard.py",
    "fallback_logo.png","Logo.png","NetoAsistan.png","neto_brand_logo.png","neto_default_logo_v12.png","neto_logo.png","neto_titlebar_logo.png",
    "neto_logo_16.png","neto_logo_20.png","neto_logo_24.png","neto_logo_28.png","neto_logo_32.png","neto_logo_36.png","neto_logo_40.png","neto_logo_48.png","neto_logo_64.png","neto_logo_96.png","neto_logo_128.png","neto_logo_256.png",
    "NetoAsistan.ico","neto_asistan.ico","neto.ico","neto_titlebar_logo.ico","neto_default_logo_v12.ico","Logo.ico","netocode.ico","kevra.png","kevr.png","kevra.ico","kevr.ico",
    "yukleme.gif","Neto.gif","neto_logo_7click.gif","neto_main_logo_source.gif","neto_first_install.gif",
    # v1.40: Neto Experience 3.0 giris logosu ve sesi (paketlenmezse
    # uygulama klasik Baslat kapisina duser).
    "neto_intro_logo.gif","neto_intro_logo.mp3","neto_startup_sound.mp3","neto_update_notification.mp3",
    "denielcz-done-463074.mp3","google_cover_config.example.json"
)
foreach ($f in $files) { if (Test-Path $f) { $argsList += @("--add-data","$f;."); Log "ADD: $f" } else { Log "SKIP: $f" } }
if (Test-Path "neto_logo_frames") { $argsList += @("--add-data","neto_logo_frames;neto_logo_frames"); Log "ADD: neto_logo_frames" }
if (Test-Path "lua") { $argsList += @("--add-data","lua;lua"); Log "ADD: lua" }
if (Test-Path "plugins") { $argsList += @("--add-data","plugins;plugins"); Log "ADD: plugins" }
if (Test-Path "assets") { $argsList += @("--add-data","assets;assets"); Log "ADD: assets" }
if (Test-Path "mobile") { $argsList += @("--add-data","mobile;mobile"); Log "ADD: mobile" }
if (Test-Path "tools\nodered\netops-flow.json") { $argsList += @("--add-data","tools\nodered;tools\nodered"); Log "ADD: tools\nodered" }
Get-ChildItem -LiteralPath $PSScriptRoot -Filter "*.nops" -File | ForEach-Object {
    $argsList += @("--add-data", "$($_.FullName);.")
    Log "ADD: $($_.Name)"
}
if (!(Test-Path "asistan beta.py")) { Log "FATAL: asistan beta.py yok."; exit 1 }
& python -m PyInstaller @argsList "asistan beta.py" 2>&1 | Tee-Object -FilePath $log -Append
$buildExitCode = $LASTEXITCODE
Log "EXIT CODE: $buildExitCode"
if (Test-Path "dist\NetOps\NetOps.exe") {
    Log "SUCCESS: dist\NetOps\NetOps.exe"
} else {
    Log "FATAL: dist\NetOps\NetOps.exe oluşturulmadı."
    if ($buildExitCode -eq 0) { $buildExitCode = 1 }
}
exit $buildExitCode




