"""Prompt similarity helpers used by generation and evaluation."""

from __future__ import annotations

from typing import Iterable, List

SHINGLE_SIZE = 8


def normalize(prompt: str) -> str:
    return "".join(prompt.lower().split())


def shingles(prompt: str) -> set:
    normalized = normalize(prompt)
    if len(normalized) <= SHINGLE_SIZE:
        return {normalized}
    return {normalized[i:i + SHINGLE_SIZE] for i in range(len(normalized) - SHINGLE_SIZE + 1)}


def jaccard(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def duplicate_report(cases: Iterable[dict], threshold: float) -> dict:
    cases = list(cases)
    normalized = [normalize(case["prompt"]) for case in cases]
    seen = set()
    repeated = 0
    for value in normalized:
        if value in seen:
            repeated += 1
        seen.add(value)

    shingle_sets = [shingles(case["prompt"]) for case in cases]
    involved = set()
    pairs = []
    cross_split_pairs = []
    for left in range(len(cases)):
        for right in range(left + 1, len(cases)):
            similarity = jaccard(shingle_sets[left], shingle_sets[right])
            if similarity >= threshold:
                involved.add(left)
                involved.add(right)
                details = (cases[left]["test_id"], cases[right]["test_id"], round(similarity, 4))
                pairs.append(details)
                if cases[left]["split"] != cases[right]["split"]:
                    cross_split_pairs.append(details)
    total = len(cases)
    return {
        "threshold": threshold,
        "exact_duplicate_cases": repeated,
        "exact_duplicate_rate": round(repeated / total, 4) if total else 0.0,
        "near_duplicate_pairs": len(pairs),
        "near_duplicate_cases": len(involved),
        "near_duplicate_rate": round(len(involved) / total, 4) if total else 0.0,
        "cross_split_near_duplicate_pairs": len(cross_split_pairs),
        "cross_split_examples": cross_split_pairs[:10],
        "examples": pairs[:10],
    }


def split_overlap(cases: Iterable[dict], key: str) -> List[str]:
    seen = {}
    overlaps = set()
    for case in cases:
        value = case[key]
        split = case["split"]
        if value in seen and seen[value] != split:
            overlaps.add(value)
        seen[value] = split
    return sorted(overlaps)
