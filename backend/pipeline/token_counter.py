"""Token counting for context window planning."""

from __future__ import annotations

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens using the cl100k_base encoding (GPT-4 family)."""
    if not text:
        return 0
    return len(_ENCODING.encode(text))