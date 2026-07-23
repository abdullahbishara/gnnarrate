"""Shared text helpers for scoring narratives against logs and knowledge bases."""

from __future__ import annotations

import re


def mentions(entity: str, text: str) -> bool:
    """Case-insensitive whole-token match. Gene symbols carry digits, so \\b works."""
    return re.search(rf"\b{re.escape(entity)}\b", text, re.IGNORECASE) is not None


def sentences(text: str) -> list[str]:
    """Split text into sentences on terminal punctuation."""
    return [s for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def has_term(text: str, terms) -> bool:
    """True if any term appears as a whole word (case-insensitive)."""
    low = text.lower()
    return any(re.search(rf"\b{re.escape(t.lower())}\b", low) for t in terms)
