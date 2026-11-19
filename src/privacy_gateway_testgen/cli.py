"""Command line interface."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .annotations import verify_cases
from .config import load_config
from .entities import CORE_DOMAINS, entity_types
from .evaluation import evaluate_dataset, markdown_report
from .generator import DatasetGenerator, compute_stats, export_dataset
from .policies import load_policy
from .templates import TEMPLATES
from .validation import validate_dataset
from .v2 import cli as v2_cli


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


def _apply_overrides(config: dict, args) -> dict:
    if getattr(args, "seed", None) is not None:
        config["seed"] = args.seed
    if getattr(args, "count", None) is not None:
        config["total_samples"] = args.count
    if getattr(args, "dataset_version", None):
        config["dataset_version"] = args.dataset_version
    return config


def _policy_for(config: dict, override: str = None) -> dict:
    path = override or config.get("_resolved_policy_file")
    if not path:
        path = os.path.join("configs", "policy.default.json")
    return load_policy(path)


def cmd_generate(args) -> int:
    config = _apply_overrides(load_config(args.config), args)
    policy = _policy_for(config)
    dataset = DatasetGenerator(config, policy).generate()
    manifest = export_dataset(dataset, args.out, config, policy)
    print(json.dumps({
        "out": os.path.abspath(args.out),
        "dataset_version": manifest["dataset_version"],
        "seed": manifest["seed"],
        "total_cases": manifest["total_cases"],
        "split_counts": manifest["split_counts"],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args) -> int:
    config = _apply_overrides(load_config(args.config), args)
    policy = _policy_for(config, args.policy)
    all_issues = []
    all_cases = []
    for path in args.input:
        cases = _load_cases(path)
        all_cases.extend(cases)
        for issue in validate_dataset(cases, policy):
            issue["source"] = path
            all_issues.append(issue)
    result = {
        "files": args.input,
        "cases": len(all_cases),
        "issue_cases": len(all_issues),
        "issues": all_issues,
        "passed": not all_issues,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"cases: {result['cases']}")
        print(f"issue cases: {result['issue_cases']}")
        for issue in all_issues[:20]:
            print(f"- {issue['test_id']}: {issue['errors'][0]}")
        print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


def cmd_stats(args) -> int:
    cases = []
    for path in args.input:
        cases.extend(_load_cases(path))
    print(json.dumps(compute_stats(cases), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_evaluate(args) -> int:
    config = _apply_overrides(load_config(args.config), args)
    policy = _policy_for(config, args.policy)
    first = DatasetGenerator(config, policy).generate()
    second = DatasetGenerator(config, policy).generate()
    first_cases = json.dumps(first["cases"], ensure_ascii=False, sort_keys=True)
    second_cases = json.dumps(second["cases"], ensure_ascii=False, sort_keys=True)
    reproducible = first_cases == second_cases
    report = evaluate_dataset(first["cases"], config, policy, reproducible=reproducible)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "evaluation.json"), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(args.out, "evaluation.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(markdown_report(report))

    if args.dataset_out:
        export_dataset(first, args.dataset_out, config, policy)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"cases: {report['total_cases']}  reproducible: {reproducible}")
        for gate in report["gates"]:
            print(f"  [{'PASS' if gate['passed'] else 'FAIL'}] {gate['name']}: {gate['value']} ({gate['requirement']})")
        print("OVERALL:", "PASS" if report["passed"] else "FAIL")
    return 0 if report["passed"] else 1


def cmd_verify(args) -> int:
    cases = _load_cases(args.input)
    before = json.dumps(cases, ensure_ascii=False, sort_keys=True)
    cases, report = verify_cases(cases, repair=args.repair)
    after = json.dumps(cases, ensure_ascii=False, sort_keys=True)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        if args.output.endswith(".jsonl"):
            with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
                for case in cases:
                    handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")
        else:
            with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(cases, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
    report["changed"] = before != after
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not report["unresolved"] else 1


def cmd_list_domains(args) -> int:
    output = {
        "domains": {domain: list(entity_types(domain)) for domain in CORE_DOMAINS},
        "lookalike": list(entity_types("lookalike")),
        "templates": [
            {
                "id": template.id,
                "length_class": template.length_class,
                "difficulty": template.difficulty,
                "domains": list(template.domains),
                "structure": template.structure,
                "negative": template.negative,
                "adversarial": template.adversarial,
            }
            for template in TEMPLATES
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="privacy-gateway-testgen",
        description="Generate synthetic privacy-gateway test prompts with exact ground truth.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="generate a dataset")
    generate.add_argument("--config", default="configs/default.json")
    generate.add_argument("--out", default="datasets/sample")
    generate.add_argument("--seed", type=int)
    generate.add_argument("--count", type=int)
    generate.add_argument("--dataset-version")
    generate.set_defaults(func=cmd_generate)

    validate = sub.add_parser("validate", help="validate dataset schema, spans and policy labels")
    validate.add_argument("--input", nargs="+", required=True)
    validate.add_argument("--config", default="configs/default.json")
    validate.add_argument("--policy")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(func=cmd_validate)

    stats = sub.add_parser("stats", help="print dataset statistics")
    stats.add_argument("--input", nargs="+", required=True)
    stats.set_defaults(func=cmd_stats)

    evaluate = sub.add_parser("evaluate", help="run quality gates and write an evaluation report")
    evaluate.add_argument("--config", default="configs/default.json")
    evaluate.add_argument("--policy")
    evaluate.add_argument("--out", default="reports")
    evaluate.add_argument("--dataset-out")
    evaluate.add_argument("--json", action="store_true")
    evaluate.add_argument("--seed", type=int)
    evaluate.add_argument("--count", type=int)
    evaluate.set_defaults(func=cmd_evaluate)

    verify = sub.add_parser("verify", help="verify imported annotation spans (optionally repair)")
    verify.add_argument("--input", required=True)
    verify.add_argument("--output")
    verify.add_argument("--repair", action="store_true")
    verify.set_defaults(func=cmd_verify)

    list_domains = sub.add_parser("list-domains", help="print domains, entity types and templates")
    list_domains.set_defaults(func=cmd_list_domains)

    generate_v2 = sub.add_parser("generate-v2", help="generate a file-aware schema 2.0 dataset")
    generate_v2.add_argument("--config", default="configs/v2/default.json")
    generate_v2.add_argument("--profile")
    generate_v2.add_argument("--out", default="datasets/v2-sample")
    generate_v2.add_argument("--seed", type=int)
    generate_v2.add_argument("--count", type=int)
    generate_v2.add_argument("--file-types", help="comma-separated override, e.g. pdf,xlsx,docx")
    generate_v2.add_argument("--domains", help="comma-separated override, e.g. pii,secrets")
    generate_v2.add_argument("--files-only", action="store_true", help="force every case to have an attachment")
    generate_v2.add_argument("--policy")
    generate_v2.set_defaults(func=v2_cli.cmd_generate_v2)

    validate_v2 = sub.add_parser("validate-v2", help="validate schema 2.0 cases and optionally an exported dataset")
    validate_v2.add_argument("--input", nargs="+")
    validate_v2.add_argument("--dataset")
    validate_v2.add_argument("--config", default="configs/v2/default.json")
    validate_v2.add_argument("--profile")
    validate_v2.add_argument("--policy")
    validate_v2.add_argument("--json", action="store_true")
    validate_v2.set_defaults(func=v2_cli.cmd_validate_v2)

    report_v2 = sub.add_parser("report-v2", help="reopen a v2 dataset, verify files and write measured reports")
    report_v2.add_argument("--dataset", required=True)
    report_v2.add_argument("--config", default="configs/v2/default.json")
    report_v2.add_argument("--profile")
    report_v2.add_argument("--out", default="reports/v2")
    report_v2.add_argument("--policy")
    report_v2.add_argument("--check-reproducible", action="store_true")
    report_v2.add_argument("--json", action="store_true")
    report_v2.set_defaults(func=v2_cli.cmd_report_v2)

    verify_v2 = sub.add_parser("verify-v2", help="reopen every attachment in an exported v2 dataset and verify annotations")
    verify_v2.add_argument("--dataset", required=True)
    verify_v2.set_defaults(func=v2_cli.cmd_verify_v2)

    profiles_v2 = sub.add_parser("list-profiles-v2", help="print v2 generation profiles")
    profiles_v2.add_argument("--config", default="configs/v2/default.json")
    profiles_v2.add_argument("--profile")
    profiles_v2.set_defaults(func=v2_cli.cmd_list_profiles_v2)

    archetypes_v2 = sub.add_parser("list-archetypes-v2", help="print v2 document archetypes")
    archetypes_v2.set_defaults(func=v2_cli.cmd_list_archetypes_v2)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
