"""Reopen, parse and verify generated files against their annotations.

A case is not "verified" because a renderer returned bytes.  Every annotation is
resolved at its recorded location, and every file is parsed with the class of
parser an evaluation harness would use.  Image OCR is deliberately reported as
layout verification, not as OCR verification.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from .renderers.base import MIME_TYPES

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _issue(kind: str, message: str, annotation: Optional[dict] = None) -> dict:
    return {"kind": kind, "message": message, "annotation_id": (annotation or {}).get("annotation_id")}


def is_ascii(value: str) -> bool:
    return all(ord(char) < 128 for char in value)


def _json_resolve(value: Any, path: str) -> Any:
    if path == "$":
        return value
    tokens = re.findall(r"\.([A-Za-z0-9_\-]+)|\[(\d+)\]", path[1:])
    current = value
    for key, index in tokens:
        if key:
            if not isinstance(current, dict) or key not in current:
                raise KeyError(key)
            current = current[key]
        else:
            if not isinstance(current, list) or int(index) >= len(current):
                raise IndexError(index)
            current = current[int(index)]
    return current


def _yaml_scalar(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if text.startswith('"') and text.endswith('"'):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    if text in ("null", "~"):
        return None
    return text


def parse_yaml_subset(text: str) -> Any:
    """Parse the strict YAML subset emitted by the generator.

    It is intentionally not a general YAML parser.  The verifier uses the same
    subset the renderer writes, and the limitation is documented.
    """
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        lines.append((indent, raw.strip()))

    def parse_block(index: int, indent: int) -> Tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        if lines[index][1].startswith("- "):
            result: List[Any] = []
            while index < len(lines) and lines[index][0] == indent and lines[index][1].startswith("- "):
                value = lines[index][1][2:].strip()
                if value:
                    result.append(_yaml_scalar(value))
                    index += 1
                else:
                    child, index = parse_block(index + 1, indent + 2)
                    result.append(child)
            return result, index
        result: Dict[str, Any] = {}
        while index < len(lines) and lines[index][0] == indent and not lines[index][1].startswith("- "):
            content = lines[index][1]
            if ":" not in content:
                index += 1
                continue
            key, rest = content.split(":", 1)
            rest = rest.strip()
            if rest:
                result[key.strip()] = _yaml_scalar(rest)
                index += 1
            else:
                child, index = parse_block(index + 1, indent + 2)
                result[key.strip()] = child
        return result, index

    parsed, _ = parse_block(0, lines[0][0] if lines else 0)
    return parsed


def _yaml_resolve(value: Any, path: str) -> Any:
    if path.startswith("$"):
        path = path[1:]
        if path.startswith("."):
            path = path[1:]
    tokens = re.findall(r"(?:^|\.)([A-Za-z0-9_\-]+)|\[(\d+)\]", path)
    current = value
    for key, index in tokens:
        if key:
            if not isinstance(current, dict) or key not in current:
                raise KeyError(key)
            current = current[key]
        else:
            if not isinstance(current, list) or int(index) >= len(current):
                raise IndexError(index)
            current = current[int(index)]
    return current


def _xml_resolve(root, path: str) -> Any:
    parts = [part for part in path.split("/") if part]
    if parts and parts[0] == root.tag.split("}")[-1]:
        parts = parts[1:]
    current = root
    for part in parts:
        match = re.match(r"^([^\[]+)(?:\[(\d+)\])?$", part)
        if not match:
            raise KeyError(part)
        tag, index = match.group(1), match.group(2)
        children = [child for child in list(current) if child.tag.split("}")[-1] == tag]
        if not children:
            raise KeyError(tag)
        current = children[int(index or 0)]
    return current


def _text_entities(data: bytes, ext: str, rendered_locations: List[dict]) -> Tuple[List[str], List[dict]]:
    text = data.decode("utf-8-sig")
    issues: List[dict] = []
    for item in rendered_locations:
        loc = item["location"]
        entity = item["entity"]
        start, end = loc.get("character_start"), loc.get("character_end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(text):
            if text[start:end] != entity.value:
                issues.append(_issue("text_span_mismatch",
                                     f"{ext} span {start}:{end} does not equal {entity.value!r}",
                                     item))
        elif entity.value not in text:
            issues.append(_issue("entity_missing", f"{entity.value!r} not found in {ext}", item))
    return [text], issues


def _csv_verify(data: bytes, rendered_locations: List[dict], meta: dict) -> Tuple[List[str], List[dict]]:
    delimiter = meta.get("delimiter", ",")
    rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig")), delimiter=delimiter))
    issues: List[dict] = []
    for item in rendered_locations:
        loc = item["location"]
        entity = item["entity"]
        row, column = loc.get("row", 0), loc.get("column", 0)
        if not (0 < row <= len(rows) and 0 < column <= len(rows[row - 1])):
            issues.append(_issue("csv_cell_out_of_range", f"row {row} column {column}", item))
            continue
        value = rows[row - 1][column - 1]
        if entity.value not in value:
            issues.append(_issue("csv_cell_mismatch", f"cell does not contain {entity.value!r}", item))
    return ["\n".join(",".join(row) for row in rows)], issues


def _json_verify(data: bytes, rendered_locations: List[dict]) -> Tuple[List[str], List[dict]]:
    value = json.loads(data.decode("utf-8-sig"))
    issues: List[dict] = []
    texts: List[str] = []
    for item in rendered_locations:
        path = item["location"].get("path", "$")
        try:
            leaf = _json_resolve(value, path)
        except (KeyError, IndexError) as exc:
            issues.append(_issue("json_path_missing", f"{path}: {exc}", item))
            continue
        if not isinstance(leaf, str) or item["entity"].value not in leaf:
            issues.append(_issue("json_value_mismatch", f"{path} does not contain {item['entity'].value!r}", item))
        texts.append(leaf if isinstance(leaf, str) else str(leaf))
    return texts, issues


def _yaml_verify(data: bytes, rendered_locations: List[dict]) -> Tuple[List[str], List[dict]]:
    value = parse_yaml_subset(data.decode("utf-8-sig"))
    issues: List[dict] = []
    texts: List[str] = []
    for item in rendered_locations:
        path = item["location"].get("path", "")
        try:
            leaf = _yaml_resolve(value, path)
        except (KeyError, IndexError) as exc:
            issues.append(_issue("yaml_path_missing", f"{path}: {exc}", item))
            continue
        if not isinstance(leaf, str) or item["entity"].value not in leaf:
            issues.append(_issue("yaml_value_mismatch", f"{path} does not contain {item['entity'].value!r}", item))
        texts.append(leaf if isinstance(leaf, str) else str(leaf))
    return texts, issues


def _xml_verify(data: bytes, rendered_locations: List[dict]) -> Tuple[List[str], List[dict]]:
    root = ET.fromstring(data.decode("utf-8-sig"))
    issues: List[dict] = []
    texts: List[str] = []
    for item in rendered_locations:
        path = item["location"].get("path", "")
        try:
            node = _xml_resolve(root, path)
        except KeyError as exc:
            issues.append(_issue("xml_path_missing", f"{path}: {exc}", item))
            continue
        text = "".join(node.itertext())
        if item["entity"].value not in text:
            issues.append(_issue("xml_value_mismatch", f"{path} does not contain {item['entity'].value!r}", item))
        texts.append(text)
    return texts, issues


def _config_verify(data: bytes, rendered_locations: List[dict], ext: str) -> Tuple[List[str], List[dict]]:
    text = data.decode("utf-8-sig")
    values: Dict[str, str] = {}
    section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            continue
        if "=" in stripped:
            key, value = stripped.split("=", 1)
            key = key.strip()
            values[(f"{section}.{key}" if section else key)] = value.strip().strip('"')
    issues: List[dict] = []
    for item in rendered_locations:
        loc = item["location"]
        key = loc.get("key", "")
        full = key if key in values else (f"{loc.get('section')}.{key.split('.')[-1]}" if loc.get("section") else key)
        value = values.get(full, values.get(key.split(".")[-1], ""))
        if item["entity"].value not in value:
            issues.append(_issue("config_value_mismatch", f"{full} does not contain {item['entity'].value!r}", item))
    return [text], issues


def _docx_paragraphs(root) -> List[str]:
    body = root.find(f"{W}body")
    result = []
    if body is None:
        return result
    for child in list(body):
        if child.tag == f"{W}p":
            result.append("".join(node.text or "" for node in child.iter(f"{W}t")))
    return result


def _docx_tables(root) -> List[List[List[str]]]:
    body = root.find(f"{W}body")
    tables = []
    if body is None:
        return tables
    for table in body.findall(f"{W}tbl"):
        rows = []
        for row in table.findall(f"{W}tr"):
            cells = []
            for cell in row.findall(f"{W}tc"):
                cells.append("".join(node.text or "" for node in cell.iter(f"{W}t")))
            rows.append(cells)
        tables.append(rows)
    return tables


def _docx_verify(data: bytes, rendered_locations: List[dict]) -> Tuple[List[str], List[dict]]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
        paragraphs = _docx_paragraphs(root)
        tables = _docx_tables(root)
        header_text = ""
        footer_text = ""
        for name in archive.namelist():
            if name.startswith("word/header") and name.endswith(".xml"):
                header_text += " ".join("".join(node.text or "" for node in ET.fromstring(archive.read(name)).iter(f"{W}t")))
            if name.startswith("word/footer") and name.endswith(".xml"):
                footer_text += " ".join("".join(node.text or "" for node in ET.fromstring(archive.read(name)).iter(f"{W}t")))
    issues: List[dict] = []
    texts: List[str] = []
    for item in rendered_locations:
        loc = item["location"]
        kind = loc.get("kind")
        entity = item["entity"]
        if kind == "docx_paragraph":
            index = loc.get("paragraph", -1)
            if not (0 <= index < len(paragraphs)):
                issues.append(_issue("docx_paragraph_out_of_range", f"paragraph {index}", item))
                continue
            text = paragraphs[index]
            if entity.value not in text:
                issues.append(_issue("docx_paragraph_mismatch", f"paragraph {index} does not contain {entity.value!r}", item))
            texts.append(text)
        elif kind == "docx_table_cell":
            table, row, column = loc.get("table", 0), loc.get("row", 0), loc.get("column", 0)
            try:
                text = tables[table - 1][row - 1][column - 1]
            except IndexError:
                issues.append(_issue("docx_table_out_of_range", f"table {table} {row}:{column}", item))
                continue
            if entity.value not in text:
                issues.append(_issue("docx_table_mismatch", f"table cell does not contain {entity.value!r}", item))
            texts.append(text)
        elif kind == "docx_header":
            if entity.value not in header_text:
                issues.append(_issue("docx_header_mismatch", f"header does not contain {entity.value!r}", item))
            texts.append(header_text)
        elif kind == "docx_footer":
            if entity.value not in footer_text:
                issues.append(_issue("docx_footer_mismatch", f"footer does not contain {entity.value!r}", item))
            texts.append(footer_text)
    return texts, issues


def _xlsx_cells(data: bytes) -> Tuple[Dict[str, Dict[str, str]], List[dict]]:
    sheets: Dict[str, Dict[str, str]] = {}
    order: List[dict] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in rels.findall(f"{REL}Relationship")}
        sheet_parent = workbook.find(f"{S}sheets")
        for sheet in (sheet_parent if sheet_parent is not None else []):
            name = sheet.get("name", "")
            rel_id = sheet.get(f"{R}id")
            target = targets.get(rel_id, "")
            path = "xl/" + target.lstrip("/") if not target.startswith("xl/") else target
            path = path.replace("xl//", "xl/")
            cells: Dict[str, str] = {}
            if path in archive.namelist():
                root = ET.fromstring(archive.read(path))
                for cell in root.iter(f"{S}c"):
                    ref = cell.get("r", "")
                    text = "".join(node.text or "" for node in cell.iter(f"{S}t"))
                    if not text:
                        value = cell.find(f"{S}v")
                        text = value.text if value is not None else ""
                    cells[ref] = text
            sheets[name] = cells
            order.append({"name": name, "hidden": sheet.get("state") == "hidden"})
    return sheets, order


def _xlsx_verify(data: bytes, rendered_locations: List[dict]) -> Tuple[List[str], List[dict]]:
    sheets, _order = _xlsx_cells(data)
    issues: List[dict] = []
    texts: List[str] = []
    for item in rendered_locations:
        loc = item["location"]
        sheet = loc.get("sheet", "")
        cell = loc.get("cell", "")
        text = sheets.get(sheet, {}).get(cell, "")
        if item["entity"].value not in text:
            issues.append(_issue("xlsx_cell_mismatch", f"{sheet}!{cell} does not contain {item['entity'].value!r}", item))
        texts.append(text)
    return texts, issues


def _pptx_slides(data: bytes) -> List[List[str]]:
    slides: List[List[str]] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ET.fromstring(archive.read("ppt/presentation.xml"))
        rels = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in rels.findall(f"{REL}Relationship")}
        for slide_id in root.iter(f"{P}sldId"):
            target = targets.get(slide_id.get(f"{R}id"), "")
            path = "ppt/" + target.lstrip("/")
            if path not in archive.namelist():
                slides.append([])
                continue
            slide_root = ET.fromstring(archive.read(path))
            shapes = []
            for shape in slide_root.iter(f"{P}sp"):
                shapes.append("".join(node.text or "" for node in shape.iter(f"{A}t")))
            slides.append(shapes)
    return slides


def _pptx_verify(data: bytes, rendered_locations: List[dict]) -> Tuple[List[str], List[dict]]:
    slides = _pptx_slides(data)
    issues: List[dict] = []
    texts: List[str] = []
    for item in rendered_locations:
        loc = item["location"]
        slide, shape = loc.get("slide", 0), loc.get("shape", 0)
        try:
            text = slides[slide - 1][shape - 1]
        except IndexError:
            issues.append(_issue("pptx_shape_out_of_range", f"slide {slide} shape {shape}", item))
            continue
        if item["entity"].value not in text:
            issues.append(_issue("pptx_shape_mismatch", f"slide {slide} shape {shape} does not contain {item['entity'].value!r}", item))
        texts.append(text)
    return texts, issues


def _pdf_text(data: bytes) -> Tuple[List[str], int, bool]:
    objects = {}
    for match in re.finditer(rb"(\d+)\s+0\s+obj\s*(.*?)\s*endobj", data, re.DOTALL):
        objects[int(match.group(1))] = match.group(2)
    page_texts: List[str] = []
    for number in sorted(objects):
        body = objects[number]
        if not re.search(rb"/Type\s*/Page\b", body) or re.search(rb"/Type\s*/Pages\b", body):
            continue
        content_match = re.search(rb"/Contents\s+(\d+)\s+0\s+R", body)
        content = objects.get(int(content_match.group(1)), b"") if content_match else b""
        texts = []
        for match in re.finditer(rb"\((?:\\.|[^\\)])*\)\s*Tj", content):
            raw = match.group(0)
            value = raw[1:raw.rfind(b")")]
            value = value.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
            texts.append(value.decode("latin-1", "replace"))
        page_texts.append(" ".join(texts))
    has_image = any(b"/Subtype /Image" in body for body in objects.values())
    return page_texts, len(page_texts), has_image


def _pdf_verify(data: bytes, rendered_locations: List[dict]) -> Tuple[List[str], List[dict]]:
    if not data.startswith(b"%PDF-"):
        return [], [_issue("pdf_magic", "missing PDF header")]
    pages, count, has_image = _pdf_text(data)
    issues: List[dict] = []
    texts: List[str] = []
    for item in rendered_locations:
        loc = item["location"]
        kind = loc.get("kind")
        page = loc.get("page", 0)
        if not (1 <= page <= count):
            issues.append(_issue("pdf_page_out_of_range", f"page {page} of {count}", item))
            continue
        if kind == "pdf_text":
            text = pages[page - 1]
            compact_text = re.sub(r"\s+", "", text)
            compact_value = re.sub(r"\s+", "", item["entity"].value)
            if compact_value not in compact_text:
                issues.append(_issue("pdf_text_mismatch", f"page {page} does not contain {item['entity'].value!r}", item))
            texts.append(text)
        elif kind == "pdf_image":
            if not has_image:
                issues.append(_issue("pdf_image_missing", "embedded image not found", item))
            texts.append(loc.get("expected_ocr_text", ""))
    return texts, issues


def _image_verify(data: bytes, ext: str, rendered_locations: List[dict]) -> Tuple[List[str], List[dict]]:
    issues: List[dict] = []
    if ext == "png":
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            return [], [_issue("png_magic", "missing PNG signature")]
        width, height = int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")
    else:
        if data[:2] != b"\xff\xd8":
            return [], [_issue("jpeg_magic", "missing JPEG SOI")]
        width = height = 0
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                height = int.from_bytes(data[index + 5:index + 7], "big")
                width = int.from_bytes(data[index + 7:index + 9], "big")
                break
            length = int.from_bytes(data[index + 2:index + 4], "big")
            index += 2 + length
    for item in rendered_locations:
        loc = item["location"]
        if loc.get("width") != width or loc.get("height") != height:
            issues.append(_issue("image_dimensions_mismatch", f"metadata {loc.get('width')}x{loc.get('height')} vs {width}x{height}", item))
        bbox = loc.get("bbox", [])
        if len(bbox) != 4 or bbox[0] < 0 or bbox[1] < 0 or bbox[0] + bbox[2] > width or bbox[1] + bbox[3] > height:
            issues.append(_issue("image_bbox_invalid", f"bbox {bbox} outside {width}x{height}", item))
        value = item["entity"].value
        line_text = loc.get("expected_ocr_text", "")
        if loc.get("entity_strategy") == "atomic_line":
            if value.upper() not in line_text.upper():
                issues.append(_issue(
                    "image_entity_fragment",
                    f"entity {value!r} is not fully present in one image line: {line_text!r}",
                    item))
            if loc.get("fragment_count") != 1 or loc.get("fragment_index") != 0:
                issues.append(_issue("image_fragment_metadata",
                                     "atomic entity must be a single fragment", item))
            if not is_ascii(value):
                issues.append(_issue("image_non_latin_entity",
                                     f"Latin-only image carries {value!r}", item))
    return [loc.get("expected_ocr_text", "") for loc in (item["location"] for item in rendered_locations)], issues


def verify_attachment(data: bytes, ext: str, mime_type: str, rendered_locations: List[dict],
                      meta: Optional[dict] = None) -> dict:
    ext = ext.lower()
    meta = meta or {}
    checks: List[str] = ["file_nonempty"]
    issues: List[dict] = []
    if not data:
        return {"status": "unverified", "checks": [], "issues": [_issue("empty_file", "file is empty")],
                "entity_count": len(rendered_locations), "extracted_entity_count": 0}
    if MIME_TYPES.get(ext) and MIME_TYPES[ext] != mime_type:
        issues.append(_issue("mime_mismatch", f"{ext} expected {MIME_TYPES[ext]}, got {mime_type}"))
    try:
        if ext in ("txt", "md", "log", "sql", "tf", "py", "js", "ts", "java", "go"):
            _, found = _text_entities(data, ext, rendered_locations)
            issues.extend(found)
            checks.append("text_decoded")
        elif ext in ("env", "ini", "conf", "toml"):
            _, found = _config_verify(data, rendered_locations, ext)
            issues.extend(found)
            checks.append("config_parsed")
        elif ext == "csv":
            _, found = _csv_verify(data, rendered_locations, meta)
            issues.extend(found)
            checks.append("csv_parsed")
        elif ext == "json":
            _, found = _json_verify(data, rendered_locations)
            issues.extend(found)
            checks.append("json_parsed")
        elif ext in ("yaml", "yml"):
            _, found = _yaml_verify(data, rendered_locations)
            issues.extend(found)
            checks.append("yaml_subset_parsed")
        elif ext == "xml":
            _, found = _xml_verify(data, rendered_locations)
            issues.extend(found)
            checks.append("xml_parsed")
        elif ext == "docx":
            _, found = _docx_verify(data, rendered_locations)
            issues.extend(found)
            checks.extend(["zip_opened", "ooxml_parsed"])
        elif ext == "xlsx":
            _, found = _xlsx_verify(data, rendered_locations)
            issues.extend(found)
            checks.extend(["zip_opened", "ooxml_parsed"])
        elif ext == "pptx":
            _, found = _pptx_verify(data, rendered_locations)
            issues.extend(found)
            checks.extend(["zip_opened", "ooxml_parsed"])
        elif ext == "pdf":
            _, found = _pdf_verify(data, rendered_locations)
            issues.extend(found)
            checks.append("pdf_parsed")
            if any(item.get("location", {}).get("kind") == "pdf_image" for item in rendered_locations):
                checks.append("ocr_layout_verified")
        elif ext in ("png", "jpg", "jpeg"):
            _, found = _image_verify(data, ext, rendered_locations)
            issues.extend(found)
            checks.append("image_decoded")
            checks.append("ocr_layout_verified")
        else:
            issues.append(_issue("unsupported_extension", ext))
    except Exception as exc:  # malformed generated file must fail loudly
        issues.append(_issue("parse_error", f"{type(exc).__name__}: {exc}"))
    entity_count = len(rendered_locations)
    extracted = entity_count - sum(1 for issue in issues if issue.get("annotation_id"))
    status = "verified" if not issues else "unverified"
    if not issues and (ext in ("png", "jpg", "jpeg")
                       or any(item.get("location", {}).get("kind") == "pdf_image" for item in rendered_locations)):
        status = "verified_layout"
    return {
        "status": status,
        "checks": checks,
        "issues": issues,
        "entity_count": entity_count,
        "extracted_entity_count": max(0, extracted),
    }


def verify_prompt_entities(case: dict) -> List[dict]:
    issues: List[dict] = []
    prompt = case.get("prompt", "")
    for annotation in case.get("entities", []):
        if annotation.get("source") != "prompt":
            continue
        start, end = annotation.get("character_start"), annotation.get("character_end")
        if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start < end <= len(prompt)):
            issues.append(_issue("prompt_span_out_of_range", "prompt span out of range", annotation))
        elif prompt[start:end] != annotation.get("exact_entity_value"):
            issues.append(_issue("prompt_span_mismatch", "prompt slice does not match value", annotation))
    return issues
