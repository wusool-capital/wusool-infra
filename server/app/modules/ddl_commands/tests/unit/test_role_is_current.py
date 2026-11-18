"""`is_current` is the one definition of "a role to show": active and not removed."""

from datetime import UTC, datetime

import pytest

from app.models import BuyerRole, SellerRole

_GONE = datetime(2026, 11, 18, tzinfo=UTC)


@pytest.mark.parametrize("model", [BuyerRole, SellerRole])
@pytest.mark.parametrize(
    ("is_active", "removed_at", "expected"),
    [
        (True, None, True),
        (False, None, False),
        (None, None, False),
        (True, _GONE, False),  # Attio deleted it; the resync has not run yet
        (False, _GONE, False),
    ],
)
def test_a_role_is_current_only_when_active_and_not_removed(
    model: type[BuyerRole] | type[SellerRole],
    is_active: bool | None,
    removed_at: datetime | None,
    expected: bool,
) -> None:
    role = model(org_attio_id="org-1", is_active=is_active, removed_at=removed_at)

    assert role.is_current is expected
