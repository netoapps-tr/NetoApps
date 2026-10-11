from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


class SourceInvariantTests(unittest.TestCase):
    def test_titlebar_uses_asynchronous_windows_message(self) -> None:
        source = (PROJECT / "asistan beta.py").read_text(encoding="utf-8-sig")
        self.assertIn("PostMessageW", source)
        self.assertNotIn("SendMessageW(hwnd, 0x00A1", source)
        self.assertNotIn("WM_NCLBUTTONDOWN / HTCAPTION", source)

    def test_power_actions_require_confirmation(self) -> None:
        source = (PROJECT / "asistan beta.py").read_text(encoding="utf-8-sig")
        self.assertNotIn('os.system("shutdown /r /t 1")', source)
        self.assertIn('onay_modu, son_soru = True, "restart"', source)
        self.assertIn('onay_modu, son_soru = True, "sleep"', source)
        self.assertIn('onay_modu, son_soru = True, "shutdown"', source)

    def test_stale_ui_identifiers_are_removed(self) -> None:
        source = (PROJECT / "asistan beta.py").read_text(encoding="utf-8-sig")
        self.assertNotIn("_v108_original_store_app_ac", source)
        self.assertNotIn("_aktif_dil()", source)
        self.assertNotIn("responsive_sidebar_uygula()", source)
        self.assertNotIn("eklenti_frame.winfo_children()", source)

    def test_browser_does_not_shadow_qt_layout_method(self) -> None:
        source = (PROJECT / "browser_engine.py").read_text(encoding="utf-8-sig")
        self.assertIn("self.main_layout", source)
        self.assertNotIn("self.layout =", source)

    def test_agent_worker_bootstrap_exists(self) -> None:
        source = (PROJECT / "neto_agent.py").read_text(encoding="utf-8-sig")
        self.assertIn("--neto-agent-worker", source)
        self.assertIn("neto_agent_worker_main", source)
        self.assertIn("worker_script", source)

    def test_build_script_uses_real_icon_and_no_global_uninstall(self) -> None:
        source = (PROJECT / "BUILD_EXE.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("requirements_live.txt", source)
        self.assertNotIn("pip uninstall -y PyQt5", source)
        self.assertIn("NetoAsistan.ico", source)
        self.assertIn("neto_settings_page", source)
        self.assertIn("neto_agent_worker", source)

    def test_requirements_are_pinned(self) -> None:
        source = (PROJECT / "requirements_live.txt").read_text(encoding="utf-8-sig")
        self.assertIn("customtkinter==6.0.0", source)
        self.assertIn("pyinstaller==6.22.1", source)
        self.assertIn("shazamio==0.8.1", source)

    def test_update_defaults_to_stable_channel(self) -> None:
        import neto_updater
        import neto_update_ui

        updater_sig = inspect.signature(neto_updater.check_for_updates)
        self.assertEqual(updater_sig.parameters["include_prerelease"].default, False)
        self.assertEqual(
            inspect.signature(neto_update_ui.schedule_startup_check).parameters["include_prerelease"].default,
            False,
        )
        self.assertEqual(
            inspect.signature(neto_update_ui.manual_check).parameters["include_prerelease"].default,
            False,
        )


class RuntimeUnitTests(unittest.TestCase):
    def test_assistant_engine_prefers_quick_resolver(self) -> None:
        from neto_assistant_engine import AssistantEngine

        calls = {"ai": 0}

        def quick(text, agent_modu=False):
            if "ubuntu" in str(text).lower():
                return "Linux köprüsü hazır."
            return None

        def ai(text, agent_modu=False):
            calls["ai"] += 1
            return "AI cevabı"

        engine = AssistantEngine(
            quick_resolver=quick,
            ai_responder=ai,
            normalizer=lambda value: str(value or "").strip(),
            name="test",
        )
        result = engine.route("Ubuntu durumu", agent_modu=False)

        self.assertEqual(result.kind, "quick")
        self.assertEqual(result.text, "Linux köprüsü hazır.")
        self.assertEqual(calls["ai"], 0)

    def test_assistant_engine_preserves_command_tokens(self) -> None:
        from neto_assistant_engine import AssistantEngine

        engine = AssistantEngine(
            ai_responder=lambda text, agent_modu=False: "__SES__:55",
            normalizer=lambda value: str(value or "").strip(),
            name="test",
        )
        result = engine.route("sesi aç", allow_quick=False)

        self.assertEqual(result.kind, "command")
        self.assertEqual(result.command, "__SES__:55")
        self.assertEqual(result.text, "__SES__:55")

    def test_translation_always_returns_text(self) -> None:
        import lang

        self.assertIsInstance(lang.T("app_title"), str)
        self.assertEqual(lang.T("missing-regression-key"), "missing-regression-key")

    def test_color_interpolation(self) -> None:
        from neto_motion_engine_v2 import interpolate_color

        self.assertEqual(interpolate_color("#000000", "#FFFFFF", 0.5), "#808080")

    def test_live_commands_do_not_use_a_shell(self) -> None:
        import neto_live_commands

        with patch.object(neto_live_commands.subprocess, "Popen") as popen:
            answer = neto_live_commands.handle_live_command("hesap makinesi aç")
        self.assertEqual(answer, "Hesap makinesi açılıyor.")
        popen.assert_called_once_with(["calc.exe"], shell=False)

    def test_live_probe_prefers_matching_microphone(self) -> None:
        import neto_live_mode

        class FakeSD:
            class default:
                device = (1, None)

            def query_devices(self):
                return [
                    {"name": "Hoparlor", "max_input_channels": 0},
                    {"name": "WO Mic", "max_input_channels": 1},
                ]

        available, index, name = neto_live_mode.probe_input_device(("WO Mic", "Microphone"), sd=FakeSD())

        self.assertTrue(available)
        self.assertEqual(index, 1)
        self.assertEqual(name, "WO Mic")

    def test_live_probe_reports_missing_microphone(self) -> None:
        import neto_live_mode

        class FakeSD:
            class default:
                device = (None, None)

            def query_devices(self):
                return [{"name": "Hoparlor", "max_input_channels": 0}]

        available, index, message = neto_live_mode.probe_input_device(("Mikrofon",), sd=FakeSD())

        self.assertFalse(available)
        self.assertIsNone(index)
        self.assertIn("Hiç mikrofon bulunamadı", message)

    def test_user_data_roots_are_absolute(self) -> None:
        import crash_guard
        import lang
        import neto_now_playing
        import neto_ai

        self.assertTrue(Path(lang.HAFIZA_DOSYA).is_absolute())
        self.assertTrue(Path(crash_guard.LOG_DIR).is_absolute())
        self.assertTrue(Path(neto_now_playing._cover_cache_dir()).is_absolute())
        self.assertTrue(neto_ai.linux_bridge_gerekli_mi("ubuntu durumu"))
        self.assertFalse(neto_ai.linux_bridge_gerekli_mi("merhaba dünya"))


if __name__ == "__main__":
    unittest.main()
