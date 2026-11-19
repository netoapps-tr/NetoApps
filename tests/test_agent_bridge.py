from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neto_agent_bridge import AgentToolBridge


class AgentBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)
        (self.workspace / "sample.py").write_text("print('ok')\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_safe_system_status_is_handled_locally(self) -> None:
        bridge = AgentToolBridge(self.workspace)
        with patch.object(bridge, "system_status", return_value={"cpu_percent": 1, "ram_percent": 2}):
            result = bridge.dispatch("sistem durumu")
        self.assertTrue(result["handled"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["cpu_percent"], 1)

    def test_gui_input_requires_explicit_approval(self) -> None:
        bridge = AgentToolBridge(self.workspace)
        result = bridge.dispatch("fare ile tıkla")
        self.assertTrue(result["handled"])
        self.assertTrue(result["approval_required"])
        self.assertFalse(result["ok"])

    def test_program_open_is_allowlisted_and_requires_approval(self) -> None:
        bridge = AgentToolBridge(self.workspace)
        result = bridge.dispatch("notepad aç")
        self.assertTrue(result["handled"])
        self.assertTrue(result["approval_required"])
        self.assertFalse(result["ok"])

    def test_file_write_is_parsed_and_requires_approval(self) -> None:
        bridge = AgentToolBridge(self.workspace)
        result = bridge.dispatch("dosya oluştur note.md içerik: merhaba NetOps")
        self.assertTrue(result["handled"])
        self.assertTrue(result["approval_required"])
        self.assertFalse((self.workspace / "note.md").exists())

        result = bridge.dispatch("dosya oluştur note.md içerik: merhaba NetOps", approved=True)
        self.assertTrue(result["ok"])
        self.assertEqual((self.workspace / "note.md").read_text(encoding="utf-8"), "merhaba NetOps")

    def test_unknown_task_keeps_skill_metadata_available(self) -> None:
        bridge = AgentToolBridge(self.workspace)
        result = bridge.dispatch("proje mimarisini anlat")
        self.assertFalse(result["handled"])
        self.assertIn("skills", result)

    def test_error_scan_reports_counts(self) -> None:
        logs = self.workspace / "logs"
        logs.mkdir()
        (logs / "crash.log").write_text("INFO ok\nTraceback: kritik hata\n", encoding="utf-8")
        bridge = AgentToolBridge(self.workspace)
        with patch("neto_pdf_report.write_report_pdf", return_value={"path": "test.pdf"}):
            result = bridge.dispatch("hata sayısını ve kritik hataları bul")

        self.assertTrue(result["handled"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["data"]["critical_count"], 1)
        self.assertEqual(result["data"]["pdf_path"], "test.pdf")

    def test_ui_scan_includes_pdf_report_path(self) -> None:
        from neto_ui_guard_agent import UIGuardReport

        bridge = AgentToolBridge(self.workspace)
        with patch("neto_ui_guard_agent.NetOpsUIGuardAgent.run", return_value=UIGuardReport(True, [], [], 1)):
            with patch("neto_pdf_report.write_report_pdf", return_value={"path": "ui-test.pdf"}):
                result = bridge.dispatch("ui kontrol")

        self.assertTrue(result["handled"])
        self.assertEqual(result["data"]["pdf_path"], "ui-test.pdf")


if __name__ == "__main__":
    unittest.main()
