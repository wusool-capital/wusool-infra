"""The Attio object-record/list-entry envelope shape, as `TypedDict`s —
generic Attio wire format, not specific to any one module's sync business
logic (same rationale as `webhook.py`'s dataclasses). Confirmed against
Attio's REST API docs, not guessed.

`AttioValueEntry` covers every attribute type's value shape in one
`total=False` dict rather than a per-type union: which keys are actually
populated depends on the attribute's type (text/number/checkbox -> `value`;
select -> `option`; status -> `status`; email -> `email_address`; domain-type
-> `domain`; date -> `date`; timestamp -> `timestamp`; record-reference ->
`target_record_id`; actor-reference -> `referenced_actor_id`/
`workspace_member_id`; currency -> `currency_value`/`currency_code`), and
`app.modules.attio.providers.attio.values` is what actually resolves that
per-field ambiguity, not this container type.
"""

from typing import Any, TypedDict


class AttioOptionRef(TypedDict):
    title: str


class AttioStatusRef(TypedDict):
    title: str


class AttioValueEntry(TypedDict, total=False):
    active_until: str | None
    value: Any
    option: AttioOptionRef
    status: AttioStatusRef
    email_address: str
    domain: str
    date: str
    timestamp: str
    target_record_id: str
    referenced_actor_id: str
    workspace_member_id: str
    currency_value: float
    currency_code: str
    currency: str


class AttioRecordRef(TypedDict, total=False):
    record_id: str
    entry_id: str


class AttioRecord(TypedDict, total=False):
    """An Attio object record or list entry, whichever shape the caller
    fetched — `values` (object record) and `entry_values` (list entry) are
    mutually exclusive in practice, both declared here since
    `values.vals()` reads whichever is present. `record_id`/`entry_id` are
    a legacy flattened fallback some callers still read directly instead of
    through `id`.
    """

    id: AttioRecordRef
    record_id: str
    entry_id: str
    parent_record_id: str | AttioRecordRef
    values: dict[str, list[AttioValueEntry]]
    entry_values: dict[str, list[AttioValueEntry]]
