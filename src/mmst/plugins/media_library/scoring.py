"""Scoring utilities for enrichment candidate ranking.

Lightweight, dependency-free similarity heuristics suitable for initial
ranking. Future upgrades could integrate rapidfuzz or Levenshtein for
improved accuracy while retaining this module as a facade.
"""
from __future__ import annotations

import math
from typing import Optional


def normalize_title(text: str) -> str:
    if not text:
        return ""
    return " ".join(text.casefold().split())


def simple_ratio(a: str, b: str) -> float:
    """Very crude similarity ratio (token overlap based). Returns 0..1."""
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    sa, sb = set(na.split()), set(nb.split())
    inter = len(sa & sb)
    union = len(sa | sb)
    if union == 0:
        return 0.0
    return inter / union


def year_proximity_score(target_year: Optional[int], candidate_year: Optional[int]) -> float:
    if not target_year or not candidate_year:
        return 0.0
    diff = abs(target_year - candidate_year)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.7
    if diff == 2:
        return 0.4
    return 0.0


def aggregate_score(base_provider_score: float, title_score: float, year_score: float) -> float:
    # Weighted linear combination; weights chosen heuristically.
    # Provider score assumed 0..1; title/year also 0..1.
    return (base_provider_score * 0.6) + (title_score * 0.3) + (year_score * 0.1)


__all__ = [
    "normalize_title",
    "simple_ratio",
    "year_proximity_score",
    "aggregate_score",
]
