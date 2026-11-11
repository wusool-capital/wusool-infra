import pytest

from app.modules.google_workspace.domain.addresses import normalize_address, parse_address_list


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Sara Lee <Sara@Acme.COM>", "sara@acme.com"),
        ("  sara@acme.com ", "sara@acme.com"),
        ("sara@acme.com", "sara@acme.com"),
        ("undisclosed-recipients:;", None),
        ("not an address", None),
        ("", None),
        ("sara@localhost", None),
    ],
)
def test_normalize_address(raw: str, expected: str | None) -> None:
    assert normalize_address(raw) == expected


def test_an_address_list_keeps_quoted_commas_and_drops_repeats_and_junk() -> None:
    value = '"Chasles, Jules" <Jules@WusoolCapital.com>, sara@acme.com, SARA@acme.com, junk'

    assert parse_address_list(value) == ("jules@wusoolcapital.com", "sara@acme.com")


def test_an_empty_address_list_is_empty() -> None:
    assert parse_address_list("") == ()
