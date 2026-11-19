from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


class LocalAgentRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "workspace"
        self.root.mkdir()
        (self.root / "app.py").write_text("def hello():\n    return 'ok'\n", encoding="utf-8")
        (self.root / "README.md").write_text("NetOps local runner\n", encoding="utf-8")
        from neto_local_agent_runner import NetOpsLocalAgentRunner

        self.runner = NetOpsLocalAgentRunner(self.root, state_dir=Path(self.temp.name) / "state")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_change_request_needs_write_approval(self) -> None:
        plan = self.runner.plan("uygulamayı düzelt ve yeni ekran ekle")

        self.assertEqual(plan.intent, "change_request")
        self.assertIn("file_write", plan.requires_approval)
        self.assertTrue(any(not step.automatic for step in plan.steps))

    def test_runner_never_reads_outside_workspace(self) -> None:
        from neto_local_agent_runner import WorkspaceBoundaryError

        with self.assertRaises(WorkspaceBoundaryError):
            self.runner.read_file(Path(self.temp.name).parent / "outside.txt")

    def test_safe_diagnosis_runs_without_shell(self) -> None:
        plan = self.runner.plan("uygulama çalışmıyor, hata bul ve test et")
        completed = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        with patch("neto_local_agent_runner.subprocess.run", return_value=completed) as run:
            result = self.runner.run_safe_steps(plan)

        self.assertTrue(result.ok)
        self.assertTrue(any(item.tool == "verify" for item in result.results))
        self.assertFalse(run.call_args.kwargs["shell"])
        self.assertEqual(run.call_args.args[0][0], sys.executable)

    def test_search_returns_workspace_relative_paths(self) -> None:
        result = self.runner.search("hello")

        self.assertTrue(result.ok)
        self.assertEqual(result.data["matches"][0]["path"], "app.py")

    def test_file_creation_requires_approval_and_stays_in_workspace(self) -> None:
        from neto_local_agent_runner import ApprovalRequired

        with self.assertRaises(ApprovalRequired):
            self.runner.create_text_file("notes.md", "safe note")

        result = self.runner.create_text_file("notes.md", "safe note", approved=True)
        self.assertTrue(result.ok)
        self.assertEqual((self.root / "notes.md").read_text(encoding="utf-8"), "safe note")

    def test_file_creation_does_not_overwrite_by_default(self) -> None:
        from neto_local_agent_runner import AgentRunnerError

        (self.root / "notes.txt").write_text("original", encoding="utf-8")
        with self.assertRaises(AgentRunnerError):
            self.runner.create_text_file("notes.txt", "replacement", approved=True)
        self.assertEqual((self.root / "notes.txt").read_text(encoding="utf-8"), "original")

    def test_chat_file_command_writes_requested_name_and_content(self) -> None:
        result = self.runner.create_text_file_from_command(
            "dosya oluştur chat-note.md içerik: NetOps çalışıyor",
            approved=True,
        )

        self.assertTrue(result.ok)
        self.assertEqual(
            (self.root / "chat-note.md").read_text(encoding="utf-8"),
            "NetOps çalışıyor",
        )

    def test_file_creation_rejects_windows_reserved_names(self) -> None:
        from neto_local_agent_runner import AgentRunnerError

        with self.assertRaises(AgentRunnerError):
            self.runner.create_text_file("CON.txt", "blocked", approved=True)

