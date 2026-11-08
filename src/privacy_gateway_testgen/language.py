"""Small language-selection helper used by every prompt template."""

from __future__ import annotations

import random


def L(rng: random.Random, language: str, thai: str, english: str) -> str:
    """Return Thai, English, or a random one of the two for mixed prompts."""
    if language == "th":
        return thai
    if language == "en":
        return english
    return thai if rng.random() < 0.5 else english


def language_of(rng: random.Random, language: str) -> str:
    return language
