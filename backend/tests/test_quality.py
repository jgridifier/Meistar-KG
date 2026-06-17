from backend.pipeline.quality import assess_page_quality


def test_good_page_passes() -> None:
    text = " ".join(["word"] * 50)
    result = assess_page_quality(1, f"# Introduction\n\n{text}")
    assert result.passed
    assert result.score >= 0.6


def test_sparse_page_fails() -> None:
    result = assess_page_quality(2, "short")
    assert not result.passed
    assert result.reasons