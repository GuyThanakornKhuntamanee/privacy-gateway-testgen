import re
import unittest

from .support import ROOT, SRC  # noqa: F401
from .support import generate_small

from privacy_gateway_testgen.entities import common
from privacy_gateway_testgen.entities.payment import TEST_BINS

FORBIDDEN_PATTERNS = [
    r"sk_live_",
    r"pk_live_",
    r"ghp_[A-Za-z0-9]{20,}",
    r"xox[bap]-",
    r"AIza[0-9A-Za-z_-]{35}",
    r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    r"BEGIN CERTIFICATE",
]

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
AWS_KEY_RE = re.compile(r"AKIA[0-9A-Z]{16}")
CONNECTION_RE = re.compile(r"postgresql://[^\s\"']+")

ALLOWED_IPV4_PREFIXES = ("10.", "127.", "192.0.2.", "198.51.100.", "203.0.113.")
ALLOWED_EXACT_IPS = {"8.8.8.8", "1.1.1.1", "93.184.216.34"}


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset, _, _ = generate_small(140, seed=424242)
        cls.cases = cls.dataset["cases"]

    def test_no_live_secret_markers_in_dataset(self):
        blob = "\n".join(case["prompt"] for case in self.cases)
        for pattern in FORBIDDEN_PATTERNS:
            self.assertIsNone(re.search(pattern, blob), f"forbidden pattern present: {pattern}")

    def test_aws_like_keys_are_explicitly_fake(self):
        blob = "\n".join(case["prompt"] for case in self.cases)
        matches = AWS_KEY_RE.findall(blob)
        self.assertTrue(matches)
        for match in matches:
            self.assertTrue("FAKE" in match or "EXAMPLE" in match, match)

    def test_emails_use_reserved_example_domains(self):
        emails = [
            annotation["exact_entity_value"]
            for case in self.cases
            for annotation in case["entities"]
            if annotation["entity_type"] == "email_address"
        ]
        self.assertTrue(emails)
        for email in emails:
            self.assertRegex(email.lower(), r"@example\.(com|org|net)$", email)

    def test_connection_strings_are_fake_and_internal(self):
        blob = "\n".join(case["prompt"] for case in self.cases)
        for value in CONNECTION_RE.findall(blob):
            self.assertIn("fake_password_", value)
            self.assertIn(".internal", value)

    def test_annotated_payment_cards_use_test_bins_and_luhn(self):
        for case in self.cases:
            for annotation in case["entities"]:
                if annotation["entity_type"] == "payment_card_number":
                    value = annotation["exact_entity_value"]
                    self.assertTrue(any(value.startswith(bin_prefix) for bin_prefix in TEST_BINS), value)
                    self.assertTrue(common.luhn_valid(value), value)

    def test_annotated_national_ids_are_synthetic_and_valid(self):
        for case in self.cases:
            for annotation in case["entities"]:
                if annotation["entity_type"] == "thai_national_id":
                    self.assertTrue(common.thai_id_valid(annotation["exact_entity_value"]))

    def test_ipv4_addresses_are_private_or_documentation_ranges(self):
        blob = "\n".join(case["prompt"] for case in self.cases)
        for value in IPV4_RE.findall(blob):
            self.assertTrue(
                value.startswith(ALLOWED_IPV4_PREFIXES) or value in ALLOWED_EXACT_IPS,
                f"unexpected IPv4 value: {value}",
            )

    def test_pem_blocks_are_not_parseable_private_keys(self):
        blob = "\n".join(case["prompt"] for case in self.cases)
        for match in re.finditer(r"-----BEGIN ([A-Z ]+)-----", blob):
            self.assertIn("EXAMPLE FAKE", match.group(1))

    def test_no_company_specific_hardcoding(self):
        with open(ROOT / "configs" / "default.json", encoding="utf-8") as handle:
            config_text = handle.read().lower()
        for marker in ("acme corp", "internal.company", "@company.com"):
            self.assertNotIn(marker, config_text)


if __name__ == "__main__":
    unittest.main()
