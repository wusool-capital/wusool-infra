"""Builds Attio's raw read-side attribute-value-entry shape —
`{"active_until": ..., "value"|"target_record_id": ...}` — for fake API
responses. Every test that hand-assembles a fake `deal`/`person` record was
building this as a bare dict.

Mirrors `attio/domain/records.py`'s `AttioValueEntry`, the production
parsing side's own type for this exact shape, but as a constructible
pydantic model rather than a `TypedDict`: a test builds one of these on
every call, it never only reads one Attio already sent.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class ValueEntry(BaseModel):
    """A scalar attribute's (text/number/checkbox/...) value entry. `value`
    is genuinely attribute-type-dependent — same reasoning as
    `attio/providers/attio/values.py::first`'s own return type."""

    model_config = ConfigDict(frozen=True)

    value: Any
    active_until: str | None = None

    def as_entries(self) -> list[dict[str, object]]:
        return [self.model_dump()]


class RefValueEntry(BaseModel):
    """A record-reference attribute's value entry. Read side only ever
    carries the target id, unlike the write side's `RecordReferenceValue`
    (`write_values.py`), which also needs `target_object`."""

    model_config = ConfigDict(frozen=True)

    target_record_id: str
    active_until: str | None = None

    def as_entries(self) -> list[dict[str, object]]:
        return [self.model_dump()]
