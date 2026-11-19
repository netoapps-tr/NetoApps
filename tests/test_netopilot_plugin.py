import json
import unittest
from pathlib import Path

from neto_plugin_manager import NetOpsPluginManager


class NetoPilotPluginTests(unittest.TestCase):
    def test_manifest_declares_only_safe_first_release_permissions(self):
        root = Path(__file__).parents[1] / "plugins" / "netopilot"
        manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
        self.assertNotIn("power_control", manifest["permissions"])
        self.assertNotIn("file_delete", manifest["permissions"])
        self.assertIn("program_launch", manifest["permissions"])

    def test_netopilot_is_discoverable_and_has_no_critical_findings(self):
        manager = NetOpsPluginManager(Path(__file__).parents[1] / "plugins")
        plugin = next(item for item in manager.discover() if item.manifest.plugin_id == "netopilot")
        self.assertTrue(plugin.scan.safe_to_review)
        self.assertEqual(plugin.scan.error_count, 0)


if __name__ == "__main__":
    unittest.main()
