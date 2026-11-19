"""Schema v2 generation, determinism and distribution tests."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest

from tests.support import ROOT
from privacy_gateway_testgen.policies import load_policy
from privacy_gateway_testgen.v2.config import load_v2_config
from privacy_gateway_testgen.v2.generate import V2Generator, export_v2_dataset
from privacy_gateway_testgen.v2.validation import validate_dataset_v2

CONFIG = str(ROOT / "configs" / "v2" / "default.json")
POLICY = str(ROOT / "configs" / "policy.default.json")


def make_config(count: int = 10, seed: int = 123, profile: str = "benchmark-balanced") -> dict:
    config = load_v2_config(CONFIG, profile=profile)
    config["total_samples"] = count
    config["seed"] = seed
    return config


def generate(config: dict):
    return V2Generator(config, load_policy(POLICY)).generate()


class V2GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = make_config(12, 123)
        cls.dataset = generate(cls.config)

    def test_cases_validate_and_have_files(self):
        issues = validate_dataset_v2(self.dataset["cases"], load_policy(POLICY))
        self.assertEqual(issues, [])
        self.assertEqual(len(self.dataset["cases"]), 12)
        self.assertGreater(len(self.dataset["files"]), 0)
        self.assertTrue(any(case["attachments"] for case in self.dataset["cases"]))
        self.assertTrue(any(not case["attachments"] for case in self.dataset["cases"]))
        for case in self.dataset["cases"]:
            self.assertIn(case["verification_status"], ("verified", "verified_partial"))
            self.assertIn(case["polarity"], ("positive", "negative"))
            self.assertTrue(case["document_fingerprint"])

    def test_every_attachment_has_metadata_and_sha(self):
        for case in self.dataset["cases"]:
            self.assertEqual(case["attachment_count"], len(case["attachments"]))
            for attachment in case["attachments"]:
                self.assertTrue(attachment["synthetic"])
                self.assertEqual(len(attachment["sha256"]), 64)
                self.assertIn(attachment["path"], self.dataset["files"])
                self.assertEqual(len(self.dataset["files"][attachment["path"]]), attachment["size_bytes"])
                self.assertEqual(hashlib.sha256(self.dataset["files"][attachment["path"]]).hexdigest(),
                                 attachment["sha256"])

    def test_ground_truth_has_prompt_and_file_provenance(self):
        sources = {item["source"] for case in self.dataset["cases"] for item in case["entities"]}
        self.assertIn("attachment", sources)
        self.assertIn("prompt", sources)
        for case in self.dataset["cases"]:
            for annotation in case["entities"]:
                if annotation["source"] == "prompt":
                    self.assertTrue(0 <= annotation["character_start"] < annotation["character_end"])
                else:
                    self.assertIn(annotation["source_attachment"], {a["attachment_id"] for a in case["attachments"]})
                    self.assertTrue(annotation["location"]["kind"])

    def test_same_seed_is_byte_reproducible(self):
        second = generate(self.config)
        first_json = json.dumps(self.dataset["cases"], ensure_ascii=False, sort_keys=True)
        second_json = json.dumps(second["cases"], ensure_ascii=False, sort_keys=True)
        self.assertEqual(first_json, second_json)
        first_hashes = {path: hashlib.sha256(data).hexdigest() for path, data in self.dataset["files"].items()}
        second_hashes = {path: hashlib.sha256(data).hexdigest() for path, data in second["files"].items()}
        self.assertEqual(first_hashes, second_hashes)

    def test_export_layout_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = export_v2_dataset(self.dataset, directory, self.config, load_policy(POLICY))
            for name in ("cases.jsonl", "all.json", "stats.json", "manifest.json",
                         "ground_truth/entities.jsonl", "train.jsonl", "validation.jsonl", "test.jsonl"):
                self.assertTrue(os.path.exists(os.path.join(directory, name)), name)
            self.assertEqual(manifest["schema_version"], "2.1")
            self.assertEqual(manifest["total_cases"], 12)
            for attachment in (item for case in self.dataset["cases"] for item in case["attachments"]):
                self.assertTrue(os.path.exists(os.path.join(directory, "attachments", *attachment["path"].split("/"))))
            with open(os.path.join(directory, "manifest.json"), encoding="utf-8") as handle:
                written = json.load(handle)
            self.assertEqual(written["attachments_sha256"], manifest["attachments_sha256"])

    def test_no_explicit_evaluation_language_in_prompts(self):
        forbidden = ("detect the pii", "please analyze the following", "personally identifiable information",
                     "api credentials", "sensitive information", "summarize this employee pii")
        for case in self.dataset["cases"]:
            lowered = case["prompt"].lower()
            for phrase in forbidden:
                self.assertNotIn(phrase, lowered)

    def test_document_fingerprints_are_unique(self):
        fingerprints = [case["document_fingerprint"] for case in self.dataset["cases"]]
        self.assertEqual(len(fingerprints), len(set(fingerprints)))


class V2DistributionTests(unittest.TestCase):
    def test_negative_cases_have_only_lookalikes(self):
        config = make_config(6, 5)
        config["distributions"]["negative_ratio"] = 1.0
        config["distributions"]["ambiguous_ratio"] = 0.0
        dataset = generate(config)
        self.assertEqual(validate_dataset_v2(dataset["cases"], load_policy(POLICY)), [])
        for case in dataset["cases"]:
            self.assertEqual(case["polarity"], "negative")
            self.assertFalse(case["detection_expected"])
            self.assertEqual(case["domains"], [])
            for annotation in case["entities"]:
                self.assertFalse(annotation["detection_expected"])
                self.assertEqual(annotation["classification_expected"], None)

    def test_ambiguous_cases_keep_context_annotations(self):
        config = make_config(6, 6)
        config["distributions"]["negative_ratio"] = 0.0
        config["distributions"]["ambiguous_ratio"] = 1.0
        dataset = generate(config)
        self.assertTrue(any(case["test_category"] == "ambiguous" for case in dataset["cases"]))
        self.assertTrue(any(case["ambiguity"]["is_ambiguous"] for case in dataset["cases"]))
        self.assertTrue(any(not item["detection_expected"] for case in dataset["cases"]
                            for item in case["entities"]))

    def test_ocr_profile_produces_image_or_scanned_cases(self):
        config = make_config(4, 9, profile="ocr")
        dataset = generate(config)
        self.assertTrue(dataset["cases"])
        for case in dataset["cases"]:
            self.assertIn(case["attachment_count"], (1, 2))
            self.assertGreaterEqual(case["attachment_count"], 1)
            for attachment in case["attachments"]:
                self.assertIn(attachment["extension"], ("png", "jpg", "jpeg", "pdf"))
            self.assertIn("ocr", case["tags"])
            self.assertEqual(case["verification_status"], "verified_partial")
            self.assertTrue(any(item["location"]["kind"] in ("image_ocr", "pdf_image")
                                for item in case["entities"] if item["source"] == "attachment"))

    def test_multi_attachment_cases_keep_per_file_provenance(self):
        config = make_config(6, 7)
        config["distributions"]["attachment_probability"] = 1.0
        config["distributions"]["attachment_count"] = {"1": 0.0, "2": 1.0, "3": 0.0}
        dataset = generate(config)
        self.assertTrue(all(case["attachment_count"] == 2 for case in dataset["cases"]))
        both = 0
        for case in dataset["cases"]:
            sources = {item["source_attachment"] for item in case["entities"] if item["source"] == "attachment"}
            self.assertTrue(sources.issubset({item["attachment_id"] for item in case["attachments"]}))
            both += 1 if len(sources) == 2 else 0
            self.assertTrue(case["attachments"][0]["sha256"] != case["attachments"][1]["sha256"])
        self.assertGreaterEqual(both, 1)

    def test_prompt_only_cases_have_inline_entities(self):
        config = make_config(4, 8)
        config["distributions"]["attachment_probability"] = 0.0
        dataset = generate(config)
        self.assertTrue(all(not case["attachments"] for case in dataset["cases"]))
        self.assertTrue(all(case["attachment_count"] == 0 for case in dataset["cases"]))
        self.assertTrue(all(any(item["source"] == "prompt" for item in case["entities"])
                            for case in dataset["cases"]))
        self.assertTrue(all(case["structure"] == "pasted_text" for case in dataset["cases"]))


if __name__ == "__main__":
    unittest.main()
