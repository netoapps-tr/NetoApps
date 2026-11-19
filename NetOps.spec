# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import sysconfig

from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all

datas = [('config.py', '.'), ('lang.py', '.'), ('temalar.py', '.'), ('neto_chat.py', '.'), ('ayarlar.py', '.'), ('neto_now_playing.py', '.'), ('neto_music_search.py', '.'), ('neto_ai.py', '.'), ('browser_engine.py', '.'), ('neto_live_mode.py', '.'), ('neto_live_app.py', '.'), ('neto_live_commands.py', '.'), ('neto_weather.py', '.'), ('neto_android_device.py', '.'), ('neto_settings_page.py', '.'), ('neto_window_manager.py', '.'), ('neto_autopilot.py', '.'), ('neto_lua_runtime.py', '.'), ('neto_lua_kernel.py', '.'), ('neto_lua_memory.py', '.'), ('neto_lua_plugins.py', '.'), ('neto_wake_bridge.py', '.'), ('neto_windows_session_bridge.py', '.'), ('setup-netops-session.ps1', '.'), ('crash_guard.py', '.'), ('fallback_logo.png', '.'), ('Logo.png', '.'), ('NetoAsistan.png', '.'), ('neto_brand_logo.png', '.'), ('neto_default_logo_v12.png', '.'), ('neto_logo.png', '.'), ('neto_titlebar_logo.png', '.'), ('neto_logo_16.png', '.'), ('neto_logo_20.png', '.'), ('neto_logo_24.png', '.'), ('neto_logo_28.png', '.'), ('neto_logo_32.png', '.'), ('neto_logo_36.png', '.'), ('neto_logo_40.png', '.'), ('neto_logo_48.png', '.'), ('neto_logo_64.png', '.'), ('neto_logo_96.png', '.'), ('neto_logo_128.png', '.'), ('neto_logo_256.png', '.'), ('NetoAsistan.ico', '.'), ('neto_asistan.ico', '.'), ('neto.ico', '.'), ('neto_titlebar_logo.ico', '.'), ('neto_default_logo_v12.ico', '.'), ('Logo.ico', '.'), ('netocode.ico', '.'), ('kevra.png', '.'), ('kevr.png', '.'), ('kevra.ico', '.'), ('kevr.ico', '.'), ('yukleme.gif', '.'), ('Neto.gif', '.'), ('neto_logo_7click.gif', '.'), ('neto_main_logo_source.gif', '.'), ('neto_first_install.gif', '.'), ('neto_intro_logo.gif', '.'), ('neto_intro_logo.mp3', '.'), ('neto_startup_sound.mp3', '.'), ('neto_update_notification.mp3', '.'), ('denielcz-done-463074.mp3', '.'), ('neto_logo_frames', 'neto_logo_frames'), ('lua', 'lua'), ('plugins', 'plugins'), ('assets', 'assets'), ('mobile', 'mobile'), ('tools/nodered', 'tools/nodered'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netoautomation.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netobackup.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netobrowser.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netoclipboard.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netodiagnostics.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netofocus.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netonotes.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netopilot.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netoplay.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netoreminders.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netoscenes.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netosecurity.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netotimer.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netoupdater.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netoweather.nops', '.'), ('C:/Users/PC/Desktop/NETO ASİSTAN SİLME/netowindow.nops', '.')]
binaries = []
# QtCore.pyd resolves shiboken6 beside the PySide6 extensions on Windows.
# Keep a copy there in addition to the standard shiboken6 package folder.
shiboken_dll = (
    Path(sysconfig.get_paths()["purelib"])
    / "shiboken6"
    / "shiboken6.abi3.dll"
)
if shiboken_dll.is_file():
    binaries.append((str(shiboken_dll), "PySide6"))

# Qt6Core loads ICU by basename. Keep the Windows ICU runtime beside Qt6Core
# so a different ICU copy collected for PDF/media modules cannot win lookup.
windows_icu_dir = Path(
    os.environ.get("WINDIR", r"C:\Windows")
) / "System32"
for icu_name in ("icu.dll", "icuuc.dll", "icuin.dll"):
    icu_dll = windows_icu_dir / icu_name
    if icu_dll.is_file():
        binaries.append((str(icu_dll), "PySide6"))
hiddenimports = ['lupa', 'lupa.lua54', 'ytmusicapi', 'flask', 'pycaw', 'comtypes', 'psutil', 'requests', 'aiohttp', 'yt_dlp', 'ytmusicapi', 'pyautogui', 'pygame', 'temalar', 'neto_astryx_design', 'neto_chat', 'ayarlar', 'neto_now_playing', 'neto_music_search', 'netops_one_engine', 'neto_ai', 'browser_engine', 'neto_live_mode', 'neto_live_app', 'neto_live_commands', 'neto_weather', 'neto_system_updater', 'neto_weather_engine', 'neto_weather_engine.engine', 'neto_weather_engine.http_client', 'neto_weather_engine.cache', 'neto_weather_engine.models', 'neto_weather_engine.providers', 'neto_weather_engine.providers.open_meteo', 'neto_weather_engine.providers.met_norway', 'neto_weather_engine.providers.rainviewer', 'neto_weather_engine.providers.aviation_weather', 'neto_weather_engine.providers.nasa_power', 'neto_weather_engine.providers.opensensemap', 'neto_weather_engine.providers.wttr', 'neto_weather_engine.analyzers', 'neto_weather_engine.analyzers.snow', 'neto_weather_engine.analyzers.consensus', 'neto_error_detection_agent', 'neto_android_device', 'neto_doctor', 'neto_sohbet_v2', 'neto_sohbet_v3', 'neto_settings_page', 'neto_window_manager', 'neto_autopilot', 'neto_autopilot_automation', 'neto_operation_loop', 'neto_system_twin', 'neto_windows_session_bridge', 'neto_agent', 'neto_agent_worker', 'neto_agent_crypto', 'neto_local_agent_runner', 'neto_automation_ui', 'neto_automation_core', 'neto_automation_guard', 'neto_automation_backup', 'neto_automation_draft', 'neto_lua_kernel', 'neto_lua_memory', 'neto_lua_plugins', 'neto_wake_bridge', 'neto_automation_worker', 'neto_scene_engine', 'neto_scene_ui', 'neto_network_scan', 'neto_adaptive_intent', 'neto_agent', 'neto_agent_bridge', 'neto_agent_crypto', 'neto_agent_worker', 'neto_ai', 'neto_android_device', 'neto_animation_agent', 'neto_anyspeech_tts', 'neto_arduino_sensor', 'neto_assistant_engine', 'neto_astryx_design', 'neto_automation_backup', 'neto_automation_core', 'neto_automation_draft', 'neto_automation_guard', 'neto_automation_standalone', 'neto_automation_ui', 'neto_automation_worker', 'neto_autopilot', 'neto_autopilot_automation', 'neto_axvord_core', 'neto_backup_manager', 'neto_branding', 'neto_builtin_plugin_contract', 'neto_builtin_skills', 'neto_chat', 'neto_command_palette', 'neto_component_updater', 'neto_dependency_installer_v3', 'neto_desktop_actions', 'neto_device_hub', 'neto_doctor', 'neto_emergency_console', 'neto_error_detection_agent', 'neto_experience3', 'neto_feature_gate', 'neto_first_install', 'neto_fluent_design', 'neto_lazy_ollama_v2', 'neto_live_app', 'neto_live_commands', 'neto_live_mode', 'neto_local_agent_runner', 'neto_local_coder', 'neto_lua_kernel', 'neto_lua_memory', 'neto_lua_plugins', 'neto_lua_runtime', 'neto_modern_ui', 'neto_motion_engine_v2', 'neto_music_search', 'neto_network_scan', 'neto_nodered_bridge', 'neto_now_playing', 'neto_now_playing_atmosphere', 'neto_now_playing_driver', 'neto_onboarding', 'neto_operation_loop', 'neto_paketleri_kur', 'neto_pdf_report', 'neto_pilot_host', 'neto_plugin_api', 'neto_plugin_doctor', 'neto_plugin_manager', 'neto_plugin_security', 'neto_power_features', 'neto_profile_cli', 'neto_public_apis', 'neto_quick_launcher', 'neto_reminders', 'neto_remote_pc_actions', 'neto_runtime_core', 'neto_runtime_host', 'neto_runtime_policy_v2', 'neto_runtime_services', 'neto_scene_engine', 'neto_scene_ui', 'neto_security', 'neto_settings_page', 'neto_sidebar_icons', 'neto_skill_loader', 'neto_sohbet_v2', 'neto_sohbet_v3', 'neto_startup_optimizer_v4', 'neto_strict_profiles', 'neto_system_control', 'neto_system_twin', 'neto_system_updater', 'neto_thread_gui_fix_v25', 'neto_titlebar_gil_fix_v27', 'neto_tray', 'neto_tum_modulleri_kur', 'neto_ui', 'neto_ui_guard_agent', 'neto_updater', 'neto_update_helper', 'neto_update_ui', 'neto_user_profiles', 'neto_v10_center', 'neto_v10_features', 'neto_version', 'neto_virtual_desktop', 'neto_visual_driver', 'neto_wake_bridge', 'neto_weather', 'neto_weather_api_test', 'neto_widget_motion', 'neto_windows_session_bridge', 'neto_window_manager', 'neto_wsl_bridge', 'neto_youtube_music_panel', 'netops_one_engine', 'netops_harbilig_engine', 'netops_ozellik_motoru', 'neto_version']
hiddenimports += ['neto_recovery_mesh', 'neto_recovery_surface']
hiddenimports += ['netops_qt_shell', 'netops_qt_backend', 'netops_icon_pack', 'neto_task_planner', 'neto_text_assistant']
hiddenimports += collect_submodules('neto_weather_engine')
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_winrt = collect_all('winrt')
datas += tmp_winrt[0]; binaries += tmp_winrt[1]; hiddenimports += tmp_winrt[2]


a = Analysis(
    ['asistan beta.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['runtime_hooks/netops_qt_path.py'],
    excludes=['PyQt5', 'PySide2', 'PyQt6', 'scipy', 'av', 'onnxruntime', 'faster_whisper', 'ctranslate2', 'soundfile', 'torch', 'torchvision', 'torchaudio', 'tensorflow', 'tensorboard', 'pandas', 'matplotlib', 'sklearn', 'sympy', 'datasets'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NetOps',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['NetoAsistan.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='NetOps',
)
