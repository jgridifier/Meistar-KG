from backend.pipeline.formula_utils import coalesce_math_blocks, tag_untagged_formulas


def test_coalesce_math_fragments() -> None:
    raw = "\n".join(
        [
            "eyt∗ = Et[rtmkt+1] − λEt[gt+1] − log 1 − e−ey",
            "t",
            "",
            "+ Et log 1 − e−ey",
            "t+1",
        ]
    )
    result = coalesce_math_blocks(raw)
    assert "$$" in result
    assert "e−eyt" in result or "e−ey t" in result


def test_tag_standalone_equation() -> None:
    text = "κn,t(mt+1) = (−γ)nκn,t(gt+1), κn,t(rtmkt+1) = λnκn,t(gt+1)."
    tagged, count = tag_untagged_formulas(text)
    assert count >= 1
    assert "<!-- formula:eq_1 -->" in tagged