"""CLI handlers for the v2 file-aware generator."""

from __future__ import annotations

import json
import os

from .. import __version__
from ..policies import load_policy
from ..v2.archetypes import ARCHETYPES
from ..v2.config import load_profiles, load_v2_config
from ..v2.evaluate import evaluate_v2, markdown_report_v2
from ..v2.generate import V2Generator, compute_stats, export_v2_dataset
from ..v2.localization import language_capability
from ..v2.verify import verify_dataset_directory
from .validation import validate_dataset_v2


def _apply_overrides(config: dict, args) -> dict:
    if getattr(args, "seed", None) is not None:
        config["seed"] = args.seed
    if getattr(args, "count", None) is not None:
        config["total_samples"] = args.count
    if getattr(args, "file_types", None):
        types = [item.strip().lower().lstrip(".") for item in args.file_types.split(",") if item.strip()]
        config["distributions"]["file_type"] = {item: 1.0 for item in types}
    if getattr(args, "domains", None):
        domains = [item.strip().lower() for item in args.domains.split(",") if item.strip()]
        config["distributions"]["domain"] = {item: 1.0 for item in domains}
    if getattr(args, "files_only", False):
        config["distributions"]["attachment_probability"] = 1.0
    return config


def _policy(config: dict, override: str = None):
    return load_policy(override or config["_resolved_policy_file"])


def cmd_generate_v2(args) -> int:
    config = _apply_overrides(load_v2_config(args.config, profile=args.profile), args)
    policy = _policy(config, args.policy)
    dataset = V2Generator(config, policy).generate()
    manifest = export_v2_dataset(dataset, args.out, config, policy)
    issues = validate_dataset_v2(dataset["cases"], policy)
    print(json.dumps({
        "out": os.path.abspath(args.out),
        "dataset_id": manifest["dataset_id"],
        "schema_version": manifest["schema_version"],
        "profile": manifest["profile"],
        "seed": manifest["seed"],
        "total_cases": manifest["total_cases"],
        "total_files": manifest["total_files"],
        "split_counts": manifest["split_counts"],
        "file_type_distribution": manifest["file_type_distribution"],
        "verification_status": manifest["verification_status"],
        "validation_issue_cases": len(issues),
    }, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


def _load_cases(path: str):
    if path.endswith(".jsonl"):
        with open(path, "r", encoding="utf-8-sig") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    with open(path, "r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("cases"), list):
        return value["cases"]
    raise ValueError(f"{path}: expected a JSON array or an object with a 'cases' array")


def cmd_validate_v2(args) -> int:
    config = load_v2_config(args.config, profile=args.profile)
    policy = _policy(config, args.policy)
    cases = []
    sources = list(args.input or [])
    if args.dataset:
        sources.append(os.path.join(args.dataset, "cases.jsonl"))
    if not sources:
        raise SystemExit("validate-v2 needs --input and/or --dataset")
    for path in sources:
        cases.extend(_load_cases(path))
    issues = validate_dataset_v2(cases, policy)
    verification = verify_dataset_directory(args.dataset) if args.dataset else None
    result = {
        "files": sources,
        "cases": len(cases),
        "issue_cases": len(issues),
        "issues": issues,
        "verification": verification,
        "passed": not issues and (verification is None or verification["passed"]),
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"cases: {len(cases)}")
        print(f"issue cases: {len(issues)}")
        for issue in issues[:20]:
            print(f"- {issue['test_id']}: {issue['errors'][0]}")
        if verification:
            print(f"files: {verification['files']}  verified: {verification['verified_files']}")
            for issue in verification["issues"][:20]:
                print(f"- {issue.get('test_id')}: {issue['kind']}: {issue['message']}")
        print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


def cmd_report_v2(args) -> int:
    verification = verify_dataset_directory(args.dataset)
    cases = _load_cases(os.path.join(args.dataset, "cases.jsonl"))
    manifest_path = os.path.join(args.dataset, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8-sig") as handle:
            manifest = json.load(handle)
    profile = args.profile or manifest.get("profile") or "real-world-enterprise"
    try:
        config = load_v2_config(args.config, profile=profile)
    except ValueError:
        config = load_v2_config(args.config, profile="real-world-enterprise")
    policy = _policy(config, args.policy)
    dataset = {
        "cases": cases,
        "files": {},
        "stats": compute_stats(cases),
        "seed": manifest.get("seed", config["seed"]),
        "dataset_version": manifest.get("dataset_version", config["dataset_version"]),
        "profile": profile,
    }
    reproducible = False
    if args.check_reproducible:
        # Rebuild with the dataset's own seed and size, not the config defaults:
        # a dataset generated with --count/--seed must still be re-checkable.
        config["seed"] = manifest.get("seed", config["seed"])
        config["total_samples"] = manifest.get("total_cases", config["total_samples"])
        second = V2Generator(config, policy).generate()
        first_json = json.dumps(cases, ensure_ascii=False, sort_keys=True)
        second_json = json.dumps(second["cases"], ensure_ascii=False, sort_keys=True)
        first_hashes = {
            attachment["path"]: attachment["sha256"]
            for case in cases for attachment in case["attachments"]
        }
        second_hashes = {
            path: __import__("hashlib").sha256(data).hexdigest()
            for path, data in second["files"].items()
        }
        reproducible = first_json == second_json and first_hashes == second_hashes
    report = evaluate_v2(dataset, config, policy, reproducible=reproducible)
    report["verification"] = {key: value for key, value in verification.items() if key not in ("file_results",)}
    report["manifest"] = {
        key: manifest.get(key) for key in ("dataset_id", "schema_version", "generator_version",
                                            "seed", "profile", "total_cases", "total_files")
    }
    # ``generated_at`` and absolute paths are machine/time specific and are
    # deliberately excluded, so evaluation.json / evaluation.md are
    # byte-identical for the same dataset on any PYTHONHASHSEED.
    report["deterministic_report"] = True
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "evaluation.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(args.out, "evaluation.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(markdown_report_v2(report))
    with open(os.path.join(args.out, "verification.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(verification, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"cases: {report['total_cases']}  files: {report['total_files']}")
        for gate in report["gates"]:
            print(f"  [{'PASS' if gate['passed'] else 'FAIL'}] {gate['name']}: {gate['value']} ({gate['requirement']})")
        print("verification:", "PASS" if verification["passed"] else "FAIL")
        readiness = report["benchmark_ready"]
        print("benchmark_ready:", "YES" if readiness["benchmark_ready"] else "NO",
              "safe_cases:", readiness["benchmark_safe_cases"],
              "excluded:", readiness["excluded_cases"])
        for reason in readiness["reasons"]:
            print("  -", reason)
        print("OVERALL:", "PASS" if report["passed"] and verification["passed"] else "FAIL")
    return 0 if report["passed"] and verification["passed"] else 1


def cmd_verify_v2(args) -> int:
    result = verify_dataset_directory(args.dataset)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


def cmd_list_profiles_v2(args) -> int:
    config = load_v2_config(args.config, profile=args.profile)
    path = config.get("profiles_file", "profiles.json")
    base = os.path.dirname(os.path.abspath(args.config))
    profiles = load_profiles(os.path.join(base, path)) if os.path.exists(os.path.join(base, path)) else {}
    print(json.dumps({
        "profiles": profiles,
        "active": config["profile"],
        "schema_version": config["schema_version"],
        "generator_version": __version__,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_list_archetypes_v2(args) -> int:
    output = [
        {
            "id": item.id,
            "label": item.label,
            "category": item.category,
            "domains": list(item.domains),
            "renderers": list(item.renderers),
            "language_capabilities": {
                renderer: list(language_capability(renderer)) for renderer in item.renderers
            },
            "difficulty": item.difficulty,
            "rationale": item.rationale,
        }
        for item in ARCHETYPES
    ]
    print(json.dumps({"archetypes": output}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
