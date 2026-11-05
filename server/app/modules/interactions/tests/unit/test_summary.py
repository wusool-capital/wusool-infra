from datetime import timedelta

from app.modules.interactions.domain.model import Channel, Role, ScoringRules, StrengthLabel
from app.modules.interactions.domain.summary import summarize
from app.modules.interactions.tests.fakes.touches import (
    JULES,
    NOW,
    RAMZY,
    email_received,
    email_sent,
    meeting,
)

RULES = ScoringRules()


def test_no_past_touches_leaves_every_field_empty() -> None:
    summary = summarize([], NOW, RULES)

    assert summary.last_interaction_at is None
    assert summary.connection_strength is None
    assert summary.strongest_connection_user is None
    assert summary.score == 0.0


def test_email_and_meeting_dates_are_split_by_channel() -> None:
    touches = [email_sent(30), email_received(5), meeting(10), meeting(40)]

    summary = summarize(touches, NOW, RULES)

    assert summary.first_interaction_at == NOW - timedelta(days=40)
    assert summary.last_interaction_at == NOW - timedelta(days=5)
    assert summary.first_email_interaction_at == NOW - timedelta(days=30)
    assert summary.last_email_interaction_at == NOW - timedelta(days=5)
    assert summary.first_calendar_interaction_at == NOW - timedelta(days=40)
    assert summary.last_calendar_interaction_at == NOW - timedelta(days=10)


def test_next_interaction_is_the_soonest_meeting_inside_the_window() -> None:
    touches = [meeting(-3), meeting(-20), meeting(-181), email_sent(1)]

    summary = summarize(touches, NOW, RULES)

    assert summary.next_interaction_at == NOW + timedelta(days=3)
    assert summary.next_calendar_interaction_at == NOW + timedelta(days=3)


def test_a_future_meeting_is_not_a_past_interaction() -> None:
    summary = summarize([meeting(-3)], NOW, RULES)

    assert summary.last_interaction_at is None
    assert summary.next_interaction_at == NOW + timedelta(days=3)


def test_last_interaction_reports_its_channel_and_subject() -> None:
    touches = [email_sent(20, subject="Older"), meeting(2, subject="Board call")]

    summary = summarize(touches, NOW, RULES)

    assert summary.last_interaction_channel is Channel.MEETING
    assert summary.last_interaction_subject == "Board call"


def test_the_sender_owns_an_email_that_also_reached_a_teammate_by_cc() -> None:
    touches = [
        email_sent(1, key="m1", member=JULES, role=Role.CC),
        email_sent(1, key="m1", member=RAMZY, role=Role.FROM),
    ]

    assert summarize(touches, NOW, RULES).last_interaction_owner == RAMZY


def test_to_beats_cc_when_the_contact_wrote_to_several_of_us() -> None:
    touches = [
        email_received(1, key="m1", member=JULES, role=Role.CC),
        email_received(1, key="m1", member=RAMZY, role=Role.TO),
    ]

    assert summarize(touches, NOW, RULES).last_interaction_owner == RAMZY


def test_a_remaining_tie_goes_to_the_stronger_pair() -> None:
    touches = [
        email_received(1, key="m1", member=JULES, role=Role.TO),
        email_received(1, key="m1", member=RAMZY, role=Role.TO),
        meeting(30, member=RAMZY),
    ]

    assert summarize(touches, NOW, RULES).last_interaction_owner == RAMZY


def test_strongest_user_and_label_come_from_the_best_pair() -> None:
    touches = [
        meeting(5, member=JULES),
        email_sent(5, member=JULES),
        email_received(6, member=JULES),
        email_sent(400, member=RAMZY),
    ]

    summary = summarize(touches, NOW, RULES)

    assert summary.strongest_connection_user == JULES
    assert summary.connection_strength is StrengthLabel.STRONG


def test_an_organization_takes_the_best_pair_across_its_contacts() -> None:
    touches = [
        email_sent(1, contact="a@acme.com"),
        meeting(1, contact="b@acme.com", member=RAMZY),
    ]

    assert summarize(touches, NOW, RULES).strongest_connection_user == RAMZY
