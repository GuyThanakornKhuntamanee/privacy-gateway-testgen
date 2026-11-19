"""Schema v2 validation: case shape, file-aware provenance and policy labels."""

from __future__ import annotations

from typing import Iterable, List, Optional

from ..models import (
    ACTIONS, CHAR_OFFSET_CONVENTION, DIFFICULTIES, DOMAINS, LANGUAGES, SPLITS,
)
from ..policies import resolve_policy
from ..models import Entity

VERIFICATION_STATUSES = ("verified", "verified_partial", "unverified")
ATTACHMENT_VERIFICATION_STATUSES = ("verified", "verified_layout", "unverified")
CATEGORIES = ("single_domain", "multi_domain", "negative", "ambiguous", "adversarial")
OBJECTIVES = (
    "detection_and_policy", "contextual_detection", "cross_domain_policy",
    "false_positive", "adversarial_robustness", "file_ingestion_and_policy",
    "ambiguous_context",
)
LOCATION_KINDS = {
    "prompt_span", "text_span", "csv_cell", "json_path", "yaml_path", "xml_path",
    "key_path", "xlsx_cell", "docx_paragraph", "docx_table_cell", "docx_header",
    "docx_footer", "pptx_shape", "pdf_text", "pdf_image", "image_ocr",
}
STRUCTURES = {"file_attachment", "pasted_text", "unstructured", "report", "markdown", "json", "yaml", "xml", "log", "table", "code"}

REQUIRED_CASE_FIELDS = (
    "schema_version", "test_id", "prompt", "language", "persona", "intent", "formality",
    "profile", "domains", "entities", "attachments", "attachment_count", "file_types",
    "archetypes", "difficulty", "test_category", "test_objective", "ambiguity",
    "policy_scenario", "policy_decision_expected", "action_expected", "routing_expected",
    "transformation_expected", "policy_rule_ids", "output_leakage_check_expected",
    "token_restoration_expected", "audit_log_expected", "rationale", "tags",
    "generation_method", "verification_status", "verification", "prompt_length",
    "prompt_length_class", "prompt_style", "context_complexity", "structure", "polarity",
    "domain_scope", "detection_mode", "split", "template_id", "template_family",
    "dataset_version", "seed", "char_offset_convention", "extraction_methods", "content_language",
    "document_fingerprint",
)
REQUIRED_ENTITY_FIELDS = (
    "annotation_id", "canonical_entity_id", "domain", "entity_type", "exact_entity_value",
    "detection_expected", "classification_expected", "valid", "note", "source",
    "source_attachment", "filename", "role", "location", "verification",
)
REQUIRED_ATTACHMENT_FIELDS = (
    "attachment_id", "filename", "extension", "file_type", "mime_type", "size_bytes",
    "sha256", "archetype", "renderer", "synthetic", "generated_seed", "expected_extraction_method",
    "verification", "path",
)


def _check(condition: bool, message: str, issues: List[str]) -> None:
    if not condition:
        issues.append(message)


def validate_case_v2(case: dict, policy: Optional[dict] = None) -> List[str]:
    issues: List[str] = []
    for field in REQUIRED_CASE_FIELDS:
        _check(field in case, f"missing field: {field}", issues)
    if issues:
        return issues
    _check(case["schema_version"] == "2.0", "schema_version must be '2.0'", issues)
    prompt = case["prompt"]
    _check(isinstance(prompt, str) and bool(prompt), "prompt must be a non-empty string", issues)
    _check(case["language"] in LANGUAGES, "invalid language", issues)
    _check(case["split"] in SPLITS, "invalid split", issues)
    _check(isinstance(case["difficulty"], int) and case["difficulty"] in DIFFICULTIES, "difficulty must be 1..5", issues)
    _check(case["verification_status"] in VERIFICATION_STATUSES, "invalid verification_status", issues)
    _check(case["test_category"] in CATEGORIES, "invalid test_category", issues)
    _check(case["test_objective"] in OBJECTIVES, "invalid test_objective", issues)
    _check(case["structure"] in STRUCTURES, "invalid structure", issues)
    _check(case["policy_decision_expected"] in ACTIONS, "invalid policy_decision_expected", issues)
    _check(case["routing_expected"] in ("external", "local", "blocked"), "invalid routing_expected", issues)
    _check(case["prompt_length"] == len(prompt), "prompt_length does not match prompt", issues)
    _check(case["prompt_length_class"] in ("short", "medium", "long"), "invalid prompt_length_class", issues)
    _check(case["char_offset_convention"] == CHAR_OFFSET_CONVENTION, "invalid char_offset_convention", issues)
    _check(isinstance(case["attachments"], list), "attachments must be an array", issues)
    _check(isinstance(case["entities"], list), "entities must be an array", issues)
    _check(case["attachment_count"] == len(case["attachments"]), "attachment_count does not match attachments", issues)
    _check(isinstance(case["ambiguity"], dict), "ambiguity must be an object", issues)
    _check(isinstance(case["verification"], dict), "verification must be an object", issues)

    attachment_ids = set()
    filenames = set()
    for index, attachment in enumerate(case["attachments"]):
        prefix = f"attachments[{index}]"
        missing = [field for field in REQUIRED_ATTACHMENT_FIELDS if field not in attachment]
        if missing:
            issues.append(f"{prefix}: missing {', '.join(missing)}")
            continue
        _check(attachment["attachment_id"] not in attachment_ids, f"{prefix}: duplicate attachment_id", issues)
        attachment_ids.add(attachment["attachment_id"])
        _check(attachment["filename"] not in filenames, f"{prefix}: duplicate filename", issues)
        filenames.add(attachment["filename"])
        _check(isinstance(attachment["size_bytes"], int) and attachment["size_bytes"] > 0,
               f"{prefix}: size_bytes must be positive", issues)
        _check(isinstance(attachment["sha256"], str) and len(attachment["sha256"]) == 64,
               f"{prefix}: sha256 must be 64 hex characters", issues)
        _check(attachment["synthetic"] is True, f"{prefix}: synthetic must be true", issues)
        _check(attachment["verification"].get("status") in ATTACHMENT_VERIFICATION_STATUSES,
               f"{prefix}: invalid verification status", issues)
    _check(sorted(case["file_types"]) == sorted({item["extension"] for item in case["attachments"]}),
           "file_types do not match attachments", issues)
    _check(sorted(case["archetypes"]) == sorted({item["archetype"] for item in case["attachments"]}),
           "archetypes do not match attachments", issues)

    expected_domains = set()
    expected_types = set()
    for index, annotation in enumerate(case["entities"]):
        prefix = f"entities[{index}]"
        missing = [field for field in REQUIRED_ENTITY_FIELDS if field not in annotation]
        if missing:
            issues.append(f"{prefix}: missing {', '.join(missing)}")
            continue
        _check(annotation["source"] in ("prompt", "attachment"), f"{prefix}: invalid source", issues)
        _check(annotation["verification"] in ("verified", "verified_layout", "unverified"),
               f"{prefix}: invalid annotation verification", issues)
        _check(annotation["domain"] in set(DOMAINS) | {"lookalike"}, f"{prefix}: invalid domain", issues)
        location = annotation["location"]
        _check(isinstance(location, dict) and location.get("kind") in LOCATION_KINDS,
               f"{prefix}: invalid location kind", issues)
        if annotation["source"] == "prompt":
            start, end = annotation.get("character_start"), annotation.get("character_end")
            _check(isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(prompt),
                   f"{prefix}: prompt span out of range", issues)
            if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(prompt):
                _check(prompt[start:end] == annotation["exact_entity_value"],
                       f"{prefix}: prompt slice does not match value", issues)
            _check(location.get("kind") == "prompt_span", f"{prefix}: prompt source needs prompt_span location", issues)
        else:
            _check(annotation["source_attachment"] in attachment_ids,
                   f"{prefix}: source_attachment does not exist", issues)
            _check(annotation["filename"] in filenames, f"{prefix}: filename does not exist", issues)
        if location.get("kind") in ("image_ocr", "pdf_image"):
            bbox = location.get("bbox")
            _check(isinstance(bbox, list) and len(bbox) == 4 and all(isinstance(value, (int, float)) for value in bbox),
                   f"{prefix}: invalid bbox", issues)
        if annotation["detection_expected"]:
            _check(annotation["classification_expected"] == annotation["entity_type"],
                   f"{prefix}: classification_expected must equal entity_type", issues)
            if annotation["domain"] != "lookalike":
                expected_domains.add(annotation["domain"])
            expected_types.add(annotation["entity_type"])
        else:
            _check(annotation["classification_expected"] is None,
                   f"{prefix}: negative annotation must not classify", issues)

    _check(case["domains"] == sorted(expected_domains), "domains do not match annotations", issues)
    _check(case["entity_types"] == sorted(expected_types), "entity_types do not match annotations", issues)
    _check(case["detection_expected"] == bool(expected_types), "detection_expected does not match annotations", issues)
    _check(case["polarity"] == ("positive" if expected_types else "negative"), "polarity does not match annotations", issues)
    expected_scope = "none" if not expected_domains else ("multi_domain" if len(expected_domains) >= 2 else "single_domain")
    _check(case["domain_scope"] == expected_scope, "domain_scope does not match annotations", issues)
    if expected_scope == "multi_domain":
        _check(case["test_category"] in ("multi_domain", "ambiguous"), "multi-domain case has wrong category", issues)
    if case["polarity"] == "negative":
        _check(case["test_category"] in ("negative", "ambiguous"), "negative case has wrong category", issues)

    if policy is not None:
        entities = [
            Entity(item["domain"], item["entity_type"], item["exact_entity_value"], valid=item["valid"])
            for item in case["entities"] if item["detection_expected"]
        ]
        try:
            resolved = resolve_policy(entities, case["policy_scenario"], policy)
        except KeyError as exc:
            issues.append(f"unknown policy scenario: {exc}")
        else:
            for key in ("policy_decision_expected", "action_expected", "routing_expected",
                        "transformation_expected", "policy_rule_ids"):
                _check(case[key] == resolved[key], f"{key} does not match policy resolution", issues)
    return issues


def validate_dataset_v2(cases: Iterable[dict], policy: Optional[dict] = None) -> List[dict]:
    results = []
    seen_ids = set()
    seen_prompts = {}
    for index, case in enumerate(cases):
        issues = validate_case_v2(case, policy)
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


def prompt_span_accuracy(cases: Iterable[dict]) -> float:
    total = 0
    correct = 0
    for case in cases:
        prompt = case.get("prompt", "")
        for annotation in case.get("entities", []):
            if annotation.get("source") != "prompt":
                continue
            total += 1
            start, end = annotation.get("character_start"), annotation.get("character_end")
            if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(prompt):
                if prompt[start:end] == annotation.get("exact_entity_value"):
                    correct += 1
    return 1.0 if total == 0 else correct / total
