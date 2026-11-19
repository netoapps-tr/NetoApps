from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path


class OperationLoopTests(unittest.TestCase):
    def test_plan_execute_verify_and_history(self):
        from neto_operation_loop import create_plan, execute_plan, recent_operations
        from neto_scene_engine import SceneAdapters

        state = {"profile": "balanced", "volume": 25, "muted": False, "brightness": None}
        scene = {
            "id": "test-workflow",
            "name": "Test çalışma",
            "description": "",
            "profile": "gaming",
            "volume": {"percent": 60, "muted": False},
            "brightness": None,
            "power": "none",
            "programs_to_open": [],
            "programs_to_close": [],
            "automations": [],
            "delay_seconds": 0,
            "triggers": [],
            "rollback_on_failure": True,
        }
        adapters = SceneAdapters(
            get_profile=lambda: state["profile"],
            set_profile=lambda value: state.__setitem__("profile", value) or True,
            get_volume=lambda: state["volume"],
            set_volume=lambda value: state.__setitem__("volume", value) or True,
            get_muted=lambda: state["muted"],
            set_muted=lambda value: state.__setitem__("muted", value) or True,
            get_brightness=lambda: state["brightness"],
            set_brightness=lambda value: state.__setitem__("brightness", value) or True,
        )

        with tempfile.TemporaryDirectory() as temp:
            old_history = os.environ.get("NETOPS_OPERATION_HISTORY")
            os.environ["NETOPS_OPERATION_HISTORY"] = str(Path(temp) / "operations.json")
            try:
                request = {"status": "preview", "scene": scene, "preview": {}}
                plan = create_plan(request)
                self.assertEqual(plan["status"], "planned")
                self.assertEqual(plan["risk"], "safe")

                result = execute_plan(plan, adapters=adapters, confirmed=True)
                self.assertEqual(result["status"], "success")
                self.assertEqual(result["verification"]["status"], "verified")
                self.assertEqual(len(recent_operations()), 1)
                self.assertEqual(state["profile"], "gaming")
                self.assertEqual(state["volume"], 60)
            finally:
                if old_history is None:
                    os.environ.pop("NETOPS_OPERATION_HISTORY", None)
                else:
                    os.environ["NETOPS_OPERATION_HISTORY"] = old_history

    def test_dangerous_plan_stays_pending_without_confirmation(self):
        from neto_operation_loop import create_plan, execute_plan

        scene = {
            "id": "test-power",
            "name": "Güç testi",
            "description": "",
            "profile": "balanced",
            "volume": {"percent": 30, "muted": False},
            "brightness": None,
            "power": "shutdown",
            "programs_to_open": [],
            "programs_to_close": [],
            "automations": [],
            "delay_seconds": 0,
            "triggers": [],
            "rollback_on_failure": True,
        }
        plan = create_plan({"status": "preview", "scene": scene, "preview": {}})
        self.assertTrue(plan["requires_confirmation"])
        self.assertEqual(execute_plan(plan)["status"], "awaiting_confirmation")

    def test_verification_failure_marks_operation_and_rolls_back(self):
        from neto_operation_loop import create_plan, execute_plan
        from neto_scene_engine import SceneAdapters

        scene = {
            "id": "test-mismatch",
            "name": "Doğrulama testi",
            "profile": "gaming",
            "volume": {"percent": 40, "muted": False},
            "brightness": None,
            "power": "none",
            "programs_to_open": [],
            "programs_to_close": [],
            "automations": [],
            "delay_seconds": 0,
            "triggers": [],
            "rollback_on_failure": True,
        }
        adapters = SceneAdapters(
            get_profile=lambda: "balanced",
            set_profile=lambda _value: True,
            get_volume=lambda: 40,
            set_volume=lambda _value: True,
            get_muted=lambda: False,
            set_muted=lambda _value: True,
        )
        plan = create_plan({"status": "preview", "scene": scene, "preview": {}})
        result = execute_plan(plan, adapters=adapters, confirmed=True)
        self.assertEqual(result["status"], "failed_verification")
        self.assertTrue(result["result"]["rolled_back"])


if __name__ == "__main__":
    unittest.main()
