from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.auth.providers import slack_identity


def _bot_returning(user: dict[str, bool]) -> SimpleNamespace:
    return SimpleNamespace(users_info=AsyncMock(return_value={"user": user}))


@pytest.mark.parametrize(
    ("user", "allow_guests", "expected"),
    [
        ({"deleted": False}, False, True),
        ({"deleted": True}, True, False),
        ({"is_restricted": True}, True, True),
        ({"is_restricted": True}, False, False),
    ],
)
async def test_member_check_refuses_leavers_and_optionally_guests(
    monkeypatch: pytest.MonkeyPatch, user: dict[str, bool], allow_guests: bool, expected: bool
) -> None:
    monkeypatch.setattr(slack_identity, "_bot", lambda: _bot_returning(user))

    assert await slack_identity.is_active_member("U1", allow_guests=allow_guests) is expected
