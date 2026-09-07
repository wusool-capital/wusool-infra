"""
app/modules/meetings/domain/role_ref.py

Minimal projection of an active buyer/seller role row this module needs to
link a meeting note to — just the two identifiers each side of the note
write needs (Postgres wants the uuid, Attio wants the list entry id), never
the full `BuyerRole`/`SellerRole` ORM entity or its mandate-profile fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

__all__ = ["ActiveRoleRef"]


@dataclass(frozen=True, slots=True)
class ActiveRoleRef:
    id: UUID
    legacy_entry_id: str | None
