"""Routes a parsed Attio webhook event to the right per-table sync function.

Attio never batches changes into one event — each record/list-entry change
is its own independent delivery, carrying only IDs, never values (see
`router.py`'s module docstring), so every dispatch here re-fetches the
current state before writing anything.

The webhook subscription is registered broadly, across the whole workspace,
rather than filtered per-object at creation time — Attio's parent/object
filter syntax wasn't confirmed reliable enough to bet correctness on (see the
webhook-registration note handed over separately). Events for object/list
types this sync doesn't cover are therefore expected and silently ignored,
not an error.
"""

import logging

from ddl_commands.modules.attio_sync import registry, upsert
from ddl_commands.shared.attio.client import AttioClient

_logger = logging.getLogger("ddl_commands.attio_sync")

_OBJECT_SYNC = {
    "organizations": upsert.sync_organization,
    "person": upsert.sync_person,
    "deals": upsert.sync_deal,
}
_OBJECT_DELETE = {
    # Only `organizations` has a deletion convention (`removed_at`) —
    # see upsert.py's module docstring for why every other table's
    # `record.deleted`/`list-entry.deleted` is deliberately a no-op here.
    "organizations": upsert.delete_organization,
}
_LIST_SYNC = {
    "buyer_role": upsert.sync_buyer_role,
    "seller_role": upsert.sync_seller_role,
    "mandates": upsert.sync_mandate,
}


async def dispatch_event(client: AttioClient, event: dict) -> None:
    event_type = event.get("event_type", "")
    ids = event.get("id") or {}

    if event_type.startswith("record."):
        await _dispatch_record_event(client, event_type, ids)
    elif event_type.startswith("list-entry."):
        await _dispatch_list_entry_event(client, event_type, ids)
    else:
        _logger.debug("ignoring unhandled event_type %s", event_type)


async def _dispatch_record_event(client: AttioClient, event_type: str, ids: dict) -> None:
    object_id = ids.get("object_id")
    record_id = ids.get("record_id")
    if not object_id or not record_id:
        return
    slug = await registry.object_slug(client, object_id)
    if slug is None:
        return  # object outside this sync's scope

    if event_type == "record.deleted":
        delete_fn = _OBJECT_DELETE.get(slug)
        if delete_fn:
            await delete_fn(record_id)
        else:
            _logger.info("ignoring record.deleted for %s (no deletion handling)", slug)
        return

    sync_fn = _OBJECT_SYNC.get(slug)
    if sync_fn:
        await sync_fn(client, record_id)


async def _dispatch_list_entry_event(client: AttioClient, event_type: str, ids: dict) -> None:
    list_id = ids.get("list_id")
    entry_id = ids.get("entry_id")
    if not list_id or not entry_id:
        return
    slug = await registry.list_slug(client, list_id)
    if slug is None:
        return  # list outside this sync's scope

    if event_type == "list-entry.deleted":
        _logger.info("ignoring list-entry.deleted for %s (no deletion handling)", slug)
        return

    sync_fn = _LIST_SYNC.get(slug)
    if sync_fn:
        await sync_fn(client, entry_id)
