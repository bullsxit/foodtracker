from __future__ import annotations

from typing import Optional


def parse_int(text: str) -> Optional[int]:
    """Parse integer from user input, returning None if invalid."""
    text = text.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_float(text: str) -> Optional[float]:
    """Parse float from user input, returning None if invalid."""
    text = text.strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None

