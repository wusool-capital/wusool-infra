"""`/enrich-seller <seller name>` and `/enrich-buyer <buyer name>` — always
kind-scoped, on purpose: there is no bare `/enrich` (would need the
role-selection modal for every single-role org too, not just an
ambiguous one). Mirrors `ddl_commands`'/`matching_engine`'s own command
handler shape: ack first, idempotency-guard on `trigger_id`, usage
message on empty text.
"""

import logging
import time
from collections.abc import Coroutine
from typing import Any, Literal

from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.enrichment.api.dependencies import (
    propose_and_post,
    resolve_org_roles,
    target_from_resolved,
)
from app.modules.enrichment.api.slack.views.role_selection import build_role_selection_modal
from app.modules.notifications import (
    SlackCommandPayload,
    build_notice_modal,
    open_loading_modal,
)
from app.modules.utilities import get_shared_idempotency_store, get_shared_task_runner

logger = logging.getLogger(__name__)

_idempotency_store = get_shared_idempotency_store()
_task_runner = get_shared_task_runner()
_TRIGGER_ID_BUDGET_MS = 2500


async def _run(
    action: str,
    command: SlackCommandPayload,
    client: AsyncWebClient,
    coro: Coroutine[Any, Any, None],
) -> None:
    started = time.monotonic()
    try:
        await coro
    except Exception:
        logger.exception("%s_failed", action)
        try:
            await client.chat_postEphemeral(
                channel=command["channel_id"],
                user=command["user_id"],
                text=f"*`/{action}` failed.* The error has been logged.",
            )
        except Exception:
            logger.exception("%s_error_notice_failed", action)
    finally:
        elapsed_ms = (time.monotonic() - started) * 1000
        log = logger.warning if elapsed_ms > _TRIGGER_ID_BUDGET_MS else logger.info
        log("%s_finished elapsed_ms=%.0f", action, elapsed_ms)


def register(app: AsyncApp) -> None:
    @app.command("/enrich-seller")
    async def handle_enrich_seller(
        ack: AsyncAck, command: SlackCommandPayload, client: AsyncWebClient
    ) -> None:
        await ack()
        await _run(
            "enrich-seller",
            command,
            client,
            _handle_enrich_command(command, client, role_kind="seller"),
        )

    @app.command("/enrich-buyer")
    async def handle_enrich_buyer(
        ack: AsyncAck, command: SlackCommandPayload, client: AsyncWebClient
    ) -> None:
        await ack()
        await _run(
            "enrich-buyer",
            command,
            client,
            _handle_enrich_command(command, client, role_kind="buyer"),
        )


async def _handle_enrich_command(
    command: SlackCommandPayload,
    client: AsyncWebClient,
    *,
    role_kind: Literal["seller", "buyer"],
) -> None:
    action = f"enrich-{role_kind}"
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
            channel=channel_id, user=user_id, text=f"*Usage:* `/{action} <{role_kind} name>`"
        )
        return

    title = f"Enrich {role_kind}"
    view_id = await open_loading_modal(client, trigger_id=command["trigger_id"], title=title)

    candidates = [c for c in await resolve_org_roles(org_name) if c.kind == role_kind]

    if not candidates:
        await client.views_update(
            view_id=view_id,
            view=build_notice_modal(
                title, f"No active {role_kind} found for *{org_name}*. _Try a different name._"
            ),
        )
        return

    if len(candidates) == 1:
        _task_runner.run(
            lambda: propose_and_post(target_from_resolved(candidates[0]), channel_id=channel_id),
            name=f"enrich:{candidates[0].role_id}",
        )
        # The proposal arrives as a channel message, not in this modal — say so
        # rather than leaving the operator on a spinner that never resolves.
        await client.views_update(
            view_id=view_id,
            view=build_notice_modal(
                title,
                f"Researching *{org_name}*… the proposal will post in this channel shortly.",
            ),
        )
        return

    await client.views_update(
        view_id=view_id,
        view=build_role_selection_modal(
            candidates, search_term=org_name, requested_by=user_id, channel_id=channel_id
        ),
    )
