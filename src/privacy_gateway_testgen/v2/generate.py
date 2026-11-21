"""Schema v2 dataset generation: realistic requests, real files, verified ground truth."""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
import copy
import datetime as _dt
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .. import __version__
from ..config import canonical_json, weighted_pick
from ..entities import EntityPool
from ..generator import split_counts
from ..models import CHAR_OFFSET_CONVENTION, Entity
from ..policies import resolve_policy
from ..textsim import jaccard, normalize, shingles
from .archetypes import ARCHETYPES, Archetype, BuildContext
from .docmodel import Block, Doc
from .extract import verify_attachment
from .localization import (
    classify_language, document_static_text, document_text, language_capability,
    language_matches, language_mix_description, localize_doc,
    residual_english_labels, script_counts,
)
from .org import make_org
from .realism import PERSONAS, build_prompt
from .renderers import render
from .scenario import ScenarioPlan, finance_checks, make_scenario, safe_negative
from .validation import STRUCTURE_REF_KINDS

GENERATION_METHOD = "archetype+span_first+scenario_plan+real_file_renderer"
INLINE_ARCHETYPES = {
    "incident_report", "support_ticket", "meeting_minutes", "customer_export",
    "transaction_export", "app_log", "troubleshooting_notes", "architecture_notes",
    "employee_list", "order_export", "customer_complaint", "api_payload",
}
ENGLISH_ONLY_RENDERERS = {"log"}  # log bodies are technical English by convention
MACHINE_KEY_RENDERERS = {"json", "xml", "yaml", "yml", "env", "ini", "conf", "toml", "sql"}
# Prompt-only content sources: not every no-attachment request is a fenced paste.
PROMPT_ONLY_FORMS = {
    "pasted_email": {"th": "\n\n--- ข้อความที่ forward ต่อ ---\n", "en": "\n\n--- forwarded message ---\n",
                     "mixed": "\n\n--- forwarded message ---\n"},
    "copied_chat": {"th": "\n\nแปะจากแชท:\n", "en": "\n\ncopied from chat:\n",
                    "mixed": "\n\nแปะจากแชท:\n"},
    "copied_ticket": {"th": "\n\nเนื้อหาตั๋ว:\n", "en": "\n\nticket text:\n", "mixed": "\n\nticket text:\n"},
    "raw_notes": {"th": "\n\nโน้ตที่พิมพ์ไว้:\n", "en": "\n\nnotes I typed up:\n",
                  "mixed": "\n\nnotes I typed up:\n"},
    "log_fragment": {"th": "\n\nจาก log:\n", "en": "\n\nfrom the log:\n", "mixed": "\n\nfrom the log:\n"},
    "pasted_table": {"th": "\n\nตารางที่ copy มา:\n", "en": "\n\ntable I copied:\n",
                     "mixed": "\n\ntable I copied:\n"},
    "report_excerpt": {"th": "\n\nตัดตอนจากรายงาน:\n", "en": "\n\nexcerpt from the report:\n",
                       "mixed": "\n\nexcerpt from the report:\n"},
    "code_config": {"th": "\n\n snippet:\n", "en": "\n\nsnippet:\n", "mixed": "\n\nsnippet:\n"},
    "pasted_file": {"th": "\n\nอันนี้แปะมาจากไฟล์:\n", "en": "\n\npasted from the file:\n",
                    "mixed": "\n\nอันนี้แปะมาจากไฟล์:\n"},
    "short_no_paste": {"th": "", "en": "", "mixed": ""},
}
PROMPT_ONLY_WEIGHTS = {
    "pasted_email": 0.12, "copied_chat": 0.10, "copied_ticket": 0.09, "raw_notes": 0.10,
    "log_fragment": 0.08, "pasted_table": 0.09, "report_excerpt": 0.08, "code_config": 0.07,
    "pasted_file": 0.12, "short_no_paste": 0.15,
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
    attachment_languages: List[str]
    structure_reference: bool
    same_archetype_bundle: bool
    old_new_bundle: bool


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_id(entity: Entity) -> str:
    canonical = entity.canonical_value or entity.value
    return "canon-" + hashlib.sha1(
        f"{entity.domain}|{entity.entity_type}|{canonical}".encode("utf-8")).hexdigest()[:12]


def _replace_entities(text: str, placements) -> str:
    for placement in sorted(placements, key=lambda item: item.start, reverse=True):
        text = text[:placement.start] + f"<{placement.entity.entity_type}>" + text[placement.end:]
    return text


def _doc_fingerprint(doc: Doc) -> str:
    # Language is not part of the identity: the same text labelled `th` in one
    # case and `mixed` in another is still one document, and shipping it twice
    # wastes a case.
    parts: List[str] = [doc.archetype, doc.title]
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
            if block.headers:
                parts.append("|".join(block.headers))
            if block.rows:
                parts.append(f"{len(block.rows)}x{len(block.rows[0])}")
                for row in block.rows:
                    parts.append("|".join(_replace_entities(cell.text, cell.placements)
                                          for cell in row))
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


def _source_line_count(doc: Doc) -> int:
    """Canonical text lines, independent of renderer bytes and platform fonts."""
    total = 0
    for block in doc.all_blocks():
        if block.kind == "table":
            total += 1 + len(block.rows)
        else:
            total += max(1, len(block.text.splitlines()))
    return total


def _doc_structure(doc: Doc, rendered) -> dict:
    tables = [block for block in doc.blocks if block.kind == "table"]
    headings = [block.text for block in doc.blocks if block.kind == "heading" and block.text]
    sheets = []
    meta_sheets = rendered.meta.get("sheets") or []
    for index, sheet in enumerate(meta_sheets):
        block = tables[index] if index < len(tables) else None
        sheets.append({
            "name": sheet["name"] if isinstance(sheet, dict) else str(sheet),
            "hidden": bool(sheet.get("hidden")) if isinstance(sheet, dict) else False,
            "rows": (len(block.rows) + 1) if block is not None else 0,
            "columns": len(block.headers) if block is not None else 0,
        })
    headers = rendered.meta.get("headers") or (tables[0].headers if tables else [])
    rows = sum(len(block.rows) for block in tables)
    if rendered.extraction_method == "structured_parser" and rendered.renderer == "csv" and tables:
        rows = len(tables[0].rows) + 1
    keys = []
    if isinstance(doc.record, dict):
        keys = [str(key) for key in doc.record.keys()]
    return {
        "renderer": rendered.renderer,
        "headings": headings,
        "tables": [
            {"title": block.title, "rows": len(block.rows), "columns": len(block.headers)}
            for block in tables
        ],
        "rows": rows,
        "columns": len(headers),
        "headers": [str(value) for value in headers],
        "sheets": sheets,
        "slides": int(rendered.meta.get("slides") or len(doc.slides) or 0),
        "slide_titles": [slide.title for slide in doc.slides],
        "pages": int(rendered.meta.get("pages") or 0),
        # Text renderers report their own line count; PDF, Office and raster
        # containers report canonical source lines.  Counting b"\n" in a
        # compressed container made this number platform-dependent.
        "lines": int(
            rendered.meta.get("line_count")
            or rendered.meta.get("text_line_count")
            or (len(rendered.meta["canonical_lines"]) if rendered.meta.get("canonical_lines") else 0)
            or _source_line_count(doc)
        ),
        "delimiter": rendered.meta.get("delimiter"),
        "keys": keys,
    }


def _choose_structure_refs(rng: random.Random, attachments: Sequence[dict]) -> List[dict]:
    candidates: List[dict] = []
    for attachment in attachments:
        structure = attachment["structure"]
        extension = attachment["extension"]
        allowed = STRUCTURE_REF_KINDS.get(extension, set())
        if not allowed:
            # A flattened screenshot has no columns or rows a user could name.
            continue
        for sheet in structure.get("sheets", []):
            if "sheet" in allowed:
                candidates.append({"attachment_id": attachment["attachment_id"],
                                   "filename": attachment["filename"],
                                   "kind": "sheet", "value": sheet["name"]})
            if "row" in allowed and sheet.get("rows", 0) > 1:
                candidates.append({"attachment_id": attachment["attachment_id"],
                                   "filename": attachment["filename"],
                                   "kind": "row", "value": rng.randint(2, sheet["rows"]),
                                   "sheet": sheet["name"]})
        if "slide" in allowed:
            for index in range(1, structure.get("slides", 0) + 1):
                candidates.append({"attachment_id": attachment["attachment_id"],
                                   "filename": attachment["filename"],
                                   "kind": "slide", "value": index})
        if "page" in allowed:
            for index in range(1, structure.get("pages", 0) + 1):
                candidates.append({"attachment_id": attachment["attachment_id"],
                                   "filename": attachment["filename"],
                                   "kind": "page", "value": index})
        if "section" in allowed:
            for heading in structure.get("headings", [])[1:]:
                candidates.append({"attachment_id": attachment["attachment_id"],
                                   "filename": attachment["filename"],
                                   "kind": "section", "value": heading})
        if "row" in allowed and structure.get("rows", 0) > 1:
            candidates.append({"attachment_id": attachment["attachment_id"],
                               "filename": attachment["filename"],
                               "kind": "row", "value": rng.randint(2, structure["rows"])})
        if "column" in allowed:
            for header in structure.get("headers", []):
                candidates.append({"attachment_id": attachment["attachment_id"],
                                   "filename": attachment["filename"],
                                   "kind": "column", "value": header})
        if "line" in allowed and structure.get("lines", 0) > 3:
            candidates.append({"attachment_id": attachment["attachment_id"],
                               "filename": attachment["filename"],
                               "kind": "line", "value": rng.randint(1, structure["lines"])})
        if "key" in allowed:
            for key in structure.get("keys", [])[:5]:
                candidates.append({"attachment_id": attachment["attachment_id"],
                                   "filename": attachment["filename"],
                                   "kind": "key", "value": key})
    if not candidates:
        return []
    first = rng.choice(candidates)
    refs = [first]
    if len(attachments) > 1 and rng.random() < 0.35:
        others = [item for item in candidates if item["attachment_id"] != first["attachment_id"]]
        if others:
            refs.append(rng.choice(others))
    for ref in refs:
        ref["valid"] = True
        ref["resolved"] = True
        ref["user_visible"] = True
    return refs


def _cross_file_links(annotations: Sequence[dict]) -> List[dict]:
    groups: Dict[str, List[dict]] = defaultdict(list)
    for annotation in annotations:
        if annotation["source"] != "attachment":
            continue
        groups[annotation["canonical_entity_id"]].append(annotation)
    links = []
    for canonical, items in sorted(groups.items(), key=lambda pair: pair[0]):
        attachment_ids = sorted({item["source_attachment"] for item in items})
        if len(attachment_ids) < 2:
            continue
        canonicals = {item["canonical_entity_value"] for item in items}
        variants = sorted({item["exact_entity_value"] for item in items})
        links.append({
            "link_id": f"XFL-{len(links) + 1:03d}",
            "canonical_entity_id": canonical,
            "canonical_entity_value": items[0]["canonical_entity_value"],
            "entity_type": items[0]["entity_type"],
            "exact_entity_value": items[0]["exact_entity_value"],
            "representation_variants": variants,
            "attachments": attachment_ids,
            "filenames": sorted({item["filename"] for item in items}),
            "occurrences": len(items),
            "consistent": len(canonicals) == 1,
        })
    return links


def _aggregate_language(languages: Sequence[str]) -> str:
    unique = sorted(set(languages))
    if not unique:
        return "mixed"
    if len(unique) == 1:
        return unique[0]
    return "mixed"


def _reference_exists(ref: dict, attachments: Sequence[dict]) -> bool:
    attachment = next((item for item in attachments
                       if item["attachment_id"] == ref.get("attachment_id")), None)
    if attachment is None:
        return False
    structure = attachment.get("structure", {})
    kind, value = ref.get("kind"), ref.get("value")
    if kind == "sheet":
        return any(sheet.get("name") == value for sheet in structure.get("sheets", []))
    if kind == "row":
        sheet = ref.get("sheet")
        if sheet:
            match = next((item for item in structure.get("sheets", []) if item.get("name") == sheet), None)
            return bool(match) and 1 <= int(value) <= int(match.get("rows", 0))
        return 1 <= int(value) <= int(structure.get("rows", 0))
    if kind == "column":
        return value in structure.get("headers", [])
    if kind == "page":
        return 1 <= int(value) <= int(structure.get("pages", 0))
    if kind == "slide":
        return 1 <= int(value) <= int(structure.get("slides", 0))
    if kind == "section":
        return value in structure.get("headings", [])
    if kind == "line":
        return 1 <= int(value) <= int(structure.get("lines", 0))
    if kind == "key":
        return value in structure.get("keys", [])
    return False


TABLE_ONLY_RENDERERS = {"csv", "xlsx"}
PROSE_ONLY_RENDERERS = {"txt", "md", "log", "pptx", "py", "js", "ts", "java", "go",
                        "sql", "tf", "png", "jpg", "jpeg"}
RECORD_ONLY_RENDERERS = {"json", "yaml", "yml", "xml", "env", "ini", "conf", "toml"}


def _revise_doc(doc: Doc, rng: random.Random, renderer: str = "pdf") -> List[dict]:
    """Pick a revision the target renderer can actually show.

    A change written into a block that the renderer never emits produces two
    byte-identical "old" and "new" files, which cannot test change detection.
    Record-only formats (JSON/YAML/XML/config) have no controlled revision
    source, so they fall back to a related render instead of a fake revision.
    """
    if renderer in RECORD_ONLY_RENDERERS:
        return []
    before = list(doc.blocks)
    if renderer in TABLE_ONLY_RENDERERS:
        doc.blocks = [block for block in before if block.kind == "table"]
    elif renderer in PROSE_ONLY_RENDERERS:
        doc.blocks = [block for block in before if block.kind != "table"]
    else:
        doc.blocks = before
    try:
        return _revise_doc_any(doc, rng)
    finally:
        kept = {id(block) for block in before}
        doc.blocks = before + [block for block in doc.blocks if id(block) not in kept]


def _revise_doc_any(doc: Doc, rng: random.Random) -> List[dict]:
    """Make a meaningful, traceable old/new pair.

    The revision always changes a value a reviewer could act on: a status, a
    due date, a monetary amount, a phone number or a system endpoint.  Cosmetic
    "(revised)" suffixes and note-only revisions are not produced.
    """
    changes: List[dict] = []
    status_map = {
        "pending": "settled", "settled": "refunded", "shipped": "delivered",
        "packed": "shipped", "proposal": "negotiation", "negotiation": "won",
        "production": "staging", "staging": "production",
        "รอดำเนินการ": "ชำระแล้ว", "ชำระแล้ว": "คืนเงินแล้ว",
        "แพ็กแล้ว": "จัดส่งแล้ว", "จัดส่งแล้ว": "ส่งถึงแล้ว",
        "เสนอราคา": "เจรจา", "เจรจา": "ปิดการขาย",
        "โปรดักชัน": "สเตจจิง", "สเตจจิง": "โปรดักชัน",
    }
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    money_pattern = re.compile(r"^(\d{1,3}(?:,\d{3})*)(\.00)?$")
    phone_pattern = re.compile(r"0\d-\d{3}-\d{4}")

    def record(change_type: str, block, row: int, column: int, before: str, after: str,
               table: str) -> dict:
        location = {"block": block.kind, "table": table, "row": row, "column": column}
        change = {
            "change_type": change_type,
            "kind": change_type,
            "from": before,
            "to": after,
            "before": before,
            "after": after,
            "source_v1": dict(location),
            "source_v2": dict(location),
        }
        changes.append(change)
        return change

    for block in doc.blocks:
        if block.kind != "table":
            continue
        for row_index, row in enumerate(block.rows, start=1):
            for column_index, value in enumerate(row, start=1):
                if value.placements:
                    continue  # never rewrite an entity value
                text = value.text
                if text.lower() in status_map:
                    replacement = status_map[text.lower()]
                    value.text = replacement
                    record("status_changed", block, row_index, column_index, text, replacement,
                           block.title)
                    return changes
    for block in doc.blocks:
        if block.kind != "table":
            continue
        for row_index, row in enumerate(block.rows, start=1):
            for column_index, value in enumerate(row, start=1):
                if value.placements or not date_pattern.match(value.text):
                    continue
                day = _dt.date.fromisoformat(value.text)
                replacement = (day + _dt.timedelta(days=1)).isoformat()
                before = value.text
                value.text = replacement
                record("due_date_updated", block, row_index, column_index, before, replacement,
                       block.title)
                return changes
    arithmetic_docs = {"invoice", "quotation", "purchase_order", "payroll",
                       "bank_statement", "expense_report"}
    for block in doc.blocks:
        if block.kind != "table":
            continue
        for row_index, row in enumerate(block.rows, start=1):
            for column_index, value in enumerate(row, start=1):
                match = money_pattern.match(value.text.strip())
                if value.placements or not match or doc.archetype in arithmetic_docs:
                    continue
                amount = int(match.group(1).replace(",", ""))
                corrected = amount + max(1, round(amount * 0.01))
                before = value.text
                value.text = f"{corrected:,}.00"
                record("amount_corrected", block, row_index, column_index, before, value.text,
                       block.title)
                return changes
    time_pattern = re.compile(r"\b\d{2}:\d{2}\b")
    for block in doc.blocks:
        if block.placements or block.kind not in ("paragraph", "note", "bullet"):
            continue
        match = time_pattern.search(block.text)
        if match:
            before = match.group(0)
            hour, minute = before.split(":")
            replacement = f"{hour}:{(int(minute) + 5) % 60:02d}"
            block.text = block.text.replace(before, replacement, 1)
            record("timeline_time_updated", block, 0, 0, before, replacement, block.kind)
            return changes
    for block in doc.blocks:
        if block.placements:
            continue
        match = phone_pattern.search(block.text)
        if match and block.kind in ("paragraph", "note", "bullet"):
            before = match.group(0)
            replacement = before[:-4] + f"{rng.randint(1000, 9999):04d}"
            block.text = block.text.replace(before, replacement)
            record("phone_changed", block, 0, 0, before, replacement, block.kind)
            return changes
    # Last resort for prose-only documents: a controlled approval change.
    before, after = "draft", "approved"
    block = Block("paragraph", text=f"Status: {after} (previously {before})")
    doc.blocks.append(block)
    record("status_changed", block, 0, 0, before, after, "document")
    return changes


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
        self.disclosure = config.get("disclosure", "metadata")
        self.distributions = config["distributions"]
        self.near_threshold = float(config.get("near_duplicate_threshold", 0.96))
        self.rng = random.Random(self.seed)
        self.families: Dict[str, List[Tuple[Archetype, str]]] = {}
        self.usage: Counter = Counter()
        self.seen_prompts = set()
        self.seen_shingles: List[set] = []
        self.seen_file_hashes: set = set()
        self.seen_skeletons: Counter = Counter()
        self.seen_documents: Counter = Counter()

    def generate(self) -> dict:
        self.rng = random.Random(self.seed)
        self.usage = Counter()
        self.seen_prompts = set()
        self.seen_shingles = []
        self.seen_file_hashes = set()
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
        attachment_languages = [
            weighted_pick(self.rng, dist["attachment_language"])
            for _ in range(attachment_count)
        ]
        realism = self.config.get("realism", {})
        same_archetype = (attachment_count >= 2
                          and self.rng.random() < float(realism.get("same_archetype_bundle_probability", 0.25)))
        old_new = same_archetype and self.rng.random() < float(realism.get("old_new_bundle_probability", 0.6))
        structure_reference = self.rng.random() < float(realism.get("structure_reference_probability", 0.45))
        return Target(
            language=language, persona=persona, intent=intent, formality=formality,
            length=length, difficulty=difficulty, domains=domains, negative=negative,
            ambiguous=ambiguous, attachment_count=attachment_count, file_types=file_types,
            ocr_difficulty=int(weighted_pick(self.rng, dist["ocr_difficulty"])),
            typo_rate=float(dist["typo_rate"]), destination=self.rng.random() < 0.14,
            prompt_entity=self.rng.random() < 0.12,
            attachment_languages=attachment_languages,
            structure_reference=structure_reference,
            same_archetype_bundle=same_archetype,
            old_new_bundle=old_new,
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

    def _maybe_hybrid(self, renderer: str, doc: Doc, sequence: int) -> None:
        """Turn one block of a PDF into an embedded screenshot region.

        Real incident reports quote a monitoring or terminal screenshot next to
        native prose.  The block stays *only* in the image, so its annotations
        keep a single source type instead of duplicating ground truth.
        """
        if renderer != "pdf" or doc.scan or doc.metadata.get("hybrid_block") is not None:
            return
        # Every second case, not a random draw: the choice must spread evenly
        # without consuming the shared RNG that shapes the rest of the dataset.
        if sequence % 2:
            return
        for index, block in enumerate(doc.blocks):
            if block.kind in ("code", "log"):
                doc.metadata.update({"hybrid_block": index, "hybrid_span": 1,
                                     "hybrid_style": "terminal"})
                return
            if block.kind == "bullet":
                span = 0
                while index + span < len(doc.blocks) and doc.blocks[index + span].kind == "bullet":
                    span += 1
                if span >= 2:
                    doc.metadata.update({"hybrid_block": index, "hybrid_span": span,
                                         "hybrid_style": "terminal"})
                    return

    def _build_case(self, split: str, sequence: int, target: Target) -> Tuple[dict, Dict[str, bytes]]:
        if target.attachment_count == 0:
            return self._build_prompt_only(split, sequence, target)
        bundle = self._pick_bundle(split, target)
        if target.same_archetype_bundle and len(bundle) >= 2:
            primary, primary_renderer = bundle[0]
            if target.old_new_bundle:
                plan = [(primary, primary_renderer, "original"), (primary, primary_renderer, "revised")]
            else:
                alternatives = [item for item in primary.renderers if item != primary_renderer]
                if alternatives:
                    plan = [(primary, primary_renderer, "original"),
                            (primary, self.rng.choice(alternatives), "related")]
                else:
                    plan = [(primary, primary_renderer, "original"), (primary, primary_renderer, "revised")]
            plan.extend([(archetype, renderer, "related") for archetype, renderer in bundle[2:]])
        else:
            plan = [(archetype, renderer, "related") for archetype, renderer in bundle]

        latin_only = any(renderer in ENGLISH_ONLY_RENDERERS for _, renderer, _ in plan)
        requested_languages = list(target.attachment_languages) or [target.language]
        if target.language in ("th", "mixed") or any(
                item in ("th", "mixed") for item in requested_languages):
            org_language = "th"
        else:
            org_language = "en"
        org = make_org(self.rng, org_language, "small" if target.difficulty <= 2 else "normal")
        pool = EntityPool(self.rng, org_language, org.as_pool_org())
        test_id = f"pgt2-{SPLIT_CODES[split]}-{sequence:05d}"
        localization = self.config.get("localization", {})
        thresholds = self.config.get("language_thresholds", {})
        scenario = make_scenario(
            test_id, self.rng, org, pool, org_language, target.negative, target.ambiguous,
            thai_date_mode=localization.get("thai_date_mode", "be"),
            currency_mode=localization.get("currency_mode", "thb"),
        )
        attachments: List[dict] = []
        annotations: List[dict] = []
        files: Dict[str, bytes] = {}
        used_names = set()
        fingerprints: List[str] = []
        previous_doc: Optional[Doc] = None
        previous_data: Optional[bytes] = None
        for index, (archetype, renderer, role) in enumerate(plan, start=1):
            revision_changes: List[dict] = []
            revision_source = role == "revised" and previous_doc is not None
            if revision_source:
                candidate = copy.deepcopy(previous_doc)
                revision_changes = _revise_doc(candidate, self.rng, renderer)
                if not revision_changes:
                    # No meaningful controlled change exists for this document:
                    # ship a related render instead of a fake "revised" copy.
                    role = "related"
                    revision_source = False
                    alternatives = [item for item in archetype.renderers if item != renderer]
                    if alternatives:
                        renderer = self.rng.choice(alternatives)
            desired = requested_languages[(index - 1) % len(requested_languages)]
            if renderer in ENGLISH_ONLY_RENDERERS:
                attachment_language = "en"
                routing = f"{renderer}_english_only"
            else:
                attachment_language = desired
                routing = None
            attachment_id = f"ATT-{index:03d}"
            ctx = BuildContext(
                rng=self.rng, language=org_language, org=org, pool=pool,
                domains=target.domains, negative=target.negative, ambiguous=target.ambiguous,
                density=2, doc_language=attachment_language,
                image_style="scan", ocr_difficulty=target.ocr_difficulty,
                scenario=scenario, variant=index, attachment_id=attachment_id,
                latin_only=renderer in ENGLISH_ONLY_RENDERERS,
            )
            if revision_source:
                doc = candidate
            else:
                doc = archetype.builder(ctx)
                previous_doc = doc
            doc.language = attachment_language
            doc.filename = f"{archetype.id}.{renderer}"
            doc.metadata.setdefault("ocr_difficulty", target.ocr_difficulty)
            doc.metadata["disclosure"] = self.disclosure
            localize_doc(doc, attachment_language,
                         localize_headers=renderer not in MACHINE_KEY_RENDERERS)
            text = document_text(doc)
            static_stats = script_counts(document_static_text(doc))
            language_check = script_counts(text)
            language_check["static"] = static_stats
            measured_language = classify_language(static_stats, thresholds)
            if measured_language is None:
                raise GenerationError(
                    f"{archetype.id}:{renderer} has no measurable language: "
                    f"thai_share={static_stats['thai_share']} "
                    f"latin_share={static_stats['latin_share']}"
                )
            if measured_language != attachment_language:
                routing = f"relabelled_from_{attachment_language}"
                previous_language = attachment_language
                attachment_language = measured_language
                doc.language = attachment_language
                if attachment_language in ("th", "mixed"):
                    # The document was authored/localized for another language;
                    # localize it for the measured one before measuring again.
                    localize_doc(doc, attachment_language,
                                 localize_headers=renderer not in MACHINE_KEY_RENDERERS)
                    text = document_text(doc)
                    static_stats = script_counts(document_static_text(doc))
                    language_check = script_counts(text)
                    language_check["static"] = static_stats
                elif previous_language in ("th", "mixed"):
                    # Localization is one-way: relabelling a Thai/Mixed document
                    # to English would leave Thai headings in an `en` file.
                    # Rebuild it in English instead of shipping a mislabelled file.
                    if revision_source:
                        raise GenerationError(
                            f"{archetype.id}:{renderer} revision cannot be rebuilt in English")
                    ctx.doc_language = "en"
                    doc = archetype.builder(ctx)
                    previous_doc = doc
                    doc.language = "en"
                    doc.filename = f"{archetype.id}.{renderer}"
                    doc.metadata.setdefault("ocr_difficulty", target.ocr_difficulty)
                    doc.metadata["disclosure"] = self.disclosure
                    localize_doc(doc, "en", localize_headers=renderer not in MACHINE_KEY_RENDERERS)
                    text = document_text(doc)
                    static_stats = script_counts(document_static_text(doc))
                    language_check = script_counts(text)
                    language_check["static"] = static_stats
                    measured_language = classify_language(static_stats, thresholds)
                    if measured_language != "en":
                        raise GenerationError(
                            f"{archetype.id}:{renderer} cannot be rendered as English "
                            f"(measured {measured_language})")
            if attachment_language == "th":
                language_check["residual_english_labels"] = residual_english_labels(text)
            language_check["matches_declared_language"] = language_matches(
                static_stats, attachment_language, thresholds)
            stem = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.splitext(os.path.basename(doc.filename))[0]) or archetype.id
            if role in ("original", "revised"):
                stem = f"{stem}_{'v1' if role == 'original' else 'v2'}"
            filename = f"{stem}.{renderer}"
            if filename in used_names:
                filename = f"{stem}_{index}.{renderer}"
            used_names.add(filename)
            doc.filename = filename
            if self.disclosure == "banner":
                # Visible notice for artifacts shared with people.  Appended
                # only in banner mode; the default metadata mode keeps files free
                # of hints a detector could read.
                doc.blocks.append(Block("note", text="Synthetic sample - not real data."))
            fingerprints.append(_doc_fingerprint(doc))
            self._maybe_hybrid(renderer, doc, sequence)
            try:
                rendered = render(doc, renderer, filename)
            except ValueError as exc:
                raise GenerationError(f"{archetype.id} renderer refused content: {exc}") from exc
            if revision_source and previous_data is not None and rendered.data == previous_data:
                # A revision the renderer does not show is a fake revision: the
                # old/new pair would be two identical files.  Skip the case rather
                # than ship a bundle that cannot test change detection.
                raise GenerationError(
                    f"{archetype.id}:{renderer} revision is not visible in the rendered file")
            file_hash = hashlib.sha256(rendered.data).hexdigest()
            if file_hash in self.seen_file_hashes:
                raise GenerationError(
                    f"{filename} duplicates an attachment already emitted; "
                    "regenerate the case with different content")
            self.seen_file_hashes.add(file_hash)
            previous_data = rendered.data
            verification = verify_attachment(rendered.data, renderer, rendered.mime_type,
                                              rendered.entity_locations, rendered.meta)
            if verification["issues"]:
                raise GenerationError(f"{archetype.id} verification failed: {verification['issues'][:2]}")
            path = f"{test_id}/{filename}"
            files[path] = rendered.data
            for item in rendered.entity_locations:
                loc = dict(item["location"])
                loc["source_type"] = loc.get("source_type", "native")
                annotations.append(self._annotation(
                    item["entity"], "attachment", attachment_id, filename, loc, item["role"],
                    "verified_layout" if renderer in ("png", "jpg", "jpeg") else "verified",
                ))
            structure = _doc_structure(doc, rendered)
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
                "renderer_version": "2.2",
                "dependency_renderer": ("reportlab+pillow+pypdf" if renderer == "pdf"
                                        else ("pillow+pypdf" if renderer in ("png", "jpg", "jpeg")
                                              else "stdlib")),
                "render_mode": rendered.meta.get("mode"),
                "text_shaping": rendered.meta.get("text_shaping"),
                "synthetic": True,
                "generated_seed": self.seed,
                "language": attachment_language,
                "language_mode": attachment_language,
                "language_requested": desired,
                "language_mix": language_mix_description(attachment_language),
                "language_capability": list(language_capability(renderer)),
                "language_routing": routing,
                "language_check": language_check,
                "structure": structure,
                "revision_changes": revision_changes,
                "expected_extraction_method": rendered.extraction_method,
                "evaluation_requirement": ("ocr_required"
                                           if rendered.extraction_method == "ocr"
                                           else "direct_text_extraction"),
                "verification": verification,
                "path": path,
                "_data": rendered,
            })

        files_meta = [{"filename": item["filename"], "archetype": item["archetype"]}
                      for item in attachments]
        prompt_entity = None
        if target.prompt_entity:
            primary_domain = target.domains[0]
            prompt_entity = (
                safe_negative(self.rng, "email_address") if target.negative
                else pool.draw(primary_domain)
            )
        structure_refs = (_choose_structure_refs(self.rng, attachments)
                          if target.structure_reference else [])
        prompt_info = build_prompt(
            self.rng, persona=target.persona, intent=target.intent, language=target.language,
            formality=target.formality, files=files_meta, length=target.length,
            typo_rate=target.typo_rate, destination=target.destination, prompt_entity=prompt_entity,
            structure_refs=structure_refs,
        )
        if prompt_info["quality_issues"]:
            raise GenerationError("prompt composition: " + "; ".join(prompt_info["quality_issues"]))
        for span in prompt_info["spans"]:
            annotations.append(self._annotation(
                span.entity, "prompt", None, None,
                {"kind": "prompt_span", "character_start": span.start, "character_end": span.end},
                "body", "verified",
            ))

        expected = [item for item in annotations if item["detection_expected"]]
        if not expected and not target.negative:
            raise GenerationError("positive case produced no detection-expected entity")
        scenario.checks.extend(finance_checks(scenario))
        bundle_meta = self._bundle_meta(sequence, target, attachments, annotations)
        if (len(attachments) > 1 and bundle_meta["relationship"]["status"] != "related"
                and not (target.ambiguous or target.negative)):
            raise GenerationError("multi-file bundle has no relationship evidence")
        case = self._assemble_case(
            split, sequence, target, prompt_info, attachments, annotations,
            _aggregate_language([item["language"] for item in attachments]),
            org.name, test_id, scenario=scenario,
            content_languages=sorted({item["language"] for item in attachments}),
            bundle=bundle_meta,
        )
        case["document_fingerprint"] = hashlib.sha1("|".join(fingerprints).encode("utf-8")).hexdigest()[:16]
        case.pop("_files", None)
        return case, files

    def _bundle_meta(self, sequence: int, target: Target, attachments: Sequence[dict],
                     annotations: Sequence[dict] = ()) -> dict:
        changes = [change for item in attachments for change in item.get("revision_changes", [])]
        if changes and len(attachments) > 1:
            kind = "old_new"
        elif target.same_archetype_bundle and len(attachments) > 1:
            kind = "same_archetype"
        elif len(attachments) > 1:
            kind = "multi_file"
        else:
            kind = "single_file"
        evidence: List[dict] = []
        canonical_groups: Dict[str, set] = defaultdict(set)
        for annotation in annotations:
            if annotation["source"] == "attachment":
                canonical_groups[annotation["canonical_entity_id"]].add(
                    annotation["source_attachment"])
        for canonical, members in sorted(canonical_groups.items()):
            if len(members) >= 2:
                evidence.append({"kind": "shared_canonical_entity", "reference": canonical,
                                 "attachments": sorted(members)})
        archetypes = {item["archetype"] for item in attachments}
        if changes:
            evidence.append({"kind": "controlled_revision", "changes": len(changes)})
        if len(attachments) > 1 and len(archetypes) == 1:
            evidence.append({"kind": "same_archetype", "archetype": sorted(archetypes)[0]})
        relationship = {
            "status": "related" if evidence else "intentionally_unrelated",
            "evidence": evidence,
        }
        return {
            "bundle_id": f"BND-{sequence:05d}",
            "kind": kind,
            "relationship": relationship,
            "members": [
                {"attachment_id": item["attachment_id"], "filename": item["filename"],
                 "archetype": item["archetype"], "role": ("revised" if item.get("revision_changes")
                                                          else ("original" if kind == "old_new" else "related"))}
                for item in attachments
            ],
            "revision_changes": changes,
        }

    def _build_prompt_only(self, split: str, sequence: int, target: Target) -> Tuple[dict, Dict[str, bytes]]:
        candidates = self._candidate_families(split, target)
        if not candidates:
            raise GenerationError("no prompt-only family")
        archetype, renderer = self._pick_family(candidates)
        form = weighted_pick(self.rng, PROMPT_ONLY_WEIGHTS)
        content_language = "th" if target.language == "mixed" and self.rng.random() < 0.5 else target.language
        if content_language not in ("th", "en"):
            content_language = "th"
        org_language = "th" if content_language == "th" or target.language == "mixed" else "en"
        org = make_org(self.rng, org_language, "small")
        pool = EntityPool(self.rng, org_language, org.as_pool_org())
        test_id = f"pgt2-{SPLIT_CODES[split]}-{sequence:05d}"
        localization = self.config.get("localization", {})
        scenario = make_scenario(
            test_id, self.rng, org, pool, org_language, target.negative, target.ambiguous,
            thai_date_mode=localization.get("thai_date_mode", "be"),
            currency_mode=localization.get("currency_mode", "thb"),
        )
        ctx = BuildContext(rng=self.rng, language=org_language, org=org, pool=pool,
                           domains=target.domains, negative=target.negative, ambiguous=target.ambiguous,
                           doc_language=content_language, scenario=scenario, attachment_id="ATT-001")
        doc = archetype.builder(ctx)
        doc.language = content_language
        localize_doc(doc, content_language)
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
        annotations: List[dict] = []
        for span in prompt_info["spans"]:
            annotations.append(self._annotation(
                span.entity, "prompt", None, None,
                {"kind": "prompt_span", "character_start": span.start, "character_end": span.end},
                "body", "verified",
            ))
        if prompt_info["quality_issues"]:
            raise GenerationError("prompt composition: " + "; ".join(prompt_info["quality_issues"]))
        if form == "short_no_paste":
            extra = (safe_negative(self.rng, "email_address") if target.negative
                     else pool.draw(target.domains[0]))
            connector = (" ข้อมูลคือ " if target.language == "th"
                         else " details: " if target.language == "en"
                         else " รายละเอียด: ")
            suffix = " ครับ" if target.language == "th" else ""
            start = len(base) + len(connector)
            builder_text = base + connector + extra.value + suffix
            annotations.append(self._annotation(
                extra, "prompt", None, None,
                {"kind": "prompt_span", "character_start": start,
                 "character_end": start + len(extra.value)},
                "body", "verified",
            ))
        else:
            lead = PROMPT_ONLY_FORMS[form][target.language]
            fenced = form in ("pasted_email", "pasted_table", "report_excerpt",
                              "log_fragment", "code_config")
            builder_text = base + lead + ("```\n" if fenced else "") + snippet
            builder_text += "```" if fenced else ""
            offset = len(base) + len(lead) + (4 if fenced else 0)
            for item in rendered.entity_locations:
                loc = item["location"]
                start = loc.get("character_start", 0)
                end = loc.get("character_end", start + len(item["entity"].value))
                annotations.append(self._annotation(
                    item["entity"], "prompt", None, None,
                    {"kind": "prompt_span", "character_start": offset + start,
                     "character_end": offset + end},
                    item["role"], "verified",
                ))
        expected = [item for item in annotations if item["detection_expected"]]
        if not expected and not target.negative:
            raise GenerationError("positive prompt-only case produced no entity")
        prompt_info = dict(prompt_info)
        prompt_info["prompt"] = builder_text
        prompt_info["prompt_form"] = form
        attachments: List[dict] = []
        case = self._assemble_case(split, sequence, target, prompt_info, attachments, annotations,
                                   content_language, org.name, test_id, scenario=scenario,
                                   content_languages=[content_language],
                                   bundle={"bundle_id": f"BND-{sequence:05d}", "kind": "prompt_only",
                                           "relationship": {"status": "not_applicable", "evidence": []},
                                           "members": [], "revision_changes": []})
        case["document_fingerprint"] = _doc_fingerprint(doc)
        case["prompt_form"] = form
        return case, {}

    def _annotation(self, entity: Entity, source: str, attachment_id: Optional[str],
                    filename: Optional[str], loc: dict, role: str, verification: str) -> dict:
        annotation = {
            "annotation_id": "",
            "canonical_entity_id": _canonical_id(entity),
            "canonical_entity_value": entity.canonical_value or entity.value,
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
                       org_name: str, test_id: str,
                       scenario: Optional[ScenarioPlan] = None,
                       content_languages: Optional[Sequence[str]] = None,
                       bundle: Optional[dict] = None) -> dict:
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
        policy_scenario = self._scenario()
        resolved = resolve_policy(expected_entities, policy_scenario, self.policy)
        domains = sorted({item["domain"] for item in expected if item["domain"] != "lookalike"})
        entity_types = sorted({item["entity_type"] for item in expected})
        file_types = sorted({item["extension"] for item in attachments})
        archetype_ids = [item["archetype"] for item in attachments]
        archetypes = sorted(set(archetype_ids))
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
        attachment_languages = [item["language"] for item in attachments]
        content_languages = list(content_languages or ([content_language] if content_language else []))
        structure_references = [dict(item) for item in prompt_info.get("structure_references", [])]
        for ref in structure_references:
            ref["resolved"] = _reference_exists(ref, attachments)
            ref["valid"] = ref["resolved"]
        cross_file_links = _cross_file_links(annotations)
        consistency_checks = list(scenario.checks) if scenario is not None else []
        if structure_references:
            resolved_count = sum(1 for ref in structure_references if ref["resolved"])
            consistency_checks.append({
                "check": "structure_reference_resolution",
                "status": "passed" if resolved_count == len(structure_references) else "failed",
                "passed": resolved_count == len(structure_references),
                "evaluated_items": len(structure_references),
                "attachment_id": None,
                "details": {"references": len(structure_references), "resolved": resolved_count},
            })
        else:
            consistency_checks.append({
                "check": "structure_reference_resolution",
                "status": "not_applicable", "passed": False, "evaluated_items": 0,
                "attachment_id": None,
                "details": {"references": 0, "reason": "the prompt cites no structure"},
            })
        if cross_file_links:
            consistent = sum(1 for link in cross_file_links if link["consistent"])
            consistency_checks.append({
                "check": "cross_file_identifiers",
                "status": "passed" if consistent == len(cross_file_links) else "failed",
                "passed": consistent == len(cross_file_links),
                "evaluated_items": len(cross_file_links),
                "attachment_id": None,
                "details": {"links": len(cross_file_links),
                            "consistent": consistent,
                            "linked_attachments": len({item for link in cross_file_links
                                                       for item in link["attachments"]})},
            })
        else:
            consistency_checks.append({
                "check": "cross_file_identifiers",
                "status": "not_applicable", "passed": False, "evaluated_items": 0,
                "attachment_id": None,
                "details": {"links": 0, "reason": "no shared identifier across attachments"},
            })
        tags = set()
        tags.update(domains)
        tags.update(entity_types)
        tags.add(f"lang:{target.language}")
        tags.add(f"content_lang:{content_language}")
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
            for language in sorted(set(attachment_languages)):
                tags.add(f"attachment_lang:{language}")
                tags.add(f"matrix:{target.language}>{language}")
        if structure_references:
            tags.add("structure_reference")
        if cross_file_links:
            tags.add("cross_file")
        if bundle:
            tags.add(f"bundle:{bundle.get('kind', 'none')}")
        if any(item["expected_extraction_method"] == "ocr" for item in attachments):
            tags.add("ocr")
        if target.negative:
            tags.add("negative")
        if target.ambiguous:
            tags.add("ambiguous")
        if target.destination:
            tags.add("destination_context")
        verification_statuses = [item["verification"]["status"] for item in attachments]
        language_ok = all(item["language_check"].get("matches_declared_language") is True
                          for item in attachments)
        prompt_stats = script_counts(prompt)
        prompt_static = prompt
        for span in sorted(prompt_info["spans"], key=lambda item: -item.start):
            prompt_static = prompt_static[:span.start] + prompt_static[span.end:]
        prompt_static_stats = script_counts(prompt_static)
        prompt_language_ok = language_matches(
            prompt_static_stats, target.language, self.config.get("language_thresholds", {}))
        if any(status == "unverified" for status in verification_statuses) or not language_ok or not prompt_language_ok:
            verification_status = "unverified"
        elif any(status == "verified_layout" for status in verification_statuses):
            verification_status = "verified_partial"
        else:
            verification_status = "verified"
        language_coverage = {
            "prompt_language": target.language,
            "attachment_languages": attachment_languages,
            "content_languages": content_languages,
            "matrices": [f"{target.language}->{item}" for item in attachment_languages] or [f"{target.language}->prompt_only"],
            "mixed_attachments": sum(1 for item in attachments if item["language"] == "mixed"),
            "mixed_script_verified": all(
                item["language_check"]["contains_both"]
                for item in attachments if item["language"] == "mixed"
            ),
            "routed_attachments": sum(1 for item in attachments if item.get("language_routing")),
            "thresholds": self.config.get("language_thresholds", {}),
            "by_file_type": {},
        }
        for item in attachments:
            bucket = language_coverage["by_file_type"].setdefault(
                item["extension"], {"attachments": 0, "declared": {}, "matches": 0})
            bucket["attachments"] += item["language_check"].get("counted_chars", 0)
            bucket["declared"][item["language"]] = bucket["declared"].get(item["language"], 0) + 1
            bucket["matches"] += 1 if item["language_check"].get("matches_declared_language") else 0
        language_stats = {
            "prompt": dict(prompt_stats, static=prompt_static_stats,
                           matches_declared_language=prompt_language_ok),
            "attachments": [
                dict(item["language_check"], attachment_id=item["attachment_id"],
                     language=item["language"], extension=item["extension"])
                for item in attachments
            ],
        }
        document_profile = [
            {
                "attachment_id": item["attachment_id"],
                "filename": item["filename"],
                "archetype": item["archetype"],
                "renderer": item["renderer"],
                "language": item["language"],
                "language_routing": item.get("language_routing"),
                "sections": len(item["structure"].get("headings", [])),
                "tables": len(item["structure"].get("tables", [])),
                "rows": item["structure"].get("rows", 0),
                "sheets": len(item["structure"].get("sheets", [])),
                "slides": item["structure"].get("slides", 0),
                "pages": item["structure"].get("pages", 0),
                "delimiter": item["structure"].get("delimiter"),
            }
            for item in attachments
        ]
        case = {
            "schema_version": "2.1",
            "test_id": test_id,
            "prompt": prompt,
            "language": target.language,
            "prompt_language": target.language,
            "content_language": content_language,
            "content_languages": content_languages,
            "language_mode": content_language,
            "language_coverage": language_coverage,
            "language_stats": language_stats,
            "scenario_id": scenario.scenario_id if scenario else f"SCN-{test_id.split('-')[-1]}",
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
            "bundle": bundle or {"bundle_id": f"BND-{sequence:05d}", "kind": "prompt_only",
                                 "members": [], "revision_changes": []},
            "cross_file_links": cross_file_links,
            "structure_references": structure_references,
            "document_profile": document_profile,
            "consistency_checks": consistency_checks,
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
            "policy_scenario": policy_scenario,
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
                f"Scenario {scenario.scenario_id if scenario else 'inline'}. Task: {target.intent}. "
                "Sensitive values are incidental to the request."
            ),
            "tags": sorted(tags),
            "generation_method": GENERATION_METHOD,
            "verification_status": verification_status,
            "evaluation_requirement": (
                "ocr_required"
                if any(item["evaluation_requirement"] == "ocr_required" for item in attachments)
                else "direct_text_extraction"
            ),
            "verification": {
                "status": verification_status,
                "attachments_checked": len(attachments),
                "attachments_verified": sum(1 for item in attachments if item["verification"]["status"] in ("verified", "verified_layout")),
                "ocr_layout_only": sum(1 for item in attachments if item["verification"]["status"] == "verified_layout"),
                "language_checked": len(attachments),
                "language_passed": language_ok,
                "prompt_language_passed": prompt_language_ok,
                "mixed_language_verified": language_coverage["mixed_script_verified"],
                "residual_english_labels": sum(
                    len(item["language_check"].get("residual_english_labels", []))
                    for item in attachments),
            },
            "prompt_length": len(prompt),
            "prompt_length_class": prompt_length_class,
            "prompt_style": target.length,
            "prompt_form": prompt_info.get("prompt_form", "with_attachment"),
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
    by_attachment_language = Counter()
    language_matrix = Counter()
    by_bundle_kind = Counter()
    by_prompt_form = Counter()
    by_evaluation_requirement = Counter()
    consistency_status = Counter()
    domain_combinations = Counter()
    prompt_lengths = []
    entity_counts = []
    file_total = 0
    ocr_cases = 0
    structure_reference_cases = 0
    cross_file_link_cases = 0
    multi_file_cases = 0
    same_archetype_bundle_cases = 0
    consistency_total = 0
    consistency_passed = 0
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
        by_attachment_language.update(item["language"] for item in case["attachments"])
        language_matrix.update(case.get("language_coverage", {}).get("matrices", []))
        by_bundle_kind[case.get("bundle", {}).get("kind", "unknown")] += 1
        by_prompt_form[case.get("prompt_form", "with_attachment")] += 1
        by_evaluation_requirement[case.get("evaluation_requirement", "direct_text_extraction")] += 1
        if "ocr" in case["tags"]:
            ocr_cases += 1
        if case.get("structure_references"):
            structure_reference_cases += 1
        if case.get("cross_file_links"):
            cross_file_link_cases += 1
        if case["attachment_count"] > 1:
            multi_file_cases += 1
        archetype_ids = [item["archetype"] for item in case["attachments"]]
        if len(archetype_ids) > 1 and len(set(archetype_ids)) < len(archetype_ids):
            same_archetype_bundle_cases += 1
        checks = case.get("consistency_checks", [])
        consistency_total += len(checks)
        consistency_passed += sum(1 for item in checks if item.get("status") == "passed")
        consistency_status.update(item.get("status", "not_evaluated") for item in checks)
    return {
        "total_cases": total,
        "total_files": file_total,
        "positive_cases": by_polarity.get("positive", 0),
        "negative_cases": by_polarity.get("negative", 0),
        "ambiguous_cases": by_category.get("ambiguous", 0),
        "multi_domain_cases": sum(1 for case in cases if case["domain_scope"] == "multi_domain"),
        "multi_file_cases": multi_file_cases,
        "same_archetype_bundle_cases": same_archetype_bundle_cases,
        "structure_reference_cases": structure_reference_cases,
        "cross_file_link_cases": cross_file_link_cases,
        "consistency_checks": consistency_total,
        "consistency_passed": consistency_passed,
        "consistency_status": dict(sorted(consistency_status.items())),
        "consistency_rate": (round(consistency_passed / (consistency_status["passed"]
                                                          + consistency_status["failed"]), 4)
                             if (consistency_status["passed"] + consistency_status["failed"]) else 0.0),
        "ocr_cases": ocr_cases,
        "mean_entities_per_case": _mean(entity_counts),
        "mean_files_per_case": round(file_total / total, 3) if total else 0.0,
        "by_split": dict(sorted(by_split.items())),
        "by_language": dict(sorted(by_language.items())),
        "by_attachment_language": dict(sorted(by_attachment_language.items())),
        "language_matrix": dict(sorted(language_matrix.items())),
        "by_bundle_kind": dict(sorted(by_bundle_kind.items())),
        "by_prompt_form": dict(sorted(by_prompt_form.items())),
        "by_evaluation_requirement": dict(sorted(by_evaluation_requirement.items())),
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


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _notice_markdown(disclosure: str) -> str:
    """Dataset-level synthetic notice: the out-of-band disclosure channel."""
    visible = disclosure == "banner"
    lines = [
        "# NOTICE — synthetic test data",
        "",
        "Every prompt, entity value and attachment in this directory is synthetic.",
        "It was produced deterministically from a seed by `privacy-gateway-testgen`.",
        "No value describes a real person, account, credential, host or payment card.",
        "",
        "## Where the synthetic marking lives (out-of-band)",
        "",
        "- every attachment record in `cases.jsonl` carries `\"synthetic\": true`;",
        "- `manifest.json` carries `\"synthetic\": true` and this notice's hash;",
        "- reserved example domains, `.internal` hosts, test-BIN card numbers and "
        "`example`/`fake` credential markers stay in the content for detector realism.",
        "",
        "## In-band disclosure",
        "",
        f"- `disclosure` mode: `{disclosure}`",
    ]
    if visible:
        lines.append("- visible notices are added to document bodies, images and configuration comments (shared-artifact mode).")
    else:
        lines += [
            "- generated files contain no \"synthetic\" notice: a detector under test must",
            "  not read a hint that could suppress a real detection. Use this notice and",
            "  `cases.jsonl` when the dataset is shared with people.",
        ]
    lines += [
        "",
        "## Ground truth",
        "",
        "- canonical text and layout are authoritative; no OCR engine was run;",
        "- `ground_truth/entities.jsonl` lists every expected detection with its location;",
        "- raster cases require OCR from the system under test and are listed separately",
        "  in `benchmark_safe_ocr_cases.jsonl`.",
        "",
    ]
    return "\n".join(lines)


def benchmark_safe_reasons(case: dict) -> List[str]:
    """Why a case may not enter a benchmark-safe subset (empty means safe).

    A raster case is not excluded for needing OCR: the gateway under test does
    the OCR, the generator only has to be correct about canonical text and
    layout.  Such cases are separated by ``evaluation_requirement`` instead of
    being discarded, so text and OCR benchmarks never share one subset.
    """
    reasons: List[str] = []
    status = case.get("verification_status")
    if status not in ("verified", "verified_partial"):
        reasons.append(f"verification_status:{status}")
    for check in case.get("consistency_checks", []):
        check_status = check.get("status")
        if check_status == "failed":
            reasons.append(f"consistency_failed:{check.get('check')}")
        elif check_status == "not_evaluated":
            reasons.append(f"consistency_not_evaluated:{check.get('check')}")
    verification = case.get("verification", {})
    if verification.get("language_passed") is not True:
        reasons.append("attachment_language_failed")
    if verification.get("prompt_language_passed") is not True:
        reasons.append("prompt_language_failed")
    for attachment in case.get("attachments", []):
        if attachment.get("language_check", {}).get("matches_declared_language") is not True:
            reasons.append(f"language_mismatch:{attachment['attachment_id']}")
        if attachment.get("verification", {}).get("status") not in ("verified", "verified_layout"):
            reasons.append(f"attachment_unverified:{attachment['attachment_id']}")
    return reasons


def export_v2_dataset(dataset: dict, out_dir: str, config: dict, policy: dict) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    cases = dataset["cases"]
    files: Dict[str, bytes] = dataset["files"]
    # Re-exporting into an existing dataset must not leave attachments from a
    # previous seed behind.  The manifest marks the directory as ours.
    if os.path.exists(os.path.join(out_dir, "manifest.json")):
        attachments_dir = os.path.join(out_dir, "attachments")
        if os.path.isdir(attachments_dir):
            shutil.rmtree(attachments_dir)
        for name in ("cases.jsonl", "all.json", "stats.json", "train.jsonl",
                     "validation.jsonl", "test.jsonl", "benchmark_safe_cases.jsonl",
                     "benchmark_safe_text_cases.jsonl", "benchmark_safe_ocr_cases.jsonl",
                     "benchmark_excluded_cases.jsonl", "NOTICE.md"):
            path = os.path.join(out_dir, name)
            if os.path.exists(path):
                os.remove(path)
        ground_truth_dir = os.path.join(out_dir, "ground_truth")
        if os.path.isdir(ground_truth_dir):
            shutil.rmtree(ground_truth_dir)
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

    safe_cases = []
    safe_text_cases = []
    safe_ocr_cases = []
    excluded_rows = []
    for case in cases:
        reasons = benchmark_safe_reasons(case)
        if reasons:
            excluded_rows.append({"test_id": case["test_id"], "reasons": reasons})
            continue
        safe_cases.append(case)
        if case.get("evaluation_requirement") == "ocr_required":
            safe_ocr_cases.append(case)
        else:
            safe_text_cases.append(case)
    _write_jsonl(os.path.join(out_dir, "benchmark_safe_cases.jsonl"), safe_cases)
    _write_jsonl(os.path.join(out_dir, "benchmark_safe_text_cases.jsonl"), safe_text_cases)
    _write_jsonl(os.path.join(out_dir, "benchmark_safe_ocr_cases.jsonl"), safe_ocr_cases)
    _write_jsonl(os.path.join(out_dir, "benchmark_excluded_cases.jsonl"), excluded_rows)
    disclosure = config.get("disclosure", "metadata")
    _write_text(os.path.join(out_dir, "NOTICE.md"), _notice_markdown(disclosure))

    config_for_hash = {key: value for key, value in config.items() if not key.startswith("_")}
    generated_names = ["cases.jsonl", "train.jsonl", "validation.jsonl", "test.jsonl", "all.json", "stats.json",
                       "ground_truth/entities.jsonl", "benchmark_safe_cases.jsonl",
                       "benchmark_safe_text_cases.jsonl", "benchmark_safe_ocr_cases.jsonl",
                       "benchmark_excluded_cases.jsonl", "NOTICE.md"]
    file_hashes = {}
    for name in generated_names:
        with open(os.path.join(out_dir, name), "rb") as handle:
            file_hashes[name] = _sha256(handle.read())
    attachment_hashes = {path: _sha256(data) for path, data in sorted(files.items())}
    verification_summary = Counter(case["verification_status"] for case in cases)
    manifest = {
        "dataset_id": f"pgt2-{dataset['seed']}-{dataset['profile']}",
        "schema_version": "2.1",
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
        "attachment_language_distribution": stats["by_attachment_language"],
        "language_matrix": stats["language_matrix"],
        "bundle_distribution": stats["by_bundle_kind"],
        "structure_reference_cases": stats["structure_reference_cases"],
        "cross_file_link_cases": stats["cross_file_link_cases"],
        "consistency_checks": stats["consistency_checks"],
        "consistency_passed": stats["consistency_passed"],
        "consistency_status": stats["consistency_status"],
        "consistency_rate": stats["consistency_rate"],
        "benchmark_safe_cases": len(safe_cases),
        "benchmark_safe_text_cases": len(safe_text_cases),
        "benchmark_safe_ocr_cases": len(safe_ocr_cases),
        "benchmark_excluded_cases": len(excluded_rows),
        "evaluation_requirement_distribution": stats["by_evaluation_requirement"],
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
        "synthetic": True,
        "disclosure": disclosure,
        "synthetic_notice": "NOTICE.md",
        "notes": "Synthetic only (see NOTICE.md). Attachment hashes and case JSON are deterministic for this seed and config.",
    }
    _write_json(os.path.join(out_dir, "manifest.json"), manifest)
    return manifest
