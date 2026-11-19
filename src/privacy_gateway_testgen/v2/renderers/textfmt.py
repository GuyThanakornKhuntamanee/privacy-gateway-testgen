"""Text, structured-text and configuration renderers.

These formats are deliberately written without third-party libraries.  The
emitters use a strict subset that the verifier can parse back, and they record
character or key-path provenance while writing rather than guessing afterwards.
"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

from ...models import Entity
from ..docmodel import Block, Cell, Doc, entity_cell, record_placements, table_records
from .base import EXTRACTION_METHODS, MIME_TYPES, RenderedFile, location

CELL_TEXT = "text_span"


def _cell_text(cell: Cell) -> str:
    return cell.text


def _wrap_entities(value: Any) -> Any:
    if isinstance(value, Entity):
        return entity_cell(value)
    if isinstance(value, Cell):
        return value
    if isinstance(value, dict):
        return {key: _wrap_entities(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wrap_entities(child) for child in value]
    return value


def _derive_record(doc: Doc) -> Any:
    if doc.record is not None:
        return _wrap_entities(doc.record)
    table = doc.table()
    if table is not None:
        return table_records(table)
    sections = []
    for block in doc.blocks:
        if block.kind in ("heading", "paragraph", "note", "bullet"):
            sections.append({"kind": block.kind, "text": Cell(block.text, block.placements)})
        elif block.kind in ("code", "log"):
            sections.append({"kind": block.kind, "text": Cell(block.text, block.placements)})
    if sections:
        return {"title": doc.title, "sections": sections}
    return {"title": doc.title}


def _json_walk(value: Any, path: str, target: List[dict]) -> Any:
    if isinstance(value, Cell):
        for placement in value.placements:
            target.append({
                "entity": placement.entity,
                "location": {
                    "kind": "json_path",
                    "path": path,
                    "character_start": placement.start,
                    "character_end": placement.end,
                },
                "role": placement.role,
            })
        return value.text
    if isinstance(value, dict):
        return {str(key): _json_walk(child, f"{path}.{key}", target) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_walk(child, f"{path}[{index}]", target) for index, child in enumerate(value)]
    return value


def _render_json(doc: Doc, filename: str) -> RenderedFile:
    locations: List[dict] = []
    plain = _json_walk(_derive_record(doc), "$", locations)
    text = json.dumps(plain, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    return RenderedFile(filename, text.encode("utf-8"), MIME_TYPES["json"], "json",
                        EXTRACTION_METHODS["json"], locations, {"encoding": "utf-8"})


def _yaml_scalar(value: str) -> str:
    if value == "":
        return '""'
    if re.match(r"^[A-Za-z0-9_./@+\-]+$", value) and value.lower() not in ("true", "false", "null", "yes", "no"):
        return value
    return json.dumps(value, ensure_ascii=False)


def _yaml_emit(value: Any, path: str, indent: int, lines: List[str], locations: List[dict],
               key: Optional[str] = None) -> None:
    prefix = " " * indent
    if isinstance(value, Cell):
        for placement in value.placements:
            locations.append({
                "entity": placement.entity,
                "location": {
                    "kind": "yaml_path", "path": path, "line": len(lines) + 1,
                    "character_start": placement.start, "character_end": placement.end,
                },
                "role": placement.role,
            })
        line = f"{prefix}{key}: {_yaml_scalar(value.text)}" if key else f"{prefix}- {_yaml_scalar(value.text)}"
        lines.append(line)
        return
    if isinstance(value, dict):
        if key:
            lines.append(f"{prefix}{key}:")
            indent += 2
            prefix = " " * indent
        for child_key, child in value.items():
            _yaml_emit(child, f"{path}.{child_key}", indent, lines, locations, key=str(child_key))
        if not value and key:
            lines[-1] = f"{prefix}{key}: {{}}"
        return
    if isinstance(value, (list, tuple)):
        if key:
            lines.append(f"{prefix}{key}:")
            indent += 2
            prefix = " " * indent
        for index, child in enumerate(value):
            _yaml_emit(child, f"{path}[{index}]", indent, lines, locations)
        if not value and key:
            lines[-1] = f"{prefix}{key}: []"
        return
    if key:
        lines.append(f"{prefix}{key}: {_yaml_scalar(str(value))}")
    else:
        lines.append(f"{prefix}- {_yaml_scalar(str(value))}")


def _render_yaml(doc: Doc, filename: str) -> RenderedFile:
    lines: List[str] = ["# synthetic example - not real data"]
    locations: List[dict] = []
    record = _derive_record(doc)
    if isinstance(record, dict):
        for key, value in record.items():
            _yaml_emit(value, f"$.{key}", 0, lines, locations, key=str(key))
    else:
        _yaml_emit(record, "$", 0, lines, locations)
    text = "\n".join(lines) + "\n"
    ext = "yml" if filename.lower().endswith(".yml") else "yaml"
    return RenderedFile(filename, text.encode("utf-8"), MIME_TYPES[ext], "yaml",
                        EXTRACTION_METHODS[ext], locations, {"encoding": "utf-8"})


def _xml_tag(name: str) -> str:
    tag = re.sub(r"[^A-Za-z0-9_.-]", "_", str(name))
    if not tag or not (tag[0].isalpha() or tag[0] == "_"):
        tag = "item_" + tag
    return tag


def _xml_emit(value: Any, tag: str, path: str, indent: int, lines: List[str], locations: List[dict]) -> None:
    prefix = " " * indent
    if isinstance(value, Cell):
        for placement in value.placements:
            locations.append({
                "entity": placement.entity,
                "location": {
                    "kind": "xml_path", "path": path,
                    "character_start": placement.start, "character_end": placement.end,
                },
                "role": placement.role,
            })
        lines.append(f"{prefix}<{tag}>{xml_escape(value.text)}</{tag}>")
        return
    if isinstance(value, dict):
        lines.append(f"{prefix}<{tag}>")
        for key, child in value.items():
            child_tag = _xml_tag(key)
            _xml_emit(child, child_tag, f"{path}/{child_tag}", indent + 2, lines, locations)
        lines.append(f"{prefix}</{tag}>")
        return
    if isinstance(value, (list, tuple)):
        lines.append(f"{prefix}<{tag}>")
        for index, child in enumerate(value):
            item_tag = "item"
            _xml_emit(child, item_tag, f"{path}/{item_tag}[{index}]", indent + 2, lines, locations)
        lines.append(f"{prefix}</{tag}>")
        return
    lines.append(f"{prefix}<{tag}>{xml_escape(str(value))}</{tag}>")


def _render_xml(doc: Doc, filename: str) -> RenderedFile:
    root = doc.metadata.get("xml_root", "document")
    root_tag = _xml_tag(root)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    locations: List[dict] = []
    _xml_emit(_derive_record(doc), root_tag, f"/{root_tag}", 0, lines, locations)
    text = "\n".join(lines) + "\n"
    return RenderedFile(filename, text.encode("utf-8"), MIME_TYPES["xml"], "xml",
                        EXTRACTION_METHODS["xml"], locations, {"encoding": "utf-8", "root": root_tag})


def _csv_grid(doc: Doc) -> Tuple[List[str], List[List[Cell]]]:
    table = doc.table()
    if table is not None:
        return list(table.headers), [list(row) for row in table.rows]
    record = _derive_record(doc)
    if isinstance(record, list) and record and isinstance(record[0], dict):
        headers = [str(key) for key in record[0].keys()]
        rows = []
        for item in record:
            rows.append([item.get(key, Cell("")) if isinstance(item.get(key), Cell) else Cell(str(item.get(key, "")))
                         for key in headers])
        return headers, rows
    return ["key", "value"], [[Cell(str(key)), item if isinstance(item, Cell) else Cell(str(item))]
                              for key, item in (record.items() if isinstance(record, dict) else [])]


def _render_csv(doc: Doc, filename: str) -> RenderedFile:
    headers, rows = _csv_grid(doc)
    delimiter = doc.metadata.get("delimiter", ",")
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([cell.text for cell in row])
    locations: List[dict] = []
    for row_index, row in enumerate(rows, start=2):
        for column_index, value in enumerate(row, start=1):
            for placement in value.placements:
                header = headers[column_index - 1] if column_index - 1 < len(headers) else ""
                locations.append({
                    "entity": placement.entity,
                    "location": {
                        "kind": "csv_cell", "row": row_index, "column": column_index,
                        "header": header, "value": value.text,
                    },
                    "role": placement.role,
                })
    return RenderedFile(filename, buffer.getvalue().encode("utf-8"), MIME_TYPES["csv"], "csv",
                        EXTRACTION_METHODS["csv"], locations,
                        {"encoding": "utf-8", "delimiter": delimiter, "headers": headers})


def _flatten_config(value: Any, prefix: str = "") -> List[Tuple[str, str, Any]]:
    pairs: List[Tuple[str, str, Any]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            full = f"{prefix}.{key}" if prefix else str(key)
            pairs.extend(_flatten_config(child, full))
    elif isinstance(value, (list, tuple)):
        text = ", ".join(item.text if isinstance(item, Cell) else str(item) for item in value)
        pairs.append((prefix, prefix.split(".")[0] if "." in prefix else "", Cell(text)))
    elif isinstance(value, Cell):
        pairs.append((prefix, prefix.split(".")[0] if "." in prefix else "", value))
    else:
        pairs.append((prefix, prefix.split(".")[0] if "." in prefix else "", Cell(str(value))))
    return pairs


def _render_config(doc: Doc, filename: str, ext: str) -> RenderedFile:
    record = _derive_record(doc)
    if not isinstance(record, dict):
        record = {"value": record}
    lines: List[str] = []
    locations: List[dict] = []
    if ext == "env":
        lines.append("# synthetic example environment - values are non-functional")
        for key, _section, value in _flatten_config(record):
            key_name = re.sub(r"[^A-Za-z0-9_]", "_", key).upper()
            text = value.text if isinstance(value, Cell) else str(value)
            if isinstance(value, Cell):
                for placement in value.placements:
                    locations.append({
                        "entity": placement.entity,
                        "location": {
                            "kind": "key_path", "key": key_name, "key_path": key, "section": "",
                            "line": len(lines) + 1,
                            "character_start": placement.start, "character_end": placement.end,
                        },
                        "role": placement.role,
                    })
            lines.append(f"{key_name}={text}")
    elif ext == "toml":
        lines.append("# synthetic example configuration")
        section = ""
        for key, pair_section, value in _flatten_config(record):
            if pair_section and pair_section != section:
                section = pair_section
                lines.append("")
                lines.append(f"[{re.sub(r'[^A-Za-z0-9_.-]', '_', section)}]")
            leaf = key.split(".")[-1]
            text = value.text if isinstance(value, Cell) else str(value)
            if isinstance(value, Cell):
                for placement in value.placements:
                    locations.append({
                        "entity": placement.entity,
                        "location": {
                            "kind": "key_path", "key": key, "section": section,
                            "line": len(lines) + 1,
                            "character_start": placement.start, "character_end": placement.end,
                        },
                        "role": placement.role,
                    })
            lines.append(f"{leaf} = {json.dumps(text, ensure_ascii=False)}")
    else:  # ini / conf
        lines.append("; synthetic example configuration")
        section = ""
        for key, pair_section, value in _flatten_config(record):
            if pair_section and pair_section != section:
                section = pair_section
                lines.append("")
                lines.append(f"[{re.sub(r'[^A-Za-z0-9_.-]', '_', section)}]")
            leaf = key.split(".")[-1]
            text = value.text if isinstance(value, Cell) else str(value)
            if isinstance(value, Cell):
                for placement in value.placements:
                    locations.append({
                        "entity": placement.entity,
                        "location": {
                            "kind": "key_path", "key": key, "section": section,
                            "line": len(lines) + 1,
                            "character_start": placement.start, "character_end": placement.end,
                        },
                        "role": placement.role,
                    })
            lines.append(f"{leaf} = {text}")
    text = "\n".join(lines) + "\n"
    return RenderedFile(filename, text.encode("utf-8"), MIME_TYPES[ext], ext,
                        EXTRACTION_METHODS[ext], locations, {"encoding": "utf-8", "format": ext})


def _table_text(block: Block) -> Tuple[str, List[Tuple[int, Any]]]:
    lines: List[str] = []
    if block.title:
        lines.append(block.title)
    headers = " | ".join(block.headers)
    lines.append(headers)
    lines.append("-" * max(8, len(headers)))
    placements: List[Tuple[int, Any]] = []
    text = "\n".join(lines) + "\n"
    for row in block.rows:
        rendered = " | ".join(cell.text for cell in row)
        row_text = rendered + "\n"
        for index, value in enumerate(row):
            column_start = sum(len(cell.text) + 3 for cell in row[:index])
            for placement in value.placements:
                placements.append((len(text) + column_start + placement.start, (
                    placement, column_start + placement.start, column_start + placement.end
                )))
        text += row_text
    return text, placements


def _render_text(doc: Doc, filename: str, ext: str) -> RenderedFile:
    markdown = ext == "md"
    chunks: List[Tuple[str, int]] = []
    full: List[str] = []
    locations: List[dict] = []

    def add(piece: str) -> None:
        full.append(piece)

    def add_block_text(piece: str, placements: List[Any], prefix: int = 0) -> None:
        base = len("".join(full))
        add(piece)
        for placement in placements:
            line = "".join(full).count("\n", 0, base + placement.start + prefix) + 1
            locations.append({
                "entity": placement.entity,
                "location": {
                    "kind": CELL_TEXT, "line": line,
                    "character_start": base + placement.start + prefix,
                    "character_end": base + placement.end + prefix,
                },
                "role": placement.role,
            })

    for block in doc.blocks:
        if block.kind == "heading":
            add(("## " if markdown else "") + block.text + "\n\n")
        elif block.kind in ("paragraph", "note"):
            add_block_text(block.text + "\n\n", block.placements)
        elif block.kind == "bullet":
            add_block_text(("- " if markdown else "- ") + block.text + "\n", block.placements, prefix=2)
        elif block.kind == "table":
            table_text, table_placements = _table_text(block)
            base = len("".join(full))
            add(table_text)
            for global_start, (placement, start, end) in table_placements:
                absolute = base + global_start
                line = "".join(full).count("\n", 0, absolute) + 1
                locations.append({
                    "entity": placement.entity,
                    "location": {
                        "kind": CELL_TEXT, "line": line,
                        "character_start": absolute,
                        "character_end": absolute + (end - start),
                    },
                    "role": placement.role,
                })
        elif block.kind in ("code", "log"):
            add_block_text(block.text, block.placements)
        elif block.kind == "keyvalue":
            text = "\n".join(f"{row[0].text}: {row[1].text}" for row in block.rows if len(row) >= 2)
            add_block_text(text + "\n\n", [])
    if doc.record is not None:
        for path, value in record_placements(_wrap_entities(doc.record)):
            prefix = f"{path}: "
            piece = prefix + value.text + "\n"
            base = len("".join(full))
            add(piece)
            for placement in value.placements:
                locations.append({
                    "entity": placement.entity,
                    "location": {
                        "kind": CELL_TEXT,
                        "line": "".join(full).count("\n", 0, base) + 1,
                        "character_start": base + len(prefix) + placement.start,
                        "character_end": base + len(prefix) + placement.end,
                    },
                    "role": placement.role,
                })
    text = "".join(full)
    if ext in ("py", "js", "ts", "java", "go", "sql", "tf") and not text:
        text = ""
    return RenderedFile(filename, text.encode("utf-8"), MIME_TYPES[ext], ext,
                        EXTRACTION_METHODS[ext], locations,
                        {"encoding": "utf-8", "line_count": text.count("\n")})


def render_text(doc: Doc, ext: str, filename: str) -> RenderedFile:
    if ext == "csv":
        return _render_csv(doc, filename)
    if ext == "json":
        return _render_json(doc, filename)
    if ext in ("yaml", "yml"):
        return _render_yaml(doc, filename)
    if ext == "xml":
        return _render_xml(doc, filename)
    if ext in ("env", "ini", "conf", "toml"):
        return _render_config(doc, filename, ext)
    return _render_text(doc, filename, ext)
