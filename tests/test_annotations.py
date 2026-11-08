import unittest

from .support import SRC  # noqa: F401

from privacy_gateway_testgen.annotations import verify_cases


class AnnotationVerificationTests(unittest.TestCase):
    def _case(self, prompt, start, end, value, status="unverified"):
        return {
            "test_id": "case-1",
            "prompt": prompt,
            "verification_status": status,
            "entities": [{
                "entity_type": "thai_national_id",
                "domain": "pii",
                "exact_entity_value": value,
                "character_start": start,
                "character_end": end,
                "detection_expected": True,
            }],
        }

    def test_unique_occurrence_can_be_repaired(self):
        case = self._case("ID 1101700203456 end", 0, 2, "1101700203456")
        cases, report = verify_cases([case], repair=True)
        annotation = cases[0]["entities"][0]
        self.assertEqual(annotation["character_start"], 3)
        self.assertEqual(annotation["character_end"], 16)
        self.assertEqual(report["spans_repaired"], 1)
        self.assertEqual(report["unresolved"], [])

    def test_unique_occurrence_is_reported_without_repair(self):
        case = self._case("ID 1101700203456 end", 0, 2, "1101700203456")
        _, report = verify_cases([case], repair=False)
        self.assertEqual(report["spans_repaired"], 0)
        self.assertEqual(len(report["unresolved"]), 1)
        self.assertIn("can be repaired", report["unresolved"][0]["reason"])

    def test_ambiguous_occurrence_is_not_silently_fixed(self):
        case = self._case("1101700203456 and 1101700203456", 0, 2, "1101700203456")
        cases, report = verify_cases([case], repair=True)
        self.assertEqual(cases[0]["entities"][0]["character_start"], 0)
        self.assertEqual(len(report["unresolved"]), 1)
        self.assertIn("2 occurrences", report["unresolved"][0]["reason"])

    def test_semantic_unverified_count_is_reported(self):
        valid = self._case("ID 1101700203456", 3, 16, "1101700203456")
        _, report = verify_cases([valid])
        self.assertEqual(report["semantics_unverified_cases"], 1)
        self.assertEqual(report["unresolved"], [])


    def test_invalid_expected_identifier_gets_a_warning(self):
        case = self._case("ID 1101700203456", 3, 16, "1101700203456")
        _, report = verify_cases([case])
        self.assertEqual(len(report["validity_warnings"]), 1)
        self.assertIn("checksum", report["validity_warnings"][0]["warning"])


if __name__ == "__main__":
    unittest.main()
