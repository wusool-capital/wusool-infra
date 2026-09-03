"""`/edit-seller`, `/edit-buyer`, `/add-seller`, `/add-buyer`. Thin adapters:
parse/validate the payload, resolve the target (fast — a single lookup),
then open the next modal in the flow. Mirrors matching-engine's
`/find-match` handler shape exactly (ack first, idempotency-guard on
`trigger_id`, usage message on empty text, ephemeral on no match).
"""

import logging
import time

from slack_bolt.async_app import AsyncApp

from app.modules.ddl_commands.api.dependencies import (
    resolve_buyer,
    resolve_seller,
    search_organizations,
)
from app.modules.ddl_commands.api.slack.views.buyer_add_form import build_buyer_add_form_modal
from app.modules.ddl_commands.api.slack.views.buyer_role_selection import (
    build_buyer_selection_modal,
)
from app.modules.ddl_commands.api.slack.views.organization_selection import (
    build_organization_selection_modal,
)
from app.modules.ddl_commands.api.slack.views.seller_add_form import build_seller_add_form_modal
from app.modules.ddl_commands.api.slack.views.seller_role_selection import (
    build_seller_selection_modal,
)
from app.modules.utilities.persistence.idempotency import InMemoryIdempotencyStore

logger = logging.getLogger(__name__)

_idempotency_store = InMemoryIdempotencyStore()

# Slack invalidates a command's `trigger_id` 3s after it's issued. Anything
# slower than this and `views_open` is already doomed — worth a WARNING.
_TRIGGER_ID_BUDGET_MS = 2500


async def _run(action: str, command: dict, client, coro) -> None:  # noqa: ANN001
    """Everything after `ack()` runs detached from the HTTP response (Bolt is
    built with `process_before_response=False`), so nothing that happens here
    can reach Slack on its own. Two distinct failure modes get lost without
    this wrapper:

    - a raised exception reaches `@bolt_app.error` but never the operator, who
      only sees Slack's own generic message;
    - overrunning Slack's 3-second `trigger_id` window raises nothing at all —
      `views_open` just fails, and the command dies silently.

    So: time every invocation, log the elapsed ms either way, and tell the
    user when their command actually failed.
    """
    started = time.monotonic()
    try:
        await coro
    except Exception:
        logger.exception("%s_failed", action)
        try:
            await client.chat_postEphemeral(
                channel=command["channel_id"],
                user=command["user_id"],
                text=f"*`/{action.replace('_', '-')}` failed.* The error has been logged.",
            )
        except Exception:
            logger.exception("%s_error_notice_failed", action)
    finally:
        elapsed_ms = (time.monotonic() - started) * 1000
        log = logger.warning if elapsed_ms > _TRIGGER_ID_BUDGET_MS else logger.info
        log("%s_finished elapsed_ms=%.0f", action, elapsed_ms)


def register(app: AsyncApp) -> None:
    @app.command("/edit-seller")
    async def handle_edit_seller(ack, command, client):  # noqa: ANN001
        await ack()
        await _run(
            "edit_seller",
            command,
            client,
            _handle_seller_command(command, client, action="edit_seller"),
        )

    @app.command("/edit-buyer")
    async def handle_edit_buyer(ack, command, client):  # noqa: ANN001
        await ack()
        await _run(
            "edit_buyer",
            command,
            client,
            _handle_buyer_command(command, client, action="edit_buyer"),
        )

    @app.command("/add-seller")
    async def handle_add_seller(ack, command, client):  # noqa: ANN001
        await ack()
        await _run(
            "add_seller", command, client, _handle_add_command(command, client, kind="seller")
        )

    @app.command("/add-buyer")
    async def handle_add_buyer(ack, command, client):  # noqa: ANN001
        await ack()
        await _run("add_buyer", command, client, _handle_add_command(command, client, kind="buyer"))


async def _handle_seller_command(command: dict, client, *, action: str) -> None:  # noqa: ANN001
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
            text=f"*Usage:* `/{action.replace('_', '-')} <seller name>`",
        )
        return

    resolution = await resolve_seller(seller_name)

    if resolution.status == "none":
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"No seller found for *{seller_name}*. _Try a different name._",
        )
        return

    assert resolution.candidates is not None
    await client.views_open(
        trigger_id=command["trigger_id"],
        view=build_seller_selection_modal(
            resolution.candidates, requested_by=user_id, channel_id=channel_id
        ),
    )


async def _handle_buyer_command(command: dict, client, *, action: str) -> None:  # noqa: ANN001
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
            text=f"*Usage:* `/{action.replace('_', '-')} <buyer name>`",
        )
        return

    resolution = await resolve_buyer(buyer_name)

    if resolution.status == "none":
        await client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"No buyer found for *{buyer_name}*. _Try a different name._",
        )
        return

    assert resolution.candidates is not None
    await client.views_open(
        trigger_id=command["trigger_id"],
        view=build_buyer_selection_modal(
            resolution.candidates, requested_by=user_id, channel_id=channel_id
        ),
    )


async def _handle_add_command(command: dict, client, *, kind: str) -> None:  # noqa: ANN001
    action = f"add_{kind}"
    idempotency_key = f"{action}:{command.get('trigger_id')}"
    if _idempotency_store.seen(idempotency_key):
        logger.info("%s_duplicate_delivery_skipped key=%s", action, idempotency_key)
        return
    _idempotency_store.mark(idempotency_key)

    org_name = (command.get("text") or "").strip()
    channel_id = command["channel_id"]
    user_id = command["user_id"]

    if not org_name:
        await client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=f"*Usage:* `/add-{kind} <organization name>`"
        )
        return

    candidates = await search_organizations(org_name)

    if not candidates:
        build_form = build_seller_add_form_modal if kind == "seller" else build_buyer_add_form_modal
        await client.views_open(
            trigger_id=command["trigger_id"],
            view=build_form(
                org=None, requested_by=user_id, channel_id=channel_id, prefill_name=org_name
            ),
        )
        return

    await client.views_open(
        trigger_id=command["trigger_id"],
        view=build_organization_selection_modal(
            candidates,
            kind=kind,
            search_term=org_name,
            requested_by=user_id,
            channel_id=channel_id,
        ),
    )
