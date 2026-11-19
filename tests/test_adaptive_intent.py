from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from neto_adaptive_intent import AdaptiveIntentModel
from netops_harbilig_engine import NetOpsHarbiligEngine


class AdaptiveIntentTests(unittest.TestCase):
    def test_model_predicts_without_external_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = AdaptiveIntentModel(Path(directory) / "model.json")
            prediction = model.predict("selamlar, nasılsın")

            self.assertIsNotNone(prediction)
            self.assertEqual(prediction.label, "quick_chat")
            self.assertGreaterEqual(prediction.confidence, 0.78)

    def test_abusive_text_is_not_learned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            model = AdaptiveIntentModel(path)
            before = model.status()["examples"]

            self.assertFalse(model.observe("amk", "quick_chat"))
            self.assertEqual(model.status()["examples"], before)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("amk", path.read_text(encoding="utf-8").casefold())
            self.assertEqual(data["version"], 2)

    def test_engine_learns_route_counters_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            engine = NetOpsHarbiligEngine(project_dir=Path(directory), internet_enabled=False)
            result = engine.answer("merhaba")

            self.assertEqual(result.intent, "quick_chat")
            self.assertGreater(engine.adaptive_model.status()["examples"], 25)
            model_text = engine.adaptive_model.path.read_text(encoding="utf-8")
            self.assertNotIn("merhaba", model_text.casefold())


if __name__ == "__main__":
    unittest.main()
