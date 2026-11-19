"""Configuration and profile loading for schema v2."""

from __future__ import annotations

import json
import os
from typing import Dict, Optional

from ..models import DIFFICULTIES, DOMAINS, LANGUAGES
from .realism import INTENT_PHRASES, PERSONAS
from .renderers import SUPPORTED_FORMATS

REQUIRED_DISTRIBUTIONS = (
    "attachment_probability", "attachment_count", "file_type", "language",
    "persona", "intent", "formality", "length", "difficulty", "domain",
    "entity_density", "ocr_difficulty", "negative_ratio", "ambiguous_ratio",
    "multi_domain_ratio", "typo_rate",
)
FORMALITIES = ("formal", "neutral", "casual")
LENGTHS = ("short", "medium", "long")
OCR_LEVELS = ("1", "2", "3", "4")


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def load_profiles(path: str) -> dict:
    return _read_json(path)


def _apply_profile(config: dict, profile_name: Optional[str]) -> dict:
    base = os.path.dirname(os.path.abspath(config.get("_path", "config.json")))
    profiles_file = config.get("profiles_file", "profiles.json")
    profiles_path = profiles_file if os.path.isabs(profiles_file) else os.path.join(base, profiles_file)
    profiles = load_profiles(profiles_path) if os.path.exists(profiles_path) else {}
    name = profile_name or config.get("profile") or "real-world-enterprise"
    if os.path.exists(name) and name.lower().endswith(".json"):
        spec = _read_json(name)
        name = spec.get("name", os.path.basename(name))
    else:
        if name not in profiles:
            raise ValueError(f"unknown profile {name!r}; available: {sorted(profiles)}")
        spec = profiles[name]
    merged = dict(config)
    distributions = dict(config.get("distributions", {}))
    distributions.update(spec.get("distributions", {}))
    merged["distributions"] = distributions
    merged["profile"] = name
    merged["_profile_spec"] = spec
    return merged


def load_v2_config(path: str, profile: Optional[str] = None) -> dict:
    config = _read_json(path)
    config["_path"] = path
    config = _apply_profile(config, profile)
    config.setdefault("near_duplicate_threshold", 0.96)
    config.setdefault("splits", {"train": 0.8, "validation": 0.1, "test": 0.1})
    config.setdefault("dataset_epoch", "2026-01-01T00:00:00Z")
    validate_v2_config(config)
    policy_file = config.get("policy_file", "../policy.default.json")
    base = os.path.dirname(os.path.abspath(path))
    config["_resolved_policy_file"] = policy_file if os.path.isabs(policy_file) else os.path.normpath(os.path.join(base, policy_file))
    return config


def validate_v2_config(config: dict) -> None:
    for key in ("schema_version", "dataset_version", "seed", "total_samples", "splits", "distributions"):
        if key not in config:
            raise ValueError(f"config missing required key: {key}")
    if config["schema_version"] != "2.0":
        raise ValueError("v2 config schema_version must be '2.0'")
    total = config["total_samples"]
    if not isinstance(total, int) or total < 1:
        raise ValueError("total_samples must be an integer >= 1")
    splits = config["splits"]
    if set(splits) != {"train", "validation", "test"}:
        raise ValueError("splits must contain train, validation, test")
    if any(not isinstance(value, (int, float)) or value < 0 for value in splits.values()) or sum(splits.values()) <= 0:
        raise ValueError("split weights must be non-negative with a positive total")
    dist = config["distributions"]
    missing = [key for key in REQUIRED_DISTRIBUTIONS if key not in dist]
    if missing:
        raise ValueError(f"missing distributions: {missing}")
    for name, allowed in (
        ("file_type", set(SUPPORTED_FORMATS)),
        ("language", set(LANGUAGES)),
        ("persona", set(PERSONAS)),
        ("intent", set(INTENT_PHRASES)),
        ("formality", set(FORMALITIES)),
        ("length", set(LENGTHS)),
        ("difficulty", {str(level) for level in DIFFICULTIES}),
        ("domain", set(DOMAINS)),
        ("entity_density", {str(level) for level in DIFFICULTIES}),
        ("ocr_difficulty", set(OCR_LEVELS)),
        ("attachment_count", {"1", "2", "3"}),
    ):
        weights = dist.get(name)
        if not isinstance(weights, dict) or not weights:
            raise ValueError(f"distribution {name} must be a non-empty object")
        unknown = set(weights) - allowed
        if unknown:
            raise ValueError(f"distribution {name} has unknown keys: {sorted(unknown)}")
        if any(not isinstance(value, (int, float)) or value < 0 for value in weights.values()):
            raise ValueError(f"distribution {name} weights must be non-negative")
        if sum(weights.values()) <= 0:
            raise ValueError(f"distribution {name} must have a positive total weight")
    for name in ("attachment_probability", "negative_ratio", "ambiguous_ratio", "multi_domain_ratio", "typo_rate"):
        value = dist.get(name)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"distribution {name} must be between 0 and 1")
    if dist["negative_ratio"] + dist["ambiguous_ratio"] > 1:
        raise ValueError("negative_ratio + ambiguous_ratio must be <= 1")
