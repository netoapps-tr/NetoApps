from __future__ import annotations

import unittest
import tempfile
from unittest.mock import patch

import neto_emergency_console as console


class EmergencyConsoleTests(unittest.TestCase):
    def test_trigger_is_not_a_visible_ui_control(self) -> None:
        self.assertEqual(console.TRIGGER, "<Control-Alt-Shift-N>")

    def test_unauthorized_operator_is_rejected(self) -> None:
        with patch.object(console, "current_identity", return_value="other-user"), patch.object(console, "is_windows_admin", return_value=False), patch.object(console, "ensure_owner", return_value="owner-user"):
            self.assertFalse(console.authorized_operator())

    def test_owner_operator_is_allowed(self) -> None:
        with patch.object(console, "current_identity", return_value="owner-user"), patch.object(console, "is_windows_admin", return_value=False), patch.object(console, "ensure_owner", return_value="owner-user"):
            self.assertTrue(console.authorized_operator())

    def test_recovery_code_is_one_time_and_not_stored_raw(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            security_dir = console.Path(directory)
            with patch.object(console, "_state_dir", return_value=security_dir):
                code = console.enroll_recovery_code()
                self.assertTrue(console.verify_recovery_code(code))
                self.assertFalse(console.verify_recovery_code(code))
                raw = console._recovery_path().read_text(encoding="utf-8")
                self.assertNotIn(code, raw)


if __name__ == "__main__":
    unittest.main()
