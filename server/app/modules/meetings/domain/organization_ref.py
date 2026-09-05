"""
app/modules/meetings/domain/organization_ref.py

Minimal organization projection this module needs from the shared
`organizations` module — just enough for name display and re-association,
never the full `Organization` ORM entity.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["OrganizationRef"]


@dataclass(frozen=True, slots=True)
class OrganizationRef:
    attio_id: str
    name: str
