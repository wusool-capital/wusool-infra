"""The 13 Attio fields the engine writes, and the rules for what to send.

Pure. Every value is held as one canonical string so that what we computed, what we last
sent and what Attio holds can be compared with `==`. Timestamps are UTC with milliseconds.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.modules.interactions.domain.model import InteractionSummary

FieldMap = Mapping[str, str | None]


class AttioObject(StrEnum):
    """The custom Attio objects the engine writes to."""

    ORGANIZATIONS = "organizations"
    PERSON = "person"


class WriteMode(StrEnum):
    """`dry_run` computes and logs counts but sends nothing."""

    OFF = "off"
    DRY_RUN = "dry_run"
    ON = "on"


class FieldKind(StrEnum):
    TIMESTAMP = "timestamp"
    SELECT = "select"
    TEXT = "text"
    ACTOR = "actor"


@dataclass(frozen=True)
class FieldSpec:
    slug: str
    kind: FieldKind


@dataclass(frozen=True)
class FieldValue:
    slug: str
    value: str


@dataclass(frozen=True)
class RecordPlan:
    writes: tuple[FieldValue, ...]
    # Fields that should become empty. Not sent yet: Attio's clear shape is unverified.
    clears_skipped: int


_FIRST = ("first_interaction_at", "first_email_interaction_at", "first_calendar_interaction_at")
_LAST = ("last_interaction_at", "last_email_interaction_at", "last_calendar_interaction_at")
_NEXT = ("next_interaction_at", "next_calendar_interaction_at")
_FOLLOW_LAST = ("last_interaction_channel", "last_interaction_subject", "last_interaction_owner")
_STRENGTH = ("connection_strength", "strongest_connection_user")

FIELDS: tuple[FieldSpec, ...] = (
    *(FieldSpec(slug, FieldKind.TIMESTAMP) for slug in (*_FIRST, *_LAST, *_NEXT)),
    FieldSpec("last_interaction_channel", FieldKind.SELECT),
    FieldSpec("connection_strength", FieldKind.SELECT),
    FieldSpec("last_interaction_subject", FieldKind.TEXT),
    FieldSpec("last_interaction_owner", FieldKind.ACTOR),
    FieldSpec("strongest_connection_user", FieldKind.ACTOR),
)

_EXTRA_FRACTION = re.compile(r"(\.\d{6})\d+")


def canonical_timestamp(value: datetime | str) -> str:
    """UTC, millisecond precision. Accepts Attio's `...447000000Z` form as well as a datetime."""
    if isinstance(value, str):
        value = datetime.fromisoformat(_EXTRA_FRACTION.sub(r"\1", value.replace("Z", "+00:00")))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="milliseconds")


def fields_for(summary: InteractionSummary, member_ids: Mapping[str, str]) -> FieldMap:
    """What the engine computed for one record. `member_ids` maps a team address to its Attio
    workspace member id; an address without one leaves that field empty."""

    def stamp(value: datetime | None) -> str | None:
        return canonical_timestamp(value) if value else None

    def member(address: str | None) -> str | None:
        return member_ids.get(address) if address else None

    return {
        "first_interaction_at": stamp(summary.first_interaction_at),
        "last_interaction_at": stamp(summary.last_interaction_at),
        "next_interaction_at": stamp(summary.next_interaction_at),
        "first_email_interaction_at": stamp(summary.first_email_interaction_at),
        "last_email_interaction_at": stamp(summary.last_email_interaction_at),
        "first_calendar_interaction_at": stamp(summary.first_calendar_interaction_at),
        "last_calendar_interaction_at": stamp(summary.last_calendar_interaction_at),
        "next_calendar_interaction_at": stamp(summary.next_calendar_interaction_at),
        "last_interaction_channel": (
            summary.last_interaction_channel.value.title()
            if summary.last_interaction_channel
            else None
        ),
        "last_interaction_subject": summary.last_interaction_subject,
        "last_interaction_owner": member(summary.last_interaction_owner),
        "strongest_connection_user": member(summary.strongest_connection_user),
        "connection_strength": (
            summary.connection_strength.value if summary.connection_strength else None
        ),
    }


def plan_record(
    computed: FieldMap, sent: FieldMap, baseline: FieldMap, read_member_ids: frozenset[str]
) -> RecordPlan:
    """What to write for one record. `sent` is what the record holds in Attio, `baseline` is
    the live value on the matching Company or Person, which also covers mail we don't read."""
    known = (computed, sent, baseline)
    merged: dict[str, str | None] = {}
    # Old mail leaves the 12-month window, so first dates may only move earlier and last
    # dates only later.
    for slug in _FIRST:
        values = [v for m in known if (v := m.get(slug))]
        merged[slug] = min(values) if values else None
    for slug in _LAST:
        values = [v for m in known if (v := m.get(slug))]
        merged[slug] = max(values) if values else None
    # The channel, subject and owner describe the last interaction, so they follow it.
    computed_last = computed.get("last_interaction_at")
    follows = computed_last is not None and computed_last == merged["last_interaction_at"]
    for slug in _FOLLOW_LAST:
        merged[slug] = computed.get(slug) if follows else sent.get(slug)
    for slug in _NEXT:
        merged[slug] = computed.get(slug)
    # Where Attio's strongest user is someone whose mailbox we don't read, our strength would
    # be missing their mail, so it is left alone.
    baseline_user = baseline.get("strongest_connection_user")
    skip_strength = baseline_user is not None and baseline_user not in read_member_ids
    for slug in _STRENGTH:
        merged[slug] = sent.get(slug) if skip_strength else computed.get(slug)

    writes: list[FieldValue] = []
    clears = 0
    for spec in FIELDS:
        new, old = merged[spec.slug], sent.get(spec.slug)
        if new == old:
            continue
        if new is None:
            clears += 1
        else:
            writes.append(FieldValue(spec.slug, new))
    return RecordPlan(tuple(writes), clears)
