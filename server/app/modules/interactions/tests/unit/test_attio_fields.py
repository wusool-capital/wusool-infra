from datetime import UTC, datetime

from app.modules.interactions.domain.attio_fields import (
    FIELDS,
    FieldValue,
    canonical_timestamp,
    fields_for,
    plan_record,
)
from app.modules.interactions.domain.model import Channel, InteractionSummary, StrengthLabel

READ = frozenset({"m-jules", "m-ramzy"})
EARLY, MID, LATE = (
    "2025-01-01T00:00:00.000+00:00",
    "2026-03-01T00:00:00.000+00:00",
    "2026-10-01T00:00:00.000+00:00",
)


def _written(plan) -> dict[str, str]:
    return {w.slug: w.value for w in plan.writes}


def test_there_are_thirteen_fields() -> None:
    assert len(FIELDS) == 13


def test_attios_own_timestamp_form_and_a_datetime_agree() -> None:
    attio = canonical_timestamp("2023-11-25T15:21:06.447000000Z")
    ours = canonical_timestamp(datetime(2023, 11, 25, 15, 21, 6, 447000, tzinfo=UTC))

    assert attio == ours == "2023-11-25T15:21:06.447+00:00"


def test_a_naive_datetime_is_read_as_utc() -> None:
    assert canonical_timestamp(datetime(2026, 1, 2, 3, 4, 5)) == "2026-01-02T03:04:05.000+00:00"


def test_fields_for_maps_channel_label_and_owner_to_what_attio_expects() -> None:
    summary = InteractionSummary(
        first_interaction_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_interaction_at=datetime(2026, 2, 1, tzinfo=UTC),
        next_interaction_at=None,
        first_email_interaction_at=None,
        last_email_interaction_at=None,
        first_calendar_interaction_at=None,
        last_calendar_interaction_at=None,
        next_calendar_interaction_at=None,
        last_interaction_channel=Channel.MEETING,
        last_interaction_owner="jules@wusoolcapital.com",
        last_interaction_subject="Board call",
        strongest_connection_user="ramzy@wusoolcapital.com",
        connection_strength=StrengthLabel.STRONG,
        score=9.0,
    )

    fields = fields_for(summary, {"jules@wusoolcapital.com": "m-jules"})

    assert fields["last_interaction_channel"] == "Meeting"
    assert fields["connection_strength"] == "Strong"
    assert fields["last_interaction_owner"] == "m-jules"
    assert fields["strongest_connection_user"] is None
    assert fields["next_interaction_at"] is None


def test_a_first_date_only_moves_earlier() -> None:
    plan = plan_record(
        computed={"first_interaction_at": MID},
        sent={"first_interaction_at": EARLY},
        baseline={},
        read_member_ids=READ,
    )

    assert "first_interaction_at" not in _written(plan)


def test_a_first_date_takes_the_baselines_earlier_value() -> None:
    plan = plan_record(
        computed={"first_interaction_at": MID},
        sent={},
        baseline={"first_interaction_at": EARLY},
        read_member_ids=READ,
    )

    assert _written(plan) == {"first_interaction_at": EARLY}


def test_a_last_date_never_moves_backwards() -> None:
    plan = plan_record(
        computed={"last_interaction_at": MID},
        sent={"last_interaction_at": LATE},
        baseline={},
        read_member_ids=READ,
    )

    assert "last_interaction_at" not in _written(plan)


def test_channel_subject_and_owner_follow_a_newer_computed_last_interaction() -> None:
    plan = plan_record(
        computed={
            "last_interaction_at": LATE,
            "last_interaction_channel": "Email",
            "last_interaction_subject": "Hello",
            "last_interaction_owner": "m-jules",
        },
        sent={"last_interaction_at": MID, "last_interaction_channel": "Meeting"},
        baseline={},
        read_member_ids=READ,
    )

    assert _written(plan) == {
        "last_interaction_at": LATE,
        "last_interaction_channel": "Email",
        "last_interaction_subject": "Hello",
        "last_interaction_owner": "m-jules",
    }


def test_channel_and_subject_stay_when_the_last_interaction_is_older_than_known() -> None:
    plan = plan_record(
        computed={
            "last_interaction_at": MID,
            "last_interaction_channel": "Email",
            "last_interaction_subject": "Old",
        },
        sent={
            "last_interaction_at": LATE,
            "last_interaction_channel": "Meeting",
            "last_interaction_subject": "Newer",
        },
        baseline={},
        read_member_ids=READ,
    )

    assert plan.writes == ()


def test_a_next_date_that_disappears_is_counted_not_cleared() -> None:
    plan = plan_record(
        computed={"next_interaction_at": None},
        sent={"next_interaction_at": LATE},
        baseline={},
        read_member_ids=READ,
    )

    assert (plan.writes, plan.clears_skipped) == ((), 1)


def test_strength_is_left_alone_when_attios_strongest_user_is_an_unread_mailbox() -> None:
    plan = plan_record(
        computed={"connection_strength": "Weak", "strongest_connection_user": "m-jules"},
        sent={"connection_strength": "Strong", "strongest_connection_user": "m-hugo"},
        baseline={"strongest_connection_user": "m-hugo"},
        read_member_ids=READ,
    )

    assert plan.writes == ()


def test_strength_is_written_when_attios_strongest_user_is_a_read_mailbox() -> None:
    plan = plan_record(
        computed={"connection_strength": "Weak", "strongest_connection_user": "m-jules"},
        sent={"connection_strength": "Strong", "strongest_connection_user": "m-jules"},
        baseline={"strongest_connection_user": "m-jules"},
        read_member_ids=READ,
    )

    assert _written(plan) == {"connection_strength": "Weak"}


def test_nothing_is_written_when_computed_matches_what_attio_holds() -> None:
    same = {
        "first_interaction_at": EARLY,
        "last_interaction_at": LATE,
        "connection_strength": "Good",
        "strongest_connection_user": "m-jules",
    }

    plan = plan_record(computed=same, sent=same, baseline={}, read_member_ids=READ)

    assert (plan.writes, plan.clears_skipped) == ((), 0)


def test_a_record_with_no_sent_values_gets_every_computed_field() -> None:
    plan = plan_record(
        computed={"last_interaction_at": LATE, "connection_strength": "Weak"},
        sent={},
        baseline={},
        read_member_ids=READ,
    )

    assert set(w.slug for w in plan.writes) == {"last_interaction_at", "connection_strength"}
    assert FieldValue("connection_strength", "Weak") in plan.writes
