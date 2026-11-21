"""Security and synthetic-only checks for schema v2 output."""

from __future__ import annotations

import io
import json
import re
import unittest
import zipfile

from tests.support import ROOT
from privacy_gateway_testgen.entities.common import luhn_valid
from privacy_gateway_testgen.policies import load_policy
from privacy_gateway_testgen.v2.config import load_v2_config
from privacy_gateway_testgen.v2.generate import V2Generator
from privacy_gateway_testgen.v2.validation import validate_dataset_v2

CONFIG = str(ROOT / "configs" / "v2" / "default.json")
POLICY = str(ROOT / "configs" / "policy.default.json")


class V2SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = load_v2_config(CONFIG, profile="benchmark-balanced")
        config["total_samples"] = 10
        config["seed"] = 2026
        config["distributions"]["attachment_probability"] = 1.0
        cls.dataset = V2Generator(config, load_policy(POLICY)).generate()

    def test_dataset_validates(self):
        self.assertEqual(validate_dataset_v2(self.dataset["cases"], load_policy(POLICY)), [])

    def test_office_files_are_macro_free(self):
        for case in self.dataset["cases"]:
            for attachment in case["attachments"]:
                if attachment["extension"] not in ("docx", "xlsx", "pptx"):
                    continue
                data = self.dataset["files"][attachment["path"]]
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    names = archive.namelist()
                    self.assertFalse(any(name.endswith("vbaProject.bin") for name in names))
                    self.assertFalse(any(name.endswith(".exe") or name.endswith(".dll") for name in names))

    def test_pdf_and_images_have_no_active_content(self):
        for case in self.dataset["cases"]:
            for attachment in case["attachments"]:
                data = self.dataset["files"][attachment["path"]]
                if attachment["extension"] == "pdf":
                    for marker in (b"/JavaScript", b"/OpenAction", b"/Launch", b"/EmbeddedFile"):
                        self.assertNotIn(marker, data)
                if attachment["extension"] in ("png", "jpg", "jpeg"):
                    self.assertIn(attachment["mime_type"], ("image/png", "image/jpeg"))

    def test_secrets_are_explicitly_non_functional(self):
        markers = ("example", "fake", "changeme", "redacted", "your_api_key", "placeholder", "synthetic")
        for case in self.dataset["cases"]:
            for annotation in case["entities"]:
                if annotation["domain"] == "secrets" and annotation["detection_expected"]:
                    self.assertTrue(
                        any(marker in annotation["exact_entity_value"].lower() for marker in markers),
                        annotation["exact_entity_value"],
                    )

    def test_emails_use_reserved_domains(self):
        pattern = re.compile(r"@([A-Za-z0-9.-]+)$")
        for case in self.dataset["cases"]:
            for annotation in case["entities"]:
                if annotation["entity_type"] == "email_address":
                    host = pattern.search(annotation["exact_entity_value"]).group(1).lower()
                    self.assertTrue(
                        host.endswith("example.com") or host.endswith("example.org")
                        or host.endswith("example.net") or host.endswith(".example"),
                        host,
                    )

    def test_payment_cards_use_test_bins_and_luhn(self):
        bins = ("411111", "424242", "555555", "601111", "378282")
        for case in self.dataset["cases"]:
            for annotation in case["entities"]:
                if annotation["entity_type"] == "payment_card_number" and annotation["detection_expected"]:
                    value = annotation["exact_entity_value"]
                    self.assertTrue(value.startswith(bins), value)
                    self.assertTrue(luhn_valid(value), value)

    def test_no_live_credential_markers(self):
        forbidden = (b"AKIA", b"sk_live_", b"ghp_", b"xoxb-", b"BEGIN RSA PRIVATE KEY")
        for path, data in self.dataset["files"].items():
            for marker in forbidden:
                self.assertNotIn(marker, data, f"{path} contains {marker!r}")

    def test_manifest_marks_synthetic(self):
        for case in self.dataset["cases"]:
            for attachment in case["attachments"]:
                self.assertIs(attachment["synthetic"], True)
                self.assertEqual(len(attachment["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
