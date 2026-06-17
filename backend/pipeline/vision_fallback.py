"""Vision LLM fallback for pages that fail quality checks."""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from backend.config.settings import LLMProvider
from backend.pipeline.llm_client import LLMClient

_VISION_PROMPT = """Extract this academic paper page as clean markdown.

Preserve:
- Heading hierarchy (# ## ###)
- Paragraph structure
- Tables as markdown tables
- Formulas as LaTeX in $$ ... $$ blocks
- Figure captions with figure numbers
- Inline citations

Return only markdown. No commentary or code fences."""


def render_page_to_png(pdf_path: Path, page_num: int, *, dpi: int = 200) -> bytes:
    """Render a 1-indexed PDF page to PNG bytes."""
    doc = fitz.open(pdf_path)
    try:
        if page_num < 1 or page_num > doc.page_count:
            raise ValueError(f"Page {page_num} out of range (1-{doc.page_count})")
        page = doc[page_num - 1]
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")
    finally:
        doc.close()


async def extract_page_with_vision(
    pdf_path: Path,
    page_num: int,
    session_id: str,
    *,
    provider: LLMProvider,
    model: str | None = None,
) -> str:
    """Re-extract a single page using a vision-capable LLM."""
    image_bytes = render_page_to_png(pdf_path, page_num)
    client = LLMClient(provider=provider, model=model)
    response = await client.vision(
        session_id=session_id,
        image_bytes=image_bytes,
        prompt=_VISION_PROMPT,
        model=model,
    )
    return response.content.strip()