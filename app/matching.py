from __future__ import annotations

import re
import unicodedata

from app.dates import strip_date_prefix


def normalize(title: str) -> str:
    """Strip any date prefix, remove diacritics, lowercase, collapse whitespace.

    Note: equality is what matters, and both sides are normalized the same way, so
    letters that NFKD does not decompose (e.g. Vietnamese 'đ') stay consistent on
    both sides and still compare equal.
    """
    without_date = strip_date_prefix(title)
    decomposed = unicodedata.normalize("NFKD", without_date)
    no_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", no_marks).strip().lower()


def matches_any(title: str, base_titles: list[str]) -> bool:
    norm = normalize(title)
    return any(norm == normalize(b) for b in base_titles)
