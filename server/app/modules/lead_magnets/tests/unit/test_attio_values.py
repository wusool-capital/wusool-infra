"""`_values`'s money serialisation, across both tables it now serves.

`serialize_money`'s currency lookup is keyed on `(table, field)` — a
`buyer_role` money field serialised against the `seller_role` table (or vice
versa) raises `UnknownMoneyFieldError` rather than silently mislabelling the
currency, which is exactly the failure this pins: `buyer_values` passing the
wrong table name would 500 every buyer submission that gave a check size.
"""

import pytest

from app.modules.attio.providers.attio.money import UnknownMoneyFieldError
from app.modules.lead_magnets.domain.shared.attio_values import buyer_values, readiness_values


def test_buyer_check_size_serialises_against_the_buyer_role_table() -> None:
    values = buyer_values(
        check_size_min=1_000_000,
        check_size_max=5_000_000,
        prior_gcc_acquisition="One deal in 2023",
        target_geography=["UAE", "KSA"],
    )
    assert values["check_size_min"] == {"currency_value": 1_000_000.0}
    assert values["check_size_max"] == {"currency_value": 5_000_000.0}
    assert values["target_geography"] == ["UAE", "KSA"]
    assert values["prior_gcc_acquisition"] == "One deal in 2023"


def test_buyer_values_omits_none_rather_than_clearing_the_field() -> None:
    values = buyer_values(
        check_size_min=None,
        check_size_max=None,
        prior_gcc_acquisition=None,
        target_geography=[],
    )
    assert values == {}


def test_buyer_values_carries_the_qualification_note_into_acquisition_enrichment() -> None:
    values = buyer_values(
        check_size_min=None,
        check_size_max=None,
        prior_gcc_acquisition=None,
        target_geography=[],
        qualification_note="Warm mandate, introduce now.",
    )
    assert values["acquisition_enrichment"] == "Warm mandate, introduce now."


def test_an_unconfigured_table_field_pair_still_raises() -> None:
    """The guard `_values`'s `table` parameter exists to preserve: a money
    field with no configured currency for its table fails loudly rather than
    writing an unlabelled amount. `est_revenue` is a real `seller_role`
    money field with no `buyer_role` entry."""
    from app.modules.lead_magnets.domain.shared.attio_values import _BUYER_MONEY, _values

    with pytest.raises(UnknownMoneyFieldError):
        _values({"est_revenue": 1.0}, table="buyer_role", money=_BUYER_MONEY | {"est_revenue"})


def test_readiness_values_is_unaffected_by_the_table_parameter() -> None:
    """The refactor's default (`table="seller_role"`) must reproduce the
    pre-existing behaviour for every caller that does not pass one."""
    from app.modules.lead_magnets.domain.readiness.readiness import AdvisoryContent

    values = readiness_values(
        score=72.5,
        band="Getting There",
        advisory=AdvisoryContent(referral=None, advisory_note=None),
        revenue_usd=1_000_000,
    )
    assert values["est_revenue"] == {"currency_value": 1_000_000.0}
