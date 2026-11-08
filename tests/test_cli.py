import json
import os
import subprocess
import sys
import tempfile
import unittest

from .support import ROOT, SRC  # noqa: F401


def run_cli(*args, cwd=ROOT):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SRC)
    environment["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "privacy_gateway_testgen", *args],
        cwd=str(cwd),
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class CliTests(unittest.TestCase):
    def test_generate_validate_and_stats(self):
        with tempfile.TemporaryDirectory() as directory:
            out = os.path.join(directory, "dataset")
            result = run_cli("generate", "--config", "configs/default.json",
                             "--out", out, "--count", "24")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(os.path.exists(os.path.join(out, "manifest.json")))

            result = run_cli("validate", "--input", os.path.join(out, "all.jsonl"),
                             "--config", "configs/default.json", "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["cases"], 24)

            result = run_cli("stats", "--input", os.path.join(out, "all.jsonl"))
            self.assertEqual(result.returncode, 0, result.stderr)
            stats = json.loads(result.stdout)
            self.assertEqual(stats["total_cases"], 24)

    def test_evaluate_writes_reports_and_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            report_dir = os.path.join(directory, "reports")
            result = run_cli("evaluate", "--config", "configs/default.json",
                             "--out", report_dir)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with open(os.path.join(report_dir, "evaluation.json"), encoding="utf-8") as handle:
                report = json.load(handle)
            self.assertTrue(report["passed"])
            self.assertTrue(os.path.exists(os.path.join(report_dir, "evaluation.md")))

    def test_verify_repairs_imported_annotations(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = os.path.join(directory, "dataset")
            run_cli("generate", "--config", "configs/default.json", "--out", dataset, "--count", "12")
            with open(os.path.join(dataset, "all.jsonl"), encoding="utf-8") as handle:
                cases = [json.loads(line) for line in handle]
            case = cases[0]
            case["verification_status"] = "unverified"
            case["entities"][0]["character_start"] += 1
            broken = os.path.join(directory, "broken.jsonl")
            with open(broken, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(case, ensure_ascii=False) + "\n")
            fixed = os.path.join(directory, "fixed.jsonl")
            result = run_cli("verify", "--input", broken, "--repair", "--output", fixed)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["spans_repaired"], 1)
            self.assertTrue(report["changed"])

    def test_verify_accepts_utf8_bom(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "bom.jsonl")
            case = {
                "test_id": "bom-1",
                "prompt": "ID 1101700203450",
                "verification_status": "unverified",
                "entities": [{
                    "entity_type": "thai_national_id",
                    "domain": "pii",
                    "exact_entity_value": "1101700203450",
                    "character_start": 3,
                    "character_end": 16,
                    "detection_expected": True,
                }],
            }
            with open(path, "w", encoding="utf-8-sig") as handle:
                handle.write(json.dumps(case) + "\n")
            result = run_cli("verify", "--input", path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["spans_valid"], 1)

    def test_list_domains(self):
        result = run_cli("list-domains")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload["domains"]), {"pii", "payment", "secrets", "infrastructure"})
        self.assertGreater(len(payload["templates"]), 20)


if __name__ == "__main__":
    unittest.main()
