import unittest
from pathlib import Path

from neto_animation_agent import NetOpsAnimationAgent
from neto_now_playing_atmosphere import atmosphere_for
from neto_ui_guard_agent import NetOpsUIGuardAgent


class UIAgentTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(__file__).parents[1]

    def test_ui_guard_finds_required_media_contracts(self):
        report = NetOpsUIGuardAgent(self.project).run()
        self.assertGreaterEqual(report.checks, 1)
        self.assertNotIn("Arayüz sözleşmesi eksik: def now_playing_idle_best_info", report.errors)

    def test_animation_agent_preserves_content(self):
        plan = NetOpsAnimationAgent().plan("normal")
        self.assertTrue(plan.protect_content_widgets)
        self.assertEqual(plan.frame_ms, 16)

    def test_atmosphere_is_stable_for_same_song_and_changes_by_song(self):
        first = atmosphere_for({"artist": "Tarkan", "title": "Şımarık", "playback_status": "playing"}, 4)
        same = atmosphere_for({"artist": "Tarkan", "title": "Şımarık", "playback_status": "playing"}, 4)
        other = atmosphere_for({"artist": "Sezen Aksu", "title": "Manifesto", "playback_status": "playing"}, 4)
        self.assertEqual(first, same)
        self.assertNotEqual(first["primary"], other["primary"])


if __name__ == "__main__":
    unittest.main()
