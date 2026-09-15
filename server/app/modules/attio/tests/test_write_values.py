"""`write_values.py`'s reference-value shapes, and `entries.py`'s private
query-body shapes — pure value objects, no client/network fake needed.

First unit tests for this module: everything else here is exercised only
indirectly, through a consumer module's fake `AttioClientProtocol`. These
two are worth testing directly because they are the one place a wrong
field name or a dropped key fails silently at Attio's end (a 400, or a
filter matching nothing) rather than at type-check time.
"""

from app.modules.attio.providers.attio import entries
from app.modules.attio.providers.attio.write_values import (
    ActorReferenceValue,
    RecordReferenceValue,
)


def test_record_reference_value_wraps_in_a_one_item_list() -> None:
    value = RecordReferenceValue(target_object="organizations", target_record_id="org-1")

    assert value.as_value() == [{"target_object": "organizations", "target_record_id": "org-1"}]


def test_actor_reference_value_wraps_in_a_one_item_list() -> None:
    value = ActorReferenceValue(
        referenced_actor_type="workspace-member", referenced_actor_id="member-1"
    )

    assert value.as_value() == [
        {"referenced_actor_type": "workspace-member", "referenced_actor_id": "member-1"}
    ]


def test_records_query_body_omits_an_unset_filter_or_offset() -> None:
    """`find_people_by_email` never paginates and never sent an `offset` key
    at all — `None`, not `0`, is what keeps that body shape unchanged."""
    body = entries._RecordsQueryBody(
        filter={"email": {"$eq": "dana@acme.com"}},
        sorts=[entries._SortSpec(attribute="created_at", direction="asc")],
        limit=500,
    )

    assert body.to_json_body() == {
        "filter": {"email": {"$eq": "dana@acme.com"}},
        "sorts": [{"attribute": "created_at", "direction": "asc"}],
        "limit": 500,
    }


def test_records_query_body_sends_an_explicit_offset_when_given_one() -> None:
    """`resolve_role_entry_id`/`find_deals_by_party` always pass a real
    offset, `0` included, on every page — that must still be sent."""
    body = entries._RecordsQueryBody(limit=500, offset=0)

    assert body.to_json_body() == {"sorts": [], "limit": 500, "offset": 0}
