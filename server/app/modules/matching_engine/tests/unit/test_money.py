import pytest

from app.modules.utilities.domain.money import Money


def test_populated_money_requires_usd_currency() -> None:
    # Deliberately violates the `Literal["USD"]` type hint -- Money's
    # `__post_init__` is the runtime backstop for exactly this, since
    # nothing stops a caller from ignoring the static type.
    with pytest.raises(ValueError, match="USD"):
        Money(amount=60_000_000, currency="AED")  # ty: ignore[invalid-argument-type]


def test_populated_money_requires_currency() -> None:
    with pytest.raises(ValueError, match="USD"):
        Money(amount=60_000_000)


def test_empty_money_remains_allowed_for_nullable_crm_fields() -> None:
    assert Money() == Money(amount=None, currency=None)
