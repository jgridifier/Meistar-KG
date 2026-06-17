"""Split assembled paper markdown into logical sections."""

from __future__ import annotations

import re

from backend.models.schemas import Section
from backend.pipeline.token_counter import count_tokens

_PAGE_MARKER = re.compile(r"<!--\s*page:(\d+)\s*-->")

_SECTION_HEADING = re.compile(
    r"^#{1,6}\s+(?:\d+(?:\.\d+)*\.?\s+)?("
    r"abstract|introduction|related work|background|preliminaries|"
    r"theoretical decompositions?|implications?|"
    r"methods?|methodology|approach|model|architecture|"
    r"experiments?|experimental setup|evaluation|results?|"
    r"discussion|analysis|conclusion|conclusions|"
    r"references|bibliography|appendix|acknowledgments?"
    r")(?:\b.*)?$",
    re.I | re.M,
)


def _page_for_position(text: str, pos: int) -> int:
    pages = [(m.start(), int(m.group(1))) for m in _PAGE_MARKER.finditer(text)]
    if not pages:
        return 1
    current = 1
    for start, page_num in pages:
        if start <= pos:
            current = page_num
        else:
            break
    return current


def split_into_sections(paper_markdown: str) -> list[Section]:
    """Split markdown into academic sections using heading detection."""
    text = paper_markdown.strip()
    if not text:
        return []

    matches = list(_SECTION_HEADING.finditer(text))

    if not matches:
        return [
            Section(
                title="Full Paper",
                content=text,
                token_count=count_tokens(text),
                page_start=_page_for_position(text, 0),
                page_end=_page_for_position(text, len(text)),
            )
        ]

    sections: list[Section] = []

    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(
                Section(
                    title="Preamble",
                    content=preamble,
                    token_count=count_tokens(preamble),
                    page_start=_page_for_position(text, 0),
                    page_end=_page_for_position(text, matches[0].start()),
                )
            )

    for i, match in enumerate(matches):
        title = match.group(1).strip().title()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        sections.append(
            Section(
                title=title,
                content=content,
                token_count=count_tokens(content),
                page_start=_page_for_position(text, start),
                page_end=_page_for_position(text, end),
            )
        )

    return sections