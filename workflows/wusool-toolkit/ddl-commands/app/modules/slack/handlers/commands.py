"""`/edit-seller`, `/remove-seller`, `/edit-buyer`, `/remove-buyer`. Thin
adapters: parse/validate the payload, resolve the target (fast — a single
lookup), then open the disambiguation modal. Mirrors matching-engine's
`/find-match` handler shape exactly (ack first, idempotency-guard on
`trigger_id`, usage message on empty text, ephemeral on no match).

`/edit-*` resolves with `include_archived=True` so an archived row can be
found and restored; `/remove-*` resolves with the default `False` — removing
an already-removed row isn't a useful action.
"""

import logging

from slack_bolt.async_app import AsyncApp

from app.modules.buyers.dependencies import resolve_buyer
from app.modules.sellers.dependencies import resolve_seller
from app.modules.slack.views.buyer_selection import build_buyer_selection_modal
from app.modules.slack.views.seller_selection import build_seller_selection_modal
from app.shared.idempotency import InMemoryIdempotencyStore

logger = logging.getLogger(__name__)

_idempotency_store = InMemoryIdempotencyStore()


def register(app: AsyncApp) -> None:
    @app.command("/edit-seller")
    async def handle_edit_seller(ack, command, client):  # noqa: ANN001
        await ack()
        await _handle_seller_command(
            command, client, action="edit_seller", include_archived=True, intent="edit"
        )

    @app.command("/remove-seller")
    async def handle_remove_seller(ack, command, client):  # noqa: ANN001
        await ack()
        await _handle_seller_command(
            command, client, action="remove_seller", include_archived=False, intent="remove"
        )

    @app.command("/edit-buyer")
    async def handle_edit_buyer(ack, command, client):  # noqa: ANN001
        await ack()
        await _handle_buyer_command(
            command, client, action="edit_buyer", include_archived=True, intent="edit"
        )

    @app.command("/remove-buyer")
    async def handle_remove_buyer(ack, command, client):  # noqa: ANN001
        await ack()
        await _handle_buyer_command(
            command, client, action="remove_buyer", include_archived=False, intent="remove"
        )


async def _handle_seller_command(
    command: dict, client, *, action: str, include_archived: bool, intent: str  # noqa: ANN001
) -> None:
    idempotency_key = f"{action}:{command.get('trigger_id')}"
    if _idempotency_store.seen(idempotency_key):
        logger.info("%s_duplicate_delivery_skipped key=%s", action, idempotency_key)
        return
    _idempotency_store.mark(idempotency_key)

    seller_name = (command.get("text") or "").strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not seller_name:
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"Usage: `/{action.replace('_', '-')} <seller name>`",
        )
        return

    resolution = await resolve_seller(seller_name, include_archived=include_archived)

    if resolution.status == "none":
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"No seller found for '{seller_name}'. Try a different name.",
        )
        return

    assert resolution.candidates is not None
    await client.views_open(
        trigger_id=command["trigger_id"],
        view=build_seller_selection_modal(
            resolution.candidates,
            requested_by=user_id,
            channel_id=channel_id,
            intent=intent,
        ),
    )


async def _handle_buyer_command(
    command: dict, client, *, action: str, include_archived: bool, intent: str  # noqa: ANN001
) -> None:
    idempotency_key = f"{action}:{command.get('trigger_id')}"
    if _idempotency_store.seen(idempotency_key):
        logger.info("%s_duplicate_delivery_skipped key=%s", action, idempotency_key)
        return
    _idempotency_store.mark(idempotency_key)

    buyer_name = (command.get("text") or "").strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not buyer_name:
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"Usage: `/{action.replace('_', '-')} <buyer name>`",
        )
        return

    resolution = await resolve_buyer(buyer_name, include_archived=include_archived)

    if resolution.status == "none":
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"No buyer found for '{buyer_name}'. Try a different name.",
        )
        return

    assert resolution.candidates is not None
    await client.views_open(
        trigger_id=command["trigger_id"],
        view=build_buyer_selection_modal(
            resolution.candidates,
            requested_by=user_id,
            channel_id=channel_id,
            intent=intent,
        ),
    )
