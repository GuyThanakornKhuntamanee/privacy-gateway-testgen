import unittest

from .support import SRC  # noqa: F401

from privacy_gateway_testgen.models import Entity
from privacy_gateway_testgen.policies import resolve_policy, validate_policy


class PolicyTests(unittest.TestCase):
    def setUp(self):
        from .support import load_defaults

        _, self.policy = load_defaults()

    def test_strictest_entity_action_wins(self):
        entities = [
            Entity("pii", "thai_national_id", "1101700203450"),
            Entity("secrets", "api_key", "sk_example_fake_x"),
        ]
        result = resolve_policy(entities, "external_assistant", self.policy)
        self.assertEqual(result["policy_decision_expected"], "BLOCK")
        self.assertEqual(result["routing_expected"], "blocked")
        self.assertEqual(result["action_expected"]["thai_national_id"], "MASK")
        self.assertEqual(result["action_expected"]["api_key"], "BLOCK")

    def test_health_data_is_redacted(self):
        result = resolve_policy([Entity("pii", "health_condition", "asthma")],
                                "external_assistant", self.policy)
        self.assertEqual(result["policy_decision_expected"], "REDACT")
        self.assertEqual(result["transformation_expected"],
                         [{"entity_type": "health_condition", "action": "REDACT"}])

    def test_scenario_floor_applies_to_detected_entities(self):
        result = resolve_policy([Entity("pii", "thai_name", "Anan Jaidee")],
                                "no_external_transfer", self.policy)
        self.assertEqual(result["policy_decision_expected"], "LOCAL_ONLY")
        self.assertEqual(result["routing_expected"], "local")

    def test_no_entities_means_allow(self):
        result = resolve_policy([], "no_external_transfer", self.policy)
        self.assertEqual(result["policy_decision_expected"], "ALLOW")
        self.assertEqual(result["routing_expected"], "local")
        self.assertEqual(result["transformation_expected"], [])

    def test_infrastructure_defaults_to_local(self):
        result = resolve_policy([Entity("infrastructure", "internal_ipv4", "10.20.1.15")],
                                "external_assistant", self.policy)
        self.assertEqual(result["policy_decision_expected"], "LOCAL_ONLY")
        self.assertEqual(result["routing_expected"], "local")

    def test_custom_action_order_is_respected(self):
        policy = {
            "action_order": ["ALLOW", "REDACT", "MASK", "TOKENIZE", "LOCAL_ONLY", "BLOCK"],
            "scenarios": {"s": {"description": "test", "routing": "external", "min_action": "ALLOW"}},
            "rules": [{"id": "r", "domains": ["pii"], "action": "MASK"}],
        }
        result = resolve_policy([Entity("pii", "thai_name", "Anan")], "s", policy)
        self.assertEqual(result["policy_decision_expected"], "MASK")

    def test_invalid_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_policy({
                "action_order": ["ALLOW", "BLOCK"],
                "scenarios": {"s": {"routing": "external"}},
                "rules": [{"id": "r", "domains": ["pii"], "action": "MASK"}],
            })
        with self.assertRaises(ValueError):
            validate_policy({
                "action_order": ["ALLOW", "MASK", "TOKENIZE", "REDACT", "LOCAL_ONLY", "BLOCK"],
                "scenarios": {"s": {"routing": "sideways"}},
                "rules": [{"id": "r", "domains": ["pii"], "action": "MASK"}],
            })


if __name__ == "__main__":
    unittest.main()
