import json
from pathlib import Path

from backend.pipeline.pdf_parser import (
    _build_page_markdown,
    _html_to_markdown,
    _load_json_document,
    finalize_document_markdown,
)


def test_build_page_markdown_handles_tables_and_formulas() -> None:
    elements = [
        {"type": "heading", "heading level": 2, "content": "Results"},
        {"type": "table", "content": "| A | B |\n|---|---|\n| 1 | 2 |"},
        {"type": "formula", "content": "E = mc^2"},
    ]
    md, has_tables, _, has_formulas = _build_page_markdown(elements)
    assert has_tables
    assert has_formulas
    assert "Results" in md
    assert "E = mc^2" in md


def test_html_to_markdown_converts_headings() -> None:
    html = "<h1>Title</h1><p>Paragraph text.</p>"
    result = _html_to_markdown(html)
    assert "# Title" in result
    assert "Paragraph text." in result


def test_finalize_document_markdown_renumbers_ids() -> None:
    text = "<!-- table:T99 -->\n| a |\n<!-- formula:eq_99 -->\n$$ x $$"
    finalized, tables, formulas = finalize_document_markdown(text)
    assert "<!-- table:T1 -->" in finalized
    assert "<!-- formula:eq_1 -->" in finalized
    assert tables == 1
    assert formulas == 1


def test_load_json_document_reads_kids(tmp_path: Path) -> None:
    payload = {
        "title": "Sample Paper",
        "number of pages": 2,
        "kids": [{"type": "paragraph", "page number": 1, "content": "Hello"}],
    }
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    doc = _load_json_document(path)
    assert len(doc.kids) == 1
    assert doc.kids[0]["content"] == "Hello"
    assert doc.title == "Sample Paper"