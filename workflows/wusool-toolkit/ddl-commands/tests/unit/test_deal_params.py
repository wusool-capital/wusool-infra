from ddl_commands.modules.attio_sync.upsert import _deal_params


def _item(**kwargs) -> dict:
    return {"active_until": None, **kwargs}


def test_deal_params_falls_back_to_source_slugs() -> None:
    """SOURCE Attio's custom "deal" object uses deal_name/deal_stage/
    deal_owner instead of DEV's native name/stage/owner -- confirmed against
    a real SOURCE record's field list, 2026-08-31."""
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


def test_deal_params_prefers_dev_slugs_when_both_present() -> None:
    data = {
        "id": {"record_id": "deal-1"},
        "values": {
            "name": [_item(value="DEV Name")],
            "deal_name": [_item(value="SOURCE Name")],
        },
    }

    params = _deal_params(data)

    assert params["name"] == "DEV Name"


def test_deal_params_falls_back_to_placeholder_when_neither_slug_present() -> None:
    data = {"id": {"record_id": "deal-1"}, "values": {}}

    params = _deal_params(data)

    assert params["name"] == "Unnamed DEV Deal [deal-1]"
