from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class AutomationRoadmapTests(unittest.TestCase):
    def test_conditional_action_is_skipped_without_side_effect(self) -> None:
        import neto_automation_core as core

        core.clear_emergency_stop()
        automation_id = core.create_automation(
            name="Roadmap koşul testi",
            trigger_type="manual",
            trigger={},
            actions=[
                {
                    "type": "wait",
                    "seconds": 0,
                    "condition": {
                        "type": "file_exists",
                        "path": str(Path(tempfile.gettempdir()) / "netops-roadmap-file-that-does-not-exist"),
                        "exists": True,
                    },
                }
            ],
            enabled=False,
        )
        try:
            result = core.execute_automation(automation_id, trigger_info={"type": "test"})
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["actions"][0]["status"], "skipped")
        finally:
            core.delete_automation(automation_id)

    def test_queue_deduplicates_active_request(self) -> None:
        import neto_automation_core as core

        automation_id = core.create_automation(
            name="Roadmap kuyruk testi",
            trigger_type="manual",
            trigger={},
            actions=[{"type": "wait", "seconds": 0}],
            enabled=False,
        )
        try:
            first = core.enqueue_automation(automation_id, {"type": "test"})
            second = core.enqueue_automation(automation_id, {"type": "test-again"})
            self.assertFalse(first["deduplicated"])
            self.assertTrue(second["deduplicated"])
            self.assertTrue(core.cancel_queued(first["id"]))
        finally:
            core.delete_automation(automation_id)

    def test_draft_is_preview_only_and_requires_confirmation(self) -> None:
        from neto_automation_draft import create_from_draft, parse_draft

        draft = parse_draft("Her gün saat 18:30 otomasyon oluştur, internet varsa çalıştır")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertEqual(draft.trigger_type, "daily")
        self.assertEqual(draft.trigger["time"], "18:30")
        with self.assertRaises(PermissionError):
            create_from_draft(draft)

    def test_emergency_stop_round_trip(self) -> None:
        import neto_automation_core as core

        core.set_emergency_stop("test")
        try:
            self.assertTrue(core.emergency_stop_active())
        finally:
            core.clear_emergency_stop()
        self.assertFalse(core.emergency_stop_active())


if __name__ == "__main__":
    unittest.main()
