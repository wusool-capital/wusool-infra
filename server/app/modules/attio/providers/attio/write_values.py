"""Typed shapes for the two record/actor-reference attribute *write*
values every caller in this repo was hand-rolling as a bare dict —
`{"target_object": ..., "target_record_id": ...}` and
`{"referenced_actor_type": ..., "referenced_actor_id": ...}`. Both wire
shapes come from `objects.ps1`'s own live-tested payloads, not guessed —
see `entries.py`'s module docstring.

Attio writes a reference-type attribute's value as a *list* even when the
attribute holds a single value — `.as_value()` returns that one-item list,
so a caller never has to remember the wrap or get the key names wrong.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class RecordReferenceValue(BaseModel):
    """A `record-reference` attribute's write value — e.g. `deal.seller_id`,
    `person.company`, `note.organization_id`."""

    model_config = ConfigDict(frozen=True)

    target_object: str
    target_record_id: str

    def as_value(self) -> list[dict[str, str]]:
        return [self.model_dump()]


class ActorReferenceValue(BaseModel):
    """An `actor-reference` attribute's write value — e.g. `deal.deal_owner`.
    `workspace-member` is the only actor type this repo ever writes; Attio
    also has `system`/`api-token` actors, but nothing here creates those."""

    model_config = ConfigDict(frozen=True)

    referenced_actor_type: Literal["workspace-member"]
    referenced_actor_id: str

    def as_value(self) -> list[dict[str, str]]:
        return [self.model_dump()]
