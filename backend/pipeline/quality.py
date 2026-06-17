"""Per-page PDF extraction quality heuristics."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_MIN_CHARS = 100
_MIN_WORDS = 20
_MIN_ALNUM_RATIO = 0.5


@dataclass
class PageQualityResult:
    page_num: int
    passed: bool
    score: float
    reasons: list[str] = field(default_factory=list)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _alnum_ratio(text: str) -> float:
    if not text:
        return 0.0
    alnum = sum(1 for c in text if c.isalnum())
    return alnum / len(text)


def assess_page_quality(page_num: int, markdown: str) -> PageQualityResult:
    """Score a single page's extracted markdown."""
    text = markdown.strip()
    reasons: list[str] = []
    score = 1.0

    if len(text) < _MIN_CHARS:
        reasons.append(f"too few characters ({len(text)} < {_MIN_CHARS})")
        score -= 0.4

    words = _word_count(text)
    if words < _MIN_WORDS:
        reasons.append(f"too few words ({words} < {_MIN_WORDS})")
        score -= 0.3

    ratio = _alnum_ratio(text)
    if ratio < _MIN_ALNUM_RATIO:
        reasons.append(f"low alphanumeric ratio ({ratio:.2f} < {_MIN_ALNUM_RATIO})")
        score -= 0.3

    if re.search(r"<!--\s*page:\d+\s*:\s*extraction failed\s*-->", text, re.I):
        reasons.append("marked as extraction failed")
        score -= 0.5

    score = max(0.0, min(1.0, score))
    passed = score >= 0.6 and len(reasons) == 0

    return PageQualityResult(
        page_num=page_num,
        passed=passed,
        score=score,
        reasons=reasons,
    )