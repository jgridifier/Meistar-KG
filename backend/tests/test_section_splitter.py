from backend.pipeline.section_splitter import split_into_sections


SAMPLE = """<!-- page:1 -->
# Attention Is All You Need

## Abstract
We propose transformers.

<!-- page:2 -->
## Introduction
Sequence modeling is important.

## Methods
We use self-attention.
"""


def test_splits_academic_headings() -> None:
    sections = split_into_sections(SAMPLE)
    titles = [s.title for s in sections]
    assert "Abstract" in titles
    assert "Introduction" in titles
    assert "Methods" in titles


def test_section_page_ranges() -> None:
    sections = split_into_sections(SAMPLE)
    abstract = next(s for s in sections if s.title == "Abstract")
    assert abstract.page_start == 1
    methods = next(s for s in sections if s.title == "Methods")
    assert methods.page_start == 2