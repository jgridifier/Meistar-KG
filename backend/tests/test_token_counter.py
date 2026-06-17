from backend.pipeline.token_counter import count_tokens


def test_count_tokens_nonempty() -> None:
    assert count_tokens("hello world") > 0


def test_count_tokens_empty() -> None:
    assert count_tokens("") == 0