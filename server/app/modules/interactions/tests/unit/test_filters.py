import pytest

from app.modules.interactions.domain.filters import is_ignored
from app.modules.interactions.domain.model import Channel, RawItem

TEAM = "jules@wusoolcapital.com"
OUTSIDE = "sara@acme.com"


def _item(
    *,
    channel: Channel = Channel.EMAIL,
    participants: tuple[str, ...] = (TEAM, OUTSIDE),
    labels: frozenset[str] = frozenset(),
    subject: str | None = "Term sheet",
    auto_submitted: str | None = None,
    all_day: bool = False,
    cancelled: bool = False,
    team_declined: bool = False,
) -> RawItem:
    return RawItem(
        channel=channel,
        participants=participants,
        labels=labels,
        subject=subject,
        auto_submitted=auto_submitted,
        all_day=all_day,
        cancelled=cancelled,
        team_declined=team_declined,
    )


def test_an_ordinary_two_party_email_is_kept() -> None:
    assert not is_ignored(_item())


def test_an_ordinary_meeting_is_kept() -> None:
    assert not is_ignored(_item(channel=Channel.MEETING))


def test_internal_only_mail_is_ignored_including_the_alias_domain() -> None:
    assert is_ignored(_item(participants=(TEAM, "ramzy@dopaminecap.com")))


def test_an_item_with_no_participants_is_ignored() -> None:
    assert is_ignored(_item(participants=()))


@pytest.mark.parametrize("label", ["SPAM", "TRASH", "DRAFT", "CHAT"])
def test_mail_in_an_ignored_gmail_label_is_dropped(label: str) -> None:
    assert is_ignored(_item(labels=frozenset({"INBOX", label})))


@pytest.mark.parametrize("label", ["INBOX", "SENT", "IMPORTANT"])
def test_ordinary_labels_do_not_drop_mail(label: str) -> None:
    assert not is_ignored(_item(labels=frozenset({label})))


@pytest.mark.parametrize(
    "subject",
    [
        "Invitation: Board call @ Tue",
        "Updated invitation: Board call",
        "Accepted: Board call",
        "Declined: Board call",
        "invitation: lower case",
        "Automatic reply: away",
        "Out of office until Monday",
        "Autoreply: thanks",
    ],
)
def test_calendar_notices_and_out_of_office_replies_are_dropped(subject: str) -> None:
    assert is_ignored(_item(subject=subject))


def test_a_subject_that_merely_mentions_an_invitation_is_kept() -> None:
    assert not is_ignored(_item(subject="Re: Invitation: board call"))


@pytest.mark.parametrize("header", ["auto-generated", "auto-replied", "Auto-Replied "])
def test_the_auto_submitted_header_marks_machine_mail(header: str) -> None:
    assert is_ignored(_item(auto_submitted=header))


def test_auto_submitted_no_means_a_human_wrote_it() -> None:
    assert not is_ignored(_item(auto_submitted="no"))


@pytest.mark.parametrize(
    "meeting",
    [
        _item(channel=Channel.MEETING, all_day=True),
        _item(channel=Channel.MEETING, cancelled=True),
        _item(channel=Channel.MEETING, team_declined=True),
    ],
    ids=["all-day", "cancelled", "declined"],
)
def test_all_day_cancelled_and_declined_meetings_are_dropped(meeting: RawItem) -> None:
    assert is_ignored(meeting)


def test_meeting_flags_do_not_apply_to_email() -> None:
    assert not is_ignored(_item(all_day=True, cancelled=True, team_declined=True))


def test_a_meeting_titled_like_a_notice_is_still_a_meeting() -> None:
    assert not is_ignored(_item(channel=Channel.MEETING, subject="Invitation: kickoff"))
