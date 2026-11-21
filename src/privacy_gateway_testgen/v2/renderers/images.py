"""Raster renderer for OCR-oriented synthetic images.

Text is drawn with Pillow (FreeType, libraqm shaping) using the bundled Sarabun
font, so Thai, English and mixed content all render with real glyphs and correct
mark placement.  The ground truth stays ours: every line is laid out here, and
its entity boxes are measured from the rendered prefix.  PNG and JPEG come from
Pillow's encoders, and degradation is derived from the case seed, so the same
case reproduces the same bytes.
"""

from __future__ import annotations

import io
import math
import random
from typing import Any, Dict, List, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from ...models import Entity
from ..docmodel import Doc, Placement
from .base import RenderedFile, disclosure_mode
from .fonts import font_path, require_text_shaping
from .textlayout import cluster_spans, wrap_ranges

# Style themes -----------------------------------------------------------------

COLORS = {
    "black": (20, 22, 26),
    "white": (255, 255, 255),
    "gray": (120, 126, 136),
    "light": (240, 242, 245),
    "red": (190, 55, 55),
    "green": (55, 160, 100),
    "blue": (55, 95, 190),
    "dark": (24, 27, 33),
}

BODY_SIZE = 21
HEADING_SIZE = 28
CODE_SIZE = 19
MARGIN = 44
DEFAULT_WIDTH = 900
DOCUMENT_STYLES = {"scan", "document", "receipt", "form", "id_card"}

_FONT_CACHE: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    key = (weight, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(str(font_path(weight)), size)
    return _FONT_CACHE[key]


def text_width(text: str, font: ImageFont.FreeTypeFont) -> float:
    return font.getlength(text)


def _missing_glyphs(text: str, font: ImageFont.FreeTypeFont) -> List[str]:
    missing: List[str] = []
    for char in sorted(set(text)):
        if char.isspace() or char in "\u200b\u200c\u200d\ufeff":
            continue
        if font.getmask(char).getbbox() is None:
            missing.append(char)
    return missing


# Line composition -------------------------------------------------------------


def _doc_lines(doc: Doc, measure, max_width: float) -> List[dict]:
    """Flatten a document into drawable lines with cluster-safe wrapping."""

    def wrap(text: str, protected: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
        return wrap_ranges(text, measure, max_width, protected)

    lines: List[dict] = []
    for block in doc.blocks:
        if block.kind == "heading":
            lines.append({"text": block.text, "placements": [], "kind": "heading"})
        elif block.kind in ("paragraph", "note", "bullet"):
            prefix = "- " if block.kind == "bullet" else ""
            text = prefix + block.text
            placements = [type(item)(item.entity, item.start + len(prefix),
                                     item.end + len(prefix), item.role)
                          for item in block.placements]
            for start, end in wrap(text, [(p.start, p.end) for p in placements]):
                lines.append({"text": text[start:end],
                              "placements": _clipped_placements(start, end, placements),
                              "kind": "body"})
        elif block.kind in ("code", "log"):
            offset = 0
            for raw_line in block.text.splitlines():
                lines.append({"text": raw_line, "placements": [], "kind": "code",
                              "offset": offset})
                offset += len(raw_line) + 1
            line_starts = [0]
            for index, char in enumerate(block.text):
                if char == "\n":
                    line_starts.append(index + 1)
            for placement in block.placements:
                line_index = max(i for i, start in enumerate(line_starts) if start <= placement.start)
                line_start = line_starts[line_index]
                target = next((line for line in lines
                               if line["kind"] == "code" and line["offset"] == line_start), None)
                if target is None:
                    continue
                local_start = placement.start - line_start
                local_end = min(len(target["text"]), placement.end - line_start)
                if local_end > local_start:
                    target["placements"].append(
                        (placement.entity, local_start, local_end, placement.role))
        elif block.kind == "table":
            header = " | ".join(block.headers)
            for start, end in wrap(header, []):
                lines.append({"text": header[start:end], "placements": [], "kind": "header"})
            for row in block.rows:
                text = " | ".join(cell.text for cell in row)
                placements = []
                column_start = 0
                for cell in row:
                    for placement in cell.placements:
                        placements.append((placement.entity, column_start + placement.start,
                                           column_start + placement.end, placement.role))
                    column_start += len(cell.text) + 3
                for start, end in wrap(text, [(a, b) for _e, a, b, _r in placements]):
                    piece = text[start:end]
                    clipped = []
                    for entity, item_start, item_end, role in placements:
                        if item_start < end and item_end > start:
                            clipped.append((entity, max(0, item_start - start),
                                            min(end - start, item_end - start), role))
                    lines.append({"text": piece, "placements": clipped, "kind": "body"})
    if doc.record is not None and not any(block.kind in ("code", "log", "table") for block in doc.blocks):
        def flatten(value: Any, prefix: str = "") -> List[tuple]:
            pairs: List[tuple] = []
            if isinstance(value, dict):
                for key, child in value.items():
                    pairs.extend(flatten(child, f"{prefix}.{key}" if prefix else str(key)))
            elif isinstance(value, (list, tuple)):
                pairs.append((prefix, ", ".join(
                    item.value if isinstance(item, Entity) else str(item) for item in value)))
            elif isinstance(value, Entity):
                pairs.append((prefix, value.value, [(value, 0, len(value.value), "body")]))
            else:
                pairs.append((prefix, str(value), []))
            return pairs

        for key, text, placements in flatten(doc.record):
            body = f"{key}: {text}"
            shifted = [Placement(entity, start + len(key) + 2, end + len(key) + 2, role)
                       for entity, start, end, role in placements]
            for start, end in wrap(body, [(item.start, item.end) for item in shifted]):
                lines.append({"text": body[start:end],
                              "placements": _clipped_placements(start, end, shifted),
                              "kind": "body"})
    return lines


def _clipped_placements(piece_start: int, piece_end: int, placements) -> List[tuple]:
    clipped = []
    for placement in placements:
        if placement.start < piece_end and placement.end > piece_start:
            local_start = max(0, placement.start - piece_start)
            local_end = min(piece_end - piece_start, placement.end - piece_start)
            if local_start != placement.start - piece_start or local_end != placement.end - piece_start:
                raise ValueError(
                    "image entity would be split across lines; layout must keep it atomic"
                )
            clipped.append((placement.entity, local_start, local_end, placement.role))
    return clipped


# Rendering --------------------------------------------------------------------


def _line_metrics(kind: str) -> Tuple[ImageFont.FreeTypeFont, int]:
    if kind == "heading":
        font = _font("bold", HEADING_SIZE)
        return font, int(round(HEADING_SIZE * 1.55))
    if kind in ("code", "header"):
        font = _font("regular", CODE_SIZE)
        return font, int(round(CODE_SIZE * 1.6))
    font = _font("regular", BODY_SIZE)
    return font, int(round(BODY_SIZE * 1.6))


def _layout(doc: Doc, style: str) -> dict:
    width = int(doc.metadata.get("image_width", DEFAULT_WIDTH))
    if style == "receipt":
        width = max(460, width // 2)
    margin = MARGIN if style not in ("receipt",) else 28
    while True:
        measure = lambda value, _w=width: text_width(value, _font("regular", BODY_SIZE))
        lines = _doc_lines(doc, measure, width - 2 * margin)
        needed = 0
        for line in lines:
            font, _height = _line_metrics(line["kind"])
            needed = max(needed, text_width(line["text"], font))
        candidate = int(math.ceil(needed + 2 * margin))
        if candidate <= width or candidate > 4000:
            break
        width = candidate
    return {"width": width, "margin": margin, "lines": lines}


def _chrome_metrics(doc: Doc, style: str) -> dict:
    """Where content starts and how much bottom room the chrome needs."""
    if doc.metadata.get("compact"):
        if style in ("terminal", "config", "code"):
            return {"start_y": 40, "left": 18, "reserve": 12, "dark": True}
        return {"start_y": 16, "left": MARGIN // 2, "reserve": 12, "dark": False}
    start_y = {"terminal": 56, "config": 56, "code": 56, "dashboard": 98,
               "chat": 74, "email": 110, "form": 98, "id_card": 134,
               "receipt": 76}.get(style, 98)
    left = {"terminal": 22, "config": 22, "code": 22, "dashboard": 32,
            "chat": 26, "email": 32, "form": MARGIN + 8, "id_card": 46,
            "receipt": 28}.get(style, MARGIN)
    reserve = 60 if style in DOCUMENT_STYLES else 40
    return {"start_y": start_y, "left": left, "reserve": reserve,
            "dark": style in ("terminal", "config", "code")}


def _draw_chrome(canvas: Image.Image, doc: Doc, style: str, width: int,
                 metrics: dict) -> Tuple[int, int, Tuple[int, int, int]]:
    """Background, header bars and footer; returns (start_y, left_x, text_color).

    With ``disclosure == "metadata"`` (the default) nothing in the image claims
    the content is synthetic: a detector under test must not read a hint that
    could suppress a detection.  ``disclosure == "banner"`` draws the visible
    notice instead, for artifacts shared with people.
    """
    draw = ImageDraw.Draw(canvas)
    title_font = _font("bold", HEADING_SIZE)
    footer = _font("regular", max(14, CODE_SIZE - 3))
    banner = disclosure_mode(doc) == "banner"
    left = metrics["left"]
    start_y = metrics["start_y"]
    if doc.metadata.get("compact"):
        if metrics["dark"]:
            canvas.paste(COLORS["dark"], (0, 0, width, canvas.height))
            draw.rectangle([0, 0, width, 30], fill=(42, 46, 54))
            for index, color in enumerate((COLORS["red"], (220, 170, 50), COLORS["green"])):
                draw.ellipse([12 + index * 16, 10, 21 + index * 16, 19], fill=color)
            return start_y, left, (210, 220, 210)
        canvas.paste(COLORS["white"], (0, 0, width, canvas.height))
        return start_y, left, COLORS["black"]
    text_color = COLORS["black"]
    if style in ("terminal", "config", "code"):
        canvas.paste(COLORS["dark"], (0, 0, width, canvas.height))
        draw.rectangle([0, 0, width, 34], fill=(42, 46, 54))
        for index, color in enumerate((COLORS["red"], (220, 170, 50), COLORS["green"])):
            draw.ellipse([14 + index * 18, 12, 24 + index * 18, 22], fill=color)
        draw.text((76, 7), "synthetic-terminal" if banner else "terminal", font=footer,
                  fill=COLORS["gray"])
        text_color = (210, 220, 210)
    elif style == "dashboard":
        draw.rectangle([0, 0, width, 62], fill=(35, 55, 90))
        draw.text((24, 14), "Synthetic Operations Dashboard" if banner else "Operations Dashboard",
                  font=title_font, fill=COLORS["white"])
        draw.rectangle([0, 62, width, 70], fill=(70, 120, 190))
    elif style == "chat":
        canvas.paste((232, 238, 244), (0, 0, width, canvas.height))
        draw.rectangle([0, 0, width, 50], fill=(245, 247, 250))
        draw.text((18, 10), "Internal Chat - Synthetic" if banner else "Internal Chat",
                  font=_font("bold", BODY_SIZE + 2), fill=COLORS["black"])
    elif style == "email":
        draw.rectangle([0, 0, width, 88], fill=(245, 247, 250))
        draw.text((26, 16), "Inbox - synthetic example" if banner else "Inbox",
                  font=title_font, fill=COLORS["black"])
        draw.line([0, 88, width, 88], fill=COLORS["gray"], width=1)
    elif style == "form":
        draw.text((MARGIN, 30), doc.title, font=title_font, fill=COLORS["black"])
        draw.line([MARGIN, 74, width - MARGIN, 74], fill=COLORS["black"], width=2)
        if banner:
            draw.text((MARGIN, canvas.height - 34), "SYNTHETIC SAMPLE - NOT A REAL DOCUMENT",
                      font=footer, fill=COLORS["gray"])
    elif style == "id_card":
        draw.rectangle([0, 0, width, 104], fill=(35, 70, 120))
        draw.text((30, 18), "SYNTHETIC ID SAMPLE" if banner else "EMPLOYEE ID",
                  font=title_font, fill=COLORS["white"])
        draw.text((30, 62),
                  "FICTIONAL - NOT A REAL IDENTITY DOCUMENT" if banner else "Internal use only",
                  font=footer, fill=(210, 225, 240))
        draw.rectangle([16, 118, width - 16, canvas.height - 34], outline=(35, 70, 120), width=2)
    elif style == "receipt":
        draw.text((28, 22), doc.title, font=_font("bold", BODY_SIZE + 3), fill=COLORS["black"])
        draw.line([28, 56, width - 28, 56], fill=COLORS["black"], width=2)
        if banner:
            draw.text((28, canvas.height - 28), "SYNTHETIC RECEIPT - NOT A REAL TRANSACTION",
                      font=footer, fill=COLORS["gray"])
    else:
        draw.rectangle([0, 0, width, canvas.height], fill=COLORS["white"])
        draw.text((MARGIN, 30), doc.title, font=title_font, fill=COLORS["black"])
        draw.line([MARGIN, 74, width - MARGIN, 74], fill=COLORS["black"], width=2)
        if banner:
            draw.text((MARGIN, canvas.height - 34), "SYNTHETIC SAMPLE - NOT REAL COMPANY DATA",
                      font=footer, fill=COLORS["gray"])
    return start_y, left, text_color


def _degrade(image: Image.Image, rng: random.Random, difficulty: int,
             style: str) -> Tuple[Image.Image, float]:
    """Visual noise/blur/skew.  Returns the image and the applied angle."""
    if difficulty >= 2:
        amount = 5 if difficulty == 2 else 14
        noise = Image.frombytes(
            "L", (image.width, image.height),
            bytes(rng.randrange(256) for _ in range(image.width * image.height)))
        noise = noise.point(lambda value: 128 + (value - 128) * amount // 128)
        image = ImageChops.add(image, Image.merge("RGB", (noise, noise, noise)),
                               scale=1.0, offset=-128)
        if style in DOCUMENT_STYLES:
            image = image.filter(ImageFilter.GaussianBlur(0.4 if difficulty == 2 else 0.8))
    angle = 0.0
    if difficulty >= 3 and style in DOCUMENT_STYLES:
        angle = rng.uniform(-1.1, 1.1)
        radians = math.radians(angle)
        cos_a, sin_a = math.cos(radians), math.sin(radians)
        cx, cy = image.width / 2, image.height / 2
        coeffs = (cos_a, -sin_a, cx - cx * cos_a + cy * sin_a,
                  sin_a, cos_a, cy - cy * cos_a - cx * sin_a)
        image = image.transform(image.size, Image.AFFINE, coeffs,
                                resample=Image.BICUBIC, fillcolor=COLORS["white"])
    if difficulty >= 4:
        gradient = Image.new("L", (1, image.height))
        for y in range(image.height):
            gradient.putpixel((0, y), max(150, 255 - int(105 * y / max(1, image.height))))
        image = Image.composite(image, Image.new("RGB", image.size, COLORS["black"]),
                                gradient.resize(image.size))
    return image, angle


def _rotate_box(box: Sequence[float], width: int, height: int,
                angle: float) -> List[float]:
    """Map a pre-rotation box onto the rotated canvas and clip to its bounds."""
    if abs(angle) < 1e-6:
        return [round(float(value), 1) for value in box]
    radians = math.radians(angle)
    cos_a, sin_a = math.cos(radians), math.sin(radians)
    cx, cy = width / 2, height / 2
    x, y, w, h = box
    points = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    mapped = []
    for px, py in points:
        dx, dy = px - cx, py - cy
        mapped.append((cx + dx * cos_a + dy * sin_a, cy - dx * sin_a + dy * cos_a))
    left = max(0.0, min(point[0] for point in mapped))
    top = max(0.0, min(point[1] for point in mapped))
    right = min(float(width), max(point[0] for point in mapped))
    bottom = min(float(height), max(point[1] for point in mapped))
    return [round(left, 1), round(top, 1), round(max(1.0, right - left), 1),
            round(max(1.0, bottom - top), 1)]


def render_raster(doc: Doc, style: str = "scan", difficulty: int = 2) -> dict:
    shaping = require_text_shaping()
    layout = _layout(doc, style)
    width = layout["width"]
    lines = layout["lines"]
    heights = [_line_metrics(line["kind"])[1] for line in lines]
    compact = bool(doc.metadata.get("compact"))
    metrics = _chrome_metrics(doc, style)
    min_height = 180 if compact else 430
    height = max(min_height, metrics["start_y"] + sum(heights) + metrics["reserve"])
    if style == "receipt":
        height = max(320, height)

    missing: List[str] = []
    for line in lines:
        font, _ = _line_metrics(line["kind"])
        missing.extend(_missing_glyphs(line["text"], font))
    if missing:
        raise ValueError(
            f"bundled font has no glyph for {''.join(sorted(set(missing))[:8])!r}; "
            "refusing to render a replacement glyph as ground truth"
        )

    canvas = Image.new("RGB", (width, height), COLORS["white"])
    start_y, left, text_color = _draw_chrome(canvas, doc, style, width, metrics)
    draw = ImageDraw.Draw(canvas)
    output_lines: List[dict] = []
    y = start_y
    x = left
    bottom_reserve = metrics["reserve"]

    for line, line_height in zip(lines, heights):
        if y + line_height > height - bottom_reserve:
            break
        font, _ = _line_metrics(line["kind"])
        kind = line["kind"]
        color = text_color
        if kind == "heading":
            color = COLORS["white"] if style in ("terminal", "config", "code") else COLORS["blue"]
        x_draw = x
        if style == "chat" and kind != "heading":
            bubble_width = min(width - 90, max(190, int(text_width(line["text"], font)) + 30))
            x_draw = x if len(output_lines) % 2 == 0 else width - 40 - bubble_width
            draw.rectangle([x_draw - 10, y - 6, x_draw + bubble_width, y + line_height - 8],
                           fill=COLORS["white"], outline=(210, 216, 224))
        draw.text((x_draw, y), line["text"], font=font, fill=color, anchor="lt")
        line_width = text_width(line["text"], font)
        placements = []
        for entity, start, end, role in line["placements"]:
            prefix = text_width(line["text"][:start], font)
            entity_width = text_width(line["text"][start:end], font)
            placements.append({
                "entity": entity, "role": role,
                "bbox": [round(x_draw + prefix, 1), round(float(y), 1),
                         round(max(1.0, entity_width), 1), round(float(line_height - 6), 1)],
                "entity_width": round(max(1.0, entity_width), 1),
                "full_width": round(entity_width, 1),
                "line_text": line["text"],
                "fragment_index": 0,
                "fragment_count": 1,
            })
        output_lines.append({
            "text": line["text"],
            "bbox": [round(float(x_draw), 1), round(float(y), 1),
                     round(float(line_width), 1), round(float(line_height - 6), 1)],
            "placements": placements,
        })
        y += line_height

    rng = random.Random(doc.metadata.get("image_seed", 0))
    canvas, angle = _degrade(canvas, rng, difficulty, style)
    if abs(angle) >= 1e-6:
        for line in output_lines:
            line["bbox"] = _rotate_box(line["bbox"], width, height, angle)
            for placement in line["placements"]:
                placement["bbox"] = _rotate_box(placement["bbox"], width, height, angle)
                placement["entity_width"] = placement["bbox"][2]

    return {
        "image": canvas,
        "width": canvas.width,
        "height": canvas.height,
        "lines": output_lines,
        "text_shaping": shaping,
        "rotation_applied": abs(angle) >= 1e-6,
        "font": {"family": "Sarabun", "body_size": BODY_SIZE, "heading_size": HEADING_SIZE,
                 "code_size": CODE_SIZE},
    }


def image_bytes(image: Image.Image, ext: str) -> bytes:
    buffer = io.BytesIO()
    if ext in ("jpg", "jpeg"):
        image.save(buffer, format="JPEG", quality=82, optimize=False, subsampling=0)
    else:
        image.save(buffer, format="PNG", compress_level=9)
    return buffer.getvalue()


def render_image(doc: Doc, ext: str, filename: str) -> RenderedFile:
    from .base import MIME_TYPES

    difficulty = int(doc.metadata.get("ocr_difficulty", 2))
    style = doc.metadata.get("image_style", "scan")
    raster = render_raster(doc, style=style, difficulty=difficulty)
    data = image_bytes(raster["image"], ext)
    locations: List[dict] = []
    for line in raster["lines"]:
        for placement in line["placements"]:
            locations.append({
                "entity": placement["entity"],
                "location": {
                    "kind": "image_ocr", "width": raster["width"], "height": raster["height"],
                    "bbox": placement["bbox"], "expected_ocr_text": line["text"],
                    "entity_strategy": "atomic_line", "fragment_index": 0,
                    "fragment_count": 1, "entity_text_width": placement["entity_width"],
                    "ocr_normalized": False, "case_sensitive": False,
                    "bbox_space": "final", "rotation_applied": raster["rotation_applied"],
                },
                "role": placement["role"],
            })
    return RenderedFile(filename, data, MIME_TYPES[ext], "jpeg" if ext in ("jpg", "jpeg") else "png",
                        "ocr", locations,
                        {"image_style": style, "ocr_difficulty": difficulty,
                         "width": raster["width"], "height": raster["height"],
                         "text_line_count": len(raster["lines"]),
                         "entity_ground_truth": "atomic_entity_no_line_break",
                         "ocr_text_source": "pre_render",
                         "text_shaping": raster["text_shaping"],
                         "rotation_applied": raster["rotation_applied"],
                         "font": raster["font"]})


__all__ = ["render_raster", "render_image", "image_bytes", "text_width", "cluster_spans"]
