from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class PdfReportTests(unittest.TestCase):
    def test_report_catalog_contains_existing_capability_groups(self) -> None:
        from neto_pdf_report import build_report_data

        data = build_report_data(PROJECT)

        self.assertGreater(data["catalog"]["files"], 20)
        self.assertIn("Agent ve AI", data["catalog"]["categories"])
        self.assertGreaterEqual(len(data["plugins"]), 1)

    def test_report_writes_a_readable_pdf(self) -> None:
        from neto_pdf_report import write_report_pdf

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "netops-report.pdf"
            result = write_report_pdf(PROJECT, target)

            self.assertTrue(result["ok"])
            self.assertTrue(target.is_file())
            self.assertGreater(target.stat().st_size, 1000)
            self.assertEqual(target.read_bytes()[:5], b"%PDF-")

            try:
                from pypdf import PdfReader

                reader = PdfReader(str(target))
                self.assertGreaterEqual(len(reader.pages), 2)
            except ImportError:
                self.assertIn(b"NetOps", target.read_bytes())


if __name__ == "__main__":
    unittest.main()
