"""NULL is normal (see the Phase 2 plan §4): proves the ORM layer tolerates
real NULLs on sparse buyer_roles money columns without raising.
"""

from app.models import BuyerRole


async def test_buyer_role_money_fields_may_be_none(any_buyer_role: BuyerRole) -> None:
    # No assertion on the value itself — None is a legitimate, expected state.
    # This test's purpose is that accessing the attribute never raises.
    _ = any_buyer_role.check_size_min
    _ = any_buyer_role.ebitda_floor
    _ = any_buyer_role.ev_ceiling
