"""CLI integration tests for schema v2."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from tests.support import ROOT
from privacy_gateway_testgen.cli import main

CONFIG = str(ROOT / "configs" / "v2" / "default.json")


class V2CliTests(unittest.TestCase):
    def test_generate_validate_verify_and_lists(self):
        with tempfile.TemporaryDirectory() as directory:
            out = os.path.join(directory, "dataset")
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                code = main([
                    "generate-v2", "--config", CONFIG, "--profile", "benchmark-balanced",
                    "--count", "8", "--seed", "321", "--out", out,
                ])
            self.assertEqual(code, 0, buffer.getvalue())
            self.assertTrue(os.path.exists(os.path.join(out, "cases.jsonl")))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["validate-v2", "--dataset", out, "--json"]), 0)
                self.assertEqual(main(["verify-v2", "--dataset", out]), 0)
                self.assertEqual(main(["list-archetypes-v2"]), 0)
                self.assertEqual(main(["list-profiles-v2", "--config", CONFIG]), 0)

    def test_report_writes_measured_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            out = os.path.join(directory, "dataset")
            reports = os.path.join(directory, "reports")
            with redirect_stdout(io.StringIO()):
                main(["generate-v2", "--config", CONFIG, "--profile", "benchmark-balanced",
                      "--count", "12", "--seed", "322", "--out", out])
                code = main(["report-v2", "--dataset", out, "--out", reports, "--json"])
            self.assertIn(code, (0, 1))
            for name in ("evaluation.json", "evaluation.md", "verification.json"):
                self.assertTrue(os.path.exists(os.path.join(reports, name)), name)
            with open(os.path.join(reports, "evaluation.json"), encoding="utf-8") as handle:
                report = json.load(handle)
            self.assertEqual(report["schema_version"], "2.0")
            self.assertIn("gates", report)
            self.assertIn("file_open_rate", report["metrics"])
            self.assertIn("openings", report["metrics"])
            self.assertEqual(report["total_cases"], 12)


if __name__ == "__main__":
    unittest.main()
