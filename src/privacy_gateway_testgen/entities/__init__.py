"""Entity factories and the per-case entity pool."""

from __future__ import annotations

import random
from typing import Dict, Optional

from ..models import Entity, LOOKALIKE_DOMAIN
from . import common, infra, lookalike, payment, pii, secrets

REGISTRY: Dict[str, Dict[str, tuple]] = {
    "pii": pii.GENERATORS,
    "payment": payment.GENERATORS,
    "secrets": secrets.GENERATORS,
    "infrastructure": infra.GENERATORS,
    LOOKALIKE_DOMAIN: lookalike.GENERATORS,
}

CORE_DOMAINS = ("pii", "payment", "secrets", "infrastructure")


class EntityPool:
    """Draws deterministic synthetic entities for one test case."""

    def __init__(self, rng: random.Random, language: str, org: Optional[dict] = None) -> None:
        self.rng = rng
        self.language = language
        self.org = org or rng.choice(common.ORGS)
        self.used = set()

    def draw(self, domain: str, entity_type: Optional[str] = None) -> Entity:
        if domain not in REGISTRY:
            raise ValueError(f"unknown domain: {domain}")
        specs = REGISTRY[domain]
        if entity_type is not None:
            if entity_type not in specs:
                raise ValueError(f"unknown entity type for {domain}: {entity_type}")
            factory = specs[entity_type][1]
        else:
            names = list(specs)
            weights = [specs[name][0] for name in names]
            entity_type = self.rng.choices(names, weights=weights, k=1)[0]
            factory = specs[entity_type][1]

        entity = factory(self.rng, self)
        for _ in range(8):
            if entity.value not in self.used:
                break
            entity = factory(self.rng, self)
        self.used.add(entity.value)
        return entity

    def draw_lookalike(self, entity_type: Optional[str] = None) -> Entity:
        return self.draw(LOOKALIKE_DOMAIN, entity_type)


def entity_types(domain: str) -> tuple:
    return tuple(REGISTRY[domain])
