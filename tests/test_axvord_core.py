from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from neto_axvord_core import AxvordCore, is_activation_command


class AxvordCoreTests(unittest.TestCase):
    def test_activation_aliases_enter_agent_mode(self) -> None:
        self.assertTrue(is_activation_command(".agent"))
        self.assertTrue(is_activation_command(" agent "))
        self.assertFalse(is_activation_command("Axvord"))
        self.assertFalse(AxvordCore.is_activation_command("axvord aç"))
        self.assertFalse(is_activation_command("axvord hakkında bilgi"))

    def test_core_exposes_local_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            core = AxvordCore(Path(directory))
            result = core.status()
        self.assertEqual(result["core_id"], "axvord")
        self.assertIn("coder", result)
        self.assertIn("skills", result)


if __name__ == "__main__":
    unittest.main()
