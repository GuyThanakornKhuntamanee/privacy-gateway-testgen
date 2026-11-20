"""Script-aware line breaking shared by the PDF and raster renderers.

Two rules matter for a Thai-first gateway's test assets:

* a Thai cluster (base character plus its combining marks) is one visual unit,
  so a break inside it would change what a reader — and an OCR engine — sees;
* an entity value is ground truth, so a line break inside it is only allowed
  when the annotation model supports fragments, which v2.2 does not.

Both rules are enforced here, and wrapping is measured in rendered width rather
than in characters, because Thai and Latin glyphs have different advances.
"""

from __future__ import annotations

import re
from typing import Callable, List, Sequence, Tuple

# Thai combining marks, plus Arabic/Hebrew-style combining ranges and the
# zero-width joiners that bind a sequence into one visual unit.
_COMBINING_RANGES: Tuple[Tuple[int, int], ...] = (
    (0x0300, 0x036F),  # combining diacritical marks
    (0x0483, 0x0489),  # Cyrillic combining
    (0x0591, 0x05BD), (0x0610, 0x061A),  # Hebrew / Arabic marks
    (0x064B, 0x065F),
    (0x0E31, 0x0E31),  # Thai MAI HAN-AKAT
    (0x0E33, 0x0E33),  # Thai SARA AM (renders as a cluster with its base)
    (0x0E34, 0x0E3A),  # Thai vowels and phinthu
    (0x0E47, 0x0E4E),  # Thai tone marks and thanthakhat
    (0x1AB0, 0x1AFF), (0x20D0, 0x20FF), (0xFE20, 0xFE2F),
)
_JOINERS = {"\u200c", "\u200d"}
_BREAK_SPACE = re.compile(r"[ \t\u00a0\u200b]")


def _is_combining(char: str) -> bool:
    code = ord(char)
    for start, end in _COMBINING_RANGES:
        if start <= code <= end:
            return True
    return False


def cluster_spans(text: str) -> List[Tuple[int, int]]:
    """Split text into visual clusters that must never be broken apart."""
    spans: List[Tuple[int, int]] = []
    start = 0
    for index, char in enumerate(text):
        if index and (_is_combining(char) or char in _JOINERS):
            continue
        if index > start:
            spans.append((start, index))
        start = index
    if text:
        spans.append((start, len(text)))
    return spans


def _inside(position: int, spans: Sequence[Tuple[int, int]]) -> bool:
    return any(start < position < end for start, end in spans)


def wrap_ranges(text: str, measure: Callable[[str], float], max_width: float,
                protected: Sequence[Tuple[int, int]] = ()) -> List[Tuple[int, int]]:
    """Line ``(start, end)`` ranges that respect clusters and entity spans.

    ``measure`` returns the rendered width of a string.  A line may exceed
    ``max_width`` only when keeping a protected span atomic requires it; callers
    widen the canvas for images and accept the slight overflow in PDF text.
    """
    spans = [(start, end) for start, end in sorted(protected) if end > start]
    clusters = cluster_spans(text)
    if not clusters:
        return [(0, len(text))]
    widths = [measure(text[start:end]) for start, end in clusters]
    ranges: List[Tuple[int, int]] = []
    index = 0
    total = len(clusters)
    while True:
        while index < total and text[clusters[index][0]:clusters[index][1]].isspace():
            index += 1
        if index >= total:
            break
        line_start = clusters[index][0]
        width = 0.0
        last_space = -1
        cursor = index
        while cursor < total:
            cluster_start, cluster_end = clusters[cursor]
            if width > 0 and width + widths[cursor] > max_width:
                break
            width += widths[cursor]
            if _BREAK_SPACE.match(text[cluster_start:cluster_end]) \
                    and not _inside(cluster_start, spans) and not _inside(cluster_end, spans):
                last_space = cursor
            cursor += 1
        if cursor >= total:
            ranges.append((line_start, len(text)))
            break
        if last_space > index:
            ranges.append((line_start, clusters[last_space][0]))
            index = last_space + 1
            continue
        cut = clusters[cursor][0]
        for span_start, span_end in spans:
            if span_start < cut < span_end:
                cut = span_end
                break
        if cut <= line_start:
            cut = clusters[cursor][1]
        ranges.append((line_start, cut))
        while index < total and clusters[index][1] <= cut:
            index += 1
    return ranges or [(0, len(text))]


_WHITESPACE = re.compile(r"\s+")


def normalize_extracted(text: str) -> str:
    """Collapse layout whitespace without erasing real word boundaries.

    Deleting every space would accept ``exam ple.com`` for ``example.com``; the
    collapse keeps one space where the extractor produced any run of whitespace,
    so a break inside a token still fails the comparison.
    """
    return _WHITESPACE.sub(" ", text).strip()
