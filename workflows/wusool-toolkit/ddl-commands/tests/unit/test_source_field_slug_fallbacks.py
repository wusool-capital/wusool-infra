"""Covers the field-slug mismatches found while auditing SOURCE Attio's
custom objects against DEV Attio's native ones -- the same class of bug as
`test_deal_params.py`'s deal_name/deal_stage/deal_owner, found by diffing a
real SOURCE record's actual field list against what upsert.py maps."""

from ddl_commands.modules.attio_sync.upsert import (
    _organization_params,
    _person_params,
    _seller_role_params,
)


def _item(**kwargs) -> dict:
    return {"active_until": None, **kwargs}


def test_organization_params_falls_back_to_source_slugs() -> None:
    data = {
        "id": {"record_id": "org-1"},
        "values": {
            "stage_focus": [_item(option={"title": "Growth"})],
            "connection_strength": [_item(option={"title": "Strong"})],
        },
    }

    params = _organization_params(data)

    assert params["stage_focus"] == ["Growth"]
    assert params["connection_strength"] == "Strong"


def test_organization_params_joins_multiple_client_type_values() -> None:
    """client_type is multi-select on SOURCE Attio; Postgres's column is
    plain text (not an array), so every selected value must be comma-joined
    rather than only the first surviving."""
    data = {
        "id": {"record_id": "org-1"},
        "values": {
            "client_type": [
                _item(option={"title": "Fundraising"}),
                _item(option={"title": "M&A"}),
            ],
        },
    }

    params = _organization_params(data)

    assert params["client_type"] == "Fundraising, M&A"


def test_organization_params_client_type_none_when_absent() -> None:
    data = {"id": {"record_id": "org-1"}, "values": {}}

    params = _organization_params(data)

    assert params["client_type"] is None


def test_organization_params_prefers_dev_slugs_when_both_present() -> None:
    data = {
        "id": {"record_id": "org-1"},
        "values": {
            "stage": [_item(option={"title": "DEV Stage"})],
            "stage_focus": [_item(option={"title": "SOURCE Stage"})],
        },
    }

    params = _organization_params(data)

    assert params["stage_focus"] == ["DEV Stage"]


def test_person_params_falls_back_to_source_slugs() -> None:
    data = {
        "id": {"record_id": "person-1"},
        "values": {
            "connection_strength": [_item(option={"title": "Warm"})],
            "email": [_item(value="test@example.com")],
        },
    }

    params = _person_params(data)

    assert params["connection_strength"] == "Warm"
    assert params["email"] == ["test@example.com"]


def test_person_params_prefers_dev_email_shape_when_present() -> None:
    data = {
        "id": {"record_id": "person-1"},
        "values": {
            "email_addresses": [_item(email_address="dev@example.com")],
            "email": [_item(value="source@example.com")],
        },
    }

    params = _person_params(data)

    assert params["email"] == ["dev@example.com"]


def test_seller_role_params_falls_back_to_source_slug() -> None:
    entry = {"entry_values": {"appetite_signal": [_item(option={"title": "Hot"})]}}

    params = _seller_role_params("org-1", entry, is_active=True)

    assert params["appetite_signal"] == "Hot"
