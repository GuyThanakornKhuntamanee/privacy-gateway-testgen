"""Pure-Python raster renderer for OCR-oriented synthetic images.

Text is drawn with a small bitmap font.  Lowercase letters use the uppercase
glyph (OCR-oriented screenshots are intentionally plain), and image ground truth
records the pre-render line text plus a bounding box.  PNG uses zlib; JPEG uses
a baseline grayscale encoder implemented here, so no imaging dependency is
needed.
"""

from __future__ import annotations

import math
import random
import struct
import zlib
from typing import Any, Dict, List, Sequence, Tuple

from ...models import Entity
from ..docmodel import Block, Doc
from .base import RenderedFile

FONT_5X7: Dict[str, Sequence[str]] = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000",) * 7,
    ".": ("00000", "00000", "00000", "00000", "00000", "00110", "00110"),
    ",": ("00000", "00000", "00000", "00000", "00110", "00110", "01100"),
    ":": ("00000", "00110", "00110", "00000", "00110", "00110", "00000"),
    ";": ("00000", "00110", "00110", "00000", "00110", "00110", "01100"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "\\": ("10000", "01000", "01000", "00100", "00010", "00010", "00001"),
    "@": ("01110", "10001", "10111", "10101", "10111", "10000", "01110"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "[": ("00110", "00100", "00100", "00100", "00100", "00100", "00110"),
    "]": ("01100", "00100", "00100", "00100", "00100", "00100", "01100"),
    "{": ("00010", "00100", "00100", "01000", "00100", "00100", "00010"),
    "}": ("01000", "00100", "00100", "00010", "00100", "00100", "01000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "*": ("00000", "10101", "01110", "11111", "01110", "10101", "00000"),
    "#": ("01010", "11111", "01010", "01010", "01010", "11111", "01010"),
    "%": ("11001", "11010", "00100", "00100", "01000", "01011", "10011"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "'": ("00100", "00100", "00000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "|": ("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "•": ("00000", "01110", "11111", "11111", "01110", "00000", "00000"),
}

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


class Canvas:
    def __init__(self, width: int, height: int, background: Tuple[int, int, int] = COLORS["white"]) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(background * (width * height))

    def pixel(self, x: int, y: int, color: Tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset:offset + 3] = bytes(color)

    def rect(self, x: int, y: int, width: int, height: int, color: Tuple[int, int, int]) -> None:
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width, x + width)
        y1 = min(self.height, y + height)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        for yy in range(y0, y1):
            offset = (yy * self.width + x0) * 3
            self.pixels[offset:offset + len(row)] = row

    def outline(self, x: int, y: int, width: int, height: int, color: Tuple[int, int, int], thickness: int = 1) -> None:
        self.rect(x, y, width, thickness, color)
        self.rect(x, y + height - thickness, width, thickness, color)
        self.rect(x, y, thickness, height, color)
        self.rect(x + width - thickness, y, thickness, height, color)

    def line(self, x1: int, y1: int, x2: int, y2: int, color: Tuple[int, int, int], thickness: int = 1) -> None:
        steps = max(abs(x2 - x1), abs(y2 - y1))
        for step in range(steps + 1):
            x = int(x1 + (x2 - x1) * step / max(1, steps))
            y = int(y1 + (y2 - y1) * step / max(1, steps))
            self.rect(x, y, thickness, thickness, color)

    def text_width(self, text: str, scale: int = 2) -> int:
        return len(text) * 6 * scale

    def text(self, x: int, y: int, text: str, scale: int = 2,
             color: Tuple[int, int, int] = COLORS["black"]) -> int:
        cursor = x
        for char in text.upper():
            if char != "•" and char not in FONT_5X7:
                raise ValueError(
                    f"image renderer is Latin-only; unsupported character {char!r} "
                    "must be routed to DOCX/XLSX/TXT"
                )
            glyph = FONT_5X7.get(char, FONT_5X7.get("?", FONT_5X7[" "]))
            for row_index, row in enumerate(glyph):
                for col_index, bit in enumerate(row):
                    if bit == "1":
                        self.rect(cursor + col_index * scale, y + row_index * scale, scale, scale, color)
            cursor += 6 * scale
        return cursor

    def wrap(self, text: str, max_chars: int) -> List[str]:
        words = text.split(" ")
        lines: List[str] = []
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if len(candidate) <= max_chars or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    def rotate(self, degrees: float, background: Tuple[int, int, int]) -> "Canvas":
        if abs(degrees) < 0.01:
            return self
        radians = math.radians(degrees)
        cos_a, sin_a = math.cos(radians), math.sin(radians)
        out = Canvas(self.width, self.height, background)
        cx, cy = self.width / 2, self.height / 2
        for y in range(self.height):
            for x in range(self.width):
                dx, dy = x - cx, y - cy
                sx = int(cx + dx * cos_a + dy * sin_a)
                sy = int(cy - dx * sin_a + dy * cos_a)
                if 0 <= sx < self.width and 0 <= sy < self.height:
                    src = (sy * self.width + sx) * 3
                    dst = (y * self.width + x) * 3
                    out.pixels[dst:dst + 3] = self.pixels[src:src + 3]
        return out

    def noise(self, rng: random.Random, amount: int = 18, density: float = 0.02) -> None:
        for _ in range(int(self.width * self.height * density)):
            x = rng.randrange(self.width)
            y = rng.randrange(self.height)
            offset = (y * self.width + x) * 3
            delta = rng.randint(-amount, amount)
            for channel in range(3):
                value = self.pixels[offset + channel] + delta
                self.pixels[offset + channel] = max(0, min(255, value))

    def shadow(self, strength: int = 35) -> None:
        for y in range(self.height):
            delta = int(strength * y / max(1, self.height))
            for x in range(0, self.width, 2):
                offset = (y * self.width + x) * 3
                for channel in range(3):
                    self.pixels[offset + channel] = max(0, self.pixels[offset + channel] - delta)

    def png(self, level: int = 6) -> bytes:
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            raw.extend(self.pixels[y * stride:(y + 1) * stride])
        compressed = zlib.compress(bytes(raw), level)
        def chunk(kind: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        header = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")

    def grayscale(self) -> bytes:
        result = bytearray(self.width * self.height)
        for index in range(self.width * self.height):
            offset = index * 3
            result[index] = int(0.299 * self.pixels[offset] + 0.587 * self.pixels[offset + 1] + 0.114 * self.pixels[offset + 2])
        return bytes(result)


# --------------------------------------------------------------------------
# Baseline grayscale JPEG
# --------------------------------------------------------------------------

ZIGZAG = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
          12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
          35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
          58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]
QUANT = [16, 11, 12, 14, 12, 10, 16, 14, 13, 14, 18, 17, 16, 19, 24, 40,
         26, 24, 22, 22, 24, 49, 35, 37, 29, 40, 58, 51, 61, 60, 57, 51,
         56, 55, 64, 72, 92, 78, 64, 68, 87, 69, 55, 56, 80, 109, 81, 87,
         95, 98, 103, 104, 103, 62, 77, 113, 121, 112, 100, 120, 92, 101, 103, 99]
QUANT_NATURAL = [0] * 64
for _zigzag_index, _natural_index in enumerate(ZIGZAG):
    QUANT_NATURAL[_natural_index] = QUANT[_zigzag_index]
DC_BITS = [0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
DC_VALS = list(range(12))
AC_BITS = [0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 0x7d]
AC_VALS = [
    0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
    0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xa1, 0x08,
    0x23, 0x42, 0xb1, 0xc1, 0x15, 0x52, 0xd1, 0xf0, 0x24, 0x33, 0x62, 0x72,
    0x82, 0x09, 0x0a, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x25, 0x26, 0x27, 0x28,
    0x29, 0x2a, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x43, 0x44, 0x45,
    0x46, 0x47, 0x48, 0x49, 0x4a, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5a, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6a, 0x73, 0x74, 0x75,
    0x76, 0x77, 0x78, 0x79, 0x7a, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x8a, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9a, 0xa2, 0xa3,
    0xa4, 0xa5, 0xa6, 0xa7, 0xa8, 0xa9, 0xaa, 0xb2, 0xb3, 0xb4, 0xb5, 0xb6,
    0xb7, 0xb8, 0xb9, 0xba, 0xc2, 0xc3, 0xc4, 0xc5, 0xc6, 0xc7, 0xc8, 0xc9,
    0xca, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xd8, 0xd9, 0xda, 0xe1, 0xe2,
    0xe3, 0xe4, 0xe5, 0xe6, 0xe7, 0xe8, 0xe9, 0xea, 0xf1, 0xf2, 0xf3, 0xf4,
    0xf5, 0xf6, 0xf7, 0xf8, 0xf9, 0xfa,
]


class BitWriter:
    def __init__(self) -> None:
        self.buffer = 0
        self.count = 0
        self.out = bytearray()

    def write(self, value: int, bits: int) -> None:
        for shift in range(bits - 1, -1, -1):
            self.buffer = (self.buffer << 1) | ((value >> shift) & 1)
            self.count += 1
            if self.count == 8:
                self.out.append(self.buffer & 0xFF)
                if self.buffer == 0xFF:
                    self.out.append(0)
                self.buffer = 0
                self.count = 0

    def finish(self) -> bytes:
        if self.count:
            while self.count != 8:
                self.buffer = (self.buffer << 1) | 1
                self.count += 1
            self.out.append(self.buffer & 0xFF)
            if self.buffer == 0xFF:
                self.out.append(0)
        return bytes(self.out)


def _huffman_codes(bits: Sequence[int], values: Sequence[int]) -> Dict[int, Tuple[int, int]]:
    table: Dict[int, Tuple[int, int]] = {}
    code = 0
    index = 0
    for length in range(1, 17):
        for _ in range(bits[length - 1]):
            table[values[index]] = (code, length)
            index += 1
            code += 1
        code <<= 1
    return table


def _category(value: int) -> int:
    return abs(value).bit_length()


def _amplitude(value: int, bits: int) -> int:
    if value >= 0:
        return value
    return value + (1 << bits) - 1


COS_TABLE = [[math.cos((2 * x + 1) * u * math.pi / 16) for x in range(8)] for u in range(8)]
SCALE = [[(1 / math.sqrt(8)) if u == 0 else 0.5 for u in range(8)] for _ in range(1)]


def _dct(block: List[float]) -> List[float]:
    temp = [[0.0] * 8 for _ in range(8)]
    for y in range(8):
        for u in range(8):
            total = sum(block[y * 8 + x] * COS_TABLE[u][x] for x in range(8))
            temp[y][u] = total * (1 / math.sqrt(8) if u == 0 else 0.5)
    out = [0.0] * 64
    for u in range(8):
        for v in range(8):
            total = sum(temp[y][u] * COS_TABLE[v][y] for y in range(8))
            out[v * 8 + u] = total * (1 / math.sqrt(8) if v == 0 else 0.5)
    return out


def _jpeg_gray(width: int, height: int, gray: bytes) -> bytes:
    dc_codes = _huffman_codes(DC_BITS, DC_VALS)
    ac_codes = _huffman_codes(AC_BITS, AC_VALS)
    writer = BitWriter()
    previous_dc = 0
    padded_w = (width + 7) // 8 * 8
    padded_h = (height + 7) // 8 * 8
    for block_y in range(0, padded_h, 8):
        for block_x in range(0, padded_w, 8):
            block = []
            for y in range(8):
                for x in range(8):
                    sx = min(width - 1, block_x + x)
                    sy = min(height - 1, block_y + y)
                    block.append(float(gray[sy * width + sx] - 128))
            coeffs = _dct(block)
            quantized = [int(round(coeffs[i] / QUANT_NATURAL[i])) for i in range(64)]
            dc = quantized[0]
            diff = dc - previous_dc
            previous_dc = dc
            size = _category(diff)
            code, length = dc_codes[size]
            writer.write(code, length)
            if size:
                writer.write(_amplitude(diff, size), size)
            zero_run = 0
            for index in range(1, 64):
                value = quantized[ZIGZAG[index]]
                if value == 0:
                    zero_run += 1
                    continue
                while zero_run > 15:
                    code, length = ac_codes[0xF0]
                    writer.write(code, length)
                    zero_run -= 16
                size = _category(value)
                code, length = ac_codes[(zero_run << 4) | size]
                writer.write(code, length)
                writer.write(_amplitude(value, size), size)
                zero_run = 0
            if zero_run:
                code, length = ac_codes[0x00]
                writer.write(code, length)
    image = writer.finish()
    dqt = bytes([0]) + bytes(QUANT)
    dht = (
        b"\x00" + bytes(DC_BITS) + bytes(DC_VALS)
        + b"\x10" + bytes(AC_BITS) + bytes(AC_VALS)
    )
    sof = struct.pack(">BHHB", 8, height, width, 1) + b"\x01\x11\x00"
    return (
        b"\xff\xd8"
        + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + b"\xff\xdb" + struct.pack(">H", len(dqt) + 2) + dqt
        + b"\xff\xc0" + struct.pack(">H", len(sof) + 2) + sof
        + b"\xff\xc4" + struct.pack(">H", len(dht) + 2) + dht
        + b"\xff\xda" + struct.pack(">H", 8) + b"\x01\x01\x00\x00\x3f\x00"
        + image
        + b"\xff\xd9"
    )


# --------------------------------------------------------------------------
# Document raster layout
# --------------------------------------------------------------------------


def _doc_lines(doc: Doc, max_chars: int) -> List[dict]:
    lines: List[dict] = []
    for block in doc.blocks:
        if block.kind == "heading":
            lines.append({"text": block.text, "placements": [], "kind": "heading"})
        elif block.kind in ("paragraph", "note", "bullet"):
            prefix = "- " if block.kind == "bullet" else ""
            text = prefix + block.text
            ranges = Canvas(10, 10).wrap(text, max_chars)
            cursor = 0
            for piece in ranges:
                start = text.find(piece, cursor)
                if start < 0:
                    start = cursor
                end = start + len(piece)
                placements = []
                for placement in block.placements:
                    adjusted_start = placement.start + len(prefix)
                    adjusted_end = placement.end + len(prefix)
                    if adjusted_start < end and adjusted_end > start:
                        placements.append((placement.entity, max(0, adjusted_start - start),
                                           min(len(piece), adjusted_end - start), placement.role))
                lines.append({"text": piece, "placements": placements, "kind": "body"})
                cursor = end + 1
        elif block.kind in ("code", "log"):
            for raw_line in block.text.splitlines():
                lines.append({"text": raw_line, "placements": [], "kind": "code"})
            # Placements in code are mapped by line-local offsets.
            line_starts = [0]
            for index, char in enumerate(block.text):
                if char == "\n":
                    line_starts.append(index + 1)
            for placement in block.placements:
                line_index = max(i for i, start in enumerate(line_starts) if start <= placement.start)
                line_start = line_starts[line_index]
                if line_index < len(lines):
                    lines[line_index]["placements"].append((
                        placement.entity, placement.start - line_start,
                        min(len(lines[line_index]["text"]), placement.end - line_start), placement.role
                    ))
        elif block.kind == "table":
            header = " | ".join(block.headers)
            for piece in Canvas(10, 10).wrap(header, max_chars):
                lines.append({"text": piece, "placements": [], "kind": "header"})
            for row in block.rows:
                text = " | ".join(cell.text for cell in row)
                placements = []
                column_start = 0
                for cell in row:
                    for placement in cell.placements:
                        placements.append((placement.entity, column_start + placement.start,
                                           column_start + placement.end, placement.role))
                    column_start += len(cell.text) + 3
                cursor = 0
                for piece in Canvas(10, 10).wrap(text, max_chars):
                    start = text.find(piece, cursor)
                    if start < 0:
                        start = cursor
                    end = start + len(piece)
                    clipped = []
                    for entity, item_start, item_end, role in placements:
                        if item_start < end and item_end > start:
                            clipped.append((entity, max(0, item_start - start),
                                            min(len(piece), item_end - start), role))
                    lines.append({"text": piece, "placements": clipped, "kind": "body"})
                    cursor = end + 1
    if doc.record is not None and not any(block.kind in ("code", "log", "table") for block in doc.blocks):
        def flatten(value: Any, prefix: str = "") -> List[tuple]:
            pairs: List[tuple] = []
            if isinstance(value, dict):
                for key, child in value.items():
                    pairs.extend(flatten(child, f"{prefix}.{key}" if prefix else str(key)))
            elif isinstance(value, (list, tuple)):
                pairs.append((prefix, ", ".join(item.value if isinstance(item, Entity) else str(item) for item in value), []))
            elif isinstance(value, Entity):
                pairs.append((prefix, value.value, [(value, 0, len(value.value), "body")]))
            else:
                pairs.append((prefix, str(value), []))
            return pairs
        for key, text, placements in flatten(doc.record):
            lines.append({"text": f"{key}: {text}", "placements": [
                (entity, start + len(key) + 2, end + len(key) + 2, role)
                for entity, start, end, role in placements], "kind": "body"})
    return lines


def render_raster(doc: Doc, style: str = "scan", difficulty: int = 2) -> dict:
    rng = random.Random(doc.metadata.get("image_seed", 0))
    width = int(doc.metadata.get("image_width", 760))
    scale = 3 if difficulty <= 2 else 2
    char_width = 6 * scale
    max_chars = max(20, (width - 80) // char_width)
    lines = _doc_lines(doc, max_chars)
    line_height = 7 * scale + 8
    height = max(420, 110 + line_height * len(lines) + 70)
    if style == "receipt":
        width = max(420, width // 2)
        max_chars = max(20, (width - 60) // char_width)
        lines = _doc_lines(doc, max_chars)
        height = max(300, 80 + line_height * len(lines) + 50)
    canvas = Canvas(width, height, COLORS["white"])
    text_color = COLORS["black"]
    body_scale = scale
    start_y = 36
    x = 40

    if style in ("terminal", "config", "code"):
        canvas = Canvas(width, height, COLORS["dark"])
        canvas.rect(0, 0, width, 28, (42, 46, 54))
        canvas.text(12, 7, "synthetic-terminal", 2, COLORS["gray"])
        canvas.rect(12, 7, 8, 8, COLORS["red"])
        canvas.rect(26, 7, 8, 8, (220, 170, 50))
        canvas.rect(40, 7, 8, 8, COLORS["green"])
        text_color = (210, 220, 210)
        start_y = 44
        x = 16
    elif style == "dashboard":
        canvas.rect(0, 0, width, 54, (35, 55, 90))
        canvas.text(22, 16, "Synthetic Operations Dashboard", 2, COLORS["white"])
        canvas.rect(0, 54, width, 6, (70, 120, 190))
        text_color = COLORS["black"]
        start_y = 82
        x = 30
    elif style == "chat":
        canvas = Canvas(width, height, (232, 238, 244))
        canvas.rect(0, 0, width, 42, (245, 247, 250))
        canvas.text(16, 12, "Internal Chat - Synthetic", 2, COLORS["black"])
        text_color = COLORS["black"]
        start_y = 62
        x = 24
    elif style == "email":
        canvas.rect(0, 0, width, 78, (245, 247, 250))
        canvas.text(24, 18, "Inbox - synthetic example", 2, COLORS["black"])
        canvas.line(0, 78, width, 78, COLORS["gray"])
        text_color = COLORS["black"]
        start_y = 100
        x = 30
    elif style == "form":
        canvas.text(40, 28, doc.title.upper(), 3, COLORS["black"])
        canvas.line(40, 70, width - 40, 70, COLORS["black"], 2)
        canvas.text(40, height - 34, "SYNTHETIC SAMPLE - NOT A REAL DOCUMENT", 2, COLORS["gray"])
        start_y = 94
        x = 50
    elif style == "id_card":
        canvas.rect(0, 0, width, 96, (35, 70, 120))
        canvas.text(30, 20, "SYNTHETIC ID SAMPLE", 3, COLORS["white"])
        canvas.text(30, 62, "FICTIONAL - NOT A REAL IDENTITY DOCUMENT", 2, (210, 225, 240))
        text_color = COLORS["black"]
        start_y = 126
        x = 44
        canvas.outline(16, 112, width - 32, height - 150, (35, 70, 120), 2)
    elif style == "receipt":
        canvas.text(30, 24, doc.title.upper(), 2, COLORS["black"])
        canvas.line(30, 54, width - 30, 54, COLORS["black"], 2)
        canvas.text(30, height - 28, "SYNTHETIC RECEIPT - NOT A REAL TRANSACTION", 1, COLORS["gray"])
        start_y = 72
        x = 30
    else:  # scan / document
        canvas.rect(0, 0, width, height, COLORS["white"])
        canvas.text(40, 28, doc.title.upper(), 3, COLORS["black"])
        canvas.line(40, 70, width - 40, 70, COLORS["black"], 2)
        canvas.text(40, height - 34, "SYNTHETIC SAMPLE - NOT REAL COMPANY DATA", 2, COLORS["gray"])
        start_y = 94
        x = 40

    y = start_y
    output_lines: List[dict] = []
    for line in lines:
        if y + line_height > height - 46:
            break
        kind = line["kind"]
        line_scale = body_scale if kind != "heading" else min(4, body_scale + 1)
        color = text_color
        if kind == "heading":
            color = COLORS["white"] if style in ("terminal", "config", "code") else COLORS["blue"]
        if style == "chat":
            bubble_width = min(width - 80, max(160, canvas.text_width(line["text"], line_scale) + 24))
            left = x if len(output_lines) % 2 == 0 else width - 48 - bubble_width
            canvas.rect(left - 8, y - 6, bubble_width, line_height + 2, (255, 255, 255))
            canvas.outline(left - 8, y - 6, bubble_width, line_height + 2, (210, 216, 224))
            x_draw = left
        else:
            x_draw = x
        canvas.text(x_draw, y, line["text"], line_scale, color)
        text_width = min(canvas.text_width(line["text"], line_scale), max(1, width - x_draw))
        bbox = [x_draw, y, text_width, line_height - 4]
        placements = []
        for entity, start, end, role in line["placements"]:
            left = x_draw + start * 6 * line_scale
            placements.append({
                "entity": entity, "role": role,
                "bbox": [left, y, max(1, min((end - start) * 6 * line_scale, max(1, width - left))),
                         line_height - 4],
            })
        output_lines.append({"text": line["text"], "bbox": bbox, "placements": placements})
        y += line_height

    if difficulty >= 2:
        canvas.noise(rng, amount=8 if difficulty == 2 else 20, density=0.008 if difficulty == 2 else 0.02)
    if difficulty >= 3:
        canvas = canvas.rotate(rng.uniform(-1.4, 1.4), COLORS["white"])
    if difficulty >= 4:
        canvas.shadow(30)
        canvas.noise(rng, amount=28, density=0.03)

    return {
        "canvas": canvas,
        "width": canvas.width,
        "height": canvas.height,
        "rgb": bytes(canvas.pixels),
        "lines": output_lines,
    }


def render_image(doc: Doc, ext: str, filename: str) -> RenderedFile:
    from .base import MIME_TYPES

    difficulty = int(doc.metadata.get("ocr_difficulty", 2))
    style = doc.metadata.get("image_style", "scan")
    raster = render_raster(doc, style=style, difficulty=difficulty)
    canvas: Canvas = raster["canvas"]
    if ext in ("jpg", "jpeg"):
        data = _jpeg_gray(canvas.width, canvas.height, canvas.grayscale())
        renderer = "jpeg"
    else:
        data = canvas.png(level=6)
        renderer = "png"
    locations: List[dict] = []
    for line in raster["lines"]:
        for placement in line["placements"]:
            locations.append({
                "entity": placement["entity"],
                "location": {
                    "kind": "image_ocr", "width": raster["width"], "height": raster["height"],
                    "bbox": placement["bbox"], "expected_ocr_text": line["text"],
                    "ocr_normalized": False, "case_sensitive": False,
                    "bbox_space": "pre_render", "rotation_applied": difficulty >= 3,
                },
                "role": placement["role"],
            })
    return RenderedFile(filename, data, MIME_TYPES[ext], renderer, "ocr", locations,
                        {"image_style": style, "ocr_difficulty": difficulty,
                         "width": canvas.width, "height": canvas.height,
                         "text_line_count": len(raster["lines"]),
                         "ocr_text_source": "pre_render"})
