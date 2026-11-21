"""Deterministic PDF 1.4 writer backed by ReportLab.

Native pages embed the bundled Sarabun TrueType font (Thai + Latin + Thai
digits), so Thai, English and mixed content are real PDF text with a ToUnicode
map: the page can be re-opened and its text extracted exactly.  Scanned pages
embed a raster produced by the Pillow renderer, and hybrid pages mix native
paragraphs with an embedded image region.  No JavaScript, remote content,
launch action or embedded file is emitted.

ReportLab runs in invariant mode (fixed document ID and creation date), so the
same document produces the same bytes for a pinned dependency version.
"""

from __future__ import annotations

import io
from typing import List, Optional, Sequence, Tuple

from reportlab.lib.colors import Color
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas

from ..docmodel import Block, Doc
from .base import EXTRACTION_METHODS, MIME_TYPES, RenderedFile
from .fonts import FONT_FAMILY, font_path
from .textlayout import wrap_ranges

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 48
TEXT_WIDTH = PAGE_WIDTH - 2 * MARGIN

FONT = FONT_FAMILY
FONT_BOLD = f"{FONT_FAMILY}-Bold"
FONT_MONO = "Courier"


def _register_fonts() -> None:
    registered = set(pdfmetrics.getRegisteredFontNames())
    if FONT not in registered:
        pdfmetrics.registerFont(TTFont(FONT, str(font_path("regular"))))
    if FONT_BOLD not in registered:
        pdfmetrics.registerFont(TTFont(FONT_BOLD, str(font_path("bold"))))


def _is_ascii(text: str) -> bool:
    return all(ord(char) < 128 for char in text)


def line_width(text: str, font: str, size: float) -> float:
    return stringWidth(text, font, size)


class PdfWriter:
    def __init__(self, title: str, author: str = "Privacy Gateway Testgen") -> None:
        _register_fonts()
        self.buffer = io.BytesIO()
        self.canvas = pdfcanvas.Canvas(self.buffer, pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
                                       invariant=1, pageCompression=1)
        self.canvas.setTitle(title)
        self.canvas.setAuthor(author)
        self.canvas.setSubject("internal document")
        self.canvas.setCreator("privacy-gateway-testgen")
        self.canvas.setProducer("privacy-gateway-testgen")
        self.pages = 1
        self.y = MARGIN  # distance from the page top to the next line box
        self.lines: List[str] = []
        self.text_shaping: Optional[str] = None

    # -- geometry ---------------------------------------------------------
    def new_page(self) -> None:
        self.canvas.showPage()
        self.pages += 1
        self.y = MARGIN

    def ensure(self, height: float) -> None:
        if self.y + height > PAGE_HEIGHT - MARGIN:
            self.new_page()

    def text(self, x: float, y: float, text: str, size: float = 10,
             font: str = FONT, color: Tuple[float, float, float] = (0.08, 0.1, 0.14)) -> None:
        if not text:
            return
        self.canvas.setFont(font, size)
        self.canvas.setFillColor(Color(*color))
        self.canvas.drawString(x, PAGE_HEIGHT - y - size, text)
        self.lines.append(text)

    def line(self, x1: float, y1: float, x2: float, y2: float,
             width: float = 0.5, color: Tuple[float, float, float] = (0.7, 0.72, 0.75)) -> None:
        self.canvas.setStrokeColor(Color(*color))
        self.canvas.setLineWidth(width)
        self.canvas.line(x1, PAGE_HEIGHT - y1, x2, PAGE_HEIGHT - y2)

    def rect(self, x: float, y: float, width: float, height: float,
             fill: Optional[Tuple[float, float, float]] = None,
             stroke: Optional[Tuple[float, float, float]] = None) -> None:
        if fill:
            self.canvas.setFillColor(Color(*fill))
            self.canvas.rect(x, PAGE_HEIGHT - y - height, width, height, stroke=0, fill=1)
        if stroke:
            self.canvas.setStrokeColor(Color(*stroke))
            self.canvas.rect(x, PAGE_HEIGHT - y - height, width, height, stroke=1, fill=0)

    # -- text blocks ------------------------------------------------------
    def draw_paragraph(self, text: str, placements: Sequence, size: float = 10,
                       leading: float = 14, font: str = FONT, x: float = MARGIN,
                       locations: Optional[List[dict]] = None,
                       max_width: float = TEXT_WIDTH) -> None:
        measure = lambda value: line_width(value, font, size)
        for start, end in wrap_ranges(text, measure, max_width,
                                      [(item.start, item.end) for item in placements]):
            piece = text[start:end]
            self.ensure(leading)
            top = self.y
            self.text(x, top, piece, size, font)
            if locations is not None:
                for placement in placements:
                    if placement.start < end and placement.end > start:
                        prefix = measure(piece[:max(0, placement.start - start)])
                        value_width = measure(piece[max(0, placement.start - start):
                                                    min(len(piece), placement.end - start)])
                        locations.append({
                            "entity": placement.entity,
                            "location": {
                                "kind": "pdf_text", "page": self.pages,
                                "source_type": "native_text",
                                "x": round(x + prefix, 2), "y": round(top, 2),
                                "width": round(max(1.0, value_width), 2),
                                "height": round(leading, 2),
                                "character_start": placement.start,
                                "character_end": placement.end,
                            },
                            "role": placement.role,
                        })
            self.y += leading
        self.y += 4

    def draw_table(self, block: Block, locations: List[dict], size: float = 8.5) -> None:
        columns = max(1, len(block.headers))
        available = PAGE_WIDTH - 2 * MARGIN
        col_width = available / columns
        leading = size + 3
        all_rows = [list(block.headers)] + [[cell.text for cell in row] for row in block.rows]
        for row_index, row in enumerate(all_rows):
            font = FONT_BOLD if row_index == 0 else FONT
            measure = lambda value, _font=font: line_width(value, _font, size)
            wrapped = [wrap_ranges(str(value), measure, col_width - 4) for value in row]
            height = max(len(lines) for lines in wrapped) * leading + 4
            self.ensure(height)
            top = self.y
            for column_index, lines in enumerate(wrapped):
                x = MARGIN + column_index * col_width
                for line_index, (start, end) in enumerate(lines):
                    self.text(x + 2, top + 2 + line_index * leading,
                              str(row[column_index])[start:end], size, font)
                if row_index > 0 and column_index < len(row):
                    cell = block.rows[row_index - 1][column_index]
                    for placement in cell.placements:
                        prefix = measure(str(row[column_index])[:placement.start])
                        value_width = measure(
                            str(row[column_index])[placement.start:placement.end])
                        locations.append({
                            "entity": placement.entity,
                            "location": {
                                "kind": "pdf_text", "page": self.pages,
                                "source_type": "native_text",
                                "x": round(x + 2 + prefix, 2), "y": round(top + 2, 2),
                                "width": round(max(1.0, value_width), 2),
                                "height": round(height, 2),
                                "character_start": placement.start,
                                "character_end": placement.end,
                            },
                            "role": placement.role,
                        })
            self.line(MARGIN, top + height, PAGE_WIDTH - MARGIN, top + height)
            self.y += height

    def draw_code(self, block: Block, locations: List[dict]) -> None:
        size, leading = 8.0, 10.0
        line_starts = [0]
        for index, char in enumerate(block.text):
            if char == "\n":
                line_starts.append(index + 1)
        for number, raw in enumerate(block.text.splitlines()):
            font = FONT_MONO if _is_ascii(raw) else FONT
            self.ensure(leading)
            top = self.y
            self.text(MARGIN, top, raw, size, font)
            line_start = line_starts[number] if number < len(line_starts) else 0
            for placement in block.placements:
                if not (line_start <= placement.start <= line_start + len(raw)):
                    continue
                local_start = max(0, placement.start - line_start)
                local_end = min(len(raw), placement.end - line_start)
                if local_end <= local_start:
                    continue
                prefix = line_width(raw[:local_start], font, size)
                value_width = line_width(raw[local_start:local_end], font, size)
                locations.append({
                    "entity": placement.entity,
                    "location": {
                        "kind": "pdf_text", "page": self.pages,
                        "source_type": "native_text",
                        "x": round(MARGIN + prefix, 2), "y": round(top, 2),
                        "width": round(max(1.0, value_width), 2), "height": leading,
                        "character_start": placement.start,
                        "character_end": placement.end,
                    },
                    "role": placement.role,
                })
            self.y += leading
        self.y += 6

    def draw_raster_block(self, blocks: Sequence[Block], doc: Doc, locations: List[dict]) -> None:
        """Embed a run of blocks as a raster region inside a native page (hybrid PDF)."""
        from .images import image_bytes, render_raster

        mini = Doc(archetype=f"{doc.archetype}_screenshot", title=doc.title,
                   filename="panel.png", blocks=list(blocks), language=doc.language,
                   metadata={"image_style": doc.metadata.get("hybrid_style", "terminal"),
                             "ocr_difficulty": int(doc.metadata.get("hybrid_difficulty", 1)),
                             "image_seed": doc.metadata.get("image_seed", 0),
                             "image_width": int(doc.metadata.get("hybrid_width", 820)),
                             "compact": True})
        raster = render_raster(mini, style=mini.metadata["image_style"],
                               difficulty=mini.metadata["ocr_difficulty"])
        self.text_shaping = raster["text_shaping"]
        scale = min(1.0, PAGE_WIDTH / raster["width"])
        draw_width = raster["width"] * scale
        draw_height = raster["height"] * scale
        self.ensure(draw_height + 10)
        x = MARGIN
        top = self.y
        self.canvas.setStrokeColor(Color(0.75, 0.77, 0.8))
        self.canvas.setLineWidth(0.5)
        self.canvas.rect(x - 2, PAGE_HEIGHT - top - draw_height - 2,
                         draw_width + 4, draw_height + 4, stroke=1, fill=0)
        image = ImageReader(io.BytesIO(image_bytes(raster["image"], "png")))
        self.canvas.drawImage(image, x, PAGE_HEIGHT - top - draw_height,
                              width=draw_width, height=draw_height, mask=None)
        for line in raster["lines"]:
            for placement in line["placements"]:
                box = placement["bbox"]
                locations.append({
                    "entity": placement["entity"],
                    "location": {
                        "kind": "pdf_image", "page": self.pages,
                        "source_type": "embedded_image",
                        "bbox": box, "expected_ocr_text": line["text"],
                        "width": raster["width"], "height": raster["height"],
                        "page_bbox": [round(x + box[0] * scale, 2),
                                      round(top + box[1] * scale, 2),
                                      round(box[2] * scale, 2), round(box[3] * scale, 2)],
                        "ocr_normalized": False, "bbox_space": "image_pixels",
                        "rotation_applied": False,
                    },
                    "role": placement["role"],
                })
        self.y = top + draw_height + 10

    # -- output -----------------------------------------------------------
    def to_bytes(self) -> bytes:
        self.canvas.showPage()
        self.canvas.save()
        return self.buffer.getvalue()


def _draw_block(writer: PdfWriter, block: Block, locations: List[dict]) -> None:
    if block.kind == "heading":
        writer.ensure(30)
        writer.text(MARGIN, writer.y, block.text, 13, FONT_BOLD)
        writer.y += 20
    elif block.kind in ("paragraph", "note"):
        writer.draw_paragraph(block.text, block.placements, locations=locations)
    elif block.kind == "bullet":
        writer.draw_paragraph("- " + block.text, [
            type(item)(item.entity, item.start + 2, item.end + 2, item.role)
            for item in block.placements
        ], locations=locations)
    elif block.kind in ("code", "log"):
        writer.draw_code(block, locations)
    elif block.kind == "table":
        writer.draw_table(block, locations)


def _render_document(doc: Doc, filename: str) -> RenderedFile:
    writer = PdfWriter(doc.title)
    locations: List[dict] = []
    hybrid_index = doc.metadata.get("hybrid_block")
    hybrid_span = int(doc.metadata.get("hybrid_span", 1))
    writer.text(MARGIN, writer.y, doc.title, 18, FONT_BOLD, (0.1, 0.12, 0.18))
    writer.y += 30
    index = 0
    while index < len(doc.blocks):
        block = doc.blocks[index]
        if hybrid_index is not None and index == hybrid_index:
            writer.draw_raster_block(doc.blocks[index:index + hybrid_span], doc, locations)
            index += hybrid_span
            continue
        index += 1
        _draw_block(writer, block, locations)
    if not doc.blocks:
        # A slide archetype rendered as PDF: one page per slide, so the content
        # is real PDF text instead of a title-only page.
        for number, slide in enumerate(doc.slides, start=1):
            if number > 1:
                writer.new_page()
            writer.text(MARGIN, writer.y, slide.title, 18, FONT_BOLD, (0.1, 0.12, 0.18))
            writer.y += 30
            for block in slide.blocks:
                _draw_block(writer, block, locations)
    mode = "hybrid" if hybrid_index is not None else "native"
    metadata = {"pages": writer.pages, "mode": mode,
                "font": {"family": FONT_FAMILY, "embedded": True,
                         "weights": ["regular", "bold"]},
                "text_source": "native_text",
                "canonical_lines": writer.lines}
    if writer.text_shaping:
        metadata["text_shaping"] = writer.text_shaping
    return RenderedFile(filename, writer.to_bytes(), MIME_TYPES["pdf"], "pdf_native",
                        EXTRACTION_METHODS["pdf"], locations, metadata)


def _render_scanned(doc: Doc, filename: str) -> RenderedFile:
    from .images import image_bytes, render_raster

    style = doc.metadata.get("image_style", "scan")
    difficulty = int(doc.metadata.get("ocr_difficulty", 2))
    raster = render_raster(doc, style=style, difficulty=difficulty)
    writer = PdfWriter(doc.title)
    writer.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=(1.0, 1.0, 1.0))
    image = ImageReader(io.BytesIO(image_bytes(raster["image"], "png")))
    writer.canvas.drawImage(image, 0, 0, width=PAGE_WIDTH, height=PAGE_HEIGHT, mask=None)
    scale_x = PAGE_WIDTH / raster["width"]
    scale_y = PAGE_HEIGHT / raster["height"]
    locations: List[dict] = []
    for line in raster["lines"]:
        for placement in line["placements"]:
            box = placement["bbox"]
            locations.append({
                "entity": placement["entity"],
                "location": {
                    "kind": "pdf_image", "page": 1, "source_type": "scanned_page",
                    "bbox": box, "expected_ocr_text": line["text"],
                    "width": raster["width"], "height": raster["height"],
                    "page_bbox": [round(box[0] * scale_x, 2), round(box[1] * scale_y, 2),
                                  round(box[2] * scale_x, 2), round(box[3] * scale_y, 2)],
                    "ocr_normalized": False, "bbox_space": "image_pixels",
                    "rotation_applied": raster["rotation_applied"],
                },
                "role": placement["role"],
            })
    return RenderedFile(filename, writer.to_bytes(), MIME_TYPES["pdf"], "pdf_scanned",
                        "ocr", locations,
                        {"pages": 1, "mode": "scanned",
                         "image_width": raster["width"], "image_height": raster["height"],
                         "ocr_difficulty": difficulty,
                         "text_shaping": raster["text_shaping"],
                         "ocr_text_source": "pre_render",
                         "text_source": "raster_page"})


def render_pdf(doc: Doc, filename: str) -> RenderedFile:
    if doc.scan or doc.metadata.get("mode") == "scanned":
        return _render_scanned(doc, filename)
    return _render_document(doc, filename)
