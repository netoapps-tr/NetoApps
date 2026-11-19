from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


class UpdateCenterTests(unittest.TestCase):
    def test_update_state_maps_legacy_netops_10x_to_current_1x_train(self) -> None:
        import neto_update_center as center

        self.assertEqual(center.update_state("netops", "10.37.0", "1.54.0"), "available")
        self.assertEqual(center.update_state("netops", "1.54.0", "1.54.0"), "current")
        self.assertEqual(center.update_state("neto_asistan", "10.36", "10.36"), "current")
        self.assertEqual(center.update_state("neto_asistan", "", "10.36"), "unknown")

    def test_catalog_selects_latest_supported_release_per_product(self) -> None:
        import neto_update_center as center

        releases = [
            {
                "tag_name": "v1.53.1",
                "name": "NetOps 1.53.1",
                "html_url": "https://github.com/netoapps-tr/NetoApps/releases/tag/v1.53.1",
                "prerelease": False,
                "draft": False,
                "assets": [
                    {
                        "name": "NetOps-1.53.1.exe",
                        "browser_download_url": "https://github.com/netoapps-tr/NetoApps/releases/download/v1.53.1/NetOps-1.53.1.exe",
                        "digest": "sha256:" + "a" * 64,
                    }
                ],
            },
            {
                "tag_name": "v10.36",
                "name": "Neto Asistan 10.36",
                "html_url": "https://github.com/netoapps-tr/NetoApps/releases/tag/v10.36",
                "prerelease": True,
                "draft": False,
                "assets": [
                    {
                        "name": "Neto.Asistan.v10.36.exe",
                        "browser_download_url": "https://github.com/netoapps-tr/NetoApps/releases/download/v10.36/Neto.Asistan.v10.36.exe",
                        "digest": "sha256:" + "b" * 64,
                    }
                ],
            },
            {
                "tag_name": "v10.35",
                "name": "Neto Asistan 10.35",
                "html_url": "https://github.com/netoapps-tr/NetoApps/releases/tag/v10.35",
                "prerelease": True,
                "draft": False,
                "assets": [
                    {
                        "name": "Neto.Asistan.v10.35.exe",
                        "browser_download_url": "https://github.com/netoapps-tr/NetoApps/releases/download/v10.35/Neto.Asistan.v10.35.exe",
                        "digest": "sha256:" + "c" * 64,
                    }
                ],
            },
        ]

        catalog = center.catalog_from_releases(releases)

        self.assertEqual(catalog["netops"]["version"], "1.53.1")
        self.assertEqual(catalog["neto_asistan"]["version"], "10.36")
        self.assertTrue(catalog["neto_asistan"]["supported_minimum"])

    def test_neto_asistan_versions_before_10_36_are_not_supported(self) -> None:
        import neto_update_center as center

        self.assertFalse(center.is_supported_version("neto_asistan", "10.35"))
        self.assertTrue(center.is_supported_version("neto_asistan", "10.36"))
        self.assertTrue(center.is_supported_version("neto_asistan", "10.40"))

    def test_download_release_verifies_sha256_and_uses_safe_filename(self) -> None:
        import neto_update_center as center

        payload = b"NUC test package"
        release = {
            "product_id": "netops",
            "asset_name": "NetOps-1.54.0.exe",
            "download_url": "https://github.com/netoapps-tr/NetoApps/releases/download/v1.54.0/NetOps-1.54.0.exe",
            "asset_digest": hashlib.sha256(payload).hexdigest(),
        }
        with TemporaryDirectory() as temp, patch.object(
            center, "_download_bytes", return_value=payload
        ):
            result = center.download_release(release, Path(temp))
            downloaded = Path(result).read_bytes()

        self.assertEqual(Path(result).name, "NetOps-1.54.0.exe")
        self.assertEqual(downloaded, payload)

    def test_catalog_ignores_update_center_assets(self) -> None:
        import neto_update_center as center

        releases = [
            {
                "tag_name": "nuc-v1.0.0",
                "name": "Neto Update Center",
                "prerelease": True,
                "draft": False,
                "assets": [
                    {
                        "name": "NetoUpdateCenter-1.0.0.exe",
                        "browser_download_url": "https://github.com/netoapps-tr/NetoApps/releases/download/nuc-v1.0.0/NetoUpdateCenter-1.0.0.exe",
                    }
                ],
            }
        ]

        self.assertEqual(center.catalog_from_releases(releases), {})


if __name__ == "__main__":
    unittest.main()
