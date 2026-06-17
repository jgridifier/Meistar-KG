"""PDF → markdown via opendataloader-pdf with markdownify cleanup."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from markdownify import markdownify as md

from backend.config.settings import get_settings
from backend.pipeline.formula_utils import coalesce_math_blocks, tag_untagged_formulas
from backend.pipeline.java_env import ensure_java_available

PageSource = Literal["opendataloader", "markdownify", "vision"]


@dataclass
class ParsedPage:
    page_num: int
    markdown: str
    source: PageSource
    quality_score: float = 1.0
    has_tables: bool = False
    has_figures: bool = False
    has_formulas: bool = False


@dataclass
class ParseResult:
    pdf_path: Path
    output_dir: Path
    pages: list[ParsedPage] = field(default_factory=list)
    paper_markdown: str = ""
    paper_title: str = ""
    total_pages: int = 0
    table_count: int = 0
    formula_count: int = 0


@dataclass
class _JsonDocument:
    kids: list[dict[str, Any]]
    title: str = ""
    author: str = ""
    number_of_pages: int = 0


def _run_opendataloader(pdf_path: Path, output_dir: Path) -> None:
    """Invoke opendataloader-pdf convert (requires Java 11+)."""
    ensure_java_available()
    import opendataloader_pdf

    output_dir.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "input_path": [str(pdf_path)],
        "output_dir": str(output_dir),
        "format": "markdown,json,html",
    }
    settings = get_settings()
    if settings.opendataloader_hybrid:
        kwargs["hybrid"] = settings.opendataloader_hybrid

    opendataloader_pdf.convert(**kwargs)


def _find_output_stem(pdf_path: Path, output_dir: Path) -> str:
    candidates = [pdf_path.stem, pdf_path.name]
    for stem in candidates:
        if (output_dir / f"{stem}.json").exists():
            return stem
    json_files = list(output_dir.glob("*.json"))
    if json_files:
        return json_files[0].stem
    return pdf_path.stem


def _load_json_document(json_path: Path) -> _JsonDocument:
    if not json_path.exists():
        return _JsonDocument(kids=[])

    data = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return _JsonDocument(kids=data)

    if isinstance(data, dict):
        kids: list[dict[str, Any]] = []
        if isinstance(data.get("kids"), list):
            kids = data["kids"]
        else:
            for key in ("elements", "content", "pages", "data"):
                if isinstance(data.get(key), list):
                    kids = data[key]
                    break
        return _JsonDocument(
            kids=kids,
            title=str(data.get("title") or "").strip(),
            author=str(data.get("author") or "").strip(),
            number_of_pages=int(data.get("number of pages") or data.get("number_of_pages") or 0),
        )

    return _JsonDocument(kids=[])


def _element_page(elem: dict[str, Any]) -> int:
    for key in ("page number", "page_number", "pageNumber", "page"):
        if key in elem:
            try:
                return int(elem[key])
            except (TypeError, ValueError):
                pass
    return 1


def _element_content(elem: dict[str, Any]) -> str:
    for key in ("content", "text", "markdown"):
        val = elem.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _heading_level(elem: dict[str, Any]) -> int:
    try:
        return max(1, min(int(elem.get("heading level") or elem.get("heading_level") or 2), 6))
    except (TypeError, ValueError):
        return 2


def _element_to_markdown(elem: dict[str, Any]) -> str:
    elem_type = (elem.get("type") or "paragraph").lower()
    content = _element_content(elem)

    if elem_type == "heading":
        level = _heading_level(elem)
        return f"{'#' * level} {content}\n\n"

    if elem_type == "table":
        return f"{content}\n\n"

    if elem_type in ("formula", "equation"):
        if content.startswith("$$"):
            return f"{content}\n\n"
        return f"$$\n{content}\n$$\n\n"

    if elem_type in ("image", "picture", "figure"):
        desc = elem.get("description") or content
        caption = elem.get("caption") or ""
        fig_num = elem.get("figure number") or elem.get("figure_number")
        prefix = f"Figure {fig_num}: " if fig_num else ""
        alt = f"{prefix}{caption or desc}".strip()
        return f"![{alt}](page_{_element_page(elem)}_figure)\n\n"

    if elem_type == "list":
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        if not lines:
            return ""
        return "\n".join(f"- {ln}" if not ln.startswith("-") else ln for ln in lines) + "\n\n"

    if elem_type in ("paragraph", "text block", "caption"):
        return f"{content}\n\n" if content else ""

    return f"{content}\n\n" if content else ""


def _group_elements_by_page(elements: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    pages: dict[int, list[dict[str, Any]]] = {}
    for elem in elements:
        page = _element_page(elem)
        pages.setdefault(page, []).append(elem)
    return pages


def _build_page_markdown(page_elements: list[dict[str, Any]]) -> tuple[str, bool, bool, bool]:
    parts = [_element_to_markdown(elem) for elem in page_elements]
    raw = "".join(parts).strip()

    has_tables = any((e.get("type") or "").lower() == "table" for e in page_elements)
    has_figures = any((e.get("type") or "").lower() in ("image", "picture", "figure") for e in page_elements)
    has_formulas = any((e.get("type") or "").lower() in ("formula", "equation") for e in page_elements)

    coalesced = coalesce_math_blocks(raw)
    return coalesced, has_tables, has_figures, has_formulas or "$$" in coalesced


def _html_to_markdown(html: str) -> str:
    cleaned = md(html, heading_style="ATX", bullets="-", strip=["script", "style"])
    return cleaned.strip()


def _extract_title(doc: _JsonDocument, elements: list[dict[str, Any]], markdown: str) -> str:
    if doc.title and doc.title.lower() not in {"untitled", "abstract"}:
        return doc.title

    for elem in elements:
        if (elem.get("type") or "").lower() != "heading":
            continue
        level = _heading_level(elem)
        content = _element_content(elem)
        if level == 1 and content and len(content) < 300:
            if content.lower() != "abstract":
                return content

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.lower().startswith("# abstract"):
            title = stripped[2:].strip()
            if title and len(title) < 300:
                return title

    return "Untitled Paper"


def finalize_document_markdown(markdown: str) -> tuple[str, int, int]:
    """Assign sequential table/formula IDs across the full document."""
    table_count = 0
    formula_count = 0

    def replace_table(_match: re.Match[str]) -> str:
        nonlocal table_count
        table_count += 1
        return f"<!-- table:T{table_count} -->"

    def replace_formula(_match: re.Match[str]) -> str:
        nonlocal formula_count
        formula_count += 1
        return f"<!-- formula:eq_{formula_count} -->"

    text = re.sub(r"<!--\s*table:T\d+\s*-->", replace_table, markdown)
    text = re.sub(r"<!--\s*table:\s*-->", replace_table, text)
    text = re.sub(r"<!--\s*formula:eq_\d+\s*-->", replace_formula, text)
    text = re.sub(r"<!--\s*formula:\s*-->", replace_formula, text)

    text, tagged = tag_untagged_formulas(text)
    formula_count = max(formula_count, tagged)

    return text, table_count, formula_count


def _count_formulas_in_text(text: str) -> int:
    tagged = len(re.findall(r"<!--\s*formula:eq_\d+\s*-->", text))
    blocks = len(re.findall(r"\$\$", text)) // 2
    return max(tagged, blocks)


def parse_pdf(pdf_path: Path, output_dir: Path) -> ParseResult:
    """Parse a PDF with opendataloader-pdf, building per-page markdown."""
    _run_opendataloader(pdf_path, output_dir)
    stem = _find_output_stem(pdf_path, output_dir)

    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    html_path = output_dir / f"{stem}.html"

    doc = _load_json_document(json_path)
    elements = doc.kids
    full_md = md_path.read_text(encoding="utf-8").strip() if md_path.exists() else ""
    full_html = html_path.read_text(encoding="utf-8") if html_path.exists() else ""

    pages_by_elem = _group_elements_by_page(elements)
    page_nums = sorted(pages_by_elem) if pages_by_elem else []

    if doc.number_of_pages and not page_nums:
        page_nums = list(range(1, doc.number_of_pages + 1))

    parsed_pages: list[ParsedPage] = []

    for page_num in page_nums:
        page_elements = pages_by_elem.get(page_num, [])
        page_md, has_tables, has_figures, has_formulas = _build_page_markdown(page_elements)
        source: PageSource = "opendataloader"

        if len(page_md) < 80 and full_html:
            page_md = _html_to_markdown(full_html)
            source = "markdownify"
        elif len(page_md) < 80 and full_md:
            page_md = full_md
            source = "opendataloader"

        parsed_pages.append(
            ParsedPage(
                page_num=page_num,
                markdown=page_md,
                source=source,
                has_tables=has_tables,
                has_figures=has_figures,
                has_formulas=has_formulas,
            )
        )

    if not parsed_pages and full_md:
        coalesced = coalesce_math_blocks(full_md)
        parsed_pages = [
            ParsedPage(page_num=1, markdown=coalesced, source="opendataloader", has_formulas="$$" in coalesced)
        ]

    assembled_parts = [f"<!-- page:{p.page_num} -->\n{p.markdown}" for p in parsed_pages]
    paper_markdown = "\n\n".join(assembled_parts)
    paper_markdown, table_count, formula_count = finalize_document_markdown(paper_markdown)
    paper_title = _extract_title(doc, elements, full_md or paper_markdown)

    for page in parsed_pages:
        page.has_formulas = _count_formulas_in_text(page.markdown) > 0

    return ParseResult(
        pdf_path=pdf_path,
        output_dir=output_dir,
        pages=parsed_pages,
        paper_markdown=paper_markdown,
        paper_title=paper_title,
        total_pages=len(parsed_pages),
        table_count=table_count,
        formula_count=formula_count,
    )