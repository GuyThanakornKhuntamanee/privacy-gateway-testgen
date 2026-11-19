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
SCHEMA_VERSIONS = ("2.0", "2.1")
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
REQUIRED_CASE_FIELDS_21 = (
    "prompt_language", "content_languages", "language_mode", "language_coverage",
    "scenario_id", "cross_file_links", "structure_references", "document_profile",
    "consistency_checks", "bundle",
)
REQUIRED_ATTACHMENT_FIELDS_21 = (
    "language", "language_mode", "language_mix", "language_capability",
    "language_check", "structure", "renderer_version", "dependency_renderer",
)
LATIN_ONLY_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def _check(condition: bool, message: str, issues: List[str]) -> None:
    if not condition:
        issues.append(message)


def validate_case_v2(case: dict, policy: Optional[dict] = None) -> List[str]:
    issues: List[str] = []
    for field in REQUIRED_CASE_FIELDS:
        _check(field in case, f"missing field: {field}", issues)
    if issues:
        return issues
    version = case["schema_version"]
    _check(version in SCHEMA_VERSIONS, "schema_version must be '2.0' or '2.1'", issues)
    if version == "2.1":
        for field in REQUIRED_CASE_FIELDS_21:
            _check(field in case, f"missing field: {field}", issues)
        if issues:
            return issues
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
        if version == "2.1":
            missing = [field for field in REQUIRED_ATTACHMENT_FIELDS_21 if field not in attachment]
            if missing:
                issues.append(f"{prefix}: missing {', '.join(missing)}")
                continue
            language = attachment["language"]
            _check(language in ("th", "en", "mixed"), f"{prefix}: invalid attachment language", issues)
            _check(attachment["language_mode"] in ("th", "en", "mixed"),
                   f"{prefix}: invalid language_mode", issues)
            _check(isinstance(attachment["language_mix"], str) and bool(attachment["language_mix"]),
                   f"{prefix}: language_mix must be a non-empty string", issues)
            _check(isinstance(attachment["language_capability"], list) and bool(attachment["language_capability"]),
                   f"{prefix}: language_capability must be a non-empty array", issues)
            if attachment["extension"] in LATIN_ONLY_EXTENSIONS:
                _check(language == "en", f"{prefix}: Latin-only renderer must carry English", issues)
                _check("en" in attachment["language_capability"],
                       f"{prefix}: capability must declare English", issues)
            elif language in ("th", "mixed"):
                _check(language in attachment["language_capability"],
                       f"{prefix}: capability does not declare {language}", issues)
            check = attachment.get("language_check", {})
            _check(isinstance(check, dict), f"{prefix}: language_check must be an object", issues)
            if isinstance(check, dict):
                if language == "th":
                    _check(bool(check.get("contains_thai")), f"{prefix}: Thai document has no Thai script", issues)
                elif language == "mixed":
                    _check(bool(check.get("contains_both")), f"{prefix}: mixed document lacks Thai or English", issues)
                elif language == "en":
                    _check(bool(check.get("contains_latin")), f"{prefix}: English document has no Latin script", issues)
            _check(isinstance(attachment.get("structure"), dict), f"{prefix}: structure must be an object", issues)
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

    if version == "2.1":
        _check_21(case, issues, attachment_ids)

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


def _structure_ref_resolves(ref: dict, attachments: List[dict]) -> bool:
    attachment = next((item for item in attachments
                       if item["attachment_id"] == ref.get("attachment_id")), None)
    if attachment is None:
        return False
    structure = attachment.get("structure") or {}
    kind, value = ref.get("kind"), ref.get("value")
    if kind == "sheet":
        return any(sheet.get("name") == value for sheet in structure.get("sheets", []))
    if kind == "row":
        sheet = ref.get("sheet")
        if sheet:
            match = next((item for item in structure.get("sheets", []) if item.get("name") == sheet), None)
            return bool(match) and 1 <= int(value) <= int(match.get("rows", 0))
        return 1 <= int(value) <= int(structure.get("rows", 0))
    if kind == "column":
        return value in structure.get("headers", [])
    if kind == "page":
        return 1 <= int(value) <= int(structure.get("pages", 0))
    if kind == "slide":
        return 1 <= int(value) <= int(structure.get("slides", 0))
    if kind == "section":
        return value in structure.get("headings", [])
    if kind == "line":
        return 1 <= int(value) <= int(structure.get("lines", 0))
    if kind == "key":
        return value in structure.get("keys", [])
    return False


def _check_21(case: dict, issues: List[str], attachment_ids: set) -> None:
    prompt_language = case.get("prompt_language")
    _check(prompt_language == case.get("language"), "prompt_language does not match language", issues)
    _check(case.get("language_mode") in ("th", "en", "mixed"), "invalid language_mode", issues)
    content_languages = case.get("content_languages")
    _check(isinstance(content_languages, list) and bool(content_languages),
           "content_languages must be a non-empty array", issues)
    _check(isinstance(case.get("scenario_id"), str) and bool(case.get("scenario_id")),
           "scenario_id must be a non-empty string", issues)
    coverage = case.get("language_coverage")
    _check(isinstance(coverage, dict), "language_coverage must be an object", issues)
    if isinstance(coverage, dict):
        actual = [item["language"] for item in case["attachments"]]
        _check(coverage.get("attachment_languages") == actual,
               "language_coverage.attachment_languages does not match attachments", issues)
        _check(coverage.get("prompt_language") == prompt_language,
               "language_coverage.prompt_language does not match", issues)
        if any(item == "mixed" for item in actual):
            _check(coverage.get("mixed_script_verified") is True,
                   "mixed attachments are not script-verified", issues)
    _check(len(case.get("document_profile", [])) == len(case["attachments"]),
           "document_profile does not match attachments", issues)
    checks = case.get("consistency_checks")
    _check(isinstance(checks, list) and bool(checks), "consistency_checks must be a non-empty array", issues)
    if isinstance(checks, list):
        for check in checks:
            _check(isinstance(check, dict) and bool(check.get("check")),
                   "consistency check is malformed", issues)
            _check(check.get("passed") is True, f"consistency check failed: {check.get('check')}", issues)
    refs = case.get("structure_references")
    _check(isinstance(refs, list), "structure_references must be an array", issues)
    if isinstance(refs, list):
        for ref in refs:
            _check(ref.get("attachment_id") in attachment_ids,
                   "structure reference attachment does not exist", issues)
            _check(ref.get("resolved") is True and _structure_ref_resolves(ref, case["attachments"]),
                   f"structure reference does not resolve: {ref.get('kind')}", issues)
    links = case.get("cross_file_links")
    _check(isinstance(links, list), "cross_file_links must be an array", issues)
    if isinstance(links, list):
        annotated = {
            (item["source_attachment"], item["canonical_entity_id"]): item
            for item in case["entities"] if item["source"] == "attachment"
        }
        for link in links:
            _check(link.get("consistent") is True, "cross-file link is inconsistent", issues)
            _check(len(link.get("attachments", [])) >= 2, "cross-file link needs two attachments", issues)
            for attachment_id in link.get("attachments", []):
                _check(attachment_id in attachment_ids, "cross-file link attachment missing", issues)
                annotation = annotated.get((attachment_id, link.get("canonical_entity_id")))
                _check(annotation is not None and annotation["exact_entity_value"] == link.get("exact_entity_value"),
                       "cross-file link value does not match annotation", issues)
    verification = case.get("verification", {})
    if isinstance(verification, dict):
        _check(verification.get("language_passed") is True, "attachment language verification failed", issues)


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
