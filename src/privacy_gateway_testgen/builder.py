"""Span-recording prompt builder.

Templates never compute character offsets after the fact.  They append text and
entities in order, so every recorded span is exact by construction even for
Thai text, multi-line blocks and JSON/YAML escaping.
"""

from __future__ import annotations

from typing import List, Optional

from .models import Entity, Span


class PromptBuilder:
    def __init__(self) -> None:
        self._parts: List[str] = []
        self._length = 0
        self.spans: List[Span] = []

    def text(self, value: str) -> "PromptBuilder":
        self._parts.append(value)
        self._length += len(value)
        return self

    def line(self, value: str = "") -> "PromptBuilder":
        return self.text(value + "\n")

    def entity(self, entity: Entity, display: Optional[str] = None) -> "PromptBuilder":
        value = entity.value if display is None else display
        start = self._length
        self._parts.append(value)
        self._length += len(value)
        self.spans.append(Span(entity=entity, start=start, end=self._length))
        return self

    def build(self) -> str:
        return "".join(self._parts)

    def block(self, lines: List[str]) -> "PromptBuilder":
        for line in lines:
            self.line(line)
        return self
