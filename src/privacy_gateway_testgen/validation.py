"""Dataset validation: schema, span integrity, taxonomy and policy consistency."""

from __future__ import annotations

from typing import Iterable, List, Optional

from .entities.common import luhn_valid, thai_id_valid
from .models import (
    ACTIONS,
    CHAR_OFFSET_CONVENTION,
    DIFFICULTIES,
    DOMAINS,
    LANGUAGES,
    LENGTH_CLASSES,
    LOOKALIKE_DOMAIN,
    POLARITIES,
    SPLITS,
    VERIFICATION_STATUSES,
    Entity,
)
from .policies import resolve_policy

STRUCTURES = {
    "unstructured", "email", "chat", "report", "markdown", "json", "yaml",
    "sql", "log", "table", "code", "terraform",
}
STYLES = {"short", "medium", "long", "contextual", "mixed_domain", "negative"}
CATEGORIES = {"single_domain", "multi_domain", "negative", "adversarial"}
OBJECTIVES = {
    "detection_and_policy", "contextual_detection", "cross_domain_policy",
    "false_positive", "adversarial_robustness",
}

REQUIRED_FIELDS = [
    "schema_version", "test_id", "prompt", "language", "domains", "entities",
    "entity_types", "detection_expected", "classification_expected",
    "policy_decision_expected", "action_expected", "routing_expected",
    "transformation_expected", "difficulty", "test_category", "test_objective",
    "rationale", "tags", "generation_method", "verification_status", "prompt_length",
    "prompt_length_class", "prompt_style", "prompt_styles",
    "context_complexity", "structure", "polarity", "domain_scope",
    "structured", "detection_mode", "edge_case", "adversarial", "split",
    "policy_scenario", "policy_rule_ids", "output_leakage_check_expected",
    "token_restoration_expected", "audit_log_expected",
    "template_id", "template_family",
    "dataset_version", "seed", "char_offset_convention",
]


def length_bucket(prompt: str) -> str:
    if len(prompt) <= 160:
        return "short"
    if len(prompt) < 800:
        return "medium"
    return "long"


def _check(condition: bool, message: str, issues: List[str]) -> None:
    if not condition:
        issues.append(message)


def validate_case(case: dict, policy: Optional[dict] = None) -> List[str]:
    issues: List[str] = []
    for field in REQUIRED_FIELDS:
        _check(field in case, f"missing field: {field}", issues)
    if issues:
        return issues

    _check(case["schema_version"] == "1.0", "schema_version must be '1.0'", issues)
    _check(isinstance(case["test_id"], str) and bool(case["test_id"]), "test_id must be a non-empty string", issues)
    prompt = case["prompt"]
    _check(isinstance(prompt, str) and bool(prompt), "prompt must be a non-empty string", issues)
    if not isinstance(prompt, str):
        return issues
    _check(case["char_offset_convention"] == CHAR_OFFSET_CONVENTION,
           f"char_offset_convention must be {CHAR_OFFSET_CONVENTION}", issues)
    _check(case["language"] in LANGUAGES, "language must be th, en or mixed", issues)
    _check(case["split"] in SPLITS, "invalid split", issues)
    _check(isinstance(case["difficulty"], int) and case["difficulty"] in DIFFICULTIES,
           "difficulty must be 1..5", issues)
    _check(case["prompt_length"] == len(prompt), "prompt_length does not match prompt", issues)
    _check(case["prompt_length_class"] == length_bucket(prompt),
           "prompt_length_class does not match measured length", issues)
    _check(case["prompt_length_class"] in LENGTH_CLASSES, "invalid prompt_length_class", issues)
    _check(case["prompt_style"] in STYLES, "invalid prompt_style", issues)
    _check(isinstance(case["prompt_styles"], list) and set(case["prompt_styles"]).issubset(STYLES),
           "prompt_styles contains invalid values", issues)
    _check(case["structure"] in STRUCTURES, "invalid structure", issues)
    _check(case["context_complexity"] in ("low", "medium", "high"), "invalid context_complexity", issues)
    _check(case["detection_mode"] in ("deterministic", "contextual"), "invalid detection_mode", issues)
    _check(case["polarity"] in POLARITIES, "invalid polarity", issues)
    _check(case["domain_scope"] in ("none", "single_domain", "multi_domain"), "invalid domain_scope", issues)
    _check(isinstance(case["structured"], bool), "structured must be boolean", issues)
    _check(isinstance(case["edge_case"], bool), "edge_case must be boolean", issues)
    _check(isinstance(case["adversarial"], bool), "adversarial must be boolean", issues)
    _check(case["test_category"] in CATEGORIES, "invalid test_category", issues)
    _check(case["test_objective"] in OBJECTIVES, "invalid test_objective", issues)
    _check(case["verification_status"] in VERIFICATION_STATUSES, "invalid verification_status", issues)
    _check(case["policy_decision_expected"] in ACTIONS, "invalid policy_decision_expected", issues)
    _check(case["routing_expected"] in ("external", "local", "blocked"), "invalid routing_expected", issues)
    _check(isinstance(case["action_expected"], dict), "action_expected must be an object", issues)
    _check(isinstance(case["transformation_expected"], list), "transformation_expected must be an array", issues)
    _check(isinstance(case["policy_rule_ids"], list), "policy_rule_ids must be an array", issues)
    _check(isinstance(case["output_leakage_check_expected"], bool),
           "output_leakage_check_expected must be boolean", issues)
    _check(case["token_restoration_expected"] in ("authorized_context_only", "not_applicable"),
           "invalid token_restoration_expected", issues)
    _check(isinstance(case["audit_log_expected"], dict), "audit_log_expected must be an object", issues)
    if isinstance(case["audit_log_expected"], dict):
        _check(isinstance(case["audit_log_expected"].get("record_fields"), list),
               "audit_log_expected.record_fields must be an array", issues)
        _check("exact_entity_value" in case["audit_log_expected"].get("forbidden_fields", []),
               "audit_log_expected must forbid exact_entity_value", issues)
    _check(isinstance(case["tags"], list) and all(isinstance(tag, str) for tag in case["tags"]),
           "tags must be an array of strings", issues)
    _check(isinstance(case["domains"], list), "domains must be an array", issues)
    _check(isinstance(case["entity_types"], list), "entity_types must be an array", issues)
    _check(isinstance(case["entities"], list), "entities must be an array", issues)

    entities = case["entities"]
    expected_domains = set()
    expected_types = set()
    last_end = -1
    for index, annotation in enumerate(entities):
        prefix = f"entities[{index}]"
        annotation_fields = ("entity_type", "domain", "character_start", "character_end",
                             "exact_entity_value", "detection_expected",
                             "classification_expected", "valid")
        missing = [field for field in annotation_fields if field not in annotation]
        if missing:
            for field in missing:
                issues.append(f"{prefix}: missing {field}")
            continue
        annotation_domain = annotation["domain"]
        if annotation_domain != LOOKALIKE_DOMAIN:
            _check(annotation_domain in DOMAINS, f"{prefix}: invalid domain", issues)
        start, end = annotation["character_start"], annotation["character_end"]
        _check(isinstance(start, int) and isinstance(end, int), f"{prefix}: offsets must be integers", issues)
        _check(0 <= start < end <= len(prompt), f"{prefix}: span out of bounds", issues)
        if 0 <= start < end <= len(prompt):
            _check(prompt[start:end] == annotation["exact_entity_value"],
                   f"{prefix}: prompt slice does not match exact_entity_value", issues)
        _check(start >= last_end, f"{prefix}: spans overlap or are not sorted", issues)
        last_end = end
        if annotation["detection_expected"]:
            expected_domains.add(annotation_domain)
            expected_types.add(annotation["entity_type"])
            _check(annotation["classification_expected"] == annotation["entity_type"],
                   f"{prefix}: classification_expected must equal entity_type for a positive entity", issues)
            if annotation["entity_type"] == "thai_national_id" and not thai_id_valid(annotation["exact_entity_value"]):
                issues.append(f"{prefix}: expected Thai national ID fails checksum")
            if annotation["entity_type"] == "payment_card_number" and not luhn_valid(annotation["exact_entity_value"]):
                issues.append(f"{prefix}: expected payment card fails Luhn check")
        else:
            _check(annotation["classification_expected"] is None,
                   f"{prefix}: negative entity must not have classification_expected", issues)
        _check(isinstance(annotation["valid"], bool), f"{prefix}: valid must be boolean", issues)

    _check(case["domains"] == sorted(expected_domains), "case domains do not match annotations", issues)
    _check(case["entity_types"] == sorted(expected_types), "case entity_types do not match annotations", issues)
    _check(case["classification_expected"] == sorted(expected_types),
           "case classification_expected does not match annotations", issues)
    _check(case["detection_expected"] == bool(expected_types),
           "detection_expected does not match annotations", issues)
    _check(case["polarity"] == ("positive" if expected_types else "negative"),
           "polarity does not match annotations", issues)
    if len(expected_domains) >= 2:
        _check(case["domain_scope"] == "multi_domain", "domain_scope should be multi_domain", issues)
    elif len(expected_domains) == 1:
        _check(case["domain_scope"] == "single_domain", "domain_scope should be single_domain", issues)
    else:
        _check(case["domain_scope"] == "none", "domain_scope should be none for a negative case", issues)

    if policy is not None:
        expected_entities = [
            Entity(
                domain=annotation["domain"],
                entity_type=annotation["entity_type"],
                value=annotation["exact_entity_value"],
                valid=annotation["valid"],
            )
            for annotation in entities
            if annotation["detection_expected"]
        ]
        try:
            resolved = resolve_policy(expected_entities, case["policy_scenario"], policy)
        except KeyError as exc:
            issues.append(f"unknown policy scenario: {exc}")
        else:
            _check(case["policy_decision_expected"] == resolved["policy_decision_expected"],
                   "policy_decision_expected does not match policy resolution", issues)
            _check(case["action_expected"] == resolved["action_expected"],
                   "action_expected does not match policy resolution", issues)
            _check(case["routing_expected"] == resolved["routing_expected"],
                   "routing_expected does not match policy resolution", issues)
            _check(case["transformation_expected"] == resolved["transformation_expected"],
                   "transformation_expected does not match policy resolution", issues)
            _check(sorted(case["policy_rule_ids"]) == resolved["policy_rule_ids"],
                   "policy_rule_ids do not match policy resolution", issues)

    return issues


def validate_dataset(cases: Iterable[dict], policy: Optional[dict] = None) -> List[dict]:
    results = []
    seen_ids = set()
    seen_prompts = {}
    for index, case in enumerate(cases):
        issues = validate_case(case, policy)
        test_id = case.get("test_id", f"index-{index}")
        if test_id in seen_ids:
            issues.append("duplicate test_id")
        seen_ids.add(test_id)
        prompt = case.get("prompt")
        if isinstance(prompt, str):
            normalized = " ".join(prompt.lower().split())
            if normalized in seen_prompts:
                issues.append(f"duplicate prompt (also {seen_prompts[normalized]})")
            else:
                seen_prompts[normalized] = test_id
        if issues:
            results.append({"test_id": test_id, "errors": issues})
    return results


def span_accuracy(cases: Iterable[dict]) -> float:
    total = 0
    correct = 0
    for case in cases:
        prompt = case.get("prompt", "")
        for annotation in case.get("entities", []):
            total += 1
            start = annotation.get("character_start")
            end = annotation.get("character_end")
            if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(prompt):
                if prompt[start:end] == annotation.get("exact_entity_value"):
                    correct += 1
    return 1.0 if total == 0 else correct / total
