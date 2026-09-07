"""Pins the exact SOURCE Attio attribute slugs each params-mapper reads.

These mappers used to try a DEV slug first and fall back to SOURCE's, from
when two workspaces had to be supported. The DEV workspace is retired and
every one of those first branches was verified absent from SOURCE's live
attribute lists (2026-09-07), so they are gone -- these tests are what stops
a mapper drifting off the slug that actually exists."""

from app.modules.ddl_commands.persistence.attio_sync import (
    _organization_params,
    _person_params,
    _seller_role_params,
)


def _item(**kwargs) -> dict:
    return {"active_until": None, **kwargs}


def test_organization_params_reads_the_source_slugs() -> None:
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


def test_organization_params_ignores_the_retired_stage_slug() -> None:
    """`stage` does not exist on SOURCE's organizations object -- only
    `stage_focus` does. Reading it would resurrect a DEV-only path."""
    data = {
        "id": {"record_id": "org-1"},
        "values": {
            "stage": [_item(option={"title": "Ignored"})],
            "stage_focus": [_item(option={"title": "Growth"})],
        },
    }

    params = _organization_params(data)

    assert params["stage_focus"] == ["Growth"]


def test_person_params_reads_the_source_slugs() -> None:
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


def test_person_params_ignores_the_multi_valued_email_shape() -> None:
    """SOURCE's person object has a single plain `email` text field; Attio's
    multi-valued `email_addresses` type is not on it."""
    data = {
        "id": {"record_id": "person-1"},
        "values": {
            "email_addresses": [_item(email_address="ignored@example.com")],
            "email": [_item(value="real@example.com")],
        },
    }

    params = _person_params(data)

    assert params["email"] == ["real@example.com"]


def test_person_params_email_is_empty_when_absent() -> None:
    params = _person_params({"id": {"record_id": "person-1"}, "values": {}})

    assert params["email"] == []


def test_seller_role_params_reads_the_source_slug() -> None:
    entry = {"entry_values": {"appetite_signal": [_item(option={"title": "Hot"})]}}

    params = _seller_role_params("org-1", entry, is_active=True)

    assert params["appetite_signal"] == "Hot"
