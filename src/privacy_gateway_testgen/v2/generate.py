"""Schema v2 dataset generation: realistic requests, real files, verified ground truth."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .. import __version__
from ..config import canonical_json, weighted_pick
from ..entities import EntityPool
from ..generator import split_counts
from ..models import CHAR_OFFSET_CONVENTION, Entity
from ..policies import resolve_policy
from ..textsim import jaccard, normalize, shingles
from .archetypes import ARCHETYPES, Archetype, BuildContext, _safe_negative
from .docmodel import Doc
from .extract import verify_attachment
from .org import make_org
from .realism import PERSONAS, build_prompt
from .renderers import render

GENERATION_METHOD = "archetype+span_first+real_file_renderer"
INLINE_ARCHETYPES = {
    "incident_report", "support_ticket", "meeting_minutes", "customer_export",
    "transaction_export", "app_log", "troubleshooting_notes", "architecture_notes",
    "employee_list", "order_export", "customer_complaint", "api_payload",
}
BUNDLE_PAIRS = {
    "transaction_export": ("invoice", "bank_statement"),
    "invoice": ("transaction_export", "purchase_order"),
    "app_log": ("application_environment_config", "deployment_log"),
    "application_environment_config": ("app_log", "database_config"),
    "server_inventory": ("architecture_notes", "access_records"),
    "architecture_notes": ("server_inventory", "kubernetes_manifest"),
    "employee_list": ("meeting_minutes", "payroll"),
    "meeting_minutes": ("employee_list", "incident_report"),
    "incident_report": ("app_log", "deployment_log"),
    "api_payload": ("app_log", "service_account_config"),
    "support_ticket": ("app_log", "customer_export"),
    "screenshot_terminal": ("application_environment_config", "deployment_log"),
    "screenshot_config": ("app_log", "database_config"),
    "payroll": ("employment_contract", "employee_list"),
}
BUNDLE_TRIPLES = {
    "incident_report": ("app_log", "application_environment_config"),
    "app_log": ("incident_report", "application_environment_config"),
}


class GenerationError(RuntimeError):
    pass


@dataclass
class Target:
    language: str
    persona: str
    intent: str
    formality: str
    length: str
    difficulty: int
    domains: List[str]
    negative: bool
    ambiguous: bool
    attachment_count: int
    file_types: List[str]
    ocr_difficulty: int
    typo_rate: float
    destination: bool
    prompt_entity: bool


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_id(entity: Entity) -> str:
    return "canon-" + hashlib.sha1(f"{entity.domain}|{entity.entity_type}|{entity.value}".encode("utf-8")).hexdigest()[:12]


def _replace_entities(text: str, placements) -> str:
    for placement in sorted(placements, key=lambda item: item.start, reverse=True):
        text = text[:placement.start] + f"<{placement.entity.entity_type}>" + text[placement.end:]
    return text


def _doc_fingerprint(doc: Doc) -> str:
    parts: List[str] = [doc.archetype, doc.title, doc.language]
    for block in doc.blocks:
        parts.append(block.kind)
        parts.append(_replace_entities(block.text, block.placements))
        if block.headers:
            parts.append("|".join(block.headers))
        if block.rows:
            parts.append(f"{len(block.rows)}x{len(block.rows[0])}")
            for row in block.rows:
                parts.append("|".join(_replace_entities(cell.text, cell.placements) for cell in row))
    for slide in doc.slides:
        parts.append("slide:" + slide.title)
        for block in slide.blocks:
            parts.append(block.kind)
            parts.append(_replace_entities(block.text, block.placements))
    if doc.record is not None:
        def walk(value):
            if isinstance(value, Entity):
                return f"<{value.entity_type}>"
            if isinstance(value, dict):
                return {key: walk(child) for key, child in value.items()}
            if isinstance(value, (list, tuple)):
                return [walk(child) for child in value]
            return value
        parts.append(json.dumps(walk(doc.record), ensure_ascii=False, sort_keys=True))
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def _length_class(prompt: str) -> str:
    if len(prompt) <= 160:
        return "short"
    if len(prompt) < 600:
        return "medium"
    return "long"


def _allowed(archetype: Archetype, spec: dict) -> bool:
    filters = spec.get("archetype_filter")
    if not filters:
        return True
    ids = filters.get("ids")
    categories = filters.get("categories")
    prefixes = filters.get("id_prefix")
    if ids and archetype.id not in ids:
        return False
    if categories and archetype.category not in categories:
        return False
    if prefixes and not any(archetype.id.startswith(prefix) for prefix in prefixes):
        return False
    return True


def _families(profile_spec: dict) -> List[Tuple[Archetype, str]]:
    result = []
    for archetype in ARCHETYPES:
        if not _allowed(archetype, profile_spec):
            continue
        for renderer in archetype.renderers:
            result.append((archetype, renderer))
    return result


def _allocate_families(families: List[Tuple[Archetype, str]], weights: Dict[str, float], rng: random.Random) -> Dict[str, List[Tuple[Archetype, str]]]:
    shuffled = list(families)
    rng.shuffle(shuffled)
    names = ["train", "validation", "test"]
    if len(shuffled) < 3:
        return {name: shuffled for name in names}
    allocation = {name: 1 for name in names}
    remaining = len(shuffled) - 3
    total = sum(weights[name] for name in names)
    quotas = {name: remaining * weights[name] / total for name in names}
    floors = {name: int(quotas[name]) for name in names}
    leftovers = remaining - sum(floors.values())
    order = sorted(names, key=lambda name: quotas[name] - floors[name], reverse=True)
    for name in order[:leftovers]:
        floors[name] += 1
    for name in names:
        allocation[name] += floors[name]
    result = {}
    cursor = 0
    for name in names:
        result[name] = shuffled[cursor:cursor + allocation[name]]
        cursor += allocation[name]
    return result


class V2Generator:
    def __init__(self, config: dict, policy: dict) -> None:
        self.config = config
        self.policy = policy
        self.seed = int(config["seed"])
        self.distributions = config["distributions"]
        self.near_threshold = float(config.get("near_duplicate_threshold", 0.96))
        self.rng = random.Random(self.seed)
        self.families: Dict[str, List[Tuple[Archetype, str]]] = {}
        self.usage: Counter = Counter()
        self.seen_prompts = set()
        self.seen_shingles: List[set] = []
        self.seen_skeletons: Counter = Counter()
        self.seen_documents: Counter = Counter()

    def generate(self) -> dict:
        self.rng = random.Random(self.seed)
        self.usage = Counter()
        self.seen_prompts = set()
        self.seen_shingles = []
        self.seen_skeletons = Counter()
        self.seen_documents = Counter()
        families = _families(self.config.get("_profile_spec", {}))
        if not families:
            raise GenerationError("profile has no usable archetypes")
        self.families = _allocate_families(families, self.config["splits"], random.Random(self.seed + 11))
        counts = split_counts(int(self.config["total_samples"]), self.config["splits"])
        cases: List[dict] = []
        files: Dict[str, bytes] = {}
        for split in ("train", "validation", "test"):
            batches = self._generate_split(split, counts[split])
            for case, case_files in batches:
                cases.append(case)
                files.update(case_files)
        dataset = {
            "cases": cases,
            "files": files,
            "stats": compute_stats(cases),
            "seed": self.seed,
            "dataset_version": self.config["dataset_version"],
            "profile": self.config["profile"],
            "families": {
                split: sorted(f"{archetype.id}:{renderer}" for archetype, renderer in pool)
                for split, pool in self.families.items()
            },
        }
        return dataset

    def _sample_target(self, split: str) -> Target:
        dist = self.distributions
        language = weighted_pick(self.rng, dist["language"])
        persona = weighted_pick(self.rng, dist["persona"])
        persona_spec = PERSONAS[persona]
        intent = (
            self.rng.choice(persona_spec["intents"])
            if self.rng.random() < 0.6 else weighted_pick(self.rng, dist["intent"])
        )
        formality = weighted_pick(self.rng, dist["formality"])
        length = weighted_pick(self.rng, dist["length"])
        difficulty = int(weighted_pick(self.rng, dist["difficulty"]))
        negative = self.rng.random() < float(dist["negative_ratio"])
        ambiguous = (not negative) and self.rng.random() < float(dist["ambiguous_ratio"])
        domains = [weighted_pick(self.rng, dist["domain"])]
        if self.rng.random() < float(dist["multi_domain_ratio"]):
            candidates = [domain for domain in dist["domain"] if domain not in domains]
            if candidates:
                domains.append(weighted_pick(self.rng, {key: dist["domain"][key] for key in candidates}))
        if self.rng.random() >= float(dist["attachment_probability"]):
            attachment_count = 0
        else:
            attachment_count = int(weighted_pick(self.rng, dist["attachment_count"]))
        available_types = sorted({renderer for _, renderer in self.families.get(split, [])})
        type_weights = {key: value for key, value in dist["file_type"].items() if key in available_types}
        if not type_weights:
            type_weights = {key: value for key, value in dist["file_type"].items()}
        file_types = [weighted_pick(self.rng, type_weights)]
        if attachment_count > 1:
            file_types.append(weighted_pick(self.rng, type_weights))
        if attachment_count > 2:
            file_types.append(weighted_pick(self.rng, type_weights))
        return Target(
            language=language, persona=persona, intent=intent, formality=formality,
            length=length, difficulty=difficulty, domains=domains, negative=negative,
            ambiguous=ambiguous, attachment_count=attachment_count, file_types=file_types,
            ocr_difficulty=int(weighted_pick(self.rng, dist["ocr_difficulty"])),
            typo_rate=float(dist["typo_rate"]), destination=self.rng.random() < 0.14,
            prompt_entity=self.rng.random() < 0.12,
        )

    def _candidate_families(self, split: str, target: Target) -> List[Tuple[Archetype, str]]:
        pool = list(self.families.get(split, []))
        if not pool:
            pool = [item for pool in self.families.values() for item in pool]
        if target.attachment_count == 0:
            inline = [item for item in pool if item[0].id in INLINE_ARCHETYPES and item[1] in ("txt", "md", "csv", "json")]
            if inline:
                pool = inline
        else:
            wanted_renderers = set(target.file_types)
            renderer_pool = [item for item in pool if item[1] in wanted_renderers]
            if renderer_pool:
                pool = renderer_pool
        domain_pool = [item for item in pool if set(item[0].domains).intersection(target.domains)]
        if domain_pool:
            pool = domain_pool
        if len(target.domains) >= 2:
            multi_pool = [item for item in pool if len(set(item[0].domains).intersection(target.domains)) >= 2]
            if multi_pool:
                pool = multi_pool
        categories = set(PERSONAS[target.persona]["categories"])
        persona_pool = [item for item in pool if item[0].category in categories]
        return persona_pool or pool

    def _pick_family(self, candidates: List[Tuple[Archetype, str]]) -> Tuple[Archetype, str]:
        if not candidates:
            raise GenerationError("no candidate family")
        weights = [1.0 / (1 + self.usage[f"{a.id}:{r}"]) for a, r in candidates]
        return self.rng.choices(candidates, weights=weights, k=1)[0]

    def _pick_bundle(self, split: str, target: Target) -> List[Tuple[Archetype, str]]:
        candidates = self._candidate_families(split, target)
        primary = self._pick_family(candidates)
        bundle = [primary]
        if target.attachment_count <= 1:
            return bundle
        by_archetype = {a.id: (a, r) for a, r in self.families.get(split, [])}
        partners = BUNDLE_PAIRS.get(primary[0].id, ())
        for partner_id in partners:
            if len(bundle) >= target.attachment_count:
                break
            partner = by_archetype.get(partner_id)
            if partner and partner[0].id not in {item[0].id for item in bundle}:
                # Prefer the requested file family when the partner supports it.
                for renderer in target.file_types:
                    if renderer in partner[0].renderers:
                        bundle.append((partner[0], renderer))
                        break
                else:
                    bundle.append(partner)
        while len(bundle) < target.attachment_count:
            extra_candidates = [item for item in self.families.get(split, []) if item[0].id not in {x[0].id for x in bundle}]
            if not extra_candidates:
                break
            bundle.append(self._pick_family(extra_candidates))
        return bundle

    def _scenario(self) -> str:
        scenarios = self.policy["scenarios"]
        names = list(scenarios)
        return self.rng.choices(names, weights=[scenarios[name].get("weight", 1) for name in names], k=1)[0]

    def _generate_split(self, split: str, count: int) -> List[Tuple[dict, Dict[str, bytes]]]:
        results: List[Tuple[dict, Dict[str, bytes]]] = []
        attempts = 0
        max_attempts = max(120, count * 50)
        while len(results) < count and attempts < max_attempts:
            attempts += 1
            target = self._sample_target(split)
            try:
                case, files = self._build_case(split, len(results) + 1, target)
            except GenerationError:
                continue
            normalized = normalize(case["prompt"])
            if normalized in self.seen_prompts:
                continue
            shingle_set = shingles(case["prompt"])
            if any(jaccard(shingle_set, other) >= self.near_threshold for other in self.seen_shingles):
                continue
            skeleton = (
                tuple(item["archetype"] for item in case["attachments"]),
                tuple(item["extension"] for item in case["attachments"]),
                tuple(case["entity_types"]),
                case["intent"],
            )
            if self.seen_skeletons[skeleton] >= 2:
                continue
            if self.seen_documents[case["document_fingerprint"]] >= 1:
                continue
            self.seen_prompts.add(normalized)
            self.seen_shingles.append(shingle_set)
            self.seen_skeletons[skeleton] += 1
            self.seen_documents[case["document_fingerprint"]] += 1
            for attachment in case["attachments"]:
                self.usage[f"{attachment['archetype']}:{attachment['extension']}"] += 1
            results.append((case, files))
        if len(results) < count:
            raise GenerationError(
                f"could only generate {len(results)}/{count} unique {split} cases; "
                "loosen distributions or add archetypes"
            )
        return results

    def _build_case(self, split: str, sequence: int, target: Target) -> Tuple[dict, Dict[str, bytes]]:
        if target.attachment_count == 0:
            return self._build_prompt_only(split, sequence, target)
        bundle = self._pick_bundle(split, target)
        content_language = "en" if any(renderer in ("pdf", "png", "jpg", "jpeg") for _, renderer in bundle) else target.language
        if content_language == "mixed":
            content_language = "th" if self.rng.random() < 0.5 else "en"
        org = make_org(self.rng, content_language, "small" if target.difficulty <= 2 else "normal")
        pool = EntityPool(self.rng, content_language, org.as_pool_org())
        test_id = f"pgt2-{SPLIT_CODES[split]}-{sequence:05d}"
        attachments: List[dict] = []
        annotations: List[dict] = []
        files: Dict[str, bytes] = {}
        used_names = set()
        all_locations: List[dict] = []
        fingerprints: List[str] = []
        for index, (archetype, renderer) in enumerate(bundle, start=1):
            ctx = BuildContext(
                rng=self.rng, language=content_language, org=org, pool=pool,
                domains=target.domains, negative=target.negative, ambiguous=target.ambiguous,
                density=2, doc_language=content_language,
                image_style="scan", ocr_difficulty=target.ocr_difficulty,
            )
            doc = archetype.builder(ctx)
            stem = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.splitext(os.path.basename(doc.filename))[0]) or archetype.id
            filename = f"{stem}.{renderer}"
            if filename in used_names:
                filename = f"{stem}_{index}.{renderer}"
            used_names.add(filename)
            doc.filename = filename
            doc.metadata.setdefault("ocr_difficulty", target.ocr_difficulty)
            fingerprints.append(_doc_fingerprint(doc))
            rendered = render(doc, renderer, filename)
            verification = verify_attachment(rendered.data, renderer, rendered.mime_type,
                                              rendered.entity_locations, rendered.meta)
            if verification["issues"]:
                raise GenerationError(f"{archetype.id} verification failed: {verification['issues'][:2]}")
            attachment_id = f"ATT-{index:03d}"
            path = f"{test_id}/{filename}"
            files[path] = rendered.data
            for item in rendered.entity_locations:
                loc = dict(item["location"])
                loc["source_type"] = loc.get("source_type", "native")
                annotations.append(self._annotation(
                    item["entity"], "attachment", attachment_id, filename, loc, item["role"],
                    "verified_layout" if renderer in ("png", "jpg", "jpeg") else "verified",
                ))
            attachments.append({
                "attachment_id": attachment_id,
                "filename": filename,
                "extension": renderer,
                "file_type": renderer,
                "mime_type": rendered.mime_type,
                "size_bytes": len(rendered.data),
                "sha256": _sha256(rendered.data),
                "archetype": archetype.id,
                "archetype_label": archetype.label,
                "archetype_category": archetype.category,
                "renderer": rendered.renderer,
                "synthetic": True,
                "generated_seed": self.seed,
                "language": content_language,
                "expected_extraction_method": rendered.extraction_method,
                "verification": verification,
                "path": path,
                "_data": rendered,
            })
            all_locations.extend(rendered.entity_locations)

        files_meta = [{"filename": item["filename"], "archetype": item["archetype"]} for item in attachments]
        prompt_entity = None
        if target.prompt_entity:
            primary_domain = target.domains[0]
            prompt_entity = (
                _safe_negative(self.rng, "email_address") if target.negative
                else pool.draw(primary_domain)
            )
        prompt_info = build_prompt(
            self.rng, persona=target.persona, intent=target.intent, language=target.language,
            formality=target.formality, files=files_meta, length=target.length,
            typo_rate=target.typo_rate, destination=target.destination, prompt_entity=prompt_entity,
        )
        for span in prompt_info["spans"]:
            annotations.append(self._annotation(
                span.entity, "prompt", None, None,
                {"kind": "prompt_span", "character_start": span.start, "character_end": span.end},
                "body", "verified",
            ))

        expected = [item for item in annotations if item["detection_expected"]]
        if not expected and not target.negative:
            raise GenerationError("positive case produced no detection-expected entity")
        case = self._assemble_case(
            split, sequence, target, prompt_info, attachments, annotations,
            content_language, org.name, test_id,
        )
        case["document_fingerprint"] = hashlib.sha1("|".join(fingerprints).encode("utf-8")).hexdigest()[:16]
        case.pop("_files", None)
        return case, files

    def _build_prompt_only(self, split: str, sequence: int, target: Target) -> Tuple[dict, Dict[str, bytes]]:
        candidates = self._candidate_families(split, target)
        if not candidates:
            raise GenerationError("no prompt-only family")
        archetype, renderer = self._pick_family(candidates)
        content_language = "th" if target.language == "mixed" and self.rng.random() < 0.5 else target.language
        if content_language not in ("th", "en"):
            content_language = "th"
        org = make_org(self.rng, content_language, "small")
        pool = EntityPool(self.rng, content_language, org.as_pool_org())
        ctx = BuildContext(rng=self.rng, language=content_language, org=org, pool=pool,
                           domains=target.domains, negative=target.negative, ambiguous=target.ambiguous,
                           doc_language=content_language)
        doc = archetype.builder(ctx)
        rendered = render(doc, "txt", "inline_snippet.txt")
        snippet = rendered.data.decode("utf-8")
        if not rendered.entity_locations or not snippet.strip():
            raise GenerationError("inline snippet has no entities")
        prompt_info = build_prompt(
            self.rng, persona=target.persona, intent=target.intent, language=target.language,
            formality=target.formality, files=[], length=target.length,
            typo_rate=target.typo_rate, destination=target.destination,
        )
        base = prompt_info["prompt"]
        lead = "\n\nอันนี้แปะมาจากไฟล์:\n```\n" if target.language != "en" else "\n\npasted from the file:\n```\n"
        builder_text = base + lead + snippet + "```"
        annotations: List[dict] = []
        for span in prompt_info["spans"]:
            annotations.append(self._annotation(
                span.entity, "prompt", None, None,
                {"kind": "prompt_span", "character_start": span.start, "character_end": span.end},
                "body", "verified",
            ))
        offset = len(base) + len(lead)
        for item in rendered.entity_locations:
            loc = item["location"]
            start = loc.get("character_start", 0)
            end = loc.get("character_end", start + len(item["entity"].value))
            annotations.append(self._annotation(
                item["entity"], "prompt", None, None,
                {"kind": "prompt_span", "character_start": offset + start, "character_end": offset + end},
                item["role"], "verified",
            ))
        expected = [item for item in annotations if item["detection_expected"]]
        if not expected and not target.negative:
            raise GenerationError("positive prompt-only case produced no entity")
        prompt_info = dict(prompt_info)
        prompt_info["prompt"] = builder_text
        attachments: List[dict] = []
        test_id = f"pgt2-{SPLIT_CODES[split]}-{sequence:05d}"
        case = self._assemble_case(split, sequence, target, prompt_info, attachments, annotations,
                                   content_language, org.name, test_id)
        case["document_fingerprint"] = _doc_fingerprint(doc)
        return case, {}

    def _annotation(self, entity: Entity, source: str, attachment_id: Optional[str],
                    filename: Optional[str], loc: dict, role: str, verification: str) -> dict:
        annotation = {
            "annotation_id": "",
            "canonical_entity_id": _canonical_id(entity),
            "domain": entity.domain,
            "entity_type": entity.entity_type,
            "exact_entity_value": entity.value,
            "detection_expected": bool(entity.detection_expected),
            "classification_expected": entity.entity_type if entity.detection_expected else None,
            "valid": bool(entity.valid),
            "note": entity.note,
            "source": source,
            "source_attachment": attachment_id,
            "filename": filename,
            "role": role,
            "location": loc,
            "verification": verification,
        }
        if loc.get("kind") == "prompt_span":
            annotation["character_start"] = loc["character_start"]
            annotation["character_end"] = loc["character_end"]
        elif loc.get("character_start") is not None:
            annotation["character_start"] = loc["character_start"]
            annotation["character_end"] = loc["character_end"]
        return annotation

    def _assemble_case(self, split: str, sequence: int, target: Target, prompt_info: dict,
                       attachments: List[dict], annotations: List[dict], content_language: str,
                       org_name: str, test_id: str) -> dict:
        for index, annotation in enumerate(annotations, start=1):
            annotation["annotation_id"] = f"ENT-{index:05d}"
        expected = [item for item in annotations if item["detection_expected"]]
        expected_entities = []
        seen = set()
        for item in expected:
            key = (item["domain"], item["entity_type"], item["exact_entity_value"])
            if key in seen:
                continue
            seen.add(key)
            expected_entities.append(Entity(item["domain"], item["entity_type"], item["exact_entity_value"],
                                            valid=item["valid"]))
        scenario = self._scenario()
        resolved = resolve_policy(expected_entities, scenario, self.policy)
        domains = sorted({item["domain"] for item in expected if item["domain"] != "lookalike"})
        entity_types = sorted({item["entity_type"] for item in expected})
        file_types = sorted({item["extension"] for item in attachments})
        archetypes = [item["archetype"] for item in attachments]
        categories = sorted({item["archetype_category"] for item in attachments})
        sensitive_actions = set(resolved["action_expected"].values()) - {"ALLOW"}
        if target.negative:
            category = "negative"
        elif target.ambiguous:
            category = "ambiguous"
        elif len(domains) >= 2:
            category = "multi_domain"
        else:
            category = "single_domain"
        if target.negative:
            objective = "false_positive"
        elif target.ambiguous:
            objective = "ambiguous_context"
        elif len(domains) >= 2:
            objective = "cross_domain_policy"
        elif attachments:
            objective = "file_ingestion_and_policy"
        else:
            objective = "contextual_detection"
        prompt = prompt_info["prompt"]
        prompt_length_class = _length_class(prompt)
        tags = set()
        tags.update(domains)
        tags.update(entity_types)
        tags.add(f"lang:{target.language}")
        tags.add(f"persona:{target.persona}")
        tags.add(f"intent:{target.intent}")
        tags.add(f"difficulty:{target.difficulty}")
        tags.add(f"split:{split}")
        tags.add(f"profile:{self.config['profile']}")
        if attachments:
            tags.add("file_aware")
            tags.update(f"file:{ext}" for ext in file_types)
            tags.update(f"archetype:{item}" for item in archetypes)
            if len(attachments) > 1:
                tags.add("multi_attachment")
        if any(item["expected_extraction_method"] == "ocr" for item in attachments):
            tags.add("ocr")
        if target.negative:
            tags.add("negative")
        if target.ambiguous:
            tags.add("ambiguous")
        if target.destination:
            tags.add("destination_context")
        verification_statuses = [item["verification"]["status"] for item in attachments]
        if any(status == "unverified" for status in verification_statuses):
            verification_status = "unverified"
        elif any(status == "verified_layout" for status in verification_statuses):
            verification_status = "verified_partial"
        else:
            verification_status = "verified"
        case = {
            "schema_version": "2.0",
            "test_id": test_id,
            "prompt": prompt,
            "language": target.language,
            "domains": domains,
            "entity_types": entity_types,
            "classification_expected": entity_types,
            "detection_expected": bool(entity_types),
            "polarity": "negative" if target.negative else "positive",
            "domain_scope": "none" if not domains else ("multi_domain" if len(domains) >= 2 else "single_domain"),
            "entities": annotations,
            "attachments": [{key: value for key, value in item.items() if not key.startswith("_")} for item in attachments],
            "attachment_count": len(attachments),
            "file_types": file_types,
            "archetypes": archetypes,
            "archetype_categories": categories,
            "persona": target.persona,
            "persona_label": PERSONAS[target.persona]["label"],
            "intent": target.intent,
            "formality": target.formality,
            "profile": self.config["profile"],
            "difficulty": target.difficulty,
            "test_category": category,
            "test_objective": objective,
            "ambiguity": {
                "is_ambiguous": bool(target.ambiguous),
                "rationale": ("Mixed lookalike and contextual values; interpretation depends on context."
                              if target.ambiguous else "Single interpretation."),
            },
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
                "record_fields": ["test_id", "policy_scenario", "entity_types", "actions", "attachments"],
                "forbidden_fields": ["exact_entity_value"],
            },
            "rationale": (
                f"Archetype {archetypes[0] if archetypes else 'inline_snippet'} from {org_name}. "
                f"Task: {target.intent}. Sensitive values are incidental to the request."
            ),
            "tags": sorted(tags),
            "generation_method": GENERATION_METHOD,
            "verification_status": verification_status,
            "verification": {
                "status": verification_status,
                "attachments_checked": len(attachments),
                "attachments_verified": sum(1 for item in attachments if item["verification"]["status"] in ("verified", "verified_layout")),
                "ocr_layout_only": sum(1 for item in attachments if item["verification"]["status"] == "verified_layout"),
            },
            "prompt_length": len(prompt),
            "prompt_length_class": prompt_length_class,
            "prompt_style": target.length,
            "prompt_styles": [prompt_length_class],
            "context_complexity": prompt_info.get("context_complexity", "medium"),
            "structure": "file_attachment" if attachments else "pasted_text",
            "detection_mode": "contextual" if target.ambiguous else "deterministic",
            "edge_case": target.difficulty >= 5 or target.ambiguous,
            "adversarial": target.difficulty >= 5,
            "split": split,
            "template_id": archetypes[0] if archetypes else "inline_snippet",
            "template_family": ":".join(
                f"{item['archetype']}:{item['extension']}" for item in attachments
            ) or "inline_snippet",
            "dataset_version": self.config["dataset_version"],
            "seed": self.seed,
            "char_offset_convention": CHAR_OFFSET_CONVENTION,
            "extraction_methods": sorted({item["expected_extraction_method"] for item in attachments}),
            "content_language": content_language,
        }
        if case["verification_status"] == "unverified":
            raise GenerationError("attachment verification failed")
        return case


SPLIT_CODES = {"train": "trn", "validation": "val", "test": "tst"}


def _mean(values: Sequence[int]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0


def compute_stats(cases: Iterable[dict]) -> dict:
    cases = list(cases)
    total = len(cases)
    by_split = Counter(case["split"] for case in cases)
    by_language = Counter(case["language"] for case in cases)
    by_persona = Counter(case["persona"] for case in cases)
    by_intent = Counter(case["intent"] for case in cases)
    by_difficulty = Counter(str(case["difficulty"]) for case in cases)
    by_polarity = Counter(case["polarity"] for case in cases)
    by_category = Counter(case["test_category"] for case in cases)
    by_action = Counter(case["policy_decision_expected"] for case in cases)
    by_domain = Counter()
    by_entity_type = Counter()
    by_file_type = Counter()
    by_attachment_extension = Counter()
    by_archetype = Counter()
    by_attachment_count = Counter()
    by_extraction = Counter()
    domain_combinations = Counter()
    prompt_lengths = []
    entity_counts = []
    file_total = 0
    ocr_cases = 0
    for case in cases:
        by_domain.update(case["domains"])
        by_entity_type.update(case["entity_types"])
        by_file_type.update(case["file_types"])
        by_attachment_extension.update(item["extension"] for item in case["attachments"])
        by_archetype.update(case["archetypes"])
        by_attachment_count[str(case["attachment_count"])] += 1
        by_extraction.update(case.get("extraction_methods", []))
        domain_combinations["+".join(case["domains"]) or "none"] += 1
        prompt_lengths.append(case["prompt_length"])
        entity_counts.append(len(case["entities"]))
        file_total += len(case["attachments"])
        if "ocr" in case["tags"]:
            ocr_cases += 1
    return {
        "total_cases": total,
        "total_files": file_total,
        "positive_cases": by_polarity.get("positive", 0),
        "negative_cases": by_polarity.get("negative", 0),
        "ambiguous_cases": by_category.get("ambiguous", 0),
        "multi_domain_cases": sum(1 for case in cases if case["domain_scope"] == "multi_domain"),
        "ocr_cases": ocr_cases,
        "mean_entities_per_case": _mean(entity_counts),
        "mean_files_per_case": round(file_total / total, 3) if total else 0.0,
        "by_split": dict(sorted(by_split.items())),
        "by_language": dict(sorted(by_language.items())),
        "by_persona": dict(sorted(by_persona.items())),
        "by_intent": dict(sorted(by_intent.items())),
        "by_difficulty": dict(sorted(by_difficulty.items())),
        "by_polarity": dict(sorted(by_polarity.items())),
        "by_category": dict(sorted(by_category.items())),
        "by_action": dict(sorted(by_action.items())),
        "by_domain": dict(sorted(by_domain.items())),
        "by_entity_type": dict(sorted(by_entity_type.items())),
        "by_file_type": dict(sorted(by_file_type.items())),
        "by_attachment_extension": dict(sorted(by_attachment_extension.items())),
        "by_archetype": dict(sorted(by_archetype.items())),
        "by_attachment_count": dict(sorted(by_attachment_count.items())),
        "by_extraction_method": dict(sorted(by_extraction.items())),
        "domain_combinations": dict(sorted(domain_combinations.items())),
        "prompt_length": {
            "min": min(prompt_lengths) if prompt_lengths else 0,
            "max": max(prompt_lengths) if prompt_lengths else 0,
            "mean": _mean(prompt_lengths),
        },
    }


def _write_json(path: str, value: Any) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _write_jsonl(path: str, rows: Iterable[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def export_v2_dataset(dataset: dict, out_dir: str, config: dict, policy: dict) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    cases = dataset["cases"]
    files: Dict[str, bytes] = dataset["files"]
    by_split: Dict[str, List[dict]] = defaultdict(list)
    for case in cases:
        by_split[case["split"]].append(case)
    attachment_root = os.path.join(out_dir, "attachments")
    os.makedirs(attachment_root, exist_ok=True)
    for case in cases:
        folder = os.path.join(attachment_root, case["test_id"])
        os.makedirs(folder, exist_ok=True)
        for attachment in case["attachments"]:
            rel = attachment["path"]
            data = files[rel]
            path = os.path.join(out_dir, "attachments", *rel.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(data)

    _write_jsonl(os.path.join(out_dir, "cases.jsonl"), cases)
    for split in ("train", "validation", "test"):
        _write_jsonl(os.path.join(out_dir, f"{split}.jsonl"), by_split.get(split, []))
    _write_json(os.path.join(out_dir, "all.json"), cases)
    stats = compute_stats(cases)
    _write_json(os.path.join(out_dir, "stats.json"), stats)
    os.makedirs(os.path.join(out_dir, "ground_truth"), exist_ok=True)
    entity_rows = []
    for case in cases:
        for annotation in case["entities"]:
            row = dict(annotation)
            row["test_id"] = case["test_id"]
            row["split"] = case["split"]
            entity_rows.append(row)
    _write_jsonl(os.path.join(out_dir, "ground_truth", "entities.jsonl"),
                 sorted(entity_rows, key=lambda item: (item["test_id"], item["annotation_id"])))

    config_for_hash = {key: value for key, value in config.items() if not key.startswith("_")}
    generated_names = ["cases.jsonl", "train.jsonl", "validation.jsonl", "test.jsonl", "all.json", "stats.json",
                       "ground_truth/entities.jsonl"]
    file_hashes = {}
    for name in generated_names:
        with open(os.path.join(out_dir, name), "rb") as handle:
            file_hashes[name] = _sha256(handle.read())
    attachment_hashes = {path: _sha256(data) for path, data in sorted(files.items())}
    verification_summary = Counter(case["verification_status"] for case in cases)
    manifest = {
        "dataset_id": f"pgt2-{dataset['seed']}-{dataset['profile']}",
        "schema_version": "2.0",
        "dataset_version": dataset["dataset_version"],
        "generator_version": __version__,
        "generated_at": config.get("dataset_epoch", "1970-01-01T00:00:00Z"),
        "seed": dataset["seed"],
        "profile": dataset["profile"],
        "total_cases": len(cases),
        "total_files": sum(len(case["attachments"]) for case in cases),
        "split_counts": {split: len(by_split.get(split, [])) for split in ("train", "validation", "test")},
        "file_type_distribution": stats["by_file_type"],
        "attachment_extension_distribution": stats["by_attachment_extension"],
        "domain_distribution": stats["by_domain"],
        "domain_combinations": stats["domain_combinations"],
        "language_distribution": stats["by_language"],
        "persona_distribution": stats["by_persona"],
        "intent_distribution": stats["by_intent"],
        "difficulty_distribution": stats["by_difficulty"],
        "attachment_count_distribution": stats["by_attachment_count"],
        "positive_negative_ratio": stats["by_polarity"],
        "verification_status": dict(sorted(verification_summary.items())),
        "families": dataset["families"],
        "near_duplicate_threshold": dataset.get("near_duplicate_threshold", config.get("near_duplicate_threshold")),
        "config_sha256": hashlib.sha256(canonical_json(config_for_hash).encode("utf-8")).hexdigest(),
        "policy_sha256": hashlib.sha256(canonical_json(policy).encode("utf-8")).hexdigest(),
        "char_offset_convention": CHAR_OFFSET_CONVENTION,
        "files": file_hashes,
        "attachments_sha256": attachment_hashes,
        "reproducible": True,
        "notes": "Synthetic only. Attachment hashes and case JSON are deterministic for this seed and config.",
    }
    _write_json(os.path.join(out_dir, "manifest.json"), manifest)
    return manifest
