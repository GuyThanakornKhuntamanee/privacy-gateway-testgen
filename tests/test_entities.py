import base64
import random
import re
import unittest

from .support import SRC  # noqa: F401

from privacy_gateway_testgen.entities import REGISTRY, EntityPool, entity_types
from privacy_gateway_testgen.entities import common
from privacy_gateway_testgen.entities.payment import TEST_BINS


class EntityFactoryTests(unittest.TestCase):
    def setUp(self):
        self.pool = EntityPool(random.Random(1234), "en")

    def test_thai_national_ids_are_valid(self):
        for _ in range(60):
            entity = self.pool.draw("pii", "thai_national_id")
            self.assertEqual(len(entity.value), 13)
            self.assertTrue(entity.value.isdigit())
            self.assertTrue(common.thai_id_valid(entity.value), entity.value)

    def test_invalid_national_id_lookalike_fails_checksum(self):
        for _ in range(60):
            entity = self.pool.draw("lookalike", "invalid_national_id")
            self.assertFalse(common.thai_id_valid(entity.value), entity.value)
            self.assertFalse(entity.detection_expected)

    def test_payment_cards_are_luhn_valid_and_use_test_bins(self):
        for _ in range(60):
            entity = self.pool.draw("payment", "payment_card_number")
            self.assertTrue(common.luhn_valid(entity.value), entity.value)
            self.assertTrue(any(entity.value.startswith(bin_prefix) for bin_prefix in TEST_BINS), entity.value)
            self.assertIn(entity.value[:6], TEST_BINS)

    def test_invalid_card_lookalike_fails_luhn(self):
        for _ in range(60):
            entity = self.pool.draw("lookalike", "invalid_card_number")
            self.assertFalse(common.luhn_valid(entity.value), entity.value)

    def test_secret_values_are_obviously_fake(self):
        secrets = [self.pool.draw("secrets", kind) for kind in entity_types("secrets")]
        rendered = [entity.value for entity in secrets]
        self.assertTrue(any(value.startswith("sk_example_fake_") for value in rendered))
        self.assertTrue(any("example-fake-signature" in value for value in rendered))
        for value in rendered:
            self.assertNotRegex(value, r"sk_live_|ghp_|xox[bap]-|AIza[0-9A-Za-z_-]{35}")
            self.assertNotRegex(value, r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")
        pem_values = [value for value in rendered if "-----BEGIN" in value]
        self.assertTrue(pem_values)
        for value in pem_values:
            self.assertIn("EXAMPLE FAKE", value)
        cloud_keys = [value for value in rendered if value.startswith("AKIA")]
        self.assertTrue(cloud_keys)
        for value in cloud_keys:
            self.assertRegex(value, r"^AKIA[0-9A-Z]{16}$")
            self.assertTrue("FAKE" in value or "EXAMPLE" in value)

    def test_jwt_is_structurally_valid_but_unsigned(self):
        entity = self.pool.draw("secrets", "jwt_token")
        parts = entity.value.split(".")
        self.assertEqual(len(parts), 3)
        header = base64.urlsafe_b64decode(parts[0] + "=" * (-len(parts[0]) % 4)).decode()
        self.assertIn('"alg":"HS256"', header)
        self.assertEqual(parts[2], "example-fake-signature")

    def test_emails_use_reserved_domains(self):
        for _ in range(60):
            entity = self.pool.draw("pii", "email_address")
            self.assertRegex(entity.value, r"@example\.(com|org|net)$")

    def test_infrastructure_uses_private_or_documentation_ranges(self):
        for _ in range(60):
            ipv4 = self.pool.draw("infrastructure", "internal_ipv4")
            self.assertTrue(ipv4.value.startswith("10."))
            host = self.pool.draw("infrastructure", "internal_hostname")
            self.assertTrue(host.value.endswith(".internal"))
            ipv6 = self.pool.draw("infrastructure", "internal_ipv6")
            self.assertTrue(ipv6.value.startswith("fd00:"))
            cloud_id = self.pool.draw("infrastructure", "cloud_resource_id")
            self.assertIn(":000000000000:", cloud_id.value)

    def test_every_registered_factory_produces_a_value(self):
        for domain, specs in REGISTRY.items():
            for kind in specs:
                entity = self.pool.draw(domain, kind)
                self.assertTrue(entity.value, f"{domain}/{kind} produced an empty value")
                self.assertEqual(entity.entity_type, kind)
                self.assertEqual(entity.domain, domain)

    def test_lookalikes_are_marked_as_not_expected(self):
        for kind in entity_types("lookalike"):
            entity = self.pool.draw_lookalike(kind)
            self.assertFalse(entity.detection_expected)
            self.assertEqual(entity.domain, "lookalike")


if __name__ == "__main__":
    unittest.main()
