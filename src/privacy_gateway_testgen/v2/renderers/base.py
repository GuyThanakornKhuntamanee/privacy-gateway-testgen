"""Renderer contract shared by every file family."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from ...models import Entity

MIME_TYPES = {
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "json": "application/json",
    "yaml": "application/yaml",
    "yml": "application/yaml",
    "xml": "application/xml",
    "log": "text/plain",
    "env": "text/plain",
    "ini": "text/plain",
    "conf": "text/plain",
    "toml": "application/toml",
    "sql": "application/sql",
    "tf": "text/plain",
    "py": "text/x-python",
    "js": "text/javascript",
    "ts": "text/typescript",
    "java": "text/x-java-source",
    "go": "text/x-go",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}

EXTRACTION_METHODS = {
    "txt": "direct_text", "md": "direct_text", "log": "direct_text",
    "env": "direct_text", "ini": "direct_text", "conf": "direct_text",
    "toml": "direct_text", "sql": "direct_text", "tf": "direct_text",
    "py": "direct_text", "js": "direct_text", "ts": "direct_text",
    "java": "direct_text", "go": "direct_text",
    "csv": "structured_parser", "json": "structured_parser", "yaml": "structured_parser",
    "yml": "structured_parser", "xml": "structured_parser",
    "docx": "office_parser", "xlsx": "office_parser", "pptx": "office_parser",
    "pdf": "pdf_text", "png": "ocr", "jpg": "ocr", "jpeg": "ocr",
}


@dataclass
class RenderedFile:
    filename: str
    data: bytes
    mime_type: str
    renderer: str
    extraction_method: str
    entity_locations: List[dict] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


def location(entity: Entity, loc: dict, role: str = "body") -> dict:
    return {"entity": entity, "location": loc, "role": role}
