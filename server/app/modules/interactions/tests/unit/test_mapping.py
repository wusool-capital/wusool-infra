from dataclasses import replace
from datetime import UTC, datetime

from app.modules.google_workspace import Attendee
from app.modules.interactions.application.mapping import email_to_item, event_to_item
from app.modules.interactions.domain.model import Channel, Direction, Role
from app.modules.interactions.tests.fakes.ingest import INTERNAL, event, message
from app.modules.interactions.tests.fakes.touches import JULES, RAMZY, SARA


def _email(**kwargs):
    return email_to_item(JULES, message(**kwargs), INTERNAL)


def _roles(item) -> set[tuple[str, Role]]:
    return {(p.email, p.role) for p in item.participants}


def test_mail_from_an_outsider_is_inbound_and_keeps_every_address_with_its_role() -> None:
    item = _email(sender=SARA, to=(JULES,), cc=("legal@acme.com",))

    assert item is not None
    assert (item.channel, item.direction) == (Channel.EMAIL, Direction.INBOUND)
    assert _roles(item) == {
        (SARA, Role.FROM),
        (JULES, Role.TO),
        ("legal@acme.com", Role.CC),
    }


def test_mail_sent_by_a_team_member_is_outbound_even_through_the_alias_domain() -> None:
    item = _email(sender="jules@dopaminecap.com", to=(SARA,))

    assert item is not None
    assert item.direction is Direction.OUTBOUND
    assert (JULES, Role.FROM) in _roles(item)


def test_team_aliases_fold_into_one_address() -> None:
    item = _email(sender=SARA, to=("ramzy@dopaminecap.com", RAMZY))

    assert item is not None
    assert _roles(item) == {(SARA, Role.FROM), (RAMZY, Role.TO)}


def test_an_address_in_two_roles_is_kept_once_per_role() -> None:
    item = _email(sender=JULES, to=(SARA,), cc=(SARA,))

    assert item is not None
    assert _roles(item) >= {(SARA, Role.TO), (SARA, Role.CC)}


def test_the_message_id_is_the_dedupe_key_and_falls_back_to_the_gmail_id() -> None:
    assert _email(message_id="<abc@x>").dedupe_key == "<abc@x>"
    assert _email(source_id="m9", message_id=None).dedupe_key == "gmail:m9"


def test_the_row_carries_what_the_message_says() -> None:
    item = _email(source_id="m7", subject="Term sheet", days_ago=2)

    assert item is not None
    assert (item.mailbox, item.source_id, item.thread_id) == (JULES, "m7", "t-m7")
    assert item.subject == "Term sheet"
    assert item.occurred_at == datetime(2026, 11, 3, 12, tzinfo=UTC)


def test_ignored_mail_maps_to_nothing() -> None:
    assert _email(sender=RAMZY, to=(JULES,)) is None
    assert _email(labels=frozenset({"SPAM"})) is None
    assert _email(subject="Accepted: Board call") is None


def test_a_message_with_no_sender_is_treated_as_inbound() -> None:
    item = _email(sender=None, to=(JULES, SARA))

    assert item is not None
    assert item.direction is Direction.INBOUND


def _meeting(**kwargs):
    return event_to_item(JULES, event(**kwargs), INTERNAL)


def test_a_meeting_has_no_direction_and_keys_on_its_ical_uid_and_utc_start() -> None:
    item = _meeting(source_id="e1", days_from_now=3)

    assert item is not None
    assert (item.channel, item.direction, item.thread_id) == (Channel.MEETING, None, None)
    assert item.dedupe_key == "e1@google.com|2026-11-08T12:00:00+00:00"
    assert item.occurred_at == datetime(2026, 11, 8, 12, tzinfo=UTC)


def test_every_guest_and_the_organizer_is_recorded_as_an_attendee() -> None:
    item = _meeting(
        attendees=(Attendee(JULES, "accepted", True), Attendee("a@acme.com", None, False)),
        organizer="boss@acme.com",
    )

    assert item is not None
    assert {p.email for p in item.participants} == {JULES, "a@acme.com", "boss@acme.com"}
    assert {p.role for p in item.participants} == {Role.ATTENDEE}


def test_an_organizer_who_is_listed_and_declined_is_not_added_back() -> None:
    item = _meeting(
        attendees=(
            Attendee(JULES, "accepted", True),
            Attendee("boss@acme.com", "declined", False),
            Attendee(SARA, "accepted", False),
        ),
        organizer="boss@acme.com",
    )

    assert item is not None
    assert "boss@acme.com" not in {p.email for p in item.participants}


def test_a_guest_who_declined_is_not_recorded() -> None:
    item = _meeting(
        attendees=(
            Attendee(JULES, "accepted", True),
            Attendee(SARA, "accepted", False),
            Attendee("no@acme.com", "declined", False),
        ),
        organizer=None,
    )

    assert item is not None
    assert "no@acme.com" not in {p.email for p in item.participants}


def test_a_meeting_the_team_member_declined_is_ignored() -> None:
    declined = (Attendee(JULES, "declined", True), Attendee(SARA, "accepted", False))

    assert _meeting(attendees=declined) is None


def test_all_day_and_internal_only_meetings_are_ignored() -> None:
    internal = (Attendee(JULES, "accepted", True), Attendee(RAMZY, "accepted", False))

    assert _meeting(all_day=True) is None
    assert _meeting(attendees=internal, organizer=RAMZY) is None


def test_a_meeting_without_a_start_or_ical_uid_cannot_be_stored() -> None:
    keyless = replace(event(), ical_uid=None)
    startless = replace(event(), starts_at=None)

    assert event_to_item(JULES, keyless, INTERNAL) is None
    assert event_to_item(JULES, startless, INTERNAL) is None
