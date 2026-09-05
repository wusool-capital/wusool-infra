"""app/modules/meetings/domain/roles.py

Role a company plays in a specific meeting, and the precedence/column-mapping
rules derived from it. Ported from Scribe's `app.shared.enums.CompanyRole`
plus the role-selection logic scattered across `app.publish.service`
(`_ROLE_PRECEDENCE`, `_select_counterparty`) and `app.ai.prompts`
(`_MOMENTUM_ROLES`, `_momentum_applies`), consolidated here since both
consumers need the same precedence and the same "which roles count as an
external counterparty" predicate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from app.modules.utilities.domain.json_types import JsonObject

__all__ = [
    "ROLE_PRECEDENCE",
    "MeetingRole",
    "RoleTag",
    "counterparty_role_column",
    "decode_role_metadata",
    "encode_role_metadata",
    "meeting_type_column",
    "momentum_applies",
    "other_roles",
    "select_primary_role",
]


class MeetingRole(StrEnum):
    """Role a company plays in a specific meeting."""

    SELLER = "seller"
    BUYER = "buyer"
    INVESTOR = "investor"
    INTERNAL = "internal"
    GENERAL = "general"


# Fixed precedence for picking the primary role when a meeting is tagged with
# more than one: seller first (the firm represents the seller when one is
# tagged), then buyer, then investor, then internal, then general.
ROLE_PRECEDENCE: tuple[MeetingRole, ...] = (
    MeetingRole.SELLER,
    MeetingRole.BUYER,
    MeetingRole.INVESTOR,
    MeetingRole.INTERNAL,
    MeetingRole.GENERAL,
)

# Roles that represent an actual external counterparty relationship that can
# have deal "momentum" — mirrors Scribe's `_MOMENTUM_ROLES`.
_MOMENTUM_ROLES = (MeetingRole.SELLER, MeetingRole.BUYER, MeetingRole.INVESTOR)


def select_primary_role(roles: dict[MeetingRole, str]) -> MeetingRole | None:
    """The highest-precedence role present in *roles* (mapping role -> org
    Attio id or org name), or None if *roles* is empty."""
    for role in ROLE_PRECEDENCE:
        if role in roles:
            return role
    return None


def other_roles(roles: dict[MeetingRole, str], primary: MeetingRole | None) -> list[MeetingRole]:
    """Every present role other than *primary*, in precedence order.

    Scribe's `_select_counterparty` only kept the first loser (a `break`
    after one iteration) and silently dropped the rest when a meeting was
    tagged with more than two roles. This returns all of them so nothing
    tagged on the meeting is lost.
    """
    return [role for role in ROLE_PRECEDENCE if role in roles and role != primary]


def counterparty_role_column(role: MeetingRole | None) -> str | None:
    """Value for the `counterparty_role` column, which only ever holds
    'seller' or 'buyer' — investor/internal/general never set it, matching
    Scribe's `app/publish/service.py` behavior."""
    if role is MeetingRole.SELLER:
        return "seller"
    if role is MeetingRole.BUYER:
        return "buyer"
    return None


def meeting_type_column(role: MeetingRole | None) -> str | None:
    """Value for the `meeting_type` column.

    Only INTERNAL maps to a value here. Scribe's own comment on this
    decision (`app/publish/service.py`): meeting_type has no source of
    truth in scribe yet (no Slack flag, no UI) — published NULL and
    backfillable rather than guessed. That applies to buyer/seller/investor/
    general alike; INTERNAL is the one role that unambiguously determines
    the column's 'internal' value on its own.
    """
    if role is MeetingRole.INTERNAL:
        return "internal"
    return None


def momentum_applies(roles: set[MeetingRole] | Mapping[MeetingRole, str]) -> bool:
    """True only if an external counterparty role (seller/buyer/investor)
    is actually present — mirrors Scribe's `_momentum_applies`."""
    return any(role in roles for role in _MOMENTUM_ROLES)


@dataclass(frozen=True, slots=True)
class RoleTag:
    """One resolved role's org reference — a single, framework-free type
    for the "other side" roles that don't reach a `meetings` column
    (`counterparty_role`/`meeting_type` only ever distinguish seller/buyer/
    internal; see the two column-mapping functions above)."""

    role: MeetingRole
    org_id: str | None
    org_name_raw: str | None


def encode_role_metadata(*, primary: MeetingRole | None, other: list[RoleTag]) -> JsonObject:
    """The one place `meetings.metadata`'s `primary_role`/`other_side` shape
    is defined — `IngestMixin.ingest_meeting` (write) and
    `PublishMixin._reconstruct_companies` (read) both go through this pair
    of functions instead of each hand-rolling the same dict literal, so the
    two can no longer silently drift apart.
    """
    return {
        "primary_role": primary.value if primary is not None else None,
        "other_side": [
            {"role": tag.role.value, "org_id": tag.org_id, "org_name_raw": tag.org_name_raw}
            for tag in other
        ],
    }


def decode_role_metadata(metadata: JsonObject | None) -> tuple[MeetingRole | None, list[RoleTag]]:
    """Inverse of `encode_role_metadata`. Never raises on a missing/
    malformed blob — an older row, or one with no roles tagged at all,
    decodes to `(None, [])`."""
    data = metadata or {}
    primary_value = data.get("primary_role")
    primary = MeetingRole(primary_value) if primary_value else None
    other = [
        RoleTag(
            role=MeetingRole(entry["role"]),
            org_id=entry.get("org_id"),
            org_name_raw=entry.get("org_name_raw"),
        )
        for entry in data.get("other_side") or []
        if isinstance(entry, dict) and "role" in entry
    ]
    return primary, other
