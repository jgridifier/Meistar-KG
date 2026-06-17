from unittest.mock import AsyncMock, patch

import pytest

from backend.models.schemas import Session
from backend.pipeline.pdf_parser import ParsedPage, ParseResult


@pytest.mark.asyncio
async def test_ingest_paper_updates_session(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))

    session = Session(paper_url="https://arxiv.org/abs/1706.03762")

    parse_result = ParseResult(
        pdf_path=tmp_path / "paper.pdf",
        output_dir=tmp_path / "parsed",
        pages=[
            ParsedPage(
                page_num=1,
                markdown="# Attention Is All You Need\n\n## Abstract\nWe propose transformers.",
                source="opendataloader",
            ),
            ParsedPage(
                page_num=2,
                markdown="## Introduction\n" + " ".join(["word"] * 60),
                source="opendataloader",
            ),
        ],
        paper_title="Attention Is All You Need",
        total_pages=2,
    )

    with (
        patch("backend.agents.ingestion.fetch_pdf", new_callable=AsyncMock) as mock_fetch,
        patch("backend.agents.ingestion.pdf_parser.parse_pdf", return_value=parse_result),
    ):
        from backend.agents.ingestion import ingest_paper

        result = await ingest_paper(session, llm_provider="openai")

    mock_fetch.assert_awaited_once()
    assert result.status == "processing"
    assert result.paper_title == "Attention Is All You Need"
    assert result.paper_markdown is not None
    assert "<!-- page:1 -->" in result.paper_markdown
    assert len(result.sections) >= 1
    assert result.metadata["context_mode"] == "full"
    assert result.error_message is None


@pytest.mark.asyncio
async def test_run_ingestion_marks_failed_on_fetch_error(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    from backend.agents.ingestion import run_ingestion
    from backend.pipeline.pdf_fetch import PDFFetchError

    session = Session(paper_url="https://example.com/bad")
    sessions = {session.id: session}

    with patch(
        "backend.agents.ingestion.fetch_pdf",
        new_callable=AsyncMock,
        side_effect=PDFFetchError("bad url"),
    ):
        await run_ingestion(session.id, sessions, llm_provider="openai")

    assert sessions[session.id].status == "failed"
    assert sessions[session.id].error_message == "bad url"