import pytest

import app.modules.attio.providers.attio.options as options_module
from app.modules.attio.providers.attio.options import OptionNotFoundError, get_option_id


@pytest.fixture(autouse=True)
def _clear_option_cache():
    options_module._cache.clear()
    yield
    options_module._cache.clear()


class _FakeClient:
    def __init__(self, options: list[dict]) -> None:
        self._options = options
        self.get_calls: list[str] = []

    async def get(self, path: str) -> dict:
        self.get_calls.append(path)
        return {"data": self._options}

    async def post(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used by this test")

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used by this test")


async def test_get_option_id_matches_by_title() -> None:
    client = _FakeClient(
        [
            {"id": {"option_id": "opt-1"}, "title": "Tier 1", "is_archived": False},
            {"id": {"option_id": "opt-2"}, "title": "Tier 2", "is_archived": False},
        ]
    )

    option_id = await get_option_id(
        client,
        target_kind="lists",
        target_slug="seller_role",
        attribute_slug="outreach_tier",
        title="Tier 2",
    )

    assert option_id == "opt-2"
    assert client.get_calls == ["/lists/seller_role/attributes/outreach_tier/options"]


async def test_get_option_id_skips_archived_options() -> None:
    client = _FakeClient(
        [{"id": {"option_id": "opt-old"}, "title": "Legacy", "is_archived": True}]
    )

    with pytest.raises(OptionNotFoundError):
        await get_option_id(
            client,
            target_kind="lists",
            target_slug="seller_role",
            attribute_slug="outreach_tier",
            title="Legacy",
        )


async def test_get_option_id_raises_clearly_when_no_match() -> None:
    client = _FakeClient([{"id": {"option_id": "opt-1"}, "title": "Tier 1", "is_archived": False}])

    with pytest.raises(OptionNotFoundError, match="Nonexistent"):
        await get_option_id(
            client,
            target_kind="lists",
            target_slug="seller_role",
            attribute_slug="outreach_tier",
            title="Nonexistent",
        )
