import json
import os
import tempfile
import unittest

from .support import SRC  # noqa: F401
from .support import generate_small

from privacy_gateway_testgen.generator import compute_stats, export_dataset
from privacy_gateway_testgen.textsim import normalize
from privacy_gateway_testgen.validation import validate_dataset


class GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset, cls.config, cls.policy = generate_small(48, seed=2222)
        cls.cases = cls.dataset["cases"]

    def test_counts_and_ids(self):
        self.assertEqual(len(self.cases), 48)
        self.assertEqual(sum(1 for case in self.cases if case["split"] == "train"), 38)
        ids = [case["test_id"] for case in self.cases]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_case_validates(self):
        self.assertEqual(validate_dataset(self.cases, self.policy), [])

    def test_prompts_are_unique(self):
        normalized = [normalize(case["prompt"]) for case in self.cases]
        self.assertEqual(len(normalized), len(set(normalized)))

    def test_every_case_has_annotations(self):
        for case in self.cases:
            self.assertGreaterEqual(len(case["entities"]), 1, case["test_id"])

    def test_template_families_do_not_cross_splits(self):
        locations = {}
        for case in self.cases:
            family = case["template_family"]
            if family in locations:
                self.assertEqual(locations[family], case["split"])
            locations[family] = case["split"]

    def test_same_seed_is_reproducible(self):
        again, _, _ = generate_small(48, seed=2222)
        self.assertEqual(
            json.dumps(self.cases, ensure_ascii=False, sort_keys=True),
            json.dumps(again["cases"], ensure_ascii=False, sort_keys=True),
        )

    def test_different_seed_changes_prompts(self):
        other, _, _ = generate_small(48, seed=9999)
        first = {case["prompt"] for case in self.cases}
        second = {case["prompt"] for case in other["cases"]}
        self.assertNotEqual(first, second)

    def test_stats_add_up(self):
        stats = compute_stats(self.cases)
        self.assertEqual(stats["total_cases"], 48)
        self.assertEqual(sum(stats["by_split"].values()), 48)
        self.assertEqual(sum(stats["by_language"].values()), 48)
        self.assertEqual(sum(stats["by_difficulty"].values()), 48)
        self.assertGreater(stats["mean_entities_per_case"], 0)

    def test_export_writes_all_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = export_dataset(self.dataset, directory, self.config, self.policy)
            expected = {"all.jsonl", "train.jsonl", "validation.jsonl", "test.jsonl",
                        "all.json", "stats.json", "manifest.json"}
            self.assertEqual(set(os.listdir(directory)), expected)
            self.assertEqual(manifest["total_cases"], 48)
            for name, digest in manifest["files"].items():
                import hashlib

                with open(os.path.join(directory, name), "rb") as handle:
                    actual = hashlib.sha256(handle.read()).hexdigest()
                self.assertEqual(actual, digest, name)
            with open(os.path.join(directory, "all.jsonl"), encoding="utf-8") as handle:
                rows = [json.loads(line) for line in handle]
            self.assertEqual(len(rows), 48)
            self.assertEqual(validate_dataset(rows, self.policy), [])

    def test_leakage_restoration_and_audit_expectations(self):
        for case in self.cases:
            self.assertEqual(
                case["output_leakage_check_expected"],
                any(action != "ALLOW" for action in case["action_expected"].values()),
            )
            self.assertIn("exact_entity_value", case["audit_log_expected"]["forbidden_fields"])
            if "TOKENIZE" in case["action_expected"].values():
                self.assertEqual(case["token_restoration_expected"], "authorized_context_only")
            else:
                self.assertEqual(case["token_restoration_expected"], "not_applicable")

    def test_domain_distribution_is_configurable(self):
        from privacy_gateway_testgen.generator import DatasetGenerator

        def share_with_infrastructure(weights):
            config = self.config.copy()
            config["seed"] = 11
            config["total_samples"] = 30
            config["splits"] = {"train": 1, "validation": 1, "test": 1}
            config["distributions"] = dict(config["distributions"])
            config["distributions"]["domain"] = weights
            dataset = DatasetGenerator(config, self.policy).generate()
            positive = [case for case in dataset["cases"] if case["polarity"] == "positive"]
            return sum(1 for case in positive if "infrastructure" in case["domains"]) / len(positive)

        infra_first = share_with_infrastructure(
            {"pii": 0, "payment": 0, "secrets": 0, "infrastructure": 1}
        )
        pii_first = share_with_infrastructure(
            {"pii": 1, "payment": 0, "secrets": 0, "infrastructure": 0}
        )
        self.assertGreater(infra_first, pii_first)
        self.assertGreater(infra_first, 0.25)

    def test_split_counts_change_with_config(self):
        config, policy = self.config.copy(), self.policy
        config["splits"] = {"train": 1, "validation": 1, "test": 1}
        config["seed"] = 7
        config["total_samples"] = 30
        from privacy_gateway_testgen.generator import DatasetGenerator

        dataset = DatasetGenerator(config, policy).generate()
        counts = {split: 0 for split in ("train", "validation", "test")}
        for case in dataset["cases"]:
            counts[case["split"]] += 1
        self.assertEqual(counts, {"train": 10, "validation": 10, "test": 10})


if __name__ == "__main__":
    unittest.main()
