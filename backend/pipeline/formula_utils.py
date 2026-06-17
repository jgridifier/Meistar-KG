"""Detect and coalesce fragmented mathematical content from PDF extraction."""

from __future__ import annotations

import re

_MATH_SYMBOLS = set("=+-−×*/^_{}[]()\\∂∑Σ∫ργλκδεθσφψω∗⊥≡≈≤≥∞")
_SUBSCRIPT_FRAGMENT = re.compile(r"^[a-z](?:\+\d+)?$", re.I)
_TINY_FRAGMENT = re.compile(r"^[\dn=+\-−∂∑Σ∫ργλκδεθσφψω∗∞.,;:]+$")
_SINGLE_SYMBOL = re.compile(r"^[^\w\s]{1,3}$")
_DISPLAY_MATH = re.compile(r"^\$\$\s*.+\s*\$\$$", re.DOTALL)


def _is_math_fragment(text: str) -> bool:
    t = text.strip()
    if not t or len(t) > 140:
        return False

    words = re.findall(r"[a-zA-Z]{4,}", t)
    if len(words) >= 3:
        return False

    if "=" in t and len(words) <= 2:
        return True
    if _SUBSCRIPT_FRAGMENT.match(t):
        return True
    if _TINY_FRAGMENT.match(t) and len(t) <= 12:
        return True
    if _SINGLE_SYMBOL.match(t):
        return True

    math_chars = sum(1 for c in t if c in _MATH_SYMBOLS or c.isdigit())
    if math_chars >= 2 and len(words) <= 1:
        return True

    return False


def _is_display_equation(text: str) -> bool:
    t = text.strip()
    if not t or len(t) > 500:
        return False
    if _is_math_fragment(t):
        return True
    words = re.findall(r"[a-zA-Z]{4,}", t)
    if "=" not in t:
        return False
    return len(words) <= 2 and any(c in _MATH_SYMBOLS for c in t)


def _join_math_fragments(parts: list[str]) -> str:
    result = ""
    for part in parts:
        p = part.strip()
        if not p:
            continue
        if not result:
            result = p
        elif len(p) <= 3 and re.match(r"^[a-z0-9+\-−]+$", p, re.I):
            result += p
        else:
            result += f" {p}"
    return re.sub(r"\s+", " ", result).strip()


def _is_prose_line(text: str) -> bool:
    words = re.findall(r"[a-zA-Z]{4,}", text)
    return len(words) >= 4


def _merge_adjacent_display_math(text: str) -> str:
    """Combine consecutive $$ blocks that were split across fragments."""
    parts = re.split(r"(\$\$.*?\$\$)", text, flags=re.DOTALL)
    merged: list[str] = []
    pending_math: list[str] = []

    def flush_math() -> None:
        if not pending_math:
            return
        body = _join_math_fragments(pending_math)
        merged.append(f"$$\n{body}\n$$")
        pending_math.clear()

    for part in parts:
        if not part:
            continue
        if part.startswith("$$") and part.endswith("$$"):
            inner = part[2:-2].strip()
            if inner:
                pending_math.append(inner)
            continue

        flush_math()
        for line in part.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if _is_math_fragment(stripped) or _is_display_equation(stripped):
                pending_math.append(stripped)
            else:
                flush_math()
                merged.append(stripped)

    flush_math()
    return "\n\n".join(merged)


def coalesce_math_blocks(text: str) -> str:
    """Merge fragmented equation lines into display-math blocks."""
    lines = text.splitlines()
    output: list[str] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if not buffer:
            return
        joined = _join_math_fragments(buffer)
        if joined:
            output.append(f"$$\n{joined}\n$$")
        buffer.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # Blank lines inside equations are common — keep buffering.
            continue

        if stripped.startswith("<!--") or stripped.startswith("#"):
            flush_buffer()
            output.append(stripped)
            continue

        if stripped.startswith("$$"):
            flush_buffer()
            output.append(stripped)
            continue

        if _is_math_fragment(stripped) or _is_display_equation(stripped):
            buffer.append(stripped)
            continue

        if buffer and not _is_prose_line(stripped):
            buffer.append(stripped)
            continue

        flush_buffer()
        output.append(stripped)

    flush_buffer()
    merged = "\n".join(output)
    return _merge_adjacent_display_math(merged)


def tag_untagged_formulas(markdown: str) -> tuple[str, int]:
    """Add formula markers before each display-math block."""
    formula_count = 0
    lines = markdown.splitlines()
    output: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("<!-- formula:"):
            output.append(line)
            i += 1
            continue

        if line.strip() == "$$":
            block = ["$$"]
            i += 1
            while i < len(lines) and lines[i].strip() != "$$":
                block.append(lines[i])
                i += 1
            if i < len(lines):
                block.append("$$")
                i += 1
            formula_count += 1
            output.append(f"<!-- formula:eq_{formula_count} -->")
            output.extend(block)
            continue

        if _is_display_equation(line):
            formula_count += 1
            output.append(f"<!-- formula:eq_{formula_count} -->")
            output.append(f"$$\n{line.strip()}\n$$")
            i += 1
            continue

        output.append(line)
        i += 1

    return "\n".join(output), formula_count