import pytest

from app.modules.discovery.domain.names import names_similar


@pytest.mark.parametrize(
    ("lead", "org"),
    [
        ("O AI Company For Artificial Intelligence", "FLOW Intelligence"),
        ("AITS - Advanced Artificial Intelligence", "FLOW Intelligence"),
        ("Gulf Capital Group", "Atlas Capital Group"),
        ("savvytec GmbH & Co. KG", "NXI GmbH & Co. KG"),
        # Investor words name a business line, so they still tell firms apart.
        ("Atlas Capital", "Atlas Ventures"),
        # One short word alone isn't enough to call two companies the same.
        ("Noor", "Noor Trading"),
        ("Acme Co", "Acme Trading"),
        ("Heilberg Solutions GmbH", "ComfNet Solutions GmbH"),
    ],
)
def test_a_shared_generic_word_is_not_a_match(lead: str, org: str) -> None:
    assert not names_similar(lead, org)


@pytest.mark.parametrize(
    ("lead", "org"),
    [
        ("Savvytec Co", "Savvytec Trading"),
        ("Acme Co", "Acme Holdings"),
        ("Blu Horizon Capital", "Blue Horizon Capital Group"),
        ("FLOW Intelligence", "Flow Intelligence Ltd"),
        ("NXI GmbH & Co. KG", "NXI GmbH"),
        # Nothing distinctive on either side: falls back to the full names.
        ("Capital Group", "Capital Group Ltd"),
    ],
)
def test_the_same_company_still_matches(lead: str, org: str) -> None:
    assert names_similar(lead, org)
