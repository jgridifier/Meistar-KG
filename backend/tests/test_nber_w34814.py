"""Integration checks for NBER w34814 using cached opendataloader output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.pipeline.pdf_parser import (
    _build_page_markdown,
    _group_elements_by_page,
    _load_json_document,
    finalize_document_markdown,
)

_FIXTURE_JSON = Path(__file__).resolve().parents[2] / "data/test/parsed2/w34814.json"


@pytest.mark.skipif(not _FIXTURE_JSON.exists(), reason="NBER fixture JSON not available")
def test_nber_fixture_has_79_pages_and_formulas() -> None:
    doc = _load_json_document(_FIXTURE_JSON)
    pages = _group_elements_by_page(doc.kids)
    assert len(pages) == 79
    assert doc.title == "Interest Rates and Equity Valuations"

    assembled = []
    for page_num in sorted(pages):
        md, _, _, has_formulas = _build_page_markdown(pages[page_num])
        if page_num >= 60:
            assert md  # appendix pages should have content
        assembled.append(f"<!-- page:{page_num} -->\n{md}")

    paper_markdown, _, formula_count = finalize_document_markdown("\n\n".join(assembled))
    assert formula_count >= 50
    assert "κn,t(mt+1)" in paper_markdown
    assert "Appendix" in paper_markdown
    assert paper_markdown.count("<!-- page:") == 79


@pytest.mark.skipif(not _FIXTURE_JSON.exists(), reason="NBER fixture JSON not available")
def test_nber_appendix_equation_coalesced() -> None:
    doc = _load_json_document(_FIXTURE_JSON)
    pages = _group_elements_by_page(doc.kids)
    md, _, _, _ = _build_page_markdown(pages[64])
    md, _, _ = finalize_document_markdown(md)
    assert "eyt∗ ≡ eyt = (1 − δ)" in md
    assert "$$" in md