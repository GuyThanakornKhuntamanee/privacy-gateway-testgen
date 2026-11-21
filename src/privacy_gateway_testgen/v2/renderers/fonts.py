"""Bundled font assets for the Thai-capable PDF and raster renderers.

The font is resolved from a package-relative path so rendering never depends on
what is installed on the machine.  A missing asset, or a Pillow build without
libraqm shaping, raises instead of silently falling back to another font: a
mis-shaped Thai glyph must never become ground truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

FONT_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"

# Sarabun (Cadson Demak), SIL Open Font License 1.1.  Thai + Latin + Thai digits
# + Thai baht sign in one family, which is what mixed Thai-English needs.
FONT_FAMILY = "Sarabun"
FONT_LICENSE = "SIL Open Font License 1.1"
FONT_SOURCE = "https://github.com/google/fonts/tree/main/ofl/sarabun"
FONT_FILES: Dict[str, str] = {
    "regular": "Sarabun-Regular.ttf",
    "bold": "Sarabun-Bold.ttf",
}


class RendererUnavailable(RuntimeError):
    """A declared rendering capability cannot actually run here."""


def font_path(weight: str = "regular") -> Path:
    try:
        name = FONT_FILES[weight]
    except KeyError:
        raise RendererUnavailable(f"unknown font weight: {weight!r}") from None
    path = FONT_DIR / name
    if not path.is_file():
        raise RendererUnavailable(
            f"bundled font asset missing: {path} (expected {FONT_FAMILY}, {FONT_LICENSE})"
        )
    return path


def require_text_shaping() -> str:
    """Return the shaping engine name, or explain why Thai cannot be shaped."""
    try:
        from PIL import features
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RendererUnavailable("Pillow is required for Thai image rendering") from exc
    if features.check("raqm"):
        return "harfbuzz"
    raise RendererUnavailable(
        "Pillow was built without libraqm; Thai combining marks would be placed "
        "incorrectly. Install a Pillow wheel that includes libraqm."
    )
