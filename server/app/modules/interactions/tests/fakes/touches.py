"""Builders for `Touch` rows, so each test states only what it is about."""

from datetime import UTC, datetime, timedelta

from app.modules.interactions.domain.model import Channel, Direction, Role, Touch

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
JULES = "jules@wusoolcapital.com"
RAMZY = "ramzy@wusoolcapital.com"
SARA = "sara@acme.com"


def _touch(
    days_ago: float,
    channel: Channel,
    direction: Direction | None,
    member: str,
    contact: str,
    key: str | None,
    subject: str | None,
    role: Role | None,
) -> Touch:
    """`days_ago` may be negative for a meeting that has not happened yet."""
    return Touch(
        dedupe_key=key or f"{channel}-{member}-{contact}-{days_ago}",
        team_member=member,
        contact=contact,
        channel=channel,
        direction=direction,
        occurred_at=NOW - timedelta(days=days_ago),
        subject=subject,
        team_role=role,
    )


def email_sent(
    days_ago: float,
    *,
    member: str = JULES,
    contact: str = SARA,
    key: str | None = None,
    subject: str | None = None,
    role: Role | None = None,
) -> Touch:
    return _touch(days_ago, Channel.EMAIL, Direction.OUTBOUND, member, contact, key, subject, role)


def email_received(
    days_ago: float,
    *,
    member: str = JULES,
    contact: str = SARA,
    key: str | None = None,
    subject: str | None = None,
    role: Role | None = None,
) -> Touch:
    return _touch(days_ago, Channel.EMAIL, Direction.INBOUND, member, contact, key, subject, role)


def meeting(
    days_ago: float,
    *,
    member: str = JULES,
    contact: str = SARA,
    key: str | None = None,
    subject: str | None = None,
    role: Role | None = Role.ATTENDEE,
) -> Touch:
    return _touch(days_ago, Channel.MEETING, None, member, contact, key, subject, role)
