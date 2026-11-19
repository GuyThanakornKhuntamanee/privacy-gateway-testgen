"""Measured evaluation for schema v2 datasets.

The report contains only values the generator can measure from the cases and
attachments it produced.  Image OCR is reported as layout verification, not as
OCR accuracy.
"""

from __future__ import annotations

import base64
import math
import re
from collections import Counter
from typing import Iterable, List

from ..models import ACTIONS
from ..textsim import duplicate_report
from .validation import prompt_span_accuracy, validate_dataset_v2

KNOWN_LIMITATIONS = [
    "PDF content is English/Latin only because the standard-library PDF writer uses built-in WinAnsi fonts. Thai PDF content is routed to DOCX/XLSX/TXT and the routing is recorded on the attachment.",
    "Image text uses a bitmap Latin font. Thai image OCR is not supported; Thai image scenarios are routed to English with an explicit language_routing field.",
    "Image and scanned-PDF annotations are verified at render-layout level. No third-party OCR engine is run in the test suite, so OCR accuracy is not claimed.",
    "PPTX speaker notes and native PowerPoint tables are not emitted; slide body text and later-slide placement are supported.",
    "YAML/TOML/INI/ENV verification uses the generator's strict subset parser, not PyYAML or tomllib.",
    "Archives, password-protected containers, audio, video, executables and recursive archive extraction are out of scope.",
    "Template-family isolation is enforced for file bundles; a very small dataset consequently has fewer families in validation/test.",
    "The default policy file is an illustrative test configuration, not legal advice or a compliance certification.",
    "All entities are synthetic. Coincidental similarity to a real person, host or company is possible but not intended.",
    "Cross-file consistency is validated on the generated scenario plan and annotations, not by executing a downstream gateway.",
]

RECOMMENDED = [
    "Run the generated files through the actual gateway extractors, then compare their extraction output with ground_truth/entities.jsonl.",
    "Add organisation-specific archetypes and policy files before using the dataset operationally.",
    "Use a larger seed/count when a profile must show every file family in every split.",
    "Review any case marked verified_partial before treating OCR-oriented labels as authoritative.",
]


def _share(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _stdev(values: List[int]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return round(math.sqrt(sum((value - mean) ** 2 for value in values) / len(values)), 2)


def _openings(cases: Iterable[dict]) -> dict:
    counts = Counter()
    total = 0
    for case in cases:
        normalized = " ".join(case["prompt"].lower().split())
        opening = " ".join(normalized.split()[:3])
        counts[opening] += 1
        total += 1
    top = counts.most_common(10)
    return {
        "top": [{"opening": value, "count": count} for value, count in top],
        "top_share": _share(top[0][1], total) if top else 0.0,
        "unique": len(counts),
    }


def _repeated_phrases(cases: Iterable[dict]) -> dict:
    counts = Counter()
    total = 0
    for case in cases:
        normalized = " ".join(case["prompt"].lower().split())
        words = normalized.split()
        grams = {" ".join(words[index:index + 4]) for index in range(max(0, len(words) - 3))}
        counts.update(grams)
        total += 1
    repeated = [(phrase, count) for phrase, count in counts.most_common(10) if count > 1]
    return {
        "top": [{"phrase": phrase, "count": count} for phrase, count in repeated],
        "top_share": _share(repeated[0][1], total) if repeated else 0.0,
    }


def _safety(cases: Iterable[dict]) -> dict:
    issues: List[str] = []
    email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+)")
    for case in cases:
        for annotation in case.get("entities", []):
            value = annotation.get("exact_entity_value", "")
            domain = annotation.get("domain")
            if domain == "secrets" and annotation.get("detection_expected"):
                lowered = value.lower()
                synthetic = any(marker in lowered for marker in ("example", "fake", "redacted", "changeme", "your_api_key"))
                if not synthetic:
                    try:
                        decoded = base64.b64decode(value, validate=True).decode("utf-8", "ignore").lower()
                    except Exception:
                        decoded = ""
                    synthetic = any(marker in decoded for marker in ("example", "fake", "synthetic"))
                if not synthetic:
                    issues.append(f"{case['test_id']}: secret lacks a synthetic marker: {annotation['entity_type']}")
            if annotation.get("entity_type") == "email_address":
                for match in email_pattern.finditer(value):
                    host = match.group(1).lower()
                    if not (host.endswith("example.com") or host.endswith("example.org")
                            or host.endswith("example.net") or host.endswith(".example")):
                        issues.append(f"{case['test_id']}: email uses a non-example domain: {host}")
    return {"passed": not issues, "issues": issues[:50], "issue_count": len(issues)}


def evaluate_v2(dataset: dict, config: dict, policy: dict, reproducible: bool = True) -> dict:
    cases = list(dataset["cases"])
    total = len(cases)
    gates_config = config["quality_gates"]
    validation_issues = validate_dataset_v2(cases, policy)
    schema_validity = 1.0 if total == 0 else 1.0 - (len(validation_issues) / total)
    prompt_accuracy = prompt_span_accuracy(cases)

    attachments = [item for case in cases for item in case["attachments"]]
    attachment_annotations = [item for case in cases for item in case["entities"] if item["source"] == "attachment"]
    verified_attachments = [item for item in attachments if item["verification"]["status"] in ("verified", "verified_layout")]
    verified_annotations = [item for item in attachment_annotations if item["verification"] in ("verified", "verified_layout")]
    extraction_failures = sum(1 for item in attachment_annotations if item["verification"] == "unverified")
    file_open_rate = _share(len(verified_attachments), len(attachments)) if attachments else 1.0
    entity_location_accuracy = (
        _share(len(verified_annotations), len(attachment_annotations)) if attachment_annotations else 1.0
    )
    extraction_accuracy = (
        _share(len(attachment_annotations) - extraction_failures, len(attachment_annotations))
        if attachment_annotations else 1.0
    )

    threshold = float(config.get("near_duplicate_threshold", 0.96))
    duplicates = duplicate_report(cases, threshold)
    skeleton_counts = Counter(case.get("document_fingerprint") for case in cases)
    repeated_skeletons = sum(count - 1 for count in skeleton_counts.values() if count > 1)
    document_duplicate_rate = _share(repeated_skeletons, total)

    domains = Counter()
    languages = Counter()
    personas = Counter()
    intents = Counter()
    difficulties = Counter()
    file_types = Counter()
    attachment_file_types = Counter()
    archetypes = Counter()
    attachment_counts = Counter(str(case["attachment_count"]) for case in cases)
    actions = Counter()
    extraction_methods = Counter()
    entity_density = Counter()
    multi_domain = 0
    negatives = 0
    ambiguous = 0
    ocr_cases = 0
    attachment_languages = Counter()
    language_matrix = Counter()
    bundle_kinds = Counter()
    mixed_attachments = 0
    mixed_attachments_verified = 0
    routed_attachments = 0
    structure_reference_cases = 0
    structure_references_total = 0
    structure_references_resolved = 0
    cross_file_cases = 0
    cross_file_links = 0
    multi_file_cases = 0
    same_archetype_cases = 0
    consistency_total = 0
    consistency_passed = 0
    prompt_lengths: List[int] = []
    for case in cases:
        domains.update(case["domains"])
        languages[case["language"]] += 1
        personas[case["persona"]] += 1
        intents[case["intent"]] += 1
        difficulties[str(case["difficulty"])] += 1
        file_types.update(case["file_types"])
        attachment_file_types.update(item["extension"] for item in case["attachments"])
        archetypes.update(case["archetypes"])
        actions[case["policy_decision_expected"]] += 1
        extraction_methods.update(case["extraction_methods"])
        multi_domain += 1 if case["domain_scope"] == "multi_domain" else 0
        negatives += 1 if case["polarity"] == "negative" else 0
        ambiguous += 1 if case["test_category"] == "ambiguous" else 0
        ocr_cases += 1 if "ocr" in case["tags"] else 0
        attachment_languages.update(item.get("language", "unknown") for item in case["attachments"])
        for matrix in case.get("language_coverage", {}).get("matrices", []):
            language_matrix[matrix] += 1
        bundle_kinds[case.get("bundle", {}).get("kind", "unknown")] += 1
        for item in case["attachments"]:
            if item.get("language") == "mixed":
                mixed_attachments += 1
                if item.get("language_check", {}).get("contains_both"):
                    mixed_attachments_verified += 1
            if item.get("language_routing"):
                routed_attachments += 1
        if case["attachment_count"] > 1:
            multi_file_cases += 1
        ids = [item["archetype"] for item in case["attachments"]]
        if len(ids) > 1 and len(set(ids)) < len(ids):
            same_archetype_cases += 1
        refs = case.get("structure_references", [])
        if refs:
            structure_reference_cases += 1
        structure_references_total += len(refs)
        structure_references_resolved += sum(1 for ref in refs if ref.get("resolved"))
        links = case.get("cross_file_links", [])
        if links:
            cross_file_cases += 1
        cross_file_links += len(links)
        checks = case.get("consistency_checks", [])
        consistency_total += len(checks)
        consistency_passed += sum(1 for check in checks if check.get("passed"))
        prompt_lengths.append(case["prompt_length"])
        count = len(case["entities"])
        entity_density["0" if count == 0 else ("1-3" if count <= 3 else ("4-6" if count <= 6 else "7+"))] += 1

    shares = {
        "domains": {key: _share(value, total) for key, value in sorted(domains.items())},
        "languages": {key: _share(value, total) for key, value in sorted(languages.items())},
        "personas": {key: _share(value, total) for key, value in sorted(personas.items())},
        "intents": {key: _share(value, total) for key, value in sorted(intents.items())},
        "difficulties": {key: _share(value, total) for key, value in sorted(difficulties.items())},
        "file_types": {key: _share(value, total) for key, value in sorted(file_types.items())},
        "archetypes": {key: _share(value, total) for key, value in sorted(archetypes.items())},
    }
    negative_ratio = _share(negatives, total)
    multi_share = _share(multi_domain, total)
    attachment_share = _share(sum(1 for case in cases if case["attachments"]), total)
    multi_file_share = _share(multi_file_cases, total)
    structure_reference_share = _share(structure_reference_cases, total)
    structure_resolution_rate = (
        _share(structure_references_resolved, structure_references_total)
        if structure_references_total else 1.0
    )
    consistency_rate = _share(consistency_passed, consistency_total) if consistency_total else 1.0
    mixed_script_rate = _share(mixed_attachments_verified, mixed_attachments) if mixed_attachments else 1.0
    opening = _openings(cases)
    phrases = _repeated_phrases(cases)
    safety = _safety(cases)
    verification_summary = Counter(case["verification_status"] for case in cases)

    gates: List[dict] = []

    def gate(name: str, passed: bool, value, requirement) -> None:
        gates.append({"name": name, "passed": bool(passed), "value": value, "requirement": requirement})

    gate("schema_validity", schema_validity >= gates_config["schema_validity"],
         round(schema_validity, 4), f">= {gates_config['schema_validity']}")
    gate("prompt_span_accuracy", prompt_accuracy >= gates_config["entity_location_accuracy"],
         round(prompt_accuracy, 4), f">= {gates_config['entity_location_accuracy']}")
    gate("file_open_rate", file_open_rate >= gates_config["file_open_rate"],
         file_open_rate, f">= {gates_config['file_open_rate']}")
    gate("entity_location_accuracy", entity_location_accuracy >= gates_config["entity_location_accuracy"],
         entity_location_accuracy, f">= {gates_config['entity_location_accuracy']}")
    gate("extraction_accuracy", extraction_accuracy >= gates_config["entity_location_accuracy"],
         extraction_accuracy, f">= {gates_config['entity_location_accuracy']}")
    gate("exact_duplicate_rate", duplicates["exact_duplicate_rate"] <= gates_config["max_exact_duplicate_rate"],
         duplicates["exact_duplicate_rate"], f"<= {gates_config['max_exact_duplicate_rate']}")
    gate("near_duplicate_rate", duplicates["near_duplicate_rate"] <= gates_config["max_near_duplicate_rate"],
         duplicates["near_duplicate_rate"], f"<= {gates_config['max_near_duplicate_rate']}")
    gate("document_duplicate_rate", document_duplicate_rate <= gates_config["max_near_duplicate_rate"],
         document_duplicate_rate, f"<= {gates_config['max_near_duplicate_rate']}")
    gate("file_type_coverage", len(file_types) >= gates_config["min_file_type_count"],
         sorted(file_types), f">= {gates_config['min_file_type_count']} types")
    gate("archetype_coverage", len(archetypes) >= gates_config["min_archetype_count"],
         len(archetypes), f">= {gates_config['min_archetype_count']}")
    gate("persona_coverage", len(personas) >= gates_config["min_persona_count"],
         len(personas), f">= {gates_config['min_persona_count']}")
    gate("intent_coverage", len(intents) >= gates_config["min_intent_count"],
         len(intents), f">= {gates_config['min_intent_count']}")
    gate("language_coverage", len(languages) >= gates_config["min_language_count"],
         sorted(languages), f">= {gates_config['min_language_count']}")
    is_21 = all(case.get("schema_version") == "2.1" for case in cases)
    if is_21:
        gate("attachment_language_coverage",
             len(attachment_languages) >= gates_config.get("min_attachment_language_count", 2),
             dict(sorted(attachment_languages.items())),
             f">= {gates_config.get('min_attachment_language_count', 2)} languages")
        gate("language_matrix_coverage",
             len(language_matrix) >= gates_config.get("min_language_matrix_combinations", 4),
             dict(sorted(language_matrix.items())),
             f">= {gates_config.get('min_language_matrix_combinations', 4)} prompt/attachment pairs")
        gate("mixed_language_script", mixed_script_rate >= 1.0, mixed_script_rate,
             "all mixed attachments contain Thai and English script")
        gate("structure_reference_resolution", structure_resolution_rate >= 1.0,
             structure_resolution_rate, "all structure references resolve")
        gate("structure_reference_share",
             structure_reference_share >= gates_config.get("min_structure_reference_share", 0.0),
             structure_reference_share,
             f">= {gates_config.get('min_structure_reference_share', 0.0)}")
        gate("multi_file_share", multi_file_share >= gates_config.get("min_multi_file_share", 0.0),
             multi_file_share, f">= {gates_config.get('min_multi_file_share', 0.0)}")
        gate("cross_file_link_coverage",
             cross_file_cases >= gates_config.get("min_cross_file_link_cases", 0),
             cross_file_cases, f">= {gates_config.get('min_cross_file_link_cases', 0)} cases")
        gate("same_archetype_bundle_coverage",
             same_archetype_cases >= gates_config.get("min_same_archetype_bundle_cases", 0),
             same_archetype_cases, f">= {gates_config.get('min_same_archetype_bundle_cases', 0)} cases")
        gate("cross_file_consistency",
             consistency_rate >= gates_config.get("min_consistency_rate", 1.0),
             consistency_rate, f">= {gates_config.get('min_consistency_rate', 1.0)}")
    gate("domain_coverage", len(domains) >= gates_config["min_domain_count"],
         sorted(domains), f">= {gates_config['min_domain_count']}")
    gate("negative_share", negative_ratio >= gates_config["min_negative_ratio"],
         negative_ratio, f">= {gates_config['min_negative_ratio']}")
    gate("multi_domain_share", multi_share >= gates_config["min_multi_domain_share"],
         multi_share, f">= {gates_config['min_multi_domain_share']}")
    gate("attachment_share", attachment_share >= gates_config["min_attachment_share"],
         attachment_share, f">= {gates_config['min_attachment_share']}")
    gate("ocr_case_coverage", ocr_cases >= gates_config["min_ocr_cases"],
         ocr_cases, f">= {gates_config['min_ocr_cases']}")
    gate("opening_repetition", opening["top_share"] <= gates_config["max_top_opening_share"],
         opening["top_share"], f"<= {gates_config['max_top_opening_share']}")
    gate("repeated_phrase_rate", phrases["top_share"] <= gates_config["max_top_phrase_share"],
         phrases["top_share"], f"<= {gates_config['max_top_phrase_share']}")
    archetype_concentration = _share(max(archetypes.values()), total) if archetypes else 0.0
    gate("archetype_concentration", archetype_concentration <= gates_config["max_archetype_share"],
         archetype_concentration, f"<= {gates_config['max_archetype_share']}")
    gate("synthetic_safety", safety["passed"], safety["issue_count"], "0 safety issues")
    if gates_config.get("require_verification", True):
        gate("attachment_verification", file_open_rate == 1.0, file_open_rate, "== 1.0")
    if gates_config.get("require_all_actions", False):
        missing = sorted(set(ACTIONS) - set(actions))
        gate("action_coverage", not missing, sorted(actions), f"all actions; missing={missing}")
    if gates_config.get("require_reproducibility", False):
        gate("reproducibility", reproducible, reproducible, "same seed + config reproduce bytes")
    passed = all(item["passed"] for item in gates)
    return {
        "schema_version": "2.1",
        "dataset_version": config["dataset_version"],
        "profile": config["profile"],
        "seed": config["seed"],
        "total_cases": total,
        "total_files": len(attachments),
        "passed": passed,
        "gates": gates,
        "failed_gates": [item["name"] for item in gates if not item["passed"]],
        "metrics": {
            "schema_validity": round(schema_validity, 4),
            "prompt_span_accuracy": round(prompt_accuracy, 4),
            "file_open_rate": file_open_rate,
            "entity_location_accuracy": entity_location_accuracy,
            "extraction_accuracy": extraction_accuracy,
            "extraction_failures": extraction_failures,
            "attachment_language_shares": {
                key: _share(value, len(attachments)) for key, value in sorted(attachment_languages.items())
            },
            "language_matrix": dict(sorted(language_matrix.items())),
            "language_matrix_combinations": len(language_matrix),
            "mixed_attachments": mixed_attachments,
            "mixed_attachments_verified": mixed_attachments_verified,
            "mixed_script_rate": mixed_script_rate,
            "routed_attachments": routed_attachments,
            "bundle_kinds": dict(sorted(bundle_kinds.items())),
            "multi_file_cases": multi_file_cases,
            "multi_file_share": multi_file_share,
            "same_archetype_bundle_cases": same_archetype_cases,
            "structure_reference_cases": structure_reference_cases,
            "structure_reference_share": structure_reference_share,
            "structure_references_total": structure_references_total,
            "structure_references_resolved": structure_references_resolved,
            "structure_resolution_rate": structure_resolution_rate,
            "cross_file_link_cases": cross_file_cases,
            "cross_file_links": cross_file_links,
            "consistency_checks": consistency_total,
            "consistency_passed": consistency_passed,
            "consistency_rate": consistency_rate,
            "detection_evaluated": False,
            "detection_note": "No detector or gateway was run; these metrics cover file ingestion and annotation provenance only.",
            "validation_issues": validation_issues[:50],
            "validation_issue_cases": len(validation_issues),
            "duplicates": duplicates,
            "document_duplicate_rate": document_duplicate_rate,
            "domain_shares": shares["domains"],
            "language_shares": shares["languages"],
            "persona_shares": shares["personas"],
            "intent_shares": shares["intents"],
            "difficulty_shares": shares["difficulties"],
            "file_type_shares": shares["file_types"],
            "file_type_counts": dict(sorted(attachment_file_types.items())),
            "archetype_shares": shares["archetypes"],
            "archetype_concentration": archetype_concentration,
            "attachment_count_distribution": dict(sorted(attachment_counts.items())),
            "entity_density_distribution": dict(sorted(entity_density.items())),
            "extraction_methods": dict(sorted(extraction_methods.items())),
            "negative_ratio": negative_ratio,
            "ambiguous_ratio": _share(ambiguous, total),
            "multi_domain_share": multi_share,
            "attachment_share": attachment_share,
            "ocr_cases": ocr_cases,
            "action_counts": dict(sorted(actions.items())),
            "split_counts": {split: sum(1 for case in cases if case["split"] == split) for split in ("train", "validation", "test")},
            "verification_status": dict(sorted(verification_summary.items())),
            "prompt_length": {
                "min": min(prompt_lengths) if prompt_lengths else 0,
                "max": max(prompt_lengths) if prompt_lengths else 0,
                "mean": round(sum(prompt_lengths) / total, 2) if total else 0.0,
                "stdev": _stdev(prompt_lengths),
            },
            "openings": opening,
            "repeated_phrases": phrases,
            "safety": safety,
            "reproducible": reproducible,
        },
        "known_limitations": list(KNOWN_LIMITATIONS),
        "recommended_improvements": list(RECOMMENDED),
    }


def markdown_report_v2(report: dict) -> str:
    metrics = report["metrics"]
    lines = [
        "# v2 Evaluation Report",
        "",
        f"- Dataset version: `{report['dataset_version']}`",
        f"- Profile: `{report['profile']}`",
        f"- Seed: `{report['seed']}`",
        f"- Cases: `{report['total_cases']}`",
        f"- Files: `{report['total_files']}`",
        f"- Overall: **{'PASS' if report['passed'] else 'FAIL'}**",
        "",
        "## Quality gates",
        "",
        "| Gate | Result | Value | Requirement |",
        "|---|---|---|---|",
    ]
    for gate in report["gates"]:
        value = gate["value"]
        if isinstance(value, (dict, list)):
            value = str(value)
        lines.append(f"| {gate['name']} | {'PASS' if gate['passed'] else 'FAIL'} | {value} | {gate['requirement']} |")
    lines.extend([
        "",
        "## Coverage",
        "",
        f"- File types: `{metrics['file_type_shares']}`",
        f"- File counts: `{metrics['file_type_counts']}`",
        f"- Archetypes: `{metrics['archetype_shares']}`",
        f"- Domains: `{metrics['domain_shares']}`",
        f"- Languages (prompt): `{metrics['language_shares']}`",
        f"- Languages (attachment): `{metrics['attachment_language_shares']}`",
        f"- Prompt/attachment language matrix: `{metrics['language_matrix']}`",
        f"- Mixed attachments verified: `{metrics['mixed_attachments_verified']}/{metrics['mixed_attachments']}`",
        f"- Routed (Latin-only renderer): `{metrics['routed_attachments']}`",
        f"- Personas: `{metrics['persona_shares']}`",
        f"- Intents: `{metrics['intent_shares']}`",
        f"- Difficulties: `{metrics['difficulty_shares']}`",
        f"- Attachment counts: `{metrics['attachment_count_distribution']}`",
        f"- Entity density: `{metrics['entity_density_distribution']}`",
        f"- Extraction methods: `{metrics['extraction_methods']}`",
        f"- Negative ratio: `{metrics['negative_ratio']}`",
        f"- Ambiguous ratio: `{metrics['ambiguous_ratio']}`",
        f"- Multi-domain share: `{metrics['multi_domain_share']}`",
        f"- Multi-file share: `{metrics['multi_file_share']}`",
        f"- Same-archetype bundle cases: `{metrics['same_archetype_bundle_cases']}`",
        f"- Structure-reference cases: `{metrics['structure_reference_cases']}` (`{metrics['structure_references_resolved']}/{metrics['structure_references_total']}` resolved)",
        f"- Cross-file link cases: `{metrics['cross_file_link_cases']}` (`{metrics['cross_file_links']}` links)",
        f"- Consistency checks: `{metrics['consistency_passed']}/{metrics['consistency_checks']}` passed",
        f"- OCR cases: `{metrics['ocr_cases']}`",
        "",
        "## Verification",
        "",
        f"- File open rate: `{metrics['file_open_rate']}`",
        f"- Extraction accuracy: `{metrics['extraction_accuracy']}` (failures `{metrics['extraction_failures']}`)",
        f"- Entity location accuracy: `{metrics['entity_location_accuracy']}`",
        f"- Verification status: `{metrics['verification_status']}`",
        f"- Validation issue cases: `{metrics['validation_issue_cases']}`",
        "",
        "## Realism diagnostics",
        "",
        f"- Top prompt openings: `{metrics['openings']['top']}`",
        f"- Top opening share: `{metrics['openings']['top_share']}`",
        f"- Repeated 4-grams: `{metrics['repeated_phrases']['top']}`",
        f"- Repeated phrase share: `{metrics['repeated_phrases']['top_share']}`",
        f"- Archetype concentration: `{metrics['archetype_concentration']}`",
        f"- Prompt length: `{metrics['prompt_length']}`",
        f"- Document duplicate rate: `{metrics['document_duplicate_rate']}`",
        "",
        "## Duplicate analysis",
        "",
        f"- Exact duplicate rate: `{metrics['duplicates']['exact_duplicate_rate']}`",
        f"- Near duplicate rate: `{metrics['duplicates']['near_duplicate_rate']}`",
        f"- Cross-split near pairs: `{metrics['duplicates']['cross_split_near_duplicate_pairs']}`",
        "",
        "## Synthetic safety",
        "",
        f"- Passed: `{metrics['safety']['passed']}`",
        f"- Issues: `{metrics['safety']['issue_count']}`",
        "",
        "## Known limitations",
        "",
    ])
    lines.extend(f"- {item}" for item in report["known_limitations"])
    lines.extend(["", "## Recommended improvements", ""])
    lines.extend(f"- {item}" for item in report["recommended_improvements"])
    lines.append("")
    return "\n".join(lines)
