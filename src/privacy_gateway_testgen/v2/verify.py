"""Re-verify an exported v2 dataset from disk."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from typing import Dict, List

from ..models import Entity
from .extract import verify_attachment, verify_prompt_entities


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_dataset_directory(dataset_dir: str) -> dict:
    cases_path = os.path.join(dataset_dir, "cases.jsonl")
    with open(cases_path, "r", encoding="utf-8-sig") as handle:
        cases = [json.loads(line) for line in handle if line.strip()]
    issues: List[dict] = []
    file_results: List[dict] = []
    statuses = Counter()
    manifest_checks = 0
    manifest_path = os.path.join(dataset_dir, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8-sig") as handle:
            manifest = json.load(handle)
        for name, expected in manifest.get("files", {}).items():
            path = os.path.join(dataset_dir, *name.split("/"))
            if not os.path.exists(path):
                issues.append({"kind": "manifest_file_missing", "message": name})
                continue
            with open(path, "rb") as handle:
                actual = _sha256(handle.read())
            manifest_checks += 1
            if actual != expected:
                issues.append({"kind": "manifest_hash_mismatch", "message": name})
        for name, expected in manifest.get("attachments_sha256", {}).items():
            path = os.path.join(dataset_dir, "attachments", *name.split("/"))
            if not os.path.exists(path):
                issues.append({"kind": "manifest_attachment_missing", "message": name})
                continue
            with open(path, "rb") as handle:
                actual = _sha256(handle.read())
            manifest_checks += 1
            if actual != expected:
                issues.append({"kind": "manifest_attachment_hash_mismatch", "message": name})
    for case in cases:
        prompt_issues = verify_prompt_entities(case)
        for issue in prompt_issues:
            issues.append({"test_id": case["test_id"], **issue})
        for attachment in case.get("attachments", []):
            path = os.path.join(dataset_dir, "attachments", *attachment["path"].split("/"))
            if not os.path.exists(path):
                issues.append({"test_id": case["test_id"], "kind": "missing_file",
                               "message": f"missing {attachment['path']}"})
                statuses["unverified"] += 1
                continue
            with open(path, "rb") as handle:
                data = handle.read()
            if _sha256(data) != attachment["sha256"]:
                issues.append({"test_id": case["test_id"], "kind": "sha256_mismatch",
                               "message": f"hash changed for {attachment['path']}"})
            locations = []
            for annotation in case["entities"]:
                if annotation.get("source_attachment") != attachment["attachment_id"]:
                    continue
                locations.append({
                    "entity": Entity(annotation["domain"], annotation["entity_type"],
                                     annotation["exact_entity_value"], valid=annotation.get("valid", True)),
                    "location": annotation["location"],
                    "role": annotation.get("role", "body"),
                })
            result = verify_attachment(data, attachment["extension"], attachment["mime_type"],
                                       locations, {"delimiter": ",", "headers": []})
            statuses[result["status"]] += 1
            file_results.append({
                "test_id": case["test_id"], "attachment_id": attachment["attachment_id"],
                "path": attachment["path"], "status": result["status"],
                "checks": result["checks"], "issue_count": len(result["issues"]),
            })
            for issue in result["issues"]:
                issues.append({"test_id": case["test_id"], "file": attachment["path"], **issue})
    verified_files = statuses.get("verified", 0) + statuses.get("verified_layout", 0)
    return {
        "dataset_dir": os.path.abspath(dataset_dir),
        "cases": len(cases),
        "files": len(file_results),
        "verified_files": verified_files,
        "file_open_rate": round(verified_files / len(file_results), 4) if file_results else 1.0,
        "statuses": dict(sorted(statuses.items())),
        "manifest_checks": manifest_checks,
        "issues": issues,
        "passed": not issues,
        "file_results": file_results,
    }
