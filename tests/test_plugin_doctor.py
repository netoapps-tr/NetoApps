import unittest
from pathlib import Path

from neto_plugin_doctor import NetoPluginDoctor


class PluginDoctorTests(unittest.TestCase):
    def test_all_first_party_plugins_pass_doctor(self):
        report = NetoPluginDoctor(Path(__file__).parents[1] / "plugins").run()
        self.assertGreaterEqual(report.plugin_count, 15)
        self.assertTrue(report.ok, report.as_dict())
        self.assertEqual(report.failed, 0)


if __name__ == "__main__":
    unittest.main()
