"""Ingestion agent: URL → structured paper markdown."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

from backend.config.settings import LLMProvider, get_settings
from backend.models.schemas import Session
from backend.pipeline import pdf_parser
from backend.pipeline.cost_tracker import get_session_total
from backend.pipeline.pdf_fetch import PDFFetchError, fetch_pdf
from backend.pipeline.pdf_parser import ParseResult, ParsedPage
from backend.pipeline.quality import assess_page_quality
from backend.pipeline.section_splitter import split_into_sections
from backend.pipeline.token_counter import count_tokens
from backend.pipeline.vision_fallback import extract_page_with_vision

logger = logging.getLogger(__name__)


def _assemble_markdown(pages: list[ParsedPage]) -> str:
    parts = [f"<!-- page:{p.page_num} -->\n{p.markdown}" for p in pages]
    return "\n\n".join(parts)


def _apply_vision_to_page(
    pages: list[ParsedPage],
    page_num: int,
    markdown: str,
) -> None:
    for page in pages:
        if page.page_num == page_num:
            page.markdown = markdown
            page.source = "vision"
            break


async def ingest_paper(
    session: Session,
    *,
    llm_provider: LLMProvider,
    vision_model: str | None = None,
) -> Session:
    """Run the full ingestion pipeline for a session."""
    settings = get_settings()
    settings.ensure_data_dirs()

    pdf_path = settings.pdf_cache_dir / f"{session.id}.pdf"
    output_dir = settings.parse_output_dir / session.id

    await fetch_pdf(session.paper_url, pdf_path)
    parse_result: ParseResult = await asyncio.to_thread(
        pdf_parser.parse_pdf, pdf_path, output_dir
    )

    pages = list(parse_result.pages)
    await _recover_low_quality_pages(
        pages,
        pdf_path=pdf_path,
        session_id=session.id,
        llm_provider=llm_provider,
        vision_model=vision_model,
    )

    paper_markdown = _assemble_markdown(pages)
    paper_markdown, table_count, formula_count = pdf_parser.finalize_document_markdown(
        paper_markdown
    )

    sections = split_into_sections(paper_markdown)
    total_tokens = count_tokens(paper_markdown)
    context_mode = (
        "full" if total_tokens < settings.token_threshold_full_context else "sectioned"
    )

    session.paper_title = parse_result.paper_title
    session.paper_markdown = paper_markdown
    session.sections = sections
    session.status = "processing"
    session.total_cost_usd = get_session_total(session.id)
    session.metadata = {
        "context_mode": context_mode,
        "total_tokens": total_tokens,
        "pdf_path": str(pdf_path),
        "total_pages": len(pages),
        "table_count": table_count,
        "formula_count": formula_count,
        "parse_output_dir": str(output_dir),
    }
    session.error_message = None

    return session


async def _recover_low_quality_pages(
    pages: list[ParsedPage],
    *,
    pdf_path: Path,
    session_id: str,
    llm_provider: LLMProvider,
    vision_model: str | None,
) -> None:
    """Re-extract low-quality pages via vision LLM when configured."""
    settings = get_settings()
    has_key = {
        "openrouter": bool(settings.openrouter_api_key),
        "openai": bool(settings.openai_api_key),
        "nvidia": bool(settings.nvidia_api_key),
    }.get(llm_provider, False)

    for page in pages:
        quality = assess_page_quality(page.page_num, page.markdown)
        page.quality_score = quality.score

        if quality.passed:
            continue

        if not has_key:
            page.markdown = (
                f"{page.markdown}\n\n<!-- page:{page.page_num}: extraction failed -->"
            ).strip()
            logger.warning(
                "Page %s failed quality check; no API key for vision fallback",
                page.page_num,
            )
            continue

        try:
            vision_md = await extract_page_with_vision(
                pdf_path,
                page.page_num,
                session_id,
                provider=llm_provider,
                model=vision_model,
            )
            vision_quality = assess_page_quality(page.page_num, vision_md)
            if vision_quality.passed:
                _apply_vision_to_page(pages, page.page_num, vision_md)
                page.quality_score = vision_quality.score
            else:
                page.markdown = (
                    f"{vision_md}\n\n<!-- page:{page.page_num}: extraction failed -->"
                ).strip()
                logger.warning("Vision fallback still low quality on page %s", page.page_num)
        except Exception:
            logger.exception("Vision fallback failed for page %s", page.page_num)
            page.markdown = (
                f"{page.markdown}\n\n<!-- page:{page.page_num}: extraction failed -->"
            ).strip()


async def run_ingestion(
    session_id: str,
    sessions: dict[str, Session],
    *,
    llm_provider: LLMProvider = "openrouter",
    vision_model: str | None = None,
    on_complete: Callable[[], None] | None = None,
) -> None:
    """Background task entry point for FastAPI."""
    session = sessions.get(session_id)
    if not session:
        return

    try:
        await ingest_paper(
            session,
            llm_provider=llm_provider,
            vision_model=vision_model,
        )
    except PDFFetchError as exc:
        logger.error("PDF fetch failed for session %s: %s", session_id, exc)
        session.status = "failed"
        session.error_message = str(exc)
    except Exception as exc:
        logger.exception("Ingestion failed for session %s", session_id)
        session.status = "failed"
        session.error_message = str(exc)
    finally:
        if on_complete:
            on_complete()