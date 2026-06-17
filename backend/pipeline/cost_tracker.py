"""Unified cost tracking for all LLM and TTS calls."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

import polars as pl

from backend.models.schemas import CostRecord

# Cost table (USD per 1M tokens or 1M chars for TTS)
# Update these as providers change pricing
COST_TABLE: dict[str, dict[str, float]] = {
    # LLM: (input_per_1M, output_per_1M)
    "openrouter/anthropic/claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "openrouter/meta-llama/llama-3.1-70b": {"input": 0.9, "output": 0.9},
    "openai/gpt-4o": {"input": 2.5, "output": 10.0},
    "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "nvidia/llama-3.1-70b-instruct": {"input": 0.97, "output": 0.97},
    # TTS: per 1M chars
    "openai/tts-1": {"chars": 15.0},
    "openai/tts-1-hd": {"chars": 30.0},
    "elevenlabs/eleven_multilingual_v2": {"chars": 90.0},
    "kokoro/kokoro-v0_19": {"chars": 0.0},  # self-hosted
}

_COST_LOG_PATH = Path("cost_log.jsonl")


def _lookup_rates(provider: str, model: str) -> dict[str, float]:
    """Resolve cost rates with provider-specific and shared model fallbacks."""
    candidates = [
        f"{provider}/{model}",
        f"openai/{model}",
        f"openrouter/{model}",
    ]
    for key in candidates:
        rates = COST_TABLE.get(key)
        if rates:
            return rates
    return {}


def compute_cost(
    provider_model: str,
    call_type: Literal["llm", "tts", "vision"],
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    chars: int | None = None,
) -> float:
    """Compute USD cost for a single API call."""
    if "/" in provider_model:
        provider, model = provider_model.split("/", 1)
        rates = _lookup_rates(provider, model)
    else:
        rates = COST_TABLE.get(provider_model, {})
    if call_type == "tts":
        return (chars or 0) * rates.get("chars", 0.0) / 1_000_000
    else:
        input_cost = (input_tokens or 0) * rates.get("input", 0.0) / 1_000_000
        output_cost = (output_tokens or 0) * rates.get("output", 0.0) / 1_000_000
        return input_cost + output_cost


def record_call(
    session_id: str,
    call_type: Literal["llm", "tts", "vision"],
    provider: str,
    model: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    chars: int | None = None,
) -> CostRecord:
    """Record a call and return the CostRecord with computed cost."""
    cost = compute_cost(
        f"{provider}/{model}",
        call_type,
        input_tokens,
        output_tokens,
        chars,
    )

    record = CostRecord(
        session_id=session_id,
        call_type=call_type,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        chars=chars,
        cost_usd=cost,
    )

    # Append to JSONL log
    with open(_COST_LOG_PATH, "a") as f:
        f.write(record.model_dump_json() + "\n")

    return record


def get_session_costs(session_id: str) -> pl.DataFrame:
    """Return all cost records for a session as a Polars DataFrame."""
    if not _COST_LOG_PATH.exists():
        return pl.DataFrame()

    records = []
    with open(_COST_LOG_PATH) as f:
        for line in f:
            r = json.loads(line)
            if r["session_id"] == session_id:
                records.append(r)

    if not records:
        return pl.DataFrame()

    return pl.DataFrame(records)


def get_session_total(session_id: str) -> float:
    """Return total USD cost for a session."""
    df = get_session_costs(session_id)
    if df.is_empty():
        return 0.0
    return df["cost_usd"].sum()


def get_all_costs() -> pl.DataFrame:
    """Return all cost records."""
    if not _COST_LOG_PATH.exists():
        return pl.DataFrame()

    records = []
    with open(_COST_LOG_PATH) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    return pl.DataFrame(records) if records else pl.DataFrame()
