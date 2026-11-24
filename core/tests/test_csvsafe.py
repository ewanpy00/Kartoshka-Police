import pytest

from app.csvsafe import cell


@pytest.mark.parametrize("value", ["=HYPERLINK(\"http://evil\",\"x\")", "+971501234567", "-1+1", "@SUM(A1)", "\tx", "\rx"])
def test_formula_starts_are_quoted(value):
    assert cell(value) == "'" + value


@pytest.mark.parametrize("value", ["https://example.org/", "abc", "", 42, True])
def test_other_values_pass_through_as_text(value):
    assert cell(value) == str(value)
