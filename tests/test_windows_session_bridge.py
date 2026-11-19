from __future__ import annotations

import unittest


class WindowsSessionBridgeTests(unittest.TestCase):
    def test_autostart_command_is_single_account_and_has_no_password(self):
        from neto_windows_session_bridge import ACCOUNT_NAME, TASK_NAME, build_autostart_command

        command = build_autostart_command(r"C:\Program Files\NetOps\NetOps.exe")
        joined = " ".join(command)
        self.assertIn(ACCOUNT_NAME, joined)
        self.assertIn(TASK_NAME, joined)
        self.assertIn("--netops-session", joined)
        self.assertNotIn("/RP", command)
        self.assertNotIn("password", joined.casefold())

    def test_non_windows_switch_does_not_claim_success(self):
        import os

        if os.name == "nt":
            self.skipTest("Windows-only fallback assertion")
        from neto_windows_session_bridge import switch_to_netops_session

        result = switch_to_netops_session()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "unsupported")


if __name__ == "__main__":
    unittest.main()
