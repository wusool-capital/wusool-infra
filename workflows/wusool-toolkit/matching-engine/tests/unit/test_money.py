import pytest
from pydantic import ValidationError

from app.shared.types import Money


def test_populated_money_requires_usd_currency() -> None:
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": 60_000_000, "currency": "AED"})


def test_populated_money_requires_currency() -> None:
    with pytest.raises(ValidationError):
        Money(amount=60_000_000)


def test_empty_money_remains_allowed_for_nullable_crm_fields() -> None:
    assert Money() == Money(amount=None, currency=None)
