"""Deterministic dataset generation engine."""

from __future__ import annotations

import json
import os
import random
from collections import Counter, defaultdict
from typing import Dict, Iterable, List

from . import __version__
from .config import canonical_json, weighted_pick
from .models import CHAR_OFFSET_CONVENTION, GENERATION_METHOD
from .policies import resolve_policy
from .templates import TEMPLATES, Template, build_draft
from .textsim import jaccard, normalize, shingles
from .validation import length_bucket, validate_case

SPLIT_CODES = {"train": "trn", "validation": "val", "test": "tst"}


def _allocate(group_size: int, split_names: List[str], weights: Dict[str, float]) -> Dict[str, int]:
    """Largest-remainder allocation with one guaranteed family per split."""
    if group_size < len(split_names):
        allocation = {name: 0 for name in split_names}
        allocation["train"] = group_size
        return allocation
    allocation = {name: 1 for name in split_names}
    remaining = group_size - len(split_names)
    total_weight = sum(weights[name] for name in split_names)
    quotas = {name: remaining * weights[name] / total_weight for name in split_names}
    floors = {name: int(quotas[name]) for name in split_names}
    assigned = sum(floors.values())
    leftovers = remaining - assigned
    order = sorted(split_names, key=lambda name: quotas[name] - floors[name], reverse=True)
    for name in order[:leftovers]:
        floors[name] += 1
    for name in split_names:
        allocation[name] += floors[name]
    return allocation


def assign_templates(templates: List[Template], rng: random.Random, weights: Dict[str, float]) -> Dict[str, List[Template]]:
    split_names = ["train", "validation", "test"]
    assigned: Dict[str, List[Template]] = {name: [] for name in split_names}
    strata = {
        "negative": [t for t in templates if t.negative],
        "positive_short": [t for t in templates if not t.negative and t.length_class == "short"],
        "positive_medium": [t for t in templates if not t.negative and t.length_class == "medium"],
        "positive_long": [t for t in templates if not t.negative and t.length_class == "long"],
    }
    for _, group in strata.items():
        shuffled = list(group)
        rng.shuffle(shuffled)
        allocation = _allocate(len(shuffled), split_names, weights)
        cursor = 0
        for name in split_names:
            assigned[name].extend(shuffled[cursor:cursor + allocation[name]])
            cursor += allocation[name]
    return assigned


def split_counts(total: int, weights: Dict[str, float]) -> Dict[str, int]:
    raw = {name: total * weight for name, weight in weights.items()}
    counts = {name: int(value) for name, value in raw.items()}
    remaining = total - sum(counts.values())
    order = sorted(raw, key=lambda name: raw[name] - counts[name], reverse=True)
    for name in order[:remaining]:
        counts[name] += 1
    for name in counts:
        if counts[name] == 0:
            counts[name] = 1
    while sum(counts.values()) > total:
        largest = max(counts, key=counts.get)
        counts[largest] -= 1
    return counts


class DatasetGenerator:
    def __init__(self, config: dict, policy: dict) -> None:
        self.config = config
        self.policy = policy
        self.seed = int(config["seed"])
        self.rng = random.Random(self.seed)
        self.distributions = config["distributions"]
        self.near_threshold = float(config.get("near_duplicate_threshold", 0.98))
        self.seen_prompts = set()
        self.seen_shingles: List[set] = []
        self.split_templates: Dict[str, List[Template]] = {}

    def generate(self) -> dict:
        self.rng = random.Random(self.seed)
        self.seen_prompts = set()
        self.seen_shingles = []
        self.split_templates = assign_templates(TEMPLATES, self.rng, self.config["splits"])
        counts = split_counts(int(self.config["total_samples"]), self.config["splits"])
        cases = []
        for split in ("train", "validation", "test"):
            cases.extend(self._generate_split(split, self.split_templates[split], counts[split]))
        return {
            "cases": cases,
            "stats": compute_stats(cases),
            "split_templates": {
                split: sorted(template.id for template in templates)
                for split, templates in self.split_templates.items()
            },
            "seed": self.seed,
            "dataset_version": self.config["dataset_version"],
            "near_duplicate_threshold": self.near_threshold,
        }

    def _sample_targets(self) -> dict:
        domain = weighted_pick(self.rng, self.distributions["domain"])
        language = weighted_pick(self.rng, self.distributions["language"])
        length = weighted_pick(self.rng, self.distributions["length"])
        difficulty = int(weighted_pick(self.rng, self.distributions["difficulty"]))
        negative = self.rng.random() < float(self.distributions["negative_ratio"])
        multi_domain = self.rng.random() < float(self.distributions["multi_domain_ratio"])
        density = int(weighted_pick(self.rng, self.distributions["entity_density"]))
        return {
            "domain": domain,
            "language": language,
            "length": length,
            "difficulty": difficulty,
            "negative": negative,
            "multi_domain": multi_domain,
            "density": density,
        }

    def _candidates(self, templates: List[Template], target: dict) -> List[Template]:
        pool = [t for t in templates if t.negative == target["negative"]]
        if not pool:
            return []
        # Length is the strongest preference: it is the easiest distribution
        # for a user to verify and the most visible property of a prompt.
        length_pool = [t for t in pool if t.length_class == target["length"]] or pool
        if target["negative"]:
            exact = [t for t in length_pool if t.difficulty == target["difficulty"]]
            return exact or length_pool

        # Within the requested length, honour the domain distribution, then
        # multi-domain preference, then difficulty.
        domain_pool = [t for t in length_pool if target["domain"] in t.domains] or length_pool
        if target["multi_domain"]:
            multi_pool = [t for t in domain_pool if len(t.domains) >= 2]
            if multi_pool:
                domain_pool = multi_pool
        exact = [t for t in domain_pool if t.difficulty == target["difficulty"]]
        return exact or domain_pool

    def _scenario(self) -> str:
        scenarios = self.policy["scenarios"]
        names = list(scenarios)
        weights = [scenarios[name].get("weight", 1) for name in names]
        return self.rng.choices(names, weights=weights, k=1)[0]

    def _generate_split(self, split: str, templates: List[Template], count: int) -> List[dict]:
        if not templates:
            raise RuntimeError(f"no templates assigned to split {split}")
        cases: List[dict] = []
        usage: Counter = Counter()
        attempts = 0
        max_attempts = count * 60
        while len(cases) < count and attempts < max_attempts:
            attempts += 1
            target = self._sample_targets()
            candidates = self._candidates(templates, target)
            if not candidates:
                continue
            # Balance rare and common templates so a split does not collapse
            # onto whichever family happens to match a difficulty bucket.
            weights = [1.0 / (1 + usage[template.id]) for template in candidates]
            template = self.rng.choices(candidates, weights=weights, k=1)[0]
            built = build_draft(template, self.rng, target["language"], target["density"])
            prompt = built["prompt"]
            expected = [span.entity for span in built["spans"] if span.entity.detection_expected]
            if bool(expected) == template.negative:
                raise RuntimeError(f"template polarity mismatch: {template.id}")
            normalized = normalize(prompt)
            if normalized in self.seen_prompts:
                continue
            shingle_set = shingles(prompt)
            if any(jaccard(shingle_set, other) >= self.near_threshold for other in self.seen_shingles):
                continue
            case = self._assemble_case(
                split=split,
                sequence=len(cases) + 1,
                template=template,
                built=built,
                language=target["language"],
                scenario=self._scenario(),
            )
            issues = validate_case(case, self.policy)
            if issues:
                raise RuntimeError(f"generated invalid case {case['test_id']}: {issues}")
            self.seen_prompts.add(normalized)
            self.seen_shingles.append(shingle_set)
            cases.append(case)
            usage[template.id] += 1
        if len(cases) < count:
            raise RuntimeError(
                f"could only generate {len(cases)}/{count} unique {split} cases; "
                "loosen distributions or add templates"
            )
        return cases

    def _assemble_case(self, split: str, sequence: int, template: Template, built: dict,
                       language: str, scenario: str) -> dict:
        prompt = built["prompt"]
        spans = sorted(built["spans"], key=lambda span: span.start)
        expected = [span.entity for span in spans if span.entity.detection_expected]
        expected_domains = sorted({entity.domain for entity in expected})
        expected_types = sorted({entity.entity_type for entity in expected})
        resolved = resolve_policy(expected, scenario, self.policy)
        measured_length = length_bucket(prompt)
        sensitive_actions = set(resolved["action_expected"].values()) - {"ALLOW"}

        styles = {measured_length}
        if template.negative:
            styles.add("negative")
        if template.contextual:
            styles.add("contextual")
        if len(expected_domains) >= 2:
            styles.add("mixed_domain")
        if template.negative:
            primary_style = "negative"
        elif template.contextual:
            primary_style = "contextual"
        elif len(expected_domains) >= 2:
            primary_style = "mixed_domain"
        else:
            primary_style = measured_length

        if template.negative:
            category = "negative"
        elif template.adversarial:
            category = "adversarial"
        elif len(expected_domains) >= 2:
            category = "multi_domain"
        else:
            category = "single_domain"

        if template.negative:
            objective = "false_positive"
        elif template.adversarial:
            objective = "adversarial_robustness"
        elif len(expected_domains) >= 2:
            objective = "cross_domain_policy"
        elif template.structure in ("unstructured", "report"):
            objective = "detection_and_policy"
        else:
            objective = "contextual_detection"

        if len(expected_domains) >= 2:
            domain_scope = "multi_domain"
        elif len(expected_domains) == 1:
            domain_scope = "single_domain"
        else:
            domain_scope = "none"

        scenario_description = self.policy["scenarios"][scenario]["description"]
        tags = set(template.tags)
        tags.update(expected_domains)
        tags.update(expected_types)
        tags.add(f"lang:{language}")
        tags.add(f"difficulty:{template.difficulty}")
        tags.add(f"split:{split}")

        return {
            "schema_version": "1.0",
            "test_id": f"pgt-{SPLIT_CODES[split]}-{sequence:05d}",
            "prompt": prompt,
            "language": language,
            "domains": expected_domains,
            "entities": [span.to_annotation() for span in spans],
            "entity_types": expected_types,
            "detection_expected": bool(expected_types),
            "classification_expected": expected_types,
            "policy_scenario": scenario,
            "policy_decision_expected": resolved["policy_decision_expected"],
            "action_expected": resolved["action_expected"],
            "routing_expected": resolved["routing_expected"],
            "transformation_expected": resolved["transformation_expected"],
            "policy_rule_ids": resolved["policy_rule_ids"],
            "output_leakage_check_expected": bool(sensitive_actions),
            "token_restoration_expected": (
                "authorized_context_only" if "TOKENIZE" in sensitive_actions else "not_applicable"
            ),
            "audit_log_expected": {
                "record_fields": ["test_id", "policy_scenario", "entity_types", "actions"],
                "forbidden_fields": ["exact_entity_value"],
            },
            "difficulty": template.difficulty,
            "test_category": category,
            "test_objective": objective,
            "rationale": f"{template.rationale} Scenario: {scenario_description}",
            "tags": sorted(tags),
            "generation_method": GENERATION_METHOD,
            "verification_status": "verified_spans",
            "prompt_length": len(prompt),
            "prompt_length_class": measured_length,
            "prompt_style": primary_style,
            "prompt_styles": sorted(styles),
            "context_complexity": template.context_complexity,
            "structure": template.structure,
            "polarity": "positive" if expected_types else "negative",
            "domain_scope": domain_scope,
            "structured": template.structure not in ("unstructured", "email", "chat", "report", "markdown"),
            "detection_mode": template.detection_mode,
            "edge_case": template.difficulty >= 5 or template.adversarial,
            "adversarial": template.adversarial,
            "split": split,
            "template_id": template.id,
            "template_family": template.family,
            "dataset_version": self.config["dataset_version"],
            "seed": self.seed,
            "char_offset_convention": CHAR_OFFSET_CONVENTION,
        }


def compute_stats(cases: Iterable[dict]) -> dict:
    cases = list(cases)
    total = len(cases)

    def count_where(values) -> dict:
        return dict(sorted(Counter(values).items()))

    by_split = count_where(case["split"] for case in cases)
    by_language = count_where(case["language"] for case in cases)
    by_length = count_where(case["prompt_length_class"] for case in cases)
    by_difficulty = count_where(str(case["difficulty"]) for case in cases)
    by_style = count_where(case["prompt_style"] for case in cases)
    by_polarity = count_where(case["polarity"] for case in cases)
    by_action = count_where(case["policy_decision_expected"] for case in cases)
    by_structure = count_where(case["structure"] for case in cases)
    by_domain = Counter()
    by_entity_type = Counter()
    entity_total = 0
    for case in cases:
        by_domain.update(case["domains"])
        by_entity_type.update(case["entity_types"])
        entity_total += len(case["entities"])
    multi_domain = sum(1 for case in cases if case["domain_scope"] == "multi_domain")
    return {
        "total_cases": total,
        "positive_cases": by_polarity.get("positive", 0),
        "negative_cases": by_polarity.get("negative", 0),
        "multi_domain_cases": multi_domain,
        "mean_entities_per_case": round(entity_total / total, 3) if total else 0.0,
        "by_split": by_split,
        "by_language": by_language,
        "by_length": by_length,
        "by_difficulty": by_difficulty,
        "by_style": by_style,
        "by_polarity": by_polarity,
        "by_action": by_action,
        "by_domain": dict(sorted(by_domain.items())),
        "by_entity_type": dict(sorted(by_entity_type.items())),
        "by_structure": by_structure,
    }


def _write_json(path: str, value) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _write_jsonl(path: str, cases: List[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")


def _sha256(path: str) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_dataset(dataset: dict, out_dir: str, config: dict, policy: dict) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    cases = dataset["cases"]
    by_split: Dict[str, List[dict]] = defaultdict(list)
    for case in cases:
        by_split[case["split"]].append(case)

    _write_jsonl(os.path.join(out_dir, "all.jsonl"), cases)
    for split in ("train", "validation", "test"):
        _write_jsonl(os.path.join(out_dir, f"{split}.jsonl"), by_split.get(split, []))
    _write_json(os.path.join(out_dir, "all.json"), cases)
    _write_json(os.path.join(out_dir, "stats.json"), compute_stats(cases))

    config_for_hash = {key: value for key, value in config.items() if not key.startswith("_")}
    manifest = {
        "schema_version": "1.0",
        "dataset_version": dataset["dataset_version"],
        "generator_version": __version__,
        "seed": dataset["seed"],
        "total_cases": len(cases),
        "split_counts": {split: len(by_split.get(split, [])) for split in ("train", "validation", "test")},
        "split_templates": dataset["split_templates"],
        "template_families": sorted({case["template_family"] for case in cases}),
        "near_duplicate_threshold": dataset["near_duplicate_threshold"],
        "config_sha256": __import__("hashlib").sha256(canonical_json(config_for_hash).encode("utf-8")).hexdigest(),
        "policy_sha256": __import__("hashlib").sha256(canonical_json(policy).encode("utf-8")).hexdigest(),
        "char_offset_convention": CHAR_OFFSET_CONVENTION,
        "files": {},
    }
    filenames = ["all.jsonl", "train.jsonl", "validation.jsonl", "test.jsonl", "all.json", "stats.json"]
    manifest["files"] = {name: _sha256(os.path.join(out_dir, name)) for name in filenames}
    _write_json(os.path.join(out_dir, "manifest.json"), manifest)
    return manifest
