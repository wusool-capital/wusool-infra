"""Resolves the UUIDs Attio's webhook payloads carry (`object_id`, `list_id`)
back to the human slugs the rest of this module works with (`organizations`,
`buyer_role`, ...).

Looked up from Attio once per process and cached, rather than hardcoding
UUIDs anywhere — those would silently go stale if a workspace were ever
recreated, whereas `api_slug` is stable and already how every other script in
this repo (`sync-postgres.ps1`, `crm-sync`) addresses objects and lists.
"""

from ddl_commands.modules.attio_sync.retry import get_with_retry
from ddl_commands.shared.attio.client import AttioClient

_KNOWN_OBJECTS = {"organizations", "person", "deals"}
_KNOWN_LISTS = {"buyer_role", "seller_role"}

_object_slug_by_id: dict[str, str] | None = None
_list_slug_by_id: dict[str, str] | None = None


async def _load_objects(client: AttioClient) -> dict[str, str]:
    response = await get_with_retry(client, "/objects")
    return {
        item["id"]["object_id"]: item["api_slug"]
        for item in response.get("data", [])
        if item.get("api_slug") in _KNOWN_OBJECTS
    }


async def _load_lists(client: AttioClient) -> dict[str, str]:
    response = await get_with_retry(client, "/lists")
    return {
        item["id"]["list_id"]: item["api_slug"]
        for item in response.get("data", [])
        if item.get("api_slug") in _KNOWN_LISTS
    }


async def object_slug(client: AttioClient, object_id: str) -> str | None:
    """Returns e.g. `"organizations"` for a webhook event's `id.object_id`,
    or `None` if the event is for an object this sync doesn't cover
    (ignore it — see `dispatch.py`)."""
    global _object_slug_by_id
    if _object_slug_by_id is None:
        _object_slug_by_id = await _load_objects(client)
    return _object_slug_by_id.get(object_id)


async def list_slug(client: AttioClient, list_id: str) -> str | None:
    """Returns e.g. `"buyer_role"` for a webhook event's `id.list_id`, or
    `None` if the event is for a list this sync doesn't cover."""
    global _list_slug_by_id
    if _list_slug_by_id is None:
        _list_slug_by_id = await _load_lists(client)
    return _list_slug_by_id.get(list_id)


def reset_cache() -> None:
    """Test-only: clears the cached lookups between test cases."""
    global _object_slug_by_id, _list_slug_by_id
    _object_slug_by_id = None
    _list_slug_by_id = None
