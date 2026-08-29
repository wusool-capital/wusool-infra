from datetime import date

import pytest

import ddl_commands.shared.attio.options as options_module
from ddl_commands.shared.attio.write_payload import build_attio_values, build_postgres_values
from ddl_commands.shared.organization_field_spec import FieldSpec


@pytest.fixture(autouse=True)
def _clear_option_cache():
    options_module._cache.clear()
    yield
    options_module._cache.clear()


class _FakeClient:
    def __init__(self, options_by_slug: dict[str, list[dict]]) -> None:
        self._options_by_slug = options_by_slug

    async def get(self, path: str) -> dict:
        slug = path.removesuffix("/options").rsplit("/", 1)[-1]
        return {"data": self._options_by_slug.get(slug, [])}

    async def post(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used in this test")


_TEXT = FieldSpec("notes", "Notes", "multiline")
_SELECT = FieldSpec("outreach_tier", "Outreach tier", "select", options=("Tier 1", "Tier 2"))
_MULTI = FieldSpec("sector_focus", "Sector focus", "multi_select_text")
_DATE = FieldSpec("re_engage_date", "Re-engage date", "date")
_CURRENCY = FieldSpec("est_revenue", "Est. revenue", "currency")
_BOOL = FieldSpec("profitable_only", "Profitable only", "bool")
_NUMBER = FieldSpec("twitter_follower_count", "Twitter follower count", "number")


async def test_build_attio_values_resolves_select_to_option_id() -> None:
    client = _FakeClient(
        {
            "outreach_tier": [
                {"id": {"option_id": "opt-tier-1"}, "title": "Tier 1", "is_archived": False}
            ]
        }
    )
    result = await build_attio_values(
        client,
        target_kind="lists",
        target_slug="seller_role",
        table="seller_role",
        fields={"outreach_tier": _SELECT},
        extracted={"outreach_tier": "Tier 1"},
    )
    assert result == {"outreach_tier": [{"option": "opt-tier-1"}]}


async def test_build_attio_values_resolves_multi_select_to_option_ids() -> None:
    client = _FakeClient(
        {
            "sector_focus": [
                {"id": {"option_id": "opt-tech"}, "title": "Tech", "is_archived": False},
                {"id": {"option_id": "opt-health"}, "title": "Healthcare", "is_archived": False},
            ]
        }
    )
    result = await build_attio_values(
        client,
        target_kind="objects",
        target_slug="organizations",
        table="organizations",
        fields={"sector_focus": _MULTI},
        extracted={"sector_focus": ["Tech", "Healthcare"]},
    )
    assert result == {"sector_focus": [{"option": "opt-tech"}, {"option": "opt-health"}]}


async def test_build_attio_values_serializes_currency_without_code() -> None:
    # currency_code must NOT be in the Attio write payload — Attio rejects it
    # as an unrecognized key (the currency is fixed per-attribute in Attio's
    # own workspace config, confirmed live 2026-08-17).
    client = _FakeClient({})
    result = await build_attio_values(
        client,
        target_kind="lists",
        target_slug="seller_role",
        table="seller_role",
        fields={"est_revenue": _CURRENCY},
        extracted={"est_revenue": 500000.0},
    )
    assert result == {"est_revenue": {"currency_value": 500000.0}}


async def test_build_attio_values_serializes_plain_date() -> None:
    client = _FakeClient({})
    result = await build_attio_values(
        client,
        target_kind="lists",
        target_slug="seller_role",
        table="seller_role",
        fields={"re_engage_date": _DATE},
        extracted={"re_engage_date": date(2026, 6, 1)},
    )
    assert result == {"re_engage_date": "2026-06-01"}


async def test_build_attio_values_skips_none_fields() -> None:
    client = _FakeClient({})
    result = await build_attio_values(
        client,
        target_kind="lists",
        target_slug="seller_role",
        table="seller_role",
        fields={"notes": _TEXT},
        extracted={"notes": None},
    )
    assert result == {}


async def test_build_attio_values_passes_bool_through() -> None:
    client = _FakeClient({})
    result = await build_attio_values(
        client,
        target_kind="lists",
        target_slug="buyer_role",
        table="buyer_role",
        fields={"profitable_only": _BOOL},
        extracted={"profitable_only": True},
    )
    assert result == {"profitable_only": True}


async def test_build_attio_values_passes_number_through() -> None:
    client = _FakeClient({})
    result = await build_attio_values(
        client,
        target_kind="objects",
        target_slug="organizations",
        table="organizations",
        fields={"twitter_follower_count": _NUMBER},
        extracted={"twitter_follower_count": 1200},
    )
    assert result == {"twitter_follower_count": 1200}


def test_build_postgres_values_wraps_currency_with_fixed_code() -> None:
    result = build_postgres_values(
        table="seller_role", fields={"est_revenue": _CURRENCY}, extracted={"est_revenue": 250.0}
    )
    assert result == {"est_revenue": {"amount": 250.0, "currency": "USD"}}


def test_build_postgres_values_passes_non_currency_through() -> None:
    result = build_postgres_values(
        table="seller_role",
        fields={"outreach_tier": _SELECT},
        extracted={"outreach_tier": "Tier 1"},
    )
    assert result == {"outreach_tier": "Tier 1"}


def test_build_postgres_values_none_currency_stays_none() -> None:
    result = build_postgres_values(
        table="seller_role", fields={"est_revenue": _CURRENCY}, extracted={"est_revenue": None}
    )
    assert result == {"est_revenue": None}


def test_build_postgres_values_passes_bool_through_unchanged() -> None:
    """#53 made `earnout_tolerance` a real boolean column; it used to be text,
    and this function stringified it on the way in. Nothing reshapes a bool now.
    """
    result = build_postgres_values(
        table="buyer_role",
        fields={"earnout_tolerance": _BOOL},
        extracted={"earnout_tolerance": True},
    )
    assert result == {"earnout_tolerance": True}


def test_build_postgres_values_passes_number_through_unchanged() -> None:
    result = build_postgres_values(
        table="organizations",
        fields={"twitter_follower_count": _NUMBER},
        extracted={"twitter_follower_count": 1200},
    )
    assert result == {"twitter_follower_count": 1200}
