"""v2 document model: span-first content that renderers can turn into real files.

A document is a small tree of blocks. Text and table cells are built through
``TextBuilder`` so every entity placement keeps its exact local offsets. The
renderer maps those local offsets to file-specific provenance (sheet/cell,
paragraph, slide, page, image box, JSON path, ...).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..models import Entity


@dataclass
class Placement:
    entity: Entity
    start: int
    end: int
    role: str = "body"


@dataclass
class Cell:
    text: str
    placements: List[Placement] = field(default_factory=list)


class TextBuilder:
    """Appends text and entities, recording offsets at insertion time."""

    def __init__(self) -> None:
        self._parts: List[str] = []
        self._length = 0
        self.placements: List[Placement] = []

    def text(self, value: str) -> "TextBuilder":
        self._parts.append(value)
        self._length += len(value)
        return self

    def line(self, value: str = "") -> "TextBuilder":
        return self.text(value + "\n")

    def entity(self, entity: Entity, role: str = "body", display: Optional[str] = None) -> "TextBuilder":
        value = entity.value if display is None else display
        start = self._length
        self._parts.append(value)
        self._length += len(value)
        self.placements.append(Placement(entity, start, self._length, role))
        return self

    def build(self) -> str:
        return "".join(self._parts)


def _apply(target: TextBuilder, value: Any, role: str = "body") -> TextBuilder:
    if isinstance(value, Entity):
        return target.entity(value, role)
    if isinstance(value, Cell):
        base = target._length
        target.text(value.text)
        for placement in value.placements:
            target.placements.append(
                Placement(placement.entity, base + placement.start, base + placement.end,
                          placement.role or role)
            )
        return target
    return target.text(str(value))


def build_text(*parts: Any, role: str = "body") -> Tuple[str, List[Placement]]:
    builder = TextBuilder()
    for part in parts:
        _apply(builder, part, role)
    return builder.build(), builder.placements


def cell(*parts: Any, role: str = "body") -> Cell:
    text, placements = build_text(*parts, role=role)
    return Cell(text, placements)


def entity_cell(entity: Entity, role: str = "body") -> Cell:
    return Cell(entity.value, [Placement(entity, 0, len(entity.value), role)])


@dataclass
class Block:
    kind: str  # heading, paragraph, bullet, table, code, log, keyvalue, note
    text: str = ""
    placements: List[Placement] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    rows: List[List[Cell]] = field(default_factory=list)
    title: str = ""
    items: List[str] = field(default_factory=list)
    language: str = ""


@dataclass
class Slide:
    title: str
    blocks: List[Block] = field(default_factory=list)


@dataclass
class Doc:
    archetype: str
    title: str
    filename: str
    blocks: List[Block] = field(default_factory=list)
    record: Optional[Any] = None
    slides: List[Slide] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    language: str = "en"
    ocr: Optional[dict] = None
    scan: bool = False

    def table(self) -> Optional[Block]:
        for block in self.blocks:
            if block.kind == "table":
                return block
        return None

    def all_blocks(self) -> List[Block]:
        result = list(self.blocks)
        for slide in self.slides:
            result.extend(slide.blocks)
        return result


class DocBuilder:
    def __init__(self, archetype: str, title: str, filename: str, language: str = "en") -> None:
        self.doc = Doc(archetype=archetype, title=title, filename=filename, language=language)

    def heading(self, text: str) -> "DocBuilder":
        self.doc.blocks.append(Block("heading", text=text))
        return self

    def para(self, *parts: Any, role: str = "body") -> "DocBuilder":
        text, placements = build_text(*parts, role=role)
        self.doc.blocks.append(Block("paragraph", text=text, placements=placements))
        return self

    def note(self, *parts: Any) -> "DocBuilder":
        text, placements = build_text(*parts, role="note")
        self.doc.blocks.append(Block("note", text=text, placements=placements))
        return self

    def bullet(self, *parts: Any) -> "DocBuilder":
        text, placements = build_text(*parts)
        self.doc.blocks.append(Block("bullet", text=text, placements=placements))
        return self

    def code(self, lines: Sequence[Any]) -> "DocBuilder":
        builder = TextBuilder()
        for line in lines:
            for part in (line if isinstance(line, (list, tuple)) else [line]):
                _apply(builder, part)
            builder.text("\n")
        self.doc.blocks.append(Block("code", text=builder.build(), placements=builder.placements))
        return self

    def log(self, lines: Sequence[Any]) -> "DocBuilder":
        return self.code(lines)

    def table(self, headers: Sequence[str], rows: Sequence[Sequence[Any]], title: str = "") -> "DocBuilder":
        grid: List[List[Cell]] = []
        for row in rows:
            grid.append([value if isinstance(value, Cell) else cell(value) for value in row])
        self.doc.blocks.append(Block("table", headers=list(headers), rows=grid, title=title))
        return self

    def keyvalue(self, pairs: Sequence[Tuple[str, Any]], title: str = "") -> "DocBuilder":
        rows = [[cell(key), value if isinstance(value, Cell) else cell(value)] for key, value in pairs]
        return self.table(["key", "value"], rows, title=title)

    def record(self, value: Any) -> "DocBuilder":
        self.doc.record = value
        return self

    def slide(self, title: str, *parts: Any) -> "DocBuilder":
        blocks: List[Block] = []
        for part in parts:
            if isinstance(part, Block):
                blocks.append(part)
            else:
                text, placements = build_text(part)
                blocks.append(Block("paragraph", text=text, placements=placements))
        self.doc.slides.append(Slide(title=title, blocks=blocks))
        return self

    def build(self, **metadata: Any) -> Doc:
        self.doc.metadata.update(metadata)
        return self.doc


def record_placements(value: Any, path: str = "$") -> List[Tuple[str, Cell]]:
    """Return leaf ``Cell`` values with a JSON/YAML-ish path."""
    found: List[Tuple[str, Cell]] = []
    if isinstance(value, Cell):
        found.append((path, value))
    elif isinstance(value, dict):
        for key, child in value.items():
            found.extend(record_placements(child, f"{path}.{key}"))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found.extend(record_placements(child, f"{path}[{index}]"))
    return found


def table_records(block: Block) -> List[Dict[str, Cell]]:
    """Convert a table block into row records keyed by header."""
    records: List[Dict[str, Cell]] = []
    for row in block.rows:
        records.append({header: value for header, value in zip(block.headers, row)})
    return records
