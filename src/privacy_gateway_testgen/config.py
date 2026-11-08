"""Configuration loading and validation."""

from __future__ import annotations

import json
import os
from typing import Dict

from .models import DIFFICULTIES, DOMAINS, LANGUAGES, LENGTH_CLASSES

DEFAULT_DISTRIBUTIONS = {
    "domain": {"pii": 0.30, "payment": 0.25, "secrets": 0.25, "infrastructure": 0.20},
    "language": {"th": 0.45, "en": 0.25, "mixed": 0.30},
    "length": {"short": 0.30, "medium": 0.40, "long": 0.30},
    "difficulty": {"1": 0.12, "2": 0.20, "3": 0.25, "4": 0.25, "5": 0.18},
    "negative_ratio": 0.20,
    "multi_domain_ratio": 0.35,
    "entity_density": {"1": 0.35, "2": 0.30, "3": 0.20, "4": 0.15},
}

DEFAULT_GATES = {
    "schema_validity": 1.0,
    "span_accuracy": 1.0,
    "max_exact_duplicate_rate": 0.0,
    "max_near_duplicate_rate": 0.05,
    "required_domains": ["pii", "payment", "secrets", "infrastructure"],
    "min_domain_share": 0.05,
    "required_languages": ["th", "en", "mixed"],
    "min_language_share": 0.08,
    "required_lengths": ["short", "medium", "long"],
    "min_length_share": 0.08,
    "required_difficulties": [1, 2, 3, 4, 5],
    "min_difficulty_share": 0.04,
    "min_entity_types": 25,
    "negative_ratio_tolerance": 0.12,
    "min_multi_domain_share": 0.12,
    "require_all_actions": True,
    "require_split_integrity": True,
    "require_reproducibility": True,
}


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as handle:
        config = json.load(handle)
    config["_path"] = path
    config.setdefault("distributions", {})
    merged_dist = dict(DEFAULT_DISTRIBUTIONS)
    merged_dist.update(config["distributions"])
    config["distributions"] = merged_dist
    gates = dict(DEFAULT_GATES)
    gates.update(config.get("quality_gates", {}))
    config["quality_gates"] = gates
    validate_config(config)
    return config


def validate_config(config: dict) -> None:
    for key in ("schema_version", "dataset_version", "seed", "total_samples", "splits", "distributions"):
        if key not in config:
            raise ValueError(f"config missing required key: {key}")
    total = config["total_samples"]
    if not isinstance(total, int) or total < 6:
        raise ValueError("total_samples must be an integer >= 6")
    splits = config["splits"]
    if set(splits) != {"train", "validation", "test"}:
        raise ValueError("splits must contain train, validation, test")
    if any(not isinstance(value, (int, float)) or value <= 0 for value in splits.values()):
        raise ValueError("split weights must be positive numbers")
    dist = config["distributions"]
    allowed_keys = {
        "domain": set(DOMAINS),
        "language": set(LANGUAGES),
        "length": set(LENGTH_CLASSES),
        "difficulty": {str(level) for level in DIFFICULTIES},
    }
    for name in ("domain", "language", "length", "difficulty", "entity_density"):
        weights = dist.get(name)
        if not isinstance(weights, dict) or not weights:
            raise ValueError(f"distribution {name} must be a non-empty object")
        if any(not isinstance(value, (int, float)) or value < 0 for value in weights.values()):
            raise ValueError(f"distribution {name} weights must be non-negative")
        if sum(weights.values()) <= 0:
            raise ValueError(f"distribution {name} must have a positive total weight")
        if name in allowed_keys:
            unknown = set(weights) - allowed_keys[name]
            if unknown:
                raise ValueError(f"distribution {name} has unknown keys: {sorted(unknown)}")
    if set(dist["entity_density"]) - {str(level) for level in DIFFICULTIES}:
        raise ValueError("entity_density keys must be difficulty levels 1..5")
    for name in ("negative_ratio", "multi_domain_ratio"):
        value = dist.get(name)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"{name} must be between 0 and 1")
    policy_file = config.get("policy_file", "configs/policy.default.json")
    base = os.path.dirname(os.path.abspath(config.get("_path", "config.json")))
    config["policy_file"] = policy_file
    config["_resolved_policy_file"] = (
        policy_file if os.path.isabs(policy_file) else os.path.join(base, policy_file)
    )


def weighted_pick(rng, weights: Dict[str, float]) -> str:
    keys = list(weights)
    values = [weights[key] for key in keys]
    return rng.choices(keys, weights=values, k=1)[0]


def canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
