"""A small deterministic PDF 1.4 writer.

Native pages use built-in Helvetica/Courier fonts (WinAnsi).  Scanned pages
embed an RGB image produced by the pure-Python raster renderer.  No JavaScript,
remote content or executable action is emitted.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from ..docmodel import Block, Doc
from .base import EXTRACTION_METHODS, MIME_TYPES, RenderedFile

PAGE_WIDTH = 595
PAGE_HEIGHT = 842
MARGIN = 48
TEXT_WIDTH = 640  # A4 minus margins, in points
FONT = "F1"
FONT_BOLD = "F2"
FONT_MONO = "F3"
FIXED_DATE = "D:20260101000000Z"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _latin(text: str) -> str:
    # Built-in fonts are WinAnsi.  PDF documents are generated with English
    # content; refusing non-Latin text prevents a silent "?" replacement from
    # ever becoming ground truth.  Thai PDF is routed to DOCX/XLSX/TXT.
    unsupported = sorted({ch for ch in text if ord(ch) > 126 or ord(ch) < 32})
    if unsupported:
        raise ValueError(
            "PDF renderer is Latin-only; unsupported characters "
            f"{''.join(unsupported[:8])!r} must be routed to DOCX/XLSX/TXT"
        )
    return text


def _wrap(text: str, max_chars: int) -> List[Tuple[int, int]]:
    ranges: List[Tuple[int, int]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space > start + 20:
                end = space
        ranges.append((start, end))
        start = end
        while start < len(text) and text[start] == " ":
            start += 1
    return ranges or [(0, 0)]


@dataclass
class PdfPage:
    content: List[str] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)
    images: List[int] = field(default_factory=list)


class PdfWriter:
    def __init__(self, title: str, author: str = "Privacy Gateway Testgen") -> None:
        self.title = _latin(title)
        self.author = _latin(author)
        self.pages: List[PdfPage] = []
        self.page = PdfPage()
        self.pages.append(self.page)
        self.y = PAGE_HEIGHT - MARGIN

    def new_page(self) -> None:
        self.page = PdfPage()
        self.pages.append(self.page)
        self.y = PAGE_HEIGHT - MARGIN

    def ensure(self, height: float) -> None:
        if self.y - height < MARGIN:
            self.new_page()

    def text(self, x: float, y: float, text: str, size: float = 10,
             font: str = FONT, color: Tuple[float, float, float] = (0.08, 0.1, 0.14)) -> None:
        text = _latin(text)
        r, g, b = color
        self.page.content.append(
            f"BT /{font} {size:.2f} Tf {r:.3f} {g:.3f} {b:.3f} rg "
            f"1 0 0 1 {x:.2f} {PAGE_HEIGHT - y:.2f} Tm ({_escape(text)}) Tj ET"
        )

    def line(self, x1: float, y1: float, x2: float, y2: float,
             width: float = 0.5, color: Tuple[float, float, float] = (0.7, 0.72, 0.75)) -> None:
        r, g, b = color
        self.page.content.append(
            f"{r:.3f} {g:.3f} {b:.3f} RG {width:.2f} w {x1:.2f} {PAGE_HEIGHT - y1:.2f} m "
            f"{x2:.2f} {PAGE_HEIGHT - y2:.2f} l S"
        )

    def rect(self, x: float, y: float, width: float, height: float,
             fill: Optional[Tuple[float, float, float]] = None,
             stroke: Optional[Tuple[float, float, float]] = None) -> None:
        if fill:
            r, g, b = fill
            self.page.content.append(f"{r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {PAGE_HEIGHT - y - height:.2f} {width:.2f} {height:.2f} re f")
        if stroke:
            r, g, b = stroke
            self.page.content.append(f"{r:.3f} {g:.3f} {b:.3f} RG {x:.2f} {PAGE_HEIGHT - y - height:.2f} {width:.2f} {height:.2f} re S")

    def draw_paragraph(self, text: str, placements: Sequence, size: float = 10,
                       leading: float = 14, font: str = FONT, x: float = MARGIN,
                       max_chars: int = 92, locations: Optional[List[dict]] = None) -> None:
        line_ranges = _wrap(text, max_chars)
        for start, end in line_ranges:
            self.ensure(leading)
            top = self.y
            self.text(x, top, text[start:end], size, font)
            if locations is not None:
                for placement in placements:
                    if placement.start < end and placement.end > start:
                        locations.append({
                            "entity": placement.entity,
                            "location": {
                                "kind": "pdf_text", "page": len(self.pages),
                                "x": round(x, 2), "y": round(top, 2),
                                "width": round(min(TEXT_WIDTH, (end - start) * size * 0.55), 2),
                                "height": round(leading, 2),
                                "character_start": placement.start,
                                "character_end": placement.end,
                            },
                            "role": placement.role,
                        })
            self.y -= leading
        self.y -= 4

    def draw_table(self, block: Block, locations: List[dict], size: float = 8.5) -> None:
        columns = max(1, len(block.headers))
        available = PAGE_WIDTH - 2 * MARGIN
        col_width = available / columns
        max_chars = max(8, int(col_width / (size * 0.52)))
        all_rows = [list(block.headers)] + [[cell.text for cell in row] for row in block.rows]
        for row_index, row in enumerate(all_rows):
            wrapped = [_wrap(str(value), max_chars) for value in row]
            height = max(len(lines) for lines in wrapped) * (size + 3) + 4
            self.ensure(height)
            top = self.y
            for column_index, lines in enumerate(wrapped):
                x = MARGIN + column_index * col_width
                for line_index, (start, end) in enumerate(lines):
                    value = str(row[column_index])[start:end]
                    self.text(x + 2, top + 2 + line_index * (size + 3), value, size,
                              FONT_BOLD if row_index == 0 else FONT)
                if row_index > 0 and column_index < len(block.rows[0]) if block.rows else False:
                    cell = block.rows[row_index - 1][column_index]
                    for placement in cell.placements:
                        locations.append({
                            "entity": placement.entity,
                            "location": {
                                "kind": "pdf_text", "page": len(self.pages),
                                "x": round(x + 2, 2), "y": round(top + 2, 2),
                                "width": round(col_width, 2), "height": round(height, 2),
                                "character_start": placement.start,
                                "character_end": placement.end,
                            },
                            "role": placement.role,
                        })
            self.line(MARGIN, top + height, PAGE_WIDTH - MARGIN, top + height)
            self.y -= height

    def to_bytes(self) -> bytes:
        objects: List[str] = []

        def add(value: str) -> int:
            objects.append(value)
            return len(objects)

        font_regular = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        font_bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        font_mono = add("<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")

        page_numbers: List[int] = []
        for page in self.pages:
            content = "\n".join(page.content).encode("latin-1", "replace")
            content_number = add(
                f"<< /Length {len(content)} >>\nstream\n" + content.decode("latin-1") + "\nendstream"
            )
            xobjects = ""
            if page.images:
                refs = " ".join(f"/Im{index + 1} {image_number} 0 R" for index, image_number in enumerate(page.images))
                xobjects = f" /XObject << {refs} >>"
            page_number = add(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R /F3 {font_mono} 0 R >>{xobjects} >> "
                f"/Contents {content_number} 0 R >>"
            )
            page_numbers.append(page_number)
        pages_number = add(
            f"<< /Type /Pages /Kids [{' '.join(f'{number} 0 R' for number in page_numbers)}] /Count {len(page_numbers)} >>"
        )
        catalog_number = add(f"<< /Type /Catalog /Pages {pages_number} 0 R >>")
        info_number = add(
            f"<< /Title ({_escape(self.title)}) /Author ({_escape(self.author)}) "
            f"/Producer (privacy-gateway-testgen) /CreationDate ({FIXED_DATE}) /ModDate ({FIXED_DATE}) >>"
        )

        header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        output = bytearray(header)
        offsets = [0]
        for number, value in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{number} 0 obj\n{value}\nendobj\n".encode("latin-1", "replace"))
        xref_offset = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_number} 0 R /Info {info_number} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return bytes(output)

    def embed_image(self, width: int, height: int, rgb: bytes) -> int:
        compressed = zlib.compress(rgb, 6)
        # Image objects are inserted after pages; record a placeholder number and
        # resolve it when the page object is written.
        image_number = 10000 + len(self.page.images)
        self.page.images.append(image_number)
        self._pending_images = getattr(self, "_pending_images", {})
        self._pending_images[image_number] = (width, height, compressed)
        return image_number

    def to_bytes_with_images(self) -> bytes:
        pending = getattr(self, "_pending_images", {})
        # Rebuild objects manually to keep image object numbers stable.
        objects: List[str] = []

        def add(value: str) -> int:
            objects.append(value)
            return len(objects)

        font_regular = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        font_bold = add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        font_mono = add("<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
        image_refs = {}
        for image_number, (width, height, compressed) in sorted(pending.items()):
            image_refs[image_number] = add(
                f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode /Length {len(compressed)} >>\n"
                f"stream\n{compressed.decode('latin-1')}\nendstream"
            )
        page_numbers = []
        for page in self.pages:
            content = "\n".join(page.content).encode("latin-1", "replace")
            content_number = add(f"<< /Length {len(content)} >>\nstream\n" + content.decode("latin-1") + "\nendstream")
            xobjects = ""
            if page.images:
                refs = " ".join(f"/Im{index + 1} {image_refs[number]} 0 R" for index, number in enumerate(page.images))
                xobjects = f" /XObject << {refs} >>"
            page_numbers.append(add(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R /F3 {font_mono} 0 R >>{xobjects} >> "
                f"/Contents {content_number} 0 R >>"
            ))
        pages_number = add(f"<< /Type /Pages /Kids [{' '.join(f'{n} 0 R' for n in page_numbers)}] /Count {len(page_numbers)} >>")
        catalog_number = add(f"<< /Type /Catalog /Pages {pages_number} 0 R >>")
        info_number = add(
            f"<< /Title ({_escape(self.title)}) /Author ({_escape(self.author)}) "
            f"/Producer (privacy-gateway-testgen) /CreationDate ({FIXED_DATE}) /ModDate ({FIXED_DATE}) >>"
        )
        header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        output = bytearray(header)
        offsets = [0]
        for number, value in enumerate(objects, start=1):
            offsets.append(len(output))
            output.extend(f"{number} 0 obj\n{value}\nendobj\n".encode("latin-1", "replace"))
        xref_offset = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        output.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_number} 0 R /Info {info_number} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return bytes(output)


def _render_document(doc: Doc, filename: str) -> RenderedFile:
    writer = PdfWriter(doc.title)
    locations: List[dict] = []
    writer.text(MARGIN, writer.y, doc.title, 18, FONT_BOLD, (0.1, 0.12, 0.18))
    writer.y -= 26
    for block in doc.blocks:
        if block.kind == "heading":
            writer.ensure(30)
            writer.text(MARGIN, writer.y, block.text, 13, FONT_BOLD)
            writer.y -= 20
        elif block.kind in ("paragraph", "note"):
            writer.draw_paragraph(block.text, block.placements, locations=locations)
        elif block.kind == "bullet":
            writer.draw_paragraph("- " + block.text, [
                type(p)(p.entity, p.start + 2, p.end + 2, p.role) for p in block.placements
            ], locations=locations)
        elif block.kind in ("code", "log"):
            for line in block.text.splitlines():
                writer.ensure(10)
                writer.text(MARGIN, writer.y, line, 8, FONT_MONO)
                writer.y -= 10
            writer.y -= 6
            # Code placements: record the enclosing line box.
            line_starts = [0]
            for index, char in enumerate(block.text):
                if char == "\n":
                    line_starts.append(index + 1)
            for placement in block.placements:
                line_index = max(i for i, start in enumerate(line_starts) if start <= placement.start)
                locations.append({
                    "entity": placement.entity,
                    "location": {
                        "kind": "pdf_text", "page": len(writer.pages),
                        "x": MARGIN, "y": max(MARGIN, writer.y + (len(line_starts) - 1 - line_index) * 10),
                        "width": max(20.0, (placement.end - placement.start) * 5.0), "height": 10.0,
                        "character_start": placement.start, "character_end": placement.end,
                    },
                    "role": placement.role,
                })
        elif block.kind == "table":
            writer.draw_table(block, locations)
    return RenderedFile(filename, writer.to_bytes(), MIME_TYPES["pdf"], "pdf_native",
                        EXTRACTION_METHODS["pdf"], locations,
                        {"pages": len(writer.pages), "mode": "native", "latin_only": True})


def _render_scanned(doc: Doc, filename: str) -> RenderedFile:
    from .images import render_raster

    raster = render_raster(doc, style=doc.metadata.get("image_style", "scan"),
                           difficulty=int(doc.metadata.get("ocr_difficulty", 2)))
    writer = PdfWriter(doc.title)
    writer.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=(1.0, 1.0, 1.0))
    image_number = writer.embed_image(raster["width"], raster["height"], raster["rgb"])
    writer.page.content.append(
        f"q {PAGE_WIDTH} 0 0 {PAGE_HEIGHT} 0 0 cm /Im1 Do Q"
    )
    locations: List[dict] = []
    for line in raster["lines"]:
        for placement in line["placements"]:
            locations.append({
                "entity": placement["entity"],
                "location": {
                    "kind": "pdf_image", "page": 1, "source_type": "embedded_image",
                    "bbox": placement["bbox"], "expected_ocr_text": line["text"],
                    "width": raster["width"], "height": raster["height"],
                    "ocr_normalized": False, "bbox_space": "pre_render",
                    "rotation_applied": int(doc.metadata.get("ocr_difficulty", 2)) >= 3,
                },
                "role": placement["role"],
            })
    data = writer.to_bytes_with_images()
    return RenderedFile(filename, data, MIME_TYPES["pdf"], "pdf_scanned",
                        "ocr", locations,
                        {"pages": 1, "mode": "scanned", "image_width": raster["width"],
                         "image_height": raster["height"], "ocr_difficulty": doc.metadata.get("ocr_difficulty", 2),
                         "ocr_text_source": "pre_render"})


def render_pdf(doc: Doc, filename: str) -> RenderedFile:
    if doc.scan or doc.metadata.get("mode") == "scanned":
        return _render_scanned(doc, filename)
    return _render_document(doc, filename)
