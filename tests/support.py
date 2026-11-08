"""Shared test helpers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from privacy_gateway_testgen.config import load_config  # noqa: E402
from privacy_gateway_testgen.generator import DatasetGenerator  # noqa: E402
from privacy_gateway_testgen.policies import load_policy  # noqa: E402

CONFIG_PATH = str(ROOT / "configs" / "default.json")
POLICY_PATH = str(ROOT / "configs" / "policy.default.json")


def load_defaults():
    return load_config(CONFIG_PATH), load_policy(POLICY_PATH)


def make_case(*, prompt="Customer 1101700203450", start=9, end=22, expected=True,
              domain="pii", entity_type="thai_national_id", policy=None):
    from privacy_gateway_testgen.policies import resolve_policy
    from privacy_gateway_testgen.models import Entity

    annotation = {
        "domain": domain,
        "entity_type": entity_type,
        "character_start": start,
        "character_end": end,
        "exact_entity_value": prompt[start:end],
        "detection_expected": expected,
        "classification_expected": entity_type if expected else None,
        "valid": True,
        "note": "",
    }
    case = {
        "schema_version": "1.0",
        "test_id": "pgt-tst-99999",
        "prompt": prompt,
        "language": "en",
        "domains": [domain] if expected else [],
        "entities": [annotation],
        "entity_types": [entity_type] if expected else [],
        "detection_expected": expected,
        "classification_expected": [entity_type] if expected else [],
        "policy_scenario": "external_assistant",
        "policy_decision_expected": "MASK" if expected else "ALLOW",
        "action_expected": {entity_type: "MASK"} if expected else {},
        "routing_expected": "external",
        "transformation_expected": [{"entity_type": entity_type, "action": "MASK"}] if expected else [],
        "policy_rule_ids": ["pii.default"] if expected else [],
        "output_leakage_check_expected": bool(expected),
        "token_restoration_expected": "not_applicable",
        "audit_log_expected": {
            "record_fields": ["test_id", "policy_scenario", "entity_types", "actions"],
            "forbidden_fields": ["exact_entity_value"],
        },
        "difficulty": 1,
        "test_category": "single_domain" if expected else "negative",
        "test_objective": "detection_and_policy" if expected else "false_positive",
        "rationale": "test",
        "tags": [],
        "generation_method": "test",
        "verification_status": "verified_spans",
        "prompt_length": len(prompt),
        "prompt_length_class": "short",
        "prompt_style": "short",
        "prompt_styles": ["short"],
        "context_complexity": "low",
        "structure": "unstructured",
        "polarity": "positive" if expected else "negative",
        "domain_scope": "single_domain" if expected else "none",
        "structured": False,
        "detection_mode": "deterministic",
        "edge_case": False,
        "adversarial": False,
        "split": "test",
        "template_id": "test",
        "template_family": "test",
        "dataset_version": "0.1.0",
        "seed": 1,
        "char_offset_convention": "unicode_codepoints_0_based_end_exclusive",
    }
    if policy is not None and expected:
        resolved = resolve_policy([Entity(domain, entity_type, annotation["exact_entity_value"])],
                                  "external_assistant", policy)
        for key in ("policy_decision_expected", "action_expected", "routing_expected",
                    "transformation_expected", "policy_rule_ids"):
            case[key] = resolved[key]
    return case


def generate_small(count=36, seed=12345):
    config, policy = load_defaults()
    config["seed"] = seed
    config["total_samples"] = count
    dataset = DatasetGenerator(config, policy).generate()
    return dataset, config, policy
