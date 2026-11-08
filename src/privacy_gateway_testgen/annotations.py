"""Verification (and optional repair) of annotations for imported prompts.

Deterministic templates record spans by construction.  Prompts authored by an
LLM or imported from another tool do not get that guarantee, so their offsets
must be checked here.  A repaired offset proves the slice matches the value; it
does not prove that the value was classified correctly.
"""

from __future__ import annotations

from typing import List, Tuple

from .entities.common import luhn_valid, thai_id_valid


def verify_cases(cases: List[dict], repair: bool = False) -> Tuple[List[dict], dict]:
    total_annotations = 0
    valid = 0
    repaired = 0
    unresolved = []
    validity_warnings = []
    changed_cases = []

    for case in cases:
        prompt = case.get("prompt", "")
        case_changed = False
        for index, annotation in enumerate(case.get("entities", [])):
            total_annotations += 1
            value = annotation.get("exact_entity_value", "")
            entity_type = annotation.get("entity_type")
            if annotation.get("detection_expected"):
                if entity_type == "thai_national_id" and not thai_id_valid(value):
                    validity_warnings.append({
                        "test_id": case.get("test_id"),
                        "annotation_index": index,
                        "warning": "expected Thai national ID fails checksum; label may be wrong",
                    })
                if entity_type == "payment_card_number" and not luhn_valid(value):
                    validity_warnings.append({
                        "test_id": case.get("test_id"),
                        "annotation_index": index,
                        "warning": "expected payment card fails Luhn check; label may be wrong",
                    })
            start = annotation.get("character_start")
            end = annotation.get("character_end")
            if isinstance(start, int) and isinstance(end, int) and prompt[start:end] == value:
                valid += 1
                continue
            occurrences = []
            cursor = prompt.find(value)
            while cursor != -1:
                occurrences.append(cursor)
                cursor = prompt.find(value, cursor + 1)
            if len(occurrences) == 1 and repair:
                annotation["character_start"] = occurrences[0]
                annotation["character_end"] = occurrences[0] + len(value)
                repaired += 1
                valid += 1
                case_changed = True
            elif len(occurrences) == 1:
                unresolved.append({
                    "test_id": case.get("test_id"),
                    "annotation_index": index,
                    "reason": "offset mismatch; unique occurrence can be repaired",
                    "suggested_start": occurrences[0],
                })
            else:
                unresolved.append({
                    "test_id": case.get("test_id"),
                    "annotation_index": index,
                    "reason": f"{len(occurrences)} occurrences found" if occurrences else "value not found in prompt",
                })
        if case_changed:
            changed_cases.append(case.get("test_id"))

    semantics_unverified = sum(1 for case in cases if case.get("verification_status") == "unverified")
    report = {
        "cases": len(cases),
        "annotations": total_annotations,
        "spans_valid": valid,
        "spans_repaired": repaired,
        "unresolved": unresolved,
        "validity_warnings": validity_warnings,
        "cases_changed": changed_cases,
        "semantics_unverified_cases": semantics_unverified,
        "note": (
            "Span verification checks only that offsets select the exact value. "
            "It does not establish that detection or classification labels are correct."
        ),
    }
    return cases, report
