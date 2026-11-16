from datetime import UTC, datetime

from app.modules.ddl_commands.persistence.attio_sync import (
    _deal_batch_params,
    _deal_params,
    _organization_batch_params,
    _organization_params,
    _person_batch_params,
    _person_params,
)


def _item(**kwargs: str | dict[str, str] | None) -> dict[str, str | dict[str, str] | None]:
    return {"active_until": None, **kwargs}


_TIMESTAMP_SLUGS = (
    "first_interaction_at",
    "next_interaction_at",
    "first_email_interaction_at",
    "last_email_interaction_at",
    "first_calendar_interaction_at",
    "last_calendar_interaction_at",
    "next_calendar_interaction_at",
)


def _record() -> dict:
    values = {slug: [_item(value="2026-11-01T09:30:00+00:00")] for slug in _TIMESTAMP_SLUGS}
    values["last_interaction_channel"] = [_item(option={"title": "Email"})]
    values["last_interaction_subject"] = [_item(value="Intro call")]
    values["last_interaction_owner"] = [_item(referenced_actor_id="user-1")]
    values["strongest_connection_user"] = [_item(referenced_actor_id="user-2")]
    return {"id": {"record_id": "rec-1"}, "values": values}


def test_organization_params_map_the_interaction_fields() -> None:
    params = _organization_params(_record())

    for slug in _TIMESTAMP_SLUGS:
        assert params[slug] == datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
    assert params["last_interaction_channel"] == "Email"
    assert params["last_interaction_subject"] == "Intro call"
    assert params["last_interaction_owner"] == "user-1"
    assert params["strongest_connection_user"] == "user-2"


def test_person_params_map_the_interaction_fields() -> None:
    params = _person_params(_record())

    for slug in _TIMESTAMP_SLUGS:
        assert params[slug] == datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
    assert params["last_interaction_channel"] == "Email"
    assert params["last_interaction_subject"] == "Intro call"
    assert params["last_interaction_owner"] == "user-1"
    assert params["strongest_connection_user"] == "user-2"


def test_interaction_fields_absent_map_to_none() -> None:
    params = _organization_params({"id": {"record_id": "rec-1"}, "values": {}})

    for slug in (*_TIMESTAMP_SLUGS, "last_interaction_channel", "last_interaction_owner"):
        assert params[slug] is None


def test_batch_params_drop_unknown_interaction_actors() -> None:
    """The nightly batch path can't use the SQL users guard, so unknown actors must be nulled."""
    org = _organization_batch_params(_record(), user_ids={"user-1"})
    person = _person_batch_params(_record(), org_ids=set(), user_ids={"user-2"})

    assert org["last_interaction_owner"] == "user-1"
    assert org["strongest_connection_user"] is None
    assert person["last_interaction_owner"] is None
    assert person["strongest_connection_user"] == "user-2"


def test_person_params_map_lead_source() -> None:
    """AZM-159 PR 5: people are tagged like organizations."""
    record = _record()
    record["values"]["lead_source"] = [_item(option={"title": "Inbound"})]
    record["values"]["lead_source_detail"] = [_item(option={"title": "Email sync"})]

    params = _person_params(record)

    assert params["lead_source"] == "Inbound"
    assert params["lead_source_detail"] == "Email sync"


def _deal_record() -> dict:
    values = {
        "last_interaction_at": [_item(value="2026-11-01T09:30:00+00:00")],
        "next_interaction_at": [_item(value="2026-11-20T08:00:00+00:00")],
        "last_interaction_subject": [_item(value="Term sheet")],
        "last_interaction_owner": [_item(referenced_actor_id="user-1")],
        "connection_strength": [_item(option={"title": "Strong"})],
    }
    return {"id": {"record_id": "deal-1"}, "values": values}


def test_deal_params_map_the_interaction_rollup() -> None:
    """AZM-159 PR 6: the deal's rollup fields are mirrored like the organization's."""
    params = _deal_params(_deal_record())

    assert params["last_interaction_at"] == datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
    assert params["next_interaction_at"] == datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
    assert params["last_interaction_subject"] == "Term sheet"
    assert params["last_interaction_owner"] == "user-1"
    assert params["connection_strength"] == "Strong"


def test_deal_batch_params_drop_an_unknown_interaction_owner() -> None:
    known = _deal_batch_params(_deal_record(), set(), set(), {"user-1"})
    unknown = _deal_batch_params(_deal_record(), set(), set(), set())

    assert known["last_interaction_owner"] == "user-1"
    assert unknown["last_interaction_owner"] is None
