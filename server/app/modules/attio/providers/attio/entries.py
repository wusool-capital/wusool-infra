"""Resolves which Attio record/entry a write actually targets, and issues
that write. `organizations` writes go straight to a record by ID (its
Postgres `attio_id` *is* the Attio record ID). `seller_role`/`buyer_role`
writes target a list *entry*, whose ID Postgres never stores — resolved live
by paging through the list's entries and matching `parent_record_id`,
exactly like this codebase's own `backfill-seller-intake-source.ps1`
(`Get-ParentRecordId`) already does. No server-side `parent_record_id`
filter is used — that script doesn't use one either, and this repo has no
verified precedent for that filter's syntax; paging through ~200-400 total
role entries once per edit is cheap at this scale.

An org can have more than one entry for the same role kind — duplicate
SOURCE-migration submissions (`workflows/crm-sync/scripts/_internal/
lists.ps1`), or the narrow window right after `/add-*` creates one before
`attio_sync/upsert.py`'s `reconcile_active_entry` catches up. `is_active` is
the signal that says which one is current; every other duplicate for that
org is soft-deleted in every sense that matters here. `resolve_role_entry_id`
below trusts that flag as a fast-path shortcut: it returns the first entry
it finds flagged `is_active` (there is only ever supposed to be one, so
there's nothing to gain by scanning further once it's found — this keeps
the common, zero-duplicate case exactly as cheap as before), and only keeps
paging when duplicates mean the *first* match it hits isn't the active one.
Falls back to newest `created_at` if nothing is flagged active at all (an
org that predates `is_active`, or genuinely hasn't been reconciled yet).

This is deliberately a different policy than `reconcile_active_entry`'s own:
that function *ignores* the current flag and always re-derives "newest wins"
from `created_at`, because its job is to correct a wrong flag, not trust
it — sharing one "pick the winner" function between the two would either
break reconcile's self-healing property or give up this function's fast
path. The two are kept as separate, small implementations on purpose.

`create_organization`/`create_role_entry` (for `/add-seller`/`/add-buyer`)
use the exact request/response shapes `workflows/crm-sync/scripts/_internal/
objects.ps1`/`lists.ps1` already use live against this same Attio instance —
`POST .../records` returns the new id at `data.id.record_id`
(`objects.ps1`'s own `Id` helper, line ~877); `POST .../entries` requires
both `parent_record_id` and `parent_object` in the body and returns the new
id at `data.id.entry_id` (`lists.ps1`, e.g. line ~984) — not inferred from
docs alone.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.attio.application.ports.client import AttioClientProtocol
from app.modules.attio.domain.records import AttioRecord
from app.modules.attio.domain.scope import record_scope
from app.modules.attio.providers.attio import values as v

_PAGE_SIZE = 500


class _SortSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    attribute: str
    direction: Literal["asc", "desc"]


class _RecordsQueryBody(BaseModel):
    """Body for `POST .../records/query` or `.../entries/query`. `filter`
    stays a bare dict — its shape genuinely varies by attribute type, and
    (see this module's own opening docstring) there is no single verified
    schema for it in this repo; everything else here has one fixed,
    well-understood shape worth actually typing.
    """

    model_config = ConfigDict(frozen=True)

    filter: dict[str, object] | None = None
    sorts: list[_SortSpec] = []
    limit: int
    # `None`, not `0`: `find_people_by_email` never paginates and its
    # original body never sent this key at all — an explicit `offset: 0`
    # would be a request-shape change `exclude_none` alone can't catch,
    # since `0` is not `None`. `resolve_role_entry_id`/`find_deals_by_party`
    # always pass a real value here, `0` included, so they still send it.
    offset: int | None = None

    def to_json_body(self) -> dict[str, object]:
        return self.model_dump(exclude_none=True)


class OrgRecordNotFoundError(Exception):
    pass


class RoleEntryNotFoundError(Exception):
    pass


class ScopeMismatchError(Exception):
    """A write targeted a record belonging to the other half of the shared
    SOURCE workspace — a dev process reaching a production record, or the
    reverse. Raised instead of issuing the PATCH."""

    def __init__(self, target: str, *, record_is_test: bool, is_test: bool) -> None:
        super().__init__(
            f"Refusing to write to {target}: it is a "
            f"{'test' if record_is_test else 'production'} record and this instance owns "
            f"{'test' if is_test else 'production'} records."
        )
        self.target = target
        self.record_is_test = record_is_test
        self.is_test = is_test


def _record_is_test(record: AttioRecord) -> bool:
    return record_scope(v.boolean(v.vals(record), "is_test"))


def _entry_parent_record_id(entry: dict) -> str | None:
    parent = entry.get("parent_record_id")
    if isinstance(parent, dict):
        return parent.get("record_id")
    return parent


def _entry_id(entry: dict) -> str:
    entry_id = entry.get("id", {})
    return entry_id["entry_id"] if isinstance(entry_id, dict) else entry_id


def _entry_is_active(entry: dict) -> bool | None:
    # Kept as its own implementation rather than `v.boolean(v.vals(e),
    # "is_active")`: this one deliberately omits "checked" from the truthy
    # set, and `is_active` is bot-owned reconciliation state whose coercion
    # shouldn't drift with the generic extractor's.
    items = [
        item
        for item in entry.get("entry_values", {}).get("is_active") or []
        if item.get("active_until") is None
    ]
    if not items:
        return None
    value = items[0].get("value")
    return value if isinstance(value, bool) else str(value).lower() in ("true", "yes", "1")


async def resolve_role_entry_id(
    client: AttioClientProtocol, list_slug: str, org_attio_id: str, *, is_test: bool
) -> str:
    """`is_test` is this process's half of the shared SOURCE workspace.
    Entries belonging to the other half are skipped, so a dev instance can
    only ever resolve — and therefore only ever PATCH — its own test
    entries. Filtering here rather than in a separate pre-check keeps the
    guard free: this already pages every entry in the list.
    """
    offset = 0
    matches: list[dict] = []
    while True:
        response = await client.post(
            f"/lists/{list_slug}/entries/query",
            _RecordsQueryBody(limit=_PAGE_SIZE, offset=offset).to_json_body(),
        )
        page = response.get("data", [])
        for entry in page:
            if _entry_parent_record_id(entry) != org_attio_id:
                continue
            if _record_is_test(entry) is not is_test:
                continue
            if _entry_is_active(entry) is True:
                return _entry_id(entry)
            matches.append(entry)
        if len(page) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE

    if not matches:
        raise RoleEntryNotFoundError(
            f"No {list_slug} entry found in Attio for organization {org_attio_id}"
        )
    return _entry_id(max(matches, key=lambda entry: entry.get("created_at") or ""))


async def assert_organization_in_scope(
    client: AttioClientProtocol, attio_id: str, *, is_test: bool
) -> None:
    """Refuse a write to an organization belonging to the other half of the
    shared workspace, before any of it lands.

    One SOURCE workspace now serves both environments, so a dev instance is
    physically able to PATCH a real production record. `is_test` is not
    re-asserted on patches — it describes where a record came from, not who
    is editing it, and rewriting it would be the very corruption this
    prevents — so a read-before-write is what stops it instead.

    Costs one extra GET per edit, against the several round-trips `/edit-*`
    already makes. Deliberately not atomic with the PATCH that follows: a
    single-writer bot at human speed has no interleaving to lose to.
    """
    fetched = await client.get(f"/objects/organizations/records/{attio_id}")
    record: AttioRecord = fetched.get("data") or {}
    record_is_test = _record_is_test(record)
    if record_is_test is not is_test:
        raise ScopeMismatchError(
            f"organization {attio_id}", record_is_test=record_is_test, is_test=is_test
        )


async def patch_organization(client: AttioClientProtocol, attio_id: str, values: dict) -> None:
    """`values` maps attribute slug -> Attio's own per-attribute write shape
    (already serialized by the caller via `money.py`/`dates.py`/option
    lookups) — this function issues the write, it doesn't shape it.
    """
    await client.patch(f"/objects/organizations/records/{attio_id}", {"data": {"values": values}})


async def patch_role_entry(
    client: AttioClientProtocol, list_slug: str, entry_id: str, entry_values: dict
) -> None:
    await client.patch(
        f"/lists/{list_slug}/entries/{entry_id}", {"data": {"entry_values": entry_values}}
    )


async def create_organization(client: AttioClientProtocol, values: dict, *, is_test: bool) -> str:
    """`values` is already Attio's own per-attribute write shape (see
    `write_payload.build_attio_values`), same as `patch_organization` — the
    only difference from an edit is this is a `POST` with no existing
    `attio_id` to target, and the new one comes back in the response.

    `is_test` is stamped here rather than by the caller, for the same reason
    `create_role_entry` stamps `is_active`: it is bot-owned, every create
    must carry it, and Attio's checkbox filter has no "is empty" — a record
    written without it is invisible in the UI of both environments.
    """
    response = await client.post(
        "/objects/organizations/records", {"data": {"values": {**values, "is_test": is_test}}}
    )
    return response["data"]["id"]["record_id"]


async def create_role_entry(
    client: AttioClientProtocol,
    list_slug: str,
    org_attio_id: str,
    entry_values: dict,
    *,
    is_test: bool,
) -> str:
    # Every entry created here is, by definition, the only one this bot knows
    # of for this org — `is_active: True` is what the dedup reconciliation
    # (`attio_sync/upsert.py::_reconcile_active_entry`) reads to decide which
    # sibling entry wins, so a freshly created entry has to assert it rather
    # than sit `null` until that reconciliation happens to run.
    response = await client.post(
        f"/lists/{list_slug}/entries",
        {
            "data": {
                "parent_record_id": org_attio_id,
                "parent_object": "organizations",
                "entry_values": {**entry_values, "is_active": True, "is_test": is_test},
            }
        },
    )
    return response["data"]["id"]["entry_id"]


_PERSON_OBJECT = "person"


async def find_people_by_email(
    client: AttioClientProtocol, email: str, *, is_test: bool
) -> list[AttioRecord]:
    """Every `person` record whose `email` equals `email`, oldest first,
    filtered to this process's half of the shared workspace.

    `person.email` on this workspace is a plain `text` attribute,
    single-valued and **not** unique — not Attio's standard multi-valued
    `email_addresses` type (the same finding `ddl_commands`'s
    `_person_params` already documents on its read side). That rules out
    `PUT ?matching_attribute=` entirely, which is why this is a query
    rather than an upsert. Attio's text `$eq` filter is case-insensitive
    (verified live 2026-09-13), so a mixed-case address entered by hand
    still matches a normalised one.

    `is_test` is filtered client-side, same reasoning as
    `resolve_role_entry_id`: Attio's checkbox filter has no "is empty",
    and an absent `is_test` reads as production (`domain/scope.py`'s null
    policy) — a server-side filter would silently miss a pre-migration
    record and create an unwanted duplicate next to a real contact.

    `sorts` is explicit and required: without one, Attio returns matches
    in "deterministic random order" — unacceptable for a path the sweeper
    can re-enter and must resolve to the same person every time.
    """
    response = await client.post(
        f"/objects/{_PERSON_OBJECT}/records/query",
        _RecordsQueryBody(
            filter={"email": {"$eq": email}},
            sorts=[_SortSpec(attribute="created_at", direction="asc")],
            limit=_PAGE_SIZE,
        ).to_json_body(),
    )
    return [r for r in response.get("data", []) if _record_is_test(r) is is_test]


async def create_person(client: AttioClientProtocol, values: dict, *, is_test: bool) -> str:
    """Exact mirror of `create_organization` — see its docstring for why
    `is_test` is stamped here rather than by the caller."""
    response = await client.post(
        f"/objects/{_PERSON_OBJECT}/records",
        {"data": {"values": {**values, "is_test": is_test}}},
    )
    return response["data"]["id"]["record_id"]


async def patch_person(client: AttioClientProtocol, attio_id: str, values: dict) -> None:
    """Only ever called with the fields a matched person's own record is
    currently missing — see `lead_magnets/providers/attio/person_writer.py`.
    Never sent `name`: it is `is_required` on this object, so it is never
    the empty field, and a lead magnet must never relabel a contact's
    existing name."""
    await client.patch(
        f"/objects/{_PERSON_OBJECT}/records/{attio_id}", {"data": {"values": values}}
    )


_DEAL_OBJECT = "deal"


async def find_deals_by_party(
    client: AttioClientProtocol, *, field: str, org_attio_id: str, is_test: bool
) -> list[AttioRecord]:
    """Every `deal` record whose `field` (`seller_id` or `buyer_id`) points at
    `org_attio_id`, oldest first, filtered to this process's half of the
    shared workspace.

    No server-side filter on `field`: it is a record-reference attribute,
    same class as `parent_record_id` above, and this module's own opening
    docstring already flags that this repo has no verified precedent for
    that filter's syntax. Paging every `deal` and matching with `v.ref` —
    the exact shape `_deal_params` already reads in production off this
    same object — client-side is the same trade `resolve_role_entry_id`
    makes above, and for the same reason: a wrong guess at the filter body
    either 400s or silently matches nothing, and either failure mode here
    means a duplicate `Inbound` deal per submission, which is the one thing
    this write exists to prevent. `is_test` is filtered client-side for the
    usual reason (no "is empty" operator, absent reads as production).
    """
    offset = 0
    matches: list[AttioRecord] = []
    while True:
        response = await client.post(
            f"/objects/{_DEAL_OBJECT}/records/query",
            _RecordsQueryBody(
                sorts=[_SortSpec(attribute="created_at", direction="asc")],
                limit=_PAGE_SIZE,
                offset=offset,
            ).to_json_body(),
        )
        page = response.get("data", [])
        for record in page:
            if v.ref(v.vals(record), field) != org_attio_id:
                continue
            if _record_is_test(record) is is_test:
                matches.append(record)
        if len(page) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return matches


async def create_deal(client: AttioClientProtocol, values: dict, *, is_test: bool) -> str:
    """Exact mirror of `create_organization` — see its docstring for why
    `is_test` is stamped here rather than by the caller."""
    response = await client.post(
        f"/objects/{_DEAL_OBJECT}/records",
        {"data": {"values": {**values, "is_test": is_test}}},
    )
    return response["data"]["id"]["record_id"]
