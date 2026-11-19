from __future__ import annotations

import inspect
import json
import os
import sys
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


class SourceInvariantTests(unittest.TestCase):
    def test_release_source_is_1_53(self) -> None:
        from neto_version import APP_VERSION, RELEASE_TAG

        self.assertEqual(APP_VERSION, "1.53.0")
        self.assertEqual(RELEASE_TAG, "v1.53.0")

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

    def test_build_includes_local_agent_runner(self) -> None:
        source = (PROJECT / "BUILD_EXE.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("neto_local_agent_runner", source)

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

    def test_legacy_10x_build_can_receive_1x_release(self) -> None:
        import neto_updater

        self.assertTrue(neto_updater.version_is_newer("1.40", "10.39.0"))
        self.assertFalse(neto_updater.version_is_newer("1.39", "10.39.0"))

    def test_error_detection_agent_reports_critical_logs(self) -> None:
        from unittest.mock import patch
        from neto_error_detection_agent import NetOpsErrorDetectionAgent

        agent = NetOpsErrorDetectionAgent(PROJECT)
        with patch.object(agent, "_iter_logs", return_value=[PROJECT / "crash.log"]), patch.object(
            Path, "read_text", return_value="INFO ready\nTraceback (most recent call last):\n"
        ):
            report = agent.run()
        self.assertEqual(report.error_count, 1)
        self.assertEqual(report.critical_count, 1)


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


class UpdaterHardeningTests(unittest.TestCase):
    def test_system_manifest_never_offers_an_older_version(self) -> None:
        import neto_system_updater as updater

        with TemporaryDirectory() as temp:
            root = Path(temp)
            changed = root / "neto_settings_page.py"
            changed.write_text("local\n", encoding="utf-8")
            manifest = {
                "manifest_version": "1",
                "version": "1.42.0",
                "release_tag": "v1.42.0",
                "files": [
                    {
                        "path": "neto_settings_page.py",
                        "url": "https://raw.githubusercontent.com/netoapps-tr/NetoApps/main/neto_settings_page.py",
                        "sha256": "a" * 64,
                    }
                ],
            }
            with patch.object(updater, "project_root", return_value=root), patch.object(
                updater, "fetch_manifest", return_value=manifest
            ), patch.object(updater, "_current_version", return_value="1.53.0"):
                result = updater.check_for_updates(force=True)

            self.assertFalse(result["available"])
            self.assertEqual(result["system_files"], [])
            self.assertIn("eski", result["message"].casefold())

    def test_stale_system_manifest_does_not_hide_new_release(self) -> None:
        import neto_updater

        stale_manifest_result = {
            "manifest_ok": True,
            "available": False,
            "update_available": False,
            "is_available": False,
            "update_mode": "system_files",
            "current_version": "1.53.0",
            "latest_version": "1.42.0",
            "system_files": [],
        }
        release = {
            "release_id": "release-154",
            "id": "release-154",
            "tag_name": "v1.54.0",
            "latest_version": "1.54.0",
            "name": "NetOps 1.54",
            "body": "Yeni sürüm",
            "html_url": "https://github.com/netoapps-tr/NetoApps/releases/tag/v1.54.0",
            "prerelease": False,
        }
        asset = {
            "id": "asset-154",
            "name": "NetOps-1.54.exe",
            "browser_download_url": "https://github.com/netoapps-tr/NetoApps/releases/download/v1.54/NetOps-1.54.exe",
            "size": 10,
            "content_type": "application/vnd.microsoft.portable-executable",
            "digest": "sha256:" + "b" * 64,
        }
        with patch.dict(neto_updater._CACHE, {"at": 0.0, "result": None}), patch(
            "neto_system_updater.check_for_updates", return_value=stale_manifest_result
        ), patch.object(neto_updater, "get_current_version", return_value="1.53.0"), patch.object(
            neto_updater, "_fetch_releases", return_value=[release]
        ), patch.object(neto_updater, "_fetch_assets", return_value=[asset]):
            result = neto_updater.check_for_updates(force=True)

        self.assertTrue(result["available"])
        self.assertEqual(result["latest_version"], "1.54.0")
        self.assertEqual(result["asset_name"], "NetOps-1.54.exe")

    def test_update_root_can_fall_back_when_temp_is_unavailable(self) -> None:
        import neto_updater

        with TemporaryDirectory() as temp:
            fallback = Path(temp) / ".neto_updates"
            with patch.dict(os.environ, {"LOCALAPPDATA": "", "APPDATA": "", "TEMP": "", "TMP": ""}, clear=False), patch.object(
                neto_updater.Path, "cwd", return_value=Path(temp)
            ), patch.object(
                neto_updater, "_can_write_directory", side_effect=lambda path: path == fallback
            ):
                # The last candidate is the project working directory fallback.
                result = neto_updater._update_root()
            self.assertEqual(result, Path(temp) / ".neto_updates")

    def test_zip_update_script_contains_backup_and_rollback(self) -> None:
        import neto_update_helper as helper

        with TemporaryDirectory() as temp:
            base = Path(temp)
            workspace = base / "updates"
            app = base / "app"
            workspace.mkdir()
            app.mkdir()
            archive_path = base / "update.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("NetOps/new_file.txt", "new")
            with patch.object(helper, "_update_root", return_value=workspace), patch.object(
                helper, "app_root", return_value=app
            ):
                script = helper._zip_update_script(archive_path, restart=False, tag="v1.42.0")
            content = script.read_text(encoding="utf-8-sig")
            self.assertIn("Backup exit code", content)
            self.assertIn("restoring previous installation", content)
            self.assertIn("/PURGE", content)
            self.assertEqual(len(list(workspace.glob("job-*"))), 1)

    def test_broken_zip_does_not_leave_job_directory(self) -> None:
        import neto_update_helper as helper

        with TemporaryDirectory() as temp:
            base = Path(temp)
            workspace = base / "updates"
            app = base / "app"
            workspace.mkdir()
            app.mkdir()
            archive_path = base / "unsafe.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escape.txt", "blocked")
            with patch.object(helper, "_update_root", return_value=workspace), patch.object(
                helper, "app_root", return_value=app
            ), self.assertRaises(RuntimeError):
                helper._zip_update_script(archive_path, restart=False)
            self.assertEqual(list(workspace.glob("job-*")), [])

    def test_system_manifest_rejects_unsafe_paths(self) -> None:
        import neto_system_updater as updater

        base = {
            "manifest_version": "1",
            "version": "1.41.0",
            "files": [
                {
                    "path": "neto_settings_page.py",
                    "url": "https://raw.githubusercontent.com/netoapps-tr/NetoApps/main/neto_settings_page.py",
                    "sha256": "a" * 64,
                }
            ],
        }
        self.assertEqual(updater.validate_manifest(base)["files"][0]["path"], "neto_settings_page.py")
        for unsafe in ("../escape.py", "NetOps.exe"):
            payload = {**base, "files": [{**base["files"][0], "path": unsafe}]}
            with self.assertRaises(ValueError):
                updater.validate_manifest(payload)

    def test_system_update_plan_contains_only_changed_files(self) -> None:
        import neto_system_updater as updater

        with TemporaryDirectory() as temp:
            root = Path(temp)
            unchanged = root / "unchanged.py"
            changed = root / "changed.py"
            unchanged.write_bytes(b"same\n")
            changed.write_bytes(b"old\n")
            import hashlib
            manifest = {
                "manifest_version": "1",
                "version": "1.41.0",
                "release_tag": "v1.41.0",
                "files": [
                    {
                        "path": "unchanged.py",
                        "url": "https://raw.githubusercontent.com/netoapps-tr/NetoApps/main/unchanged.py",
                        "sha256": hashlib.sha256(b"same\n").hexdigest(),
                    },
                    {
                        "path": "changed.py",
                        "url": "https://raw.githubusercontent.com/netoapps-tr/NetoApps/main/changed.py",
                        "sha256": hashlib.sha256(b"new\n").hexdigest(),
                    },
                ],
            }
            with patch.object(updater, "project_root", return_value=root), patch.object(
                updater, "fetch_manifest", return_value=manifest
            ), patch.object(updater, "_current_version", return_value="1.41.0"):
                result = updater.check_for_updates(force=True)
            self.assertTrue(result["available"])
            self.assertEqual([item["path"] for item in result["system_files"]], ["changed.py"])

    def test_full_program_download_is_disabled_for_141_channel(self) -> None:
        import neto_updater

        with self.assertRaises(RuntimeError):
            neto_updater.download_update(
                {
                    "download_url": "https://github.com/netoapps-tr/NetoApps/releases/download/v1.41.0/NetOps.zip",
                    "asset_digest": "a" * 64,
                }
            )

    def test_file_update_keeps_persistent_rollback_metadata(self) -> None:
        import neto_update_helper as helper

        with TemporaryDirectory() as temp:
            base = Path(temp)
            workspace = base / "updates"
            app = base / "app"
            job = workspace / "job"
            payload = job / "payload"
            workspace.mkdir()
            app.mkdir()
            payload.mkdir(parents=True)
            staged = payload / "neto_settings_page.py"
            staged.write_bytes(b"new")
            plan = {
                "update_mode": "system_files",
                "root": str(app),
                "job": str(job),
                "version": "1.41.0",
                "files": [{"path": "neto_settings_page.py", "staged_path": str(staged)}],
            }
            with patch.object(helper, "_update_root", return_value=workspace), patch.object(
                helper.subprocess, "Popen"
            ) as popen:
                result = helper.install_file_update(plan, restart=False)
            metadata = json.loads((job / "rollback.json").read_text(encoding="utf-8"))
            self.assertTrue(result["ok"])
            self.assertEqual(metadata["files"], ["neto_settings_page.py"])
            popen.assert_called_once()

    def test_hidden_rollback_does_nothing_without_verified_history(self) -> None:
        import neto_system_updater as updater

        with TemporaryDirectory() as temp:
            with patch.object(updater, "update_root", return_value=Path(temp)):
                result = updater.hidden_rollback_command("nops-restore-141")
            self.assertFalse(result["ok"])
            self.assertIn("onceki", result["message"])

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
