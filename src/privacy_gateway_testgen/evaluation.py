"""Quality-gate evaluation over a generated dataset.

The evaluator reports what it measured.  It never fills in missing results.
"""

from __future__ import annotations

from typing import Iterable, List

from .models import ACTIONS
from .textsim import duplicate_report, split_overlap
from .validation import span_accuracy, validate_dataset

KNOWN_LIMITATIONS = [
    "Template-family isolation keeps validation/test prompts out of training, but a small dataset therefore has fewer template families per split.",
    "Negative lookalikes may still be flagged by pattern-only detectors; that is the intended false-positive probe, not a label error.",
    "Thai names, addresses and organisations are synthetic combinations that could coincidentally match real entities.",
    "Only documented test card BINs are used. No PCI DSS compliance is claimed or implied.",
    "The default policy file is an illustrative test configuration, not legal advice.",
    "LLM-generated prompts are not produced by this tool; imported annotations must be checked with the separate verification command before they are trusted.",
    "No performance, latency or production-readiness claim is made by the evaluator.",
    "Language, length, difficulty and domain weights are preferences, not exact quotas: prompt length and difficulty are coupled to the available template families, so the configured distribution can drift. The evaluator reports configured-vs-measured deltas.",
]

RECOMMENDED_IMPROVEMENTS = [
    "Add organisation-specific entity factories and policy files before deployment.",
    "Grow the template inventory when validation/test diversity matters more than dataset size.",
    "Run the manual review workflow for any LLM-authored cases before using them as ground truth.",
    "Re-run this evaluator after every template, factory or policy change.",
]


def _share(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def evaluate_dataset(cases: Iterable[dict], config: dict, policy: dict, reproducible: bool = True) -> dict:
    cases = list(cases)
    total = len(cases)
    gates_config = config["quality_gates"]
    issues = validate_dataset(cases, policy)
    schema_validity = 1.0 if total == 0 else 1.0 - (len(issues) / total)
    span_accuracy_value = span_accuracy(cases)
    threshold = float(config.get("near_duplicate_threshold", 0.98))
    duplicates = duplicate_report(cases, threshold)

    domains = {}
    languages = {}
    lengths = {}
    difficulties = {}
    entity_types = set()
    actions = {}
    structures = {}
    multi_domain = 0
    negatives = 0
    for case in cases:
        for domain in case["domains"]:
            domains[domain] = domains.get(domain, 0) + 1
        languages[case["language"]] = languages.get(case["language"], 0) + 1
        lengths[case["prompt_length_class"]] = lengths.get(case["prompt_length_class"], 0) + 1
        difficulties[case["difficulty"]] = difficulties.get(case["difficulty"], 0) + 1
        actions[case["policy_decision_expected"]] = actions.get(case["policy_decision_expected"], 0) + 1
        structures[case["structure"]] = structures.get(case["structure"], 0) + 1
        entity_types.update(case["entity_types"])
        if case["domain_scope"] == "multi_domain":
            multi_domain += 1
        if case["polarity"] == "negative":
            negatives += 1

    domain_shares = {domain: _share(count, total) for domain, count in sorted(domains.items())}
    language_shares = {language: _share(count, total) for language, count in sorted(languages.items())}
    length_shares = {length: _share(count, total) for length, count in sorted(lengths.items())}
    difficulty_shares = {str(level): _share(count, total) for level, count in sorted(difficulties.items())}
    negative_ratio = _share(negatives, total)
    multi_share = _share(multi_domain, total)
    target_negative = float(config["distributions"]["negative_ratio"])

    def delta(actual: dict, target: dict) -> dict:
        keys = sorted(set(actual) | set(target))
        return {key: round(float(actual.get(key, 0.0)) - float(target.get(key, 0.0)), 4) for key in keys}

    targets = config["distributions"]
    fidelity = {
        "language": {
            "target": {key: float(value) for key, value in targets["language"].items()},
            "measured": language_shares,
            "delta": delta(language_shares, targets["language"]),
        },
        "length": {
            "target": {key: float(value) for key, value in targets["length"].items()},
            "measured": length_shares,
            "delta": delta(length_shares, targets["length"]),
        },
        "difficulty": {
            "target": {key: float(value) for key, value in targets["difficulty"].items()},
            "measured": difficulty_shares,
            "delta": delta(difficulty_shares, targets["difficulty"]),
        },
        "domain": {
            "target": {key: float(value) for key, value in targets["domain"].items()},
            "measured": domain_shares,
            "delta": delta(domain_shares, targets["domain"]),
        },
    }
    fidelity["max_abs_delta"] = max(
        abs(value) for dimension in fidelity.values() for value in dimension["delta"].values()
    )

    family_overlap = split_overlap(cases, "template_family")
    prompt_overlap = []
    seen_by_split = {}
    for case in cases:
        from .textsim import normalize

        key = normalize(case["prompt"])
        previous = seen_by_split.get(key)
        if previous is not None and previous != case["split"]:
            prompt_overlap.append(case["test_id"])
        seen_by_split[key] = case["split"]
    split_integrity = not family_overlap and not prompt_overlap and duplicates["cross_split_near_duplicate_pairs"] == 0

    gates: List[dict] = []

    def gate(name: str, passed: bool, value, requirement) -> None:
        gates.append({"name": name, "passed": bool(passed), "value": value, "requirement": requirement})

    gate("schema_validity", schema_validity >= gates_config["schema_validity"],
         round(schema_validity, 4), f">= {gates_config['schema_validity']}")
    gate("span_accuracy", span_accuracy_value >= gates_config["span_accuracy"],
         round(span_accuracy_value, 4), f">= {gates_config['span_accuracy']}")
    gate("exact_duplicate_rate", duplicates["exact_duplicate_rate"] <= gates_config["max_exact_duplicate_rate"],
         duplicates["exact_duplicate_rate"], f"<= {gates_config['max_exact_duplicate_rate']}")
    gate("near_duplicate_rate", duplicates["near_duplicate_rate"] <= gates_config["max_near_duplicate_rate"],
         duplicates["near_duplicate_rate"], f"<= {gates_config['max_near_duplicate_rate']}")

    for domain in gates_config["required_domains"]:
        share = domain_shares.get(domain, 0.0)
        gate(f"domain:{domain}", share >= gates_config["min_domain_share"], share,
             f">= {gates_config['min_domain_share']}")
    for language in gates_config["required_languages"]:
        share = language_shares.get(language, 0.0)
        gate(f"language:{language}", share >= gates_config["min_language_share"], share,
             f">= {gates_config['min_language_share']}")
    for length in gates_config["required_lengths"]:
        share = length_shares.get(length, 0.0)
        gate(f"length:{length}", share >= gates_config["min_length_share"], share,
             f">= {gates_config['min_length_share']}")
    for level in gates_config["required_difficulties"]:
        share = difficulty_shares.get(str(level), 0.0)
        gate(f"difficulty:{level}", share >= gates_config["min_difficulty_share"], share,
             f">= {gates_config['min_difficulty_share']}")

    gate("entity_type_coverage", len(entity_types) >= gates_config["min_entity_types"],
         len(entity_types), f">= {gates_config['min_entity_types']}")
    gate("negative_ratio", abs(negative_ratio - target_negative) <= gates_config["negative_ratio_tolerance"],
         negative_ratio, f"{target_negative} +/- {gates_config['negative_ratio_tolerance']}")
    gate("multi_domain_share", multi_share >= gates_config["min_multi_domain_share"],
         multi_share, f">= {gates_config['min_multi_domain_share']}")
    if gates_config.get("require_all_actions", True):
        missing = sorted(set(ACTIONS) - set(actions))
        gate("action_coverage", not missing, sorted(actions), f"all actions; missing={missing}")
    if gates_config.get("require_split_integrity", True):
        gate("split_integrity", split_integrity,
             {"family_overlap": family_overlap, "prompt_overlap": prompt_overlap},
             "no template family or exact prompt crosses splits")
    if gates_config.get("require_reproducibility", True):
        gate("reproducibility", reproducible, reproducible, "two runs with the same seed are byte-identical")

    passed = all(item["passed"] for item in gates)
    return {
        "schema_version": "1.0",
        "dataset_version": config["dataset_version"],
        "seed": config["seed"],
        "total_cases": total,
        "passed": passed,
        "gates": gates,
        "failed_gates": [item["name"] for item in gates if not item["passed"]],
        "metrics": {
            "schema_validity": round(schema_validity, 4),
            "span_accuracy": round(span_accuracy_value, 4),
            "validation_issues": issues[:50],
            "validation_issue_cases": len(issues),
            "duplicates": duplicates,
            "domain_shares": domain_shares,
            "language_shares": language_shares,
            "length_shares": length_shares,
            "difficulty_shares": difficulty_shares,
            "negative_ratio": negative_ratio,
            "target_negative_ratio": target_negative,
            "multi_domain_share": multi_share,
            "distribution_fidelity": fidelity,
            "entity_types": sorted(entity_types),
            "entity_type_count": len(entity_types),
            "action_counts": dict(sorted(actions.items())),
            "structure_counts": dict(sorted(structures.items())),
            "split_counts": {
                split: sum(1 for case in cases if case["split"] == split)
                for split in ("train", "validation", "test")
            },
            "split_integrity": {
                "passed": split_integrity,
                "family_overlap": family_overlap,
                "prompt_overlap": prompt_overlap,
                "cross_split_near_duplicate_pairs": duplicates["cross_split_near_duplicate_pairs"],
            },
            "reproducible": reproducible,
        },
        "known_limitations": list(KNOWN_LIMITATIONS),
        "recommended_improvements": list(RECOMMENDED_IMPROVEMENTS),
    }


def markdown_report(report: dict) -> str:
    lines = [
        "# Evaluation Report",
        "",
        f"- Dataset version: `{report['dataset_version']}`",
        f"- Seed: `{report['seed']}`",
        f"- Cases: `{report['total_cases']}`",
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
        lines.append(
            f"| {gate['name']} | {'PASS' if gate['passed'] else 'FAIL'} | {value} | {gate['requirement']} |"
        )
    lines.extend([
        "",
        "## Coverage",
        "",
        f"- Domains: `{report['metrics']['domain_shares']}`",
        f"- Languages: `{report['metrics']['language_shares']}`",
        f"- Lengths: `{report['metrics']['length_shares']}`",
        f"- Difficulties: `{report['metrics']['difficulty_shares']}`",
        f"- Actions: `{report['metrics']['action_counts']}`",
        f"- Entity types: `{report['metrics']['entity_type_count']}`",
        f"- Negative ratio: `{report['metrics']['negative_ratio']}` (target `{report['metrics']['target_negative_ratio']}`)",
        f"- Multi-domain share: `{report['metrics']['multi_domain_share']}`",
        f"- Split counts: `{report['metrics']['split_counts']}`",
        "",
        "## Duplicate analysis",
        "",
        f"- Exact duplicate rate: `{report['metrics']['duplicates']['exact_duplicate_rate']}`",
        f"- Near duplicate rate (threshold {report['metrics']['duplicates']['threshold']}): "
        f"`{report['metrics']['duplicates']['near_duplicate_rate']}`",
        f"- Near duplicate pairs: `{report['metrics']['duplicates']['near_duplicate_pairs']}`",
        "",
        "## Configured vs measured distributions",
        "",
    ])
    fidelity = report["metrics"]["distribution_fidelity"]
    for dimension in ("language", "length", "difficulty", "domain"):
        lines.append(f"- {dimension} delta: `{fidelity[dimension]['delta']}`")
    lines.append(f"- Maximum absolute delta: `{fidelity['max_abs_delta']}`")
    lines.extend([
        "",
        "## Known limitations",
        "",
    ])
    lines.extend(f"- {item}" for item in report["known_limitations"])
    lines.extend(["", "## Recommended improvements", ""])
    lines.extend(f"- {item}" for item in report["recommended_improvements"])
    lines.append("")
    return "\n".join(lines)
