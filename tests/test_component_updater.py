import io
import json
import zipfile
import unittest
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

import neto_component_updater as updater
import neto_now_playing_driver
import neto_visual_driver


class ComponentUpdaterTests(unittest.TestCase):
    def setUp(self):
        self.digest = "a" * 64
        self.payload = {
            "manifest_version": "1",
            "components": {
                "visual_driver": {
                    "version": "1.1.0",
                    "module": "neto_visual_driver.py",
                    "asset_url": "https://github.com/example/netops/releases/download/v1/visual.zip",
                    "sha256": self.digest,
                },
                "now_playing_driver": {
                    "version": "1.2.0",
                    "module": "neto_now_playing_driver.py",
                    "asset_url": "https://objects.githubusercontent.com/example/now.zip",
                    "sha256": self.digest,
                },
            },
        }

    def test_manifest_normalizes_supported_components(self):
        manifest = updater.validate_manifest(self.payload)
        self.assertEqual(manifest["components"]["visual_driver"]["sha256"], self.digest)
        self.assertEqual(manifest["components"]["now_playing_driver"]["module"], "neto_now_playing_driver.py")

    def test_manifest_rejects_non_github_asset(self):
        self.payload["components"]["visual_driver"]["asset_url"] = "https://example.com/driver.zip"
        with self.assertRaises(ValueError):
            updater.validate_manifest(self.payload)

    def test_version_comparison(self):
        self.assertTrue(updater.version_is_newer("1.10.0", "1.9.0"))
        self.assertFalse(updater.version_is_newer("1.9.0", "1.10.0"))

    def test_driver_contracts_are_available(self):
        self.assertTrue(neto_visual_driver.health()["ok"])
        self.assertTrue(neto_now_playing_driver.health()["ok"])
        self.assertGreaterEqual(neto_visual_driver.frame_ms(), 16)
        self.assertEqual(neto_now_playing_driver.interval("ui_pump_ms"), 120)
        self.assertEqual(updater.current_component_versions()["visual_driver"], "10.37.0")

    def test_zip_path_escape_is_rejected(self):
        with TemporaryDirectory() as temp:
            archive_path = Path(temp) / "unsafe.zip"
            destination = Path(temp) / "out"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../escape.py", "bad")
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaises(RuntimeError):
                    updater._safe_extract(archive, destination)

    def test_rollback_selects_previous_verified_version(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "components"
            component_root = root / "visual_driver"
            for version in ("10.36.0", "10.37.0"):
                version_dir = component_root / version
                version_dir.mkdir(parents=True)
                (version_dir / "neto_visual_driver.py").write_text("DRIVER_VERSION = '%s'\n" % version, encoding="utf-8")
                (version_dir / "component.json").write_text(json.dumps({
                    "id": "visual_driver",
                    "version": version,
                    "module": "neto_visual_driver.py",
                }), encoding="utf-8")
            active_path = root / "active.json"
            active_path.write_text(json.dumps({
                "visual_driver": {
                    "version": "10.37.0",
                    "path": str((component_root / "10.37.0").resolve()),
                    "module": "neto_visual_driver.py",
                }
            }), encoding="utf-8")
            with patch.object(updater, "component_root", return_value=root):
                result = updater.rollback_component("visual_driver")
            self.assertEqual(result["version"], "10.36.0")
            self.assertTrue(result["restart_required"])
            active = json.loads(active_path.read_text(encoding="utf-8"))
            self.assertEqual(active["visual_driver"]["version"], "10.36.0")


if __name__ == "__main__":
    unittest.main()
