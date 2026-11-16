"""Implements `SeedSourcePort` from Attio's custom objects and the standard ones they came from.

Each Organization or Person carries `legacy_attio_id`, the id of the Company or Person it was
copied from. That Company or Person holds the live values, including mail the engine can't read.
"""

from collections.abc import AsyncIterator, Callable

from pydantic import BaseModel

from app.modules.attio import AttioClientProtocol, owns_record
from app.modules.attio.domain.records import AttioRecord
from app.modules.attio.providers.attio.retry import post_with_retry
from app.modules.attio.providers.attio.values import (
    ValuesBySlug,
    actor,
    boolean,
    first,
    raw_items,
    record_id,
    vals,
)
from app.modules.interactions.application.ports.sent_values import SeedRow
from app.modules.interactions.domain.attio_fields import (
    FIELDS,
    AttioObject,
    FieldKind,
    FieldSpec,
    canonical_timestamp,
)

_PAGE_SIZE = 500
_STANDARD_OBJECT = {AttioObject.ORGANIZATIONS: "companies", AttioObject.PERSON: "people"}
# Standard dates are `interaction` attributes, so the date sits under `interacted_at`.
_STANDARD_DATES = {
    "first_interaction_at": "first_interaction",
    "first_email_interaction_at": "first_email_interaction",
    "first_calendar_interaction_at": "first_calendar_interaction",
    "last_interaction_at": "last_interaction",
    "last_email_interaction_at": "last_email_interaction",
    "last_calendar_interaction_at": "last_calendar_interaction",
}


class _InteractionValue(BaseModel):
    interacted_at: str | None = None


class AttioSeedSource:
    def __init__(
        self,
        client: AttioClientProtocol,
        owns: Callable[[bool | None], bool] = owns_record,
    ) -> None:
        self._client = client
        # Only records of this instance's scope, so test and prod records never mix.
        self._owns = owns

    async def rows(self, obj: AttioObject) -> list[SeedRow]:
        standard = {
            record_id(record): vals(record) async for record in self._records(_STANDARD_OBJECT[obj])
        }
        out: list[SeedRow] = []
        async for record in self._records(obj.value):
            values = vals(record)
            if not self._owns(boolean(values, "is_test")):
                continue
            live = standard.get(str(first(values, "legacy_attio_id") or ""))
            for spec in FIELDS:
                value = _current(spec, values)
                baseline = _baseline(spec.slug, live) if live is not None else None
                if value is not None or baseline is not None:
                    out.append(SeedRow(record_id(record), spec.slug, value, baseline))
        return out

    async def _records(self, slug: str) -> AsyncIterator[AttioRecord]:
        offset = 0
        while True:
            response = await post_with_retry(
                self._client,
                f"/objects/{slug}/records/query",
                {"limit": _PAGE_SIZE, "offset": offset},
            )
            page = response.get("data", [])
            for record in page:
                yield record
            if len(page) < _PAGE_SIZE:
                return
            offset += _PAGE_SIZE


def _current(spec: FieldSpec, values: ValuesBySlug) -> str | None:
    if spec.kind is FieldKind.ACTOR:
        return actor(values, spec.slug)
    value = first(values, spec.slug)
    if value is None or value == "":
        return None
    return canonical_timestamp(str(value)) if spec.kind is FieldKind.TIMESTAMP else str(value)


def _baseline(slug: str, live: ValuesBySlug) -> str | None:
    if slug == "strongest_connection_user":
        return actor(live, slug)
    standard = _STANDARD_DATES.get(slug)
    entries = raw_items(live, standard) if standard else []
    if not entries:
        return None
    interacted = _InteractionValue.model_validate(entries[0]).interacted_at
    return canonical_timestamp(interacted) if interacted else None
