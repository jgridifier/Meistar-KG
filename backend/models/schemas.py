"""Pydantic models for Meistar-KG."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field
import uuid


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class Section(BaseModel):
    title: str
    content: str
    token_count: int
    page_start: int
    page_end: int


class ScriptChunk(BaseModel):
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    script_text: str
    source_section: str
    source_page: int
    content_type: Literal["explanation", "table", "formula", "transition", "summary"]
    table_highlight: dict | None = None   # {"table_id": "T2", "rows": [...], "cols": [...]}
    formula_ref: str | None = None
    tts_ssml: str | None = None
    estimated_duration_sec: float | None = None


class AudioChunk(BaseModel):
    chunk_id: str
    audio_url: str
    duration_sec: float
    word_timestamps: list[dict] | None = None
    pdf_page: int
    pdf_section: str
    provider: str
    cost_usd: float
    chars: int


class Annotation(BaseModel):
    annotation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chunk_id: str
    pdf_page: int
    question: str
    answer: str
    visual: str | None = None  # Mermaid/SVG string if "draw it out"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    paper_url: str
    paper_title: str | None = None
    paper_markdown: str | None = None
    sections: list[Section] = []
    script: list[ScriptChunk] = []
    audio_chunks: list[AudioChunk] = []
    kg_session_context: dict = {}
    annotations: list[Annotation] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["ingesting", "processing", "ready", "playing", "complete"] = "ingesting"
    total_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# API request/response
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    paper_url: str
    tts_provider: Literal["openai", "elevenlabs", "kokoro"] = "openai"
    llm_provider: Literal["openrouter", "openai", "nvidia"] = "openrouter"


class QARequest(BaseModel):
    question: str
    chunk_id: str
    pdf_page: int


class QAResponse(BaseModel):
    answer: str
    visual: str | None = None  # Mermaid/SVG if applicable
    kg_connections: list[dict] = []  # related KG nodes surfaced


# ---------------------------------------------------------------------------
# Cost tracking
# ---------------------------------------------------------------------------

class CostRecord(BaseModel):
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    call_type: Literal["llm", "tts", "vision"]
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    chars: int | None = None
    cost_usd: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
