"""Core data structures shared by entity factories, templates and the generator.

Character offsets use Python string indices: 0-based Unicode code points with an
exclusive end.  Thai characters are in the BMP, so this is also the UTF-16
offset for the prompts produced here; consumers that slice differently should
use the companion ``privacy_gateway_testgen.validation`` helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

DOMAINS = ("pii", "payment", "secrets", "infrastructure")
LOOKALIKE_DOMAIN = "lookalike"
LANGUAGES = ("th", "en", "mixed")
LENGTH_CLASSES = ("short", "medium", "long")
DIFFICULTIES = (1, 2, 3, 4, 5)
SPLITS = ("train", "validation", "test")
ACTIONS = ("ALLOW", "MASK", "TOKENIZE", "REDACT", "LOCAL_ONLY", "BLOCK")
POLARITIES = ("positive", "negative")
VERIFICATION_STATUSES = ("verified_spans", "verified_manual", "unverified")

CHAR_OFFSET_CONVENTION = "unicode_codepoints_0_based_end_exclusive"
GENERATION_METHOD = "template+deterministic_entity_factories"


@dataclass(frozen=True)
class Entity:
    """A value produced by an entity factory.

    ``detection_expected`` is false for lookalike/negative values: they are
    annotated so false-positive behaviour can be measured, but they are not
    sensitive entities under the test oracle.
    """

    domain: str
    entity_type: str
    value: str
    valid: bool = True
    detection_expected: bool = True
    note: str = ""


@dataclass
class Span:
    entity: Entity
    start: int
    end: int

    def to_annotation(self) -> dict:
        ent = self.entity
        return {
            "domain": ent.domain,
            "entity_type": ent.entity_type,
            "character_start": self.start,
            "character_end": self.end,
            "exact_entity_value": ent.value,
            "detection_expected": ent.detection_expected,
            "classification_expected": ent.entity_type if ent.detection_expected else None,
            "valid": ent.valid,
            "note": ent.note,
        }


@dataclass
class Draft:
    """Output of one template before policy resolution and case assembly."""

    prompt: str
    spans: List[Span]
    template_id: str
    family: str
    length_class: str
    difficulty: int
    language: str
    structure: str
    context_complexity: str
    detection_mode: str
    negative: bool
    adversarial: bool
    rationale: str
    tags: List[str] = field(default_factory=list)
    template_domains: tuple = ()

    @property
    def positive(self) -> bool:
        return any(s.entity.detection_expected for s in self.spans)

    def expected_entities(self) -> List[Entity]:
        return [s.entity for s in self.spans if s.entity.detection_expected]
