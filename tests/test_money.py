import pytest

from hermes_fetch_ai.money import BASE_PER_FET, MAX_PRICE_BASE, format_fet, parse_fet


@pytest.mark.parametrize(
    ("text", "base"),
    [
        ("0", 0),
        ("1", BASE_PER_FET),
        ("0.05", 50_000_000_000_000_000),
        ("0.1", 100_000_000_000_000_000),
        ("12.5", 12 * BASE_PER_FET + BASE_PER_FET // 2),
        ("0.000000000000000001", 1),
        ("1000", MAX_PRICE_BASE),
    ],
)
def test_parse_fet_is_exact(text, base):
    assert parse_fet(text) == base


@pytest.mark.parametrize(
    "text",
    ["", " 1", "1 ", "-1", "+1", "1e3", "0.1e1", "01", "1.", ".5", "1,000", "0x10", "nan", "inf"],
)
def test_parse_fet_rejects_anything_but_plain_decimals(text):
    with pytest.raises(ValueError, match="not a FET amount"):
        parse_fet(text)


def test_parse_fet_rejects_more_than_18_decimals():
    with pytest.raises(ValueError):
        parse_fet("0.0000000000000000001")


def test_parse_fet_rejects_non_strings():
    with pytest.raises(ValueError):
        parse_fet(0.05)


@pytest.mark.parametrize("text", ["0", "1", "0.05", "12.5", "0.000000000000000001", "1000"])
def test_format_fet_round_trips(text):
    assert format_fet(parse_fet(text)) == text


def test_format_fet_rejects_negative_amounts():
    with pytest.raises(ValueError):
        format_fet(-1)
