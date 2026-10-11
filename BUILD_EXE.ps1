$ErrorActionPreference = "Continue"
Set-Location -LiteralPath $PSScriptRoot
$log = Join-Path $PSScriptRoot "BUILD_LOG.txt"
if (Test-Path $log) { Remove-Item $log -Force }
function Log($s) { $s | Tee-Object -FilePath $log -Append }
Log "=== NETOPS BUILD START ==="
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
    "--clean","--noconfirm","--windowed","--onefile","--noupx",
    "--name","NetOps",
    "--exclude-module","PyQt5","--exclude-module","PySide2","--exclude-module","PySide6","--exclude-module","PyQt6","--exclude-module","scipy","--exclude-module","av","--exclude-module","onnxruntime","--exclude-module","faster_whisper","--exclude-module","ctranslate2","--exclude-module","soundfile","--exclude-module","torch","--exclude-module","torchvision","--exclude-module","torchaudio","--exclude-module","tensorflow","--exclude-module","tensorboard","--exclude-module","pandas","--exclude-module","matplotlib","--exclude-module","sklearn","--exclude-module","sympy","--exclude-module","datasets",
    "--collect-all","customtkinter","--collect-submodules","neto_weather_engine","--hidden-import","lupa","--hidden-import","lupa.lua54","--hidden-import","ytmusicapi",
    "--hidden-import","flask","--hidden-import","pycaw","--hidden-import","comtypes","--hidden-import","psutil","--hidden-import","requests","--hidden-import","aiohttp","--hidden-import","yt_dlp","--hidden-import","ytmusicapi","--hidden-import","pyautogui","--hidden-import","pygame",
    # Optional browser uses Qt WebEngine in a separate process; the main EXE remains lean.
    "--hidden-import","temalar","--hidden-import","neto_chat","--hidden-import","ayarlar","--hidden-import","neto_now_playing","--hidden-import","neto_music_search","--hidden-import","netops_one_engine","--hidden-import","neto_ai","--hidden-import","browser_engine","--hidden-import","neto_live_mode","--hidden-import","neto_live_app","--hidden-import","neto_live_commands","--hidden-import","neto_weather",
    "--hidden-import","neto_weather_engine","--hidden-import","neto_weather_engine.engine","--hidden-import","neto_weather_engine.http_client","--hidden-import","neto_weather_engine.cache","--hidden-import","neto_weather_engine.models","--hidden-import","neto_weather_engine.providers","--hidden-import","neto_weather_engine.providers.open_meteo","--hidden-import","neto_weather_engine.providers.met_norway","--hidden-import","neto_weather_engine.providers.rainviewer","--hidden-import","neto_weather_engine.providers.aviation_weather","--hidden-import","neto_weather_engine.providers.nasa_power","--hidden-import","neto_weather_engine.providers.opensensemap","--hidden-import","neto_weather_engine.providers.wttr","--hidden-import","neto_weather_engine.analyzers","--hidden-import","neto_weather_engine.analyzers.snow","--hidden-import","neto_weather_engine.analyzers.consensus",
    "--hidden-import","neto_android_device","--hidden-import","neto_doctor","--hidden-import","neto_sohbet_v2","--hidden-import","neto_sohbet_v3","--hidden-import","neto_settings_page","--hidden-import","neto_window_manager","--hidden-import","neto_autopilot","--hidden-import","neto_agent","--hidden-import","neto_agent_worker","--hidden-import","neto_agent_crypto","--hidden-import","neto_automation_ui","--hidden-import","neto_automation_core","--hidden-import","neto_automation_guard","--hidden-import","neto_automation_backup","--hidden-import","neto_automation_draft","--hidden-import","neto_lua_kernel","--hidden-import","neto_lua_memory","--hidden-import","neto_lua_plugins","--hidden-import","neto_wake_bridge","--hidden-import","neto_automation_worker","--hidden-import","neto_scene_engine","--hidden-import","neto_scene_ui","--hidden-import","neto_network_scan"
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
    "neto_android_device.py","neto_settings_page.py","neto_window_manager.py","neto_autopilot.py","neto_lua_runtime.py","neto_lua_kernel.py","neto_lua_memory.py","neto_lua_plugins.py","neto_wake_bridge.py","crash_guard.py",
    "fallback_logo.png","Logo.png","NetoAsistan.png","neto_brand_logo.png","neto_default_logo_v12.png","neto_logo.png","neto_titlebar_logo.png",
    "neto_logo_16.png","neto_logo_20.png","neto_logo_24.png","neto_logo_28.png","neto_logo_32.png","neto_logo_36.png","neto_logo_40.png","neto_logo_48.png","neto_logo_64.png","neto_logo_96.png","neto_logo_128.png","neto_logo_256.png",
    "NetoAsistan.ico","neto_asistan.ico","neto.ico","neto_titlebar_logo.ico","neto_default_logo_v12.ico","Logo.ico","netocode.ico","kevra.png","kevr.png","kevra.ico","kevr.ico",
    "yukleme.gif","Neto.gif","neto_logo_7click.gif","neto_main_logo_source.gif","neto_first_install.gif",
    # v1.40: Neto Experience 3.0 giris logosu ve sesi (paketlenmezse
    # uygulama klasik Baslat kapisina duser).
    "neto_intro_logo.gif","neto_intro_logo.mp3",
    "denielcz-done-463074.mp3","google_cover_config.example.json"
)
foreach ($f in $files) { if (Test-Path $f) { $argsList += @("--add-data","$f;."); Log "ADD: $f" } else { Log "SKIP: $f" } }
if (Test-Path "neto_logo_frames") { $argsList += @("--add-data","neto_logo_frames;neto_logo_frames"); Log "ADD: neto_logo_frames" }
if (Test-Path "lua") { $argsList += @("--add-data","lua;lua"); Log "ADD: lua" }
if (!(Test-Path "asistan beta.py")) { Log "FATAL: asistan beta.py yok."; exit 1 }
python -m PyInstaller @argsList "asistan beta.py" 2>&1 | Tee-Object -FilePath $log -Append
Log "EXIT CODE: $LASTEXITCODE"
if (Test-Path "dist\NetOps.exe") { Log "SUCCESS: dist\NetOps.exe" }
exit $LASTEXITCODE




