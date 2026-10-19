import re
from dataclasses import fields

import pytest

from app.models import Activity
from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivitySource,
    ActorType,
    EventType,
    SubjectType,
)
from app.modules.activities.domain.event import _LEDGER_LINKS

_EVENT_TYPE_FORMAT = re.compile(r"^[a-z_]+[.][a-z_]+$")


def _check_values(constraint_name: str) -> set[str]:
    for constraint in Activity.__table__.constraints:
        if constraint.name == constraint_name:
            return set(re.findall(r"'([^']+)'", str(constraint.sqltext)))
    raise AssertionError(f"{constraint_name} not on the Activity model")


def test_every_event_type_matches_the_database_format() -> None:
    assert all(_EVENT_TYPE_FORMAT.match(e.value) for e in EventType)


def test_actor_types_match_the_model_check() -> None:
    assert {a.value for a in ActorType} == _check_values("activities_actor_type_check")


def test_subject_types_match_the_model_check() -> None:
    assert {s.value for s in SubjectType} == _check_values("activities_subject_type_check")


def test_ledger_links_match_activity_columns_and_check() -> None:
    event_fields = {f.name for f in fields(ActivityEvent)}
    columns = {c.name for c in Activity.__table__.columns}
    assert set(_LEDGER_LINKS) <= event_fields
    assert set(_LEDGER_LINKS) <= columns
    check = str(
        next(
            c.sqltext
            for c in Activity.__table__.constraints
            if c.name == "activities_single_ledger_link"
        )
    )
    assert all(name in check for name in _LEDGER_LINKS)


def test_event_needs_a_subject() -> None:
    with pytest.raises(ValueError, match="subject"):
        ActivityEvent(
            subject_type=SubjectType.PERSON,
            event_type=EventType.CRM_RECORD_UPDATED,
            source=ActivitySource.ATTIO_WEBHOOK,
            actor=ActivityActor.system("test"),
        )


def test_event_links_at_most_one_ledger_row() -> None:
    from uuid import uuid4

    with pytest.raises(ValueError, match="at most one"):
        ActivityEvent(
            subject_type=SubjectType.PERSON,
            event_type=EventType.CRM_RECORD_UPDATED,
            source=ActivitySource.ATTIO_WEBHOOK,
            actor=ActivityActor.system("test"),
            subject_attio_id="p-1",
            tool_run_id=uuid4(),
            meeting_id=uuid4(),
        )


@pytest.mark.parametrize(
    ("attio_type", "expected"),
    [
        ("workspace-member", ActorType.ATTIO_MEMBER),
        ("api-token", ActorType.ATTIO_API_TOKEN),
        ("system", ActorType.ATTIO_SYSTEM),
        (None, ActorType.UNKNOWN),
        ("something-new", ActorType.UNKNOWN),
    ],
)
def test_attio_actor_mapping(attio_type: str | None, expected: ActorType) -> None:
    assert ActivityActor.attio(attio_type, "id-1").type is expected


def test_only_attio_members_carry_a_users_fk_value() -> None:
    assert ActivityActor.attio("workspace-member", "m1").attio_member_id == "m1"
    assert ActivityActor.attio("api-token", "t1").attio_member_id is None
    assert ActivityActor.slack("U1").attio_member_id is None
    assert ActivityActor.slack(None).type is ActorType.UNKNOWN
