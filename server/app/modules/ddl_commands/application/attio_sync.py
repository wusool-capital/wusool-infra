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

from app.modules.attio import AttioClientProtocol, WebhookEvent, WebhookEventId
from app.modules.ddl_commands.application.ports.attio_sync import (
    AttioRegistryPort,
    AttioSyncRepositoryPort,
)

_logger = logging.getLogger("app.modules.ddl_commands.attio_sync")


async def _sync_source_deal(
    upsert: AttioSyncRepositoryPort, client: AttioClientProtocol, record_id: str
) -> None:
    """SOURCE Attio's custom deal object is slug "deal" (singular) -- see
    `config.py`'s `attio_deal_object_slug` and `sync_deal`'s docstring. Both
    slugs land in the same `deals` Postgres table."""
    await upsert.sync_deal(client, record_id, object_slug="deal")


_LIST_SYNC_METHODS = {
    "buyer_role": "sync_buyer_role",
    "seller_role": "sync_seller_role",
}


async def dispatch_event(
    upsert: AttioSyncRepositoryPort,
    registry: AttioRegistryPort,
    client: AttioClientProtocol,
    event: WebhookEvent,
) -> None:
    event_type = event.event_type
    ids = event.id

    if event_type.startswith("record."):
        await _dispatch_record_event(upsert, registry, client, event_type, ids)
    elif event_type.startswith("list-entry."):
        await _dispatch_list_entry_event(upsert, registry, client, event_type, ids)
    else:
        _logger.debug("ignoring unhandled event_type %s", event_type)


async def _dispatch_record_event(
    upsert: AttioSyncRepositoryPort,
    registry: AttioRegistryPort,
    client: AttioClientProtocol,
    event_type: str,
    ids: WebhookEventId,
) -> None:
    object_id = ids.object_id
    record_id = ids.record_id
    if not object_id or not record_id:
        return
    slug = await registry.object_slug(client, object_id)
    if slug is None:
        return  # object outside this sync's scope

    if event_type == "record.deleted":
        if slug == "organizations":
            await upsert.delete_organization(record_id)
        elif slug == "person":
            await upsert.delete_person(record_id)
        else:
            _logger.info("ignoring record.deleted for %s (no deletion handling)", slug)
        return

    if slug == "organizations":
        await upsert.sync_organization(client, record_id)
    elif slug == "person":
        await upsert.sync_person(client, record_id)
    elif slug == "deals":
        await upsert.sync_deal(client, record_id)
    elif slug == "deal":
        await _sync_source_deal(upsert, client, record_id)
    elif slug == "note":
        await upsert.sync_note(client, record_id)


async def _dispatch_list_entry_event(
    upsert: AttioSyncRepositoryPort,
    registry: AttioRegistryPort,
    client: AttioClientProtocol,
    event_type: str,
    ids: WebhookEventId,
) -> None:
    list_id = ids.list_id
    entry_id = ids.entry_id
    if not list_id or not entry_id:
        return
    slug = await registry.list_slug(client, list_id)
    if slug is None:
        return  # list outside this sync's scope

    if event_type == "list-entry.deleted":
        _logger.info("ignoring list-entry.deleted for %s (no deletion handling)", slug)
        return

    method_name = _LIST_SYNC_METHODS.get(slug)
    if method_name:
        await getattr(upsert, method_name)(client, entry_id)
