import unittest

from neto_pilot_host import build_handlers


class PilotHostTests(unittest.TestCase):
    def test_program_opening_uses_existing_netops_callback(self):
        calls = []
        handlers = build_handlers({"_neto_agent_uygulama_ac": lambda name: calls.append(name)})
        result = handlers["launch_program"]("Notepad")
        self.assertTrue(result["ok"])
        self.assertEqual(calls, ["Notepad"])

    def test_window_move_is_explicitly_unavailable(self):
        result = build_handlers({})["move_window"]("x", 1)
        self.assertFalse(result["ok"])
        self.assertIn("etkin değil", result["error"])


if __name__ == "__main__":
    unittest.main()
