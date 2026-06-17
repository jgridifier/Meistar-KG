"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["openrouter", "openai", "nvidia"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM providers
    openrouter_api_key: str = ""
    openai_api_key: str = ""
    nvidia_api_key: str = ""

    default_llm_provider: LLMProvider = "openrouter"
    default_llm_model: str = "anthropic/claude-3-5-sonnet"
    vision_llm_model: str = "gpt-4o"

    # TTS (used by later stages)
    openai_tts_voice: str = "alloy"
    elevenlabs_api_key: str = ""

    # Graph (used by later stages)
    grafeo_api_key: str = ""
    grafeo_base_url: str = ""

    # App
    secret_key: str = "changeme"
    database_url: str = "sqlite:///./meistar.db"
    data_dir: Path = Path("data")

    # PDF parsing — opendataloader-pdf requires Java 11+ installed
    opendataloader_hybrid: str = ""

    # Ingestion thresholds
    token_threshold_full_context: int = 150_000

    @property
    def pdf_cache_dir(self) -> Path:
        return self.data_dir / "pdfs"

    @property
    def parse_output_dir(self) -> Path:
        return self.data_dir / "parsed"

    def ensure_data_dirs(self) -> None:
        self.pdf_cache_dir.mkdir(parents=True, exist_ok=True)
        self.parse_output_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()