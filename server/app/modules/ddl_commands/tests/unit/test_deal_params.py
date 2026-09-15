from datetime import timedelta

from app.modules.ddl_commands.persistence.attio_sync import _deal_params


def _item(**kwargs) -> dict:
    return {"active_until": None, **kwargs}


def test_deal_params_reads_the_prefixed_slugs() -> None:
    """Deal_V2 prefixes these: deal_name/deal_stage/deal_owner/deal_value,
    with no unprefixed equivalent on the object. Verified against its full
    attribute list, 2026-09-07."""
    data = {
        "id": {"record_id": "deal-1"},
        "values": {
            "deal_name": [_item(value="Revival")],
            "deal_stage": [_item(status={"title": "Diligence"})],
            "deal_owner": [_item(referenced_actor_id="user-1")],
        },
    }

    params = _deal_params(data)

    assert params["name"] == "Revival"
    assert params["stage"] == "Diligence"
    assert params["owner_attio_id"] == "user-1"


def test_deal_params_ignores_the_unprefixed_slugs() -> None:
    """`name` is the legacy standard `deals` object's slug. That object is
    out of this sync's scope entirely -- it has no `is_test` attribute, so
    its records could never be assigned to an environment."""
    data = {
        "id": {"record_id": "deal-1"},
        "values": {
            "name": [_item(value="Ignored")],
            "deal_name": [_item(value="Revival")],
        },
    }

    params = _deal_params(data)

    assert params["name"] == "Revival"


def test_deal_params_falls_back_to_placeholder_when_unnamed() -> None:
    data = {"id": {"record_id": "deal-1"}, "values": {}}

    params = _deal_params(data)

    assert params["name"] == "Unnamed Deal [deal-1]"


def test_deal_params_converts_time_in_stage_days_to_an_interval() -> None:
    """Attio's attribute is "Time In Stage (Days)", a plain number, while the
    Postgres column is an interval. Binding the bare number would be read as
    microseconds, so 12 days would silently land as 12 microseconds."""
    data = {
        "id": {"record_id": "deal-1"},
        "values": {
            "deal_name": [_item(value="Deal X")],
            "time_in_stage": [_item(value=12)],
        },
    }

    params = _deal_params(data)

    assert params["time_in_stage"] == timedelta(days=12)


def test_deal_params_leaves_time_in_stage_null_when_absent() -> None:
    """A deal that has never changed stage has no value in Attio; it must stay
    NULL rather than becoming a zero-length interval, which would read as
    "arrived in this stage just now"."""
    data = {"id": {"record_id": "deal-1"}, "values": {"deal_name": [_item(value="Deal X")]}}

    assert _deal_params(data)["time_in_stage"] is None


def test_deal_params_accepts_a_fractional_day_count() -> None:
    """The Attio attribute is a number, not an integer -- a deal that moved
    stage hours ago carries a fraction."""
    data = {
        "id": {"record_id": "deal-1"},
        "values": {
            "deal_name": [_item(value="Deal X")],
            "time_in_stage": [_item(value=1.5)],
        },
    }

    assert _deal_params(data)["time_in_stage"] == timedelta(hours=36)
