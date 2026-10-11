from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class AutopilotAutomationTests(unittest.TestCase):
    def test_parser_catalog_api(self):
        import neto_autopilot

        request = neto_autopilot.prepare(
            "Autopilot APIzone'u her 5 dakikada kontrol et, çökerse bildir"
        )
        self.assertIsNotNone(request)
        self.assertEqual(request["status"], "automation_preview")
        self.assertEqual(request["draft"].api_name, "APIzone")
        self.assertEqual(request["draft"].trigger, {"seconds": 300})

    def test_parser_verified_api(self):
        import neto_autopilot

        request = neto_autopilot.prepare(
            "Autopilot Jikan'ı her 1 saatte takip et"
        )
        self.assertEqual(request["status"], "automation_preview")
        self.assertEqual(request["draft"].api_name, "Jikan")
        self.assertEqual(request["draft"].trigger, {"seconds": 3600})

    def test_exact_resolver_does_not_confuse_catapi_and_cataas(self):
        import neto_public_apis

        catapi = neto_public_apis.resolve_verified("Catapi")
        cataas = neto_public_apis.resolve_verified("Cataas")
        self.assertEqual((catapi or {}).get("name"), "Catapi")
        self.assertEqual((cataas or {}).get("name"), "Cataas")

    def test_watch_notifies_down_once_then_recovery(self):
        # Core paths are calculated at import time, so isolate the DB before import.
        import importlib
        import sys

        with tempfile.TemporaryDirectory() as temp:
            old = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = temp
            try:
                sys.modules.pop("neto_automation_core", None)
                core = importlib.import_module("neto_automation_core")
                import neto_public_apis

                api = {"id": "demo-api", "name": "Demo API", "url": "https://example.com"}
                states = [
                    {"ok": True, "api": api, "status": 200, "latency_ms": 10, "health_state": "ok"},
                    {"ok": False, "api": api, "error": "HTTP 503", "latency_ms": 10, "health_state": "transient"},
                    {"ok": False, "api": api, "error": "HTTP 503", "latency_ms": 10, "health_state": "transient"},
                    {"ok": True, "api": api, "status": 200, "latency_ms": 10, "health_state": "ok"},
                ]
                notifications = []
                action = core._normalize_action(
                    {
                        "type": "public_api_watch",
                        "api": "demo-api",
                        "api_label": "Demo API",
                        "notify_on": ["down", "recovered"],
                    },
                    0,
                )
                with mock.patch.object(core, "_require_action_permissions", lambda *args, **kwargs: None), \
                     mock.patch.object(core, "_notify_windows", lambda title, msg: notifications.append((title, msg)) or True), \
                     mock.patch.object(neto_public_apis, "resolve_verified", lambda name: api), \
                     mock.patch.object(neto_public_apis, "resolve_free_entry", lambda name: None), \
                     mock.patch.object(neto_public_apis, "call_verified_exact", lambda name, timeout=8: states.pop(0)):
                    seen = []
                    for _ in range(4):
                        result = core._execute_action(
                            action,
                            context={"automation_name": "test"},
                            transaction=Path(core.TRANSACTION_DIR) / "test",
                            run_id="run",
                            automation_id="automation",
                        )
                        seen.append((result.data["state"], result.data["notified"]))

                self.assertEqual(seen, [("up", False), ("down", True), ("down", False), ("up", True)])
                self.assertEqual(len(notifications), 2)
            finally:
                if old is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = old


if __name__ == "__main__":
    unittest.main()
