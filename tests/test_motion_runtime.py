import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from neto_motion_engine_v2 import MotionEngine


class Clock:
    def __init__(self):
        self.now = 10.0
        self.jobs = {}
        self.next_id = 0
        self.alive = True

    def winfo_exists(self):
        return self.alive

    def after(self, milliseconds, callback):
        self.next_id += 1
        self.jobs[self.next_id] = (self.now + milliseconds / 1000, callback)
        return self.next_id

    def after_cancel(self, key):
        self.jobs.pop(key, None)

    def advance(self, seconds):
        end = self.now + seconds
        while self.jobs:
            key = min(self.jobs, key=lambda k: self.jobs[k][0])
            due, callback = self.jobs[key]
            if due > end:
                break
            self.now = due
            del self.jobs[key]
            callback()
        self.now = end


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.time_patch = patch("neto_motion_engine_v2.time.perf_counter", lambda: self.clock.now)
        self.prefs_patch = patch("neto_motion_engine_v2._runtime_preferences",
                                return_value={"enabled": True, "duration_scale": 1, "frame_ms": 16})
        self.time_patch.start()
        self.prefs_patch.start()
        self.addCleanup(self.time_patch.stop)
        self.addCleanup(self.prefs_patch.stop)
        self.engine = MotionEngine(self.clock)

    def test_many_animations_share_one_timer_and_finish(self):
        completed = []
        for i in range(50):
            self.engine.tween(str(i), 240, lambda p: None, on_complete=lambda i=i: completed.append(i))
        self.assertEqual(len(self.clock.jobs), 1)
        self.clock.advance(0.5)
        self.assertEqual(len(completed), 50)
        self.assertFalse(self.clock.jobs)

    def test_reverse_cancels_stale_completion(self):
        completed = []
        self.engine.tween("menu", 250, lambda p: None, on_complete=lambda: completed.append("closed"))
        self.clock.advance(0.08)
        self.engine.tween("menu", 250, lambda p: None, on_complete=lambda: completed.append("open"))
        self.clock.advance(0.6)
        self.assertEqual(completed, ["open"])

    def test_replacement_from_update_never_runs_old_finish(self):
        completed = []
        def update(p):
            if p == 1:
                self.engine.tween("menu", 80, lambda p: None,
                                  on_complete=lambda: completed.append("new"))
        self.engine.tween("menu", 80, update, on_complete=lambda: completed.append("stale"))
        self.clock.advance(0.5)
        self.assertEqual(completed, ["new"])

    def test_destroyed_root_discards_work(self):
        self.engine.tween("hover", 200, lambda p: self.fail("destroyed widget updated"))
        self.clock.alive = False
        self.clock.advance(1)
        self.assertFalse(self.engine._jobs)
        self.assertFalse(self.clock.jobs)

    def test_disabled_animation_reaches_exact_final_state(self):
        values, completed = [], []
        with patch("neto_motion_engine_v2._runtime_preferences", return_value={"enabled": False}):
            self.engine.number("menu", 104, 280, values.append, on_complete=lambda: completed.append(True))
        self.assertEqual(values, [280])
        self.assertEqual(completed, [True])
        self.assertFalse(self.clock.jobs)


if __name__ == "__main__":
    unittest.main()
