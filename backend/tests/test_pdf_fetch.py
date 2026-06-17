import pytest

from backend.pipeline.pdf_fetch import PDFFetchError, resolve_pdf_url


def test_resolve_arxiv_abs_url() -> None:
    url = "https://arxiv.org/abs/1706.03762"
    assert resolve_pdf_url(url) == "https://arxiv.org/pdf/1706.03762.pdf"


def test_resolve_arxiv_pdf_url() -> None:
    url = "https://arxiv.org/pdf/1706.03762"
    assert resolve_pdf_url(url) == "https://arxiv.org/pdf/1706.03762.pdf"


def test_resolve_direct_pdf_url() -> None:
    url = "https://example.com/papers/sample.pdf"
    assert resolve_pdf_url(url) == url


def test_unsupported_url_raises() -> None:
    with pytest.raises(PDFFetchError):
        resolve_pdf_url("https://example.com/paper.html")