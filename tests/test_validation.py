import unittest

from .support import SRC  # noqa: F401
from .support import load_defaults, make_case

from privacy_gateway_testgen.validation import span_accuracy, validate_case, validate_dataset


class ValidationTests(unittest.TestCase):
    def setUp(self):
        _, self.policy = load_defaults()

    def test_generated_style_case_is_valid(self):
        case = make_case(policy=self.policy)
        self.assertEqual(validate_case(case, self.policy), [])

    def test_prompt_tampering_breaks_spans(self):
        case = make_case(policy=self.policy)
        case["prompt"] = "X" + case["prompt"]
        issues = validate_case(case, self.policy)
        self.assertTrue(any("slice does not match" in issue for issue in issues))
        self.assertTrue(any("prompt_length" in issue for issue in issues))

    def test_bad_enum_and_offsets_are_rejected(self):
        case = make_case(policy=self.policy)
        case["language"] = "fr"
        case["entities"][0]["character_start"] = 999
        issues = validate_case(case, self.policy)
        self.assertTrue(any("language" in issue for issue in issues))
        self.assertTrue(any("out of bounds" in issue for issue in issues))

    def test_policy_mismatch_is_rejected(self):
        case = make_case(policy=self.policy)
        case["policy_decision_expected"] = "BLOCK"
        issues = validate_case(case, self.policy)
        self.assertTrue(any("policy_decision_expected" in issue for issue in issues))

    def test_duplicate_ids_and_prompts_are_reported(self):
        first = make_case(policy=self.policy)
        second = make_case(policy=self.policy)
        issues = validate_dataset([first, second], self.policy)
        self.assertEqual(len(issues), 1)
        self.assertTrue(any("duplicate test_id" in issue for issue in issues[0]["errors"]))
        self.assertTrue(any("duplicate prompt" in issue for issue in issues[0]["errors"]))

    def test_span_accuracy_counts_correct_slices(self):
        good = make_case(policy=self.policy)
        bad = make_case(policy=self.policy)
        bad["entities"][0]["character_start"] = 0
        bad["entities"][0]["character_end"] = 3
        accuracy = span_accuracy([good, bad])
        self.assertEqual(accuracy, 0.5)

    def test_invalid_expected_identifier_fails_semantic_check(self):
        case = make_case(prompt="Customer 1101700203456", start=9, end=22, policy=self.policy)
        issues = validate_case(case, self.policy)
        self.assertTrue(any("fails checksum" in issue for issue in issues))
        card_case = make_case(prompt="Card 4111111111111112", start=5, end=21,
                              domain="payment", entity_type="payment_card_number",
                              policy=self.policy)
        issues = validate_case(card_case, self.policy)
        self.assertTrue(any("fails Luhn" in issue for issue in issues))

    def test_negative_case_requires_no_expected_entities(self):
        case = make_case(prompt="Order ORD-2026-000001", start=6, end=21,
                         expected=False, domain="lookalike", entity_type="order_id",
                         policy=self.policy)
        self.assertEqual(validate_case(case, self.policy), [])
        case["domains"] = ["pii"]
        self.assertTrue(any("domains" in issue for issue in validate_case(case, self.policy)))


if __name__ == "__main__":
    unittest.main()
