import copy
import unittest

from .support import SRC  # noqa: F401
from .support import generate_small

from privacy_gateway_testgen.evaluation import evaluate_dataset, markdown_report


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset, cls.config, cls.policy = generate_small(140, seed=20260314)

    def test_default_dataset_passes_all_gates(self):
        report = evaluate_dataset(self.dataset["cases"], self.config, self.policy, reproducible=True)
        self.assertTrue(report["passed"], report["failed_gates"])
        self.assertGreater(len(report["gates"]), 10)
        self.assertGreaterEqual(report["metrics"]["entity_type_count"], 25)
        self.assertIn("distribution_fidelity", report["metrics"])
        self.assertGreaterEqual(report["metrics"]["distribution_fidelity"]["max_abs_delta"], 0)

    def test_tampered_span_fails_span_gate(self):
        cases = copy.deepcopy(self.dataset["cases"])
        cases[0]["entities"][0]["character_start"] += 1
        report = evaluate_dataset(cases, self.config, self.policy, reproducible=True)
        self.assertFalse(report["passed"])
        failed = report["failed_gates"]
        self.assertIn("span_accuracy", failed)
        self.assertTrue(report["metrics"]["validation_issue_cases"] >= 1)

    def test_duplicate_prompt_fails_duplicate_gate(self):
        cases = copy.deepcopy(self.dataset["cases"][:20])
        cases.append(copy.deepcopy(cases[0]))
        cases[-1]["test_id"] = "pgt-tst-99999"
        report = evaluate_dataset(cases, self.config, self.policy, reproducible=True)
        self.assertIn("exact_duplicate_rate", report["failed_gates"])
        self.assertGreater(report["metrics"]["duplicates"]["exact_duplicate_cases"], 0)

    def test_non_reproducible_run_fails_gate(self):
        report = evaluate_dataset(self.dataset["cases"], self.config, self.policy, reproducible=False)
        self.assertIn("reproducibility", report["failed_gates"])

    def test_markdown_report_lists_gates(self):
        report = evaluate_dataset(self.dataset["cases"], self.config, self.policy, reproducible=True)
        markdown = markdown_report(report)
        self.assertIn("# Evaluation Report", markdown)
        self.assertIn("schema_validity", markdown)
        self.assertIn("Known limitations", markdown)


if __name__ == "__main__":
    unittest.main()
