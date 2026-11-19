import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from neto_plugin_manager import NetOpsPluginManager
from neto_plugin_security import scan_plugin


class NopsPluginTests(unittest.TestCase):
    def test_builtin_netoplay_is_discoverable_without_importing_code(self):
        manager = NetOpsPluginManager(Path(__file__).parents[1] / "plugins")
        plugins = manager.discover()
        by_id = {item.manifest.plugin_id: item for item in plugins}
        self.assertIn("netoplay", by_id)
        self.assertTrue(by_id["netoplay"].scan.safe_to_review)

    def test_security_agent_reports_process_and_dynamic_code(self):
        root = Path(__file__).parents[1] / ".test_tmp_nops_security"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        try:
            (root / "main.py").write_text(
                "import subprocess\nexec('print(1)')\n", encoding="utf-8"
            )
            report = scan_plugin("bad", root)
            codes = {finding.code for finding in report.findings}
            self.assertIn("PLUGIN_PROCESS", codes)
            self.assertIn("PLUGIN_DYNAMIC_CODE", codes)
            self.assertFalse(report.safe_to_review)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_nops_zip_rejects_path_traversal(self):
        root = Path(__file__).parents[1] / ".test_tmp_nops_zip"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        try:
            bundle = root / "bad.nops"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("../escape.txt", "no")
            manager = NetOpsPluginManager(root / "plugins")
            with self.assertRaises(ValueError):
                manager.stage_nops(bundle)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_reinstall_keeps_plugin_files_and_registry(self):
        root = Path(__file__).parents[1] / ".test_tmp_nops_persist"
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        try:
            bundle = root / "persist.nops"
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("plugin.json", json.dumps({"id": "persist", "name": "Persist", "entry": "main.py"}))
                archive.writestr("main.py", "def register(api):\n    return {}\n")
            manager = NetOpsPluginManager(root / "plugins")
            manager.stage_nops(bundle)
            user_state = root / "plugins" / "persist" / "user_state.json"
            user_state.write_text("keep", encoding="utf-8")
            manager.stage_nops(bundle)
            self.assertEqual(user_state.read_text(encoding="utf-8"), "keep")
            registry = json.loads((root / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
            self.assertTrue(registry["plugins"]["persist"]["installed"])
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
