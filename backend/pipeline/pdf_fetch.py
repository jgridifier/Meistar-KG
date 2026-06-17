"""Fetch and cache PDFs from paper URLs."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

_ARXIV_ABS = re.compile(r"arxiv\.org/abs/([\d.]+(?:v\d+)?)", re.I)
_ARXIV_PDF = re.compile(r"arxiv\.org/pdf/([\d.]+(?:v\d+)?)", re.I)


class PDFFetchError(Exception):
    """Raised when a PDF cannot be resolved or downloaded."""


def resolve_pdf_url(url: str) -> str:
    """Normalize common academic URLs to a direct PDF link."""
    url = url.strip()

    abs_match = _ARXIV_ABS.search(url)
    if abs_match:
        paper_id = abs_match.group(1)
        return f"https://arxiv.org/pdf/{paper_id}.pdf"

    pdf_match = _ARXIV_PDF.search(url)
    if pdf_match:
        paper_id = pdf_match.group(1)
        if not url.endswith(".pdf"):
            return f"https://arxiv.org/pdf/{paper_id}.pdf"
        return url

    parsed = urlparse(url)
    if parsed.path.lower().endswith(".pdf"):
        return url

    raise PDFFetchError(
        f"Unsupported URL format: {url}. Provide a direct .pdf link or arXiv abs/pdf URL."
    )


async def fetch_pdf(url: str, dest_path: Path, *, timeout: float = 120.0) -> Path:
    """Download a PDF to dest_path and return the path."""
    resolved = resolve_pdf_url(url)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(resolved)
        if response.status_code != 200:
            raise PDFFetchError(f"Failed to download PDF ({response.status_code}): {resolved}")

        content_type = response.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and not resolved.endswith(".pdf"):
            raise PDFFetchError(f"URL did not return a PDF: {resolved} (content-type: {content_type})")

        dest_path.write_bytes(response.content)

    if dest_path.stat().st_size < 1024:
        raise PDFFetchError(f"Downloaded file is too small to be a valid PDF: {dest_path}")

    return dest_path