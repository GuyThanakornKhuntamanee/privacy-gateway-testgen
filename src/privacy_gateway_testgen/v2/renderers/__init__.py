"""Renderer dispatch by file extension."""

from __future__ import annotations

from ..docmodel import Doc
from .base import EXTRACTION_METHODS, MIME_TYPES, RenderedFile
from .images import render_image
from .ooxml import render_ooxml
from .pdf import render_pdf
from .textfmt import render_text

TEXT_FORMATS = {
    "txt", "md", "csv", "json", "yaml", "yml", "xml", "log", "env", "ini",
    "conf", "toml", "sql", "tf", "py", "js", "ts", "java", "go",
}
OOXML_FORMATS = {"docx", "xlsx", "pptx"}
IMAGE_FORMATS = {"png", "jpg", "jpeg"}

SUPPORTED_FORMATS = tuple(sorted(TEXT_FORMATS | OOXML_FORMATS | IMAGE_FORMATS | {"pdf"}))


def render(doc: Doc, ext: str, filename: str) -> RenderedFile:
    ext = ext.lower().lstrip(".")
    if ext in TEXT_FORMATS:
        return render_text(doc, ext, filename)
    if ext in OOXML_FORMATS:
        return render_ooxml(doc, ext, filename)
    if ext == "pdf":
        return render_pdf(doc, filename)
    if ext in IMAGE_FORMATS:
        return render_image(doc, ext, filename)
    raise ValueError(f"unsupported file type: {ext}")
