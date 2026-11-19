from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from neto_local_coder import build_prompt
from neto_skill_loader import build_context, discover, select


class SkillLoaderTests(unittest.TestCase):
    def test_discovers_and_selects_relevant_skill_without_executing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "windows-app-automation"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                "---\nname: Windows Automation\ndescription: Windows uygulama test ve pencere kontrolü\n---\n"
                "Bu yalnızca kılavuz metnidir.\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"NETOPS_SKILL_DIRS": str(root)}, clear=False):
                records = discover()
                selected = select("Windows uygulama testi", limit=2)
                context = build_context("Windows uygulama testi", max_chars=800)

            self.assertGreaterEqual(len(records), 1)
            self.assertTrue(any(record.name == "Windows Automation" for record in selected))
            self.assertIn("Bu yalnızca kılavuz metnidir", context)

    def test_prompt_contains_skill_policy(self) -> None:
        prompt = build_prompt("fare ile tıkla", "kod", "--- SKILL: test ---\nOnay iste.")
        self.assertIn("AKTİF SKILL KILAVUZLARI", prompt)
        self.assertIn("Onay iste", prompt)
        self.assertIn("izin atlatma", prompt)


if __name__ == "__main__":
    unittest.main()
