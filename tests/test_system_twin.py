from __future__ import annotations

import unittest


class SystemTwinTests(unittest.TestCase):
    def test_impact_report_finds_target_process_without_network(self):
        from neto_system_twin import impact_report

        snapshot = {
            "processes": [
                {"pid": 10, "name": "chrome.exe", "status": "running", "memory_percent": 4.2},
                {"pid": 20, "name": "code.exe", "status": "running", "memory_percent": 2.1},
            ]
        }
        report = impact_report("programı kapat chrome", snapshot)
        self.assertTrue(report["requires_confirmation"])
        self.assertEqual(report["matches"][0]["name"], "chrome.exe")

    def test_format_snapshot_is_compact_and_turkish(self):
        from neto_system_twin import format_snapshot

        text = format_snapshot(
            {
                "host": {"name": "test-pc", "system": "Windows", "release": "11"},
                "metrics": {"cpu_percent": 12.0, "memory_percent": 44.0, "disk_percent": 70.0},
                "nodes": [{"id": "host"}],
                "edges": [],
                "processes": [{"name": "NetOps"}],
            }
        )
        self.assertIn("NetOps Sistem İkizi", text)
        self.assertIn("Öne çıkan süreçler", text)


if __name__ == "__main__":
    unittest.main()
