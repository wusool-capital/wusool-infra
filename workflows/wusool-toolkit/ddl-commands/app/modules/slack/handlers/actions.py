"""Selection-modal submissions, edit-form submissions, and archive/cancel
button actions for sellers and buyers. Thin adapters: parse the Slack
payload, call the application use case, translate the result back into a
Slack message. Every write re-validates against the database inside its use
case — Slack payload state is never trusted on its own.
"""

import json

from pydantic import ValidationError
from slack_bolt.async_app import AsyncApp

from app.modules.buyers.application.use_cases import (
    BuyerAlreadyArchivedError,
    BuyerNotFoundError,
)
from app.modules.buyers.dependencies import (
    build_archive_buyer_use_case,
    build_update_buyer_use_case,
    resolve_buyer_by_id,
)
from app.modules.buyers.schemas import BuyerUpdate
from app.modules.matching.dependencies import (
    count_match_results_for_buyer,
    count_match_results_for_seller,
)
from app.modules.sellers.application.use_cases import (
    SellerAlreadyArchivedError,
    SellerNotFoundError,
)
from app.modules.sellers.dependencies import (
    build_archive_seller_use_case,
    build_update_seller_use_case,
    resolve_seller_by_id,
)
from app.modules.sellers.schemas import SellerUpdate
from app.modules.slack.views.buyer_form import build_buyer_edit_form_modal
from app.modules.slack.views.form_values import (
    extract_money,
    get_bool_select,
    get_checkbox_selected,
    get_date,
    get_number,
    get_text,
    pydantic_errors_to_slack,
)
from app.modules.slack.views.remove_confirmation import build_remove_confirmation_blocks
from app.modules.slack.views.seller_form import build_seller_edit_form_modal


def register(app: AsyncApp) -> None:
    @app.view("seller_selection_modal")
    async def handle_seller_selection_submission(ack, body, view, client):  # noqa: ANN001
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body.get("user", {}).get("id")
        channel_id = metadata.get("channel_id")
        intent = metadata.get("intent")
        if not channel_id or not intent:
            await ack()
            return

        selected = view["state"]["values"]["seller_role_id"]["selected_seller"]["selected_option"]
        seller_role_id = selected["value"]

        if intent == "edit":
            role = await resolve_seller_by_id(seller_role_id)
            if role is None:
                await ack()
                await client.chat_postEphemeral(
                    channel=channel_id, user=requested_by, text="This seller could not be found."
                )
                return
            await ack(
                response_action="update",
                view=build_seller_edit_form_modal(
                    role, requested_by=requested_by, channel_id=channel_id
                ),
            )
            return

        await ack()
        role = await resolve_seller_by_id(seller_role_id)
        org_name = role.organization.name if role else seller_role_id
        count = await count_match_results_for_seller(seller_role_id)
        await client.chat_postEphemeral(
            channel=channel_id,
            user=requested_by,
            text=f"Remove seller profile for {org_name}?",
            blocks=build_remove_confirmation_blocks(seller_role_id, org_name, count, kind="seller"),
        )

    @app.view("buyer_selection_modal")
    async def handle_buyer_selection_submission(ack, body, view, client):  # noqa: ANN001
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body.get("user", {}).get("id")
        channel_id = metadata.get("channel_id")
        intent = metadata.get("intent")
        if not channel_id or not intent:
            await ack()
            return

        selected = view["state"]["values"]["buyer_role_id"]["selected_buyer"]["selected_option"]
        buyer_role_id = selected["value"]

        if intent == "edit":
            role = await resolve_buyer_by_id(buyer_role_id)
            if role is None:
                await ack()
                await client.chat_postEphemeral(
                    channel=channel_id, user=requested_by, text="This buyer could not be found."
                )
                return
            await ack(
                response_action="update",
                view=build_buyer_edit_form_modal(
                    role, requested_by=requested_by, channel_id=channel_id
                ),
            )
            return

        await ack()
        role = await resolve_buyer_by_id(buyer_role_id)
        org_name = role.organization.name if role else buyer_role_id
        count = await count_match_results_for_buyer(buyer_role_id)
        await client.chat_postEphemeral(
            channel=channel_id,
            user=requested_by,
            text=f"Remove buyer profile for {org_name}?",
            blocks=build_remove_confirmation_blocks(buyer_role_id, org_name, count, kind="buyer"),
        )

    @app.view("seller_edit_form_modal")
    async def handle_seller_edit_form_submission(ack, body, view, client):  # noqa: ANN001
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body.get("user", {}).get("id")
        channel_id = metadata.get("channel_id")
        seller_role_id = metadata.get("seller_role_id")
        org_name = metadata.get("org_name", "")
        archived = bool(metadata.get("archived", False))

        values = view["state"]["values"]
        raw_fields = _extract_seller_fields(values)

        errors: dict[str, str] = {}
        validated: SellerUpdate | None = None
        try:
            validated = SellerUpdate.model_validate(raw_fields)
        except ValidationError as exc:
            errors.update(pydantic_errors_to_slack(exc.errors()))

        restore_confirmed = get_checkbox_selected(values, "restore_confirmation", "confirm_restore")
        if archived and not restore_confirmed:
            errors["restore_confirmation"] = (
                "You must confirm you intend to restore this profile."
            )

        if errors:
            await ack(response_action="errors", errors=errors)
            return

        await ack()
        assert validated is not None
        fields = validated.model_dump()

        try:
            await build_update_seller_use_case().execute(
                seller_role_id, fields, requested_by, restore=archived
            )
        except SellerNotFoundError:
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="This seller could not be found."
            )
            return
        except SellerAlreadyArchivedError:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=requested_by,
                text="This seller is archived — reopen with `/edit-seller` to restore it.",
            )
            return

        verb = "Restored and updated" if archived else "Updated"
        await client.chat_postEphemeral(
            channel=channel_id, user=requested_by, text=f"{verb} seller profile for {org_name}."
        )

    @app.view("buyer_edit_form_modal")
    async def handle_buyer_edit_form_submission(ack, body, view, client):  # noqa: ANN001
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body.get("user", {}).get("id")
        channel_id = metadata.get("channel_id")
        buyer_role_id = metadata.get("buyer_role_id")
        org_name = metadata.get("org_name", "")
        archived = bool(metadata.get("archived", False))

        values = view["state"]["values"]
        raw_fields = _extract_buyer_fields(values)

        errors: dict[str, str] = {}
        validated: BuyerUpdate | None = None
        try:
            validated = BuyerUpdate.model_validate(raw_fields)
        except ValidationError as exc:
            errors.update(pydantic_errors_to_slack(exc.errors()))

        restore_confirmed = get_checkbox_selected(values, "restore_confirmation", "confirm_restore")
        if archived and not restore_confirmed:
            errors["restore_confirmation"] = (
                "You must confirm you intend to restore this profile."
            )

        if errors:
            await ack(response_action="errors", errors=errors)
            return

        await ack()
        assert validated is not None
        fields = validated.model_dump()

        try:
            await build_update_buyer_use_case().execute(
                buyer_role_id, fields, requested_by, restore=archived
            )
        except BuyerNotFoundError:
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="This buyer could not be found."
            )
            return
        except BuyerAlreadyArchivedError:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=requested_by,
                text="This buyer is archived — reopen with `/edit-buyer` to restore it.",
            )
            return

        verb = "Restored and updated" if archived else "Updated"
        await client.chat_postEphemeral(
            channel=channel_id, user=requested_by, text=f"{verb} buyer profile for {org_name}."
        )

    @app.action("archive_seller")
    async def handle_archive_seller(ack, body, client, respond):  # noqa: ANN001
        await ack()
        await _handle_archive_decision(
            body,
            client,
            respond,
            kind="seller",
            use_case=build_archive_seller_use_case(),
            not_found_error=SellerNotFoundError,
            already_archived_error=SellerAlreadyArchivedError,
        )

    @app.action("cancel_seller")
    async def handle_cancel_seller(ack, respond):  # noqa: ANN001
        await ack()
        await respond(replace_original=True, text="Cancelled.")

    @app.action("archive_buyer")
    async def handle_archive_buyer(ack, body, client, respond):  # noqa: ANN001
        await ack()
        await _handle_archive_decision(
            body,
            client,
            respond,
            kind="buyer",
            use_case=build_archive_buyer_use_case(),
            not_found_error=BuyerNotFoundError,
            already_archived_error=BuyerAlreadyArchivedError,
        )

    @app.action("cancel_buyer")
    async def handle_cancel_buyer(ack, respond):  # noqa: ANN001
        await ack()
        await respond(replace_original=True, text="Cancelled.")


async def _handle_archive_decision(
    body: dict, client, respond, *, kind: str, use_case, not_found_error, already_archived_error  # noqa: ANN001
) -> None:
    action = body["actions"][0]
    role_id = action.get("value")
    channel_id = body["channel"]["id"]
    user_id = body["user"]["id"]

    try:
        await use_case.execute(role_id, user_id)
    except not_found_error:
        await client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=f"This {kind} could not be found."
        )
        return
    except already_archived_error:
        await client.chat_postEphemeral(
            channel=channel_id, user=user_id, text=f"This {kind} has already been archived."
        )
        return

    await client.chat_postEphemeral(
        channel=channel_id, user=user_id, text=f"Archived by <@{user_id}>."
    )
    await respond(replace_original=True, text=f"🗑️ Archived by <@{user_id}>.")


def _extract_seller_fields(values: dict) -> dict:
    return {
        "outreach_tier": get_text(values, "outreach_tier", "outreach_tier"),
        "appetite_signal": get_text(values, "appetite_signal", "appetite_signal"),
        "relationship_status": get_text(values, "relationship_status", "relationship_status"),
        "est_revenue": extract_money(values, "est_revenue"),
        "est_ebitda": extract_money(values, "est_ebitda"),
        "owner_salary": extract_money(values, "owner_salary"),
        "valuation_low": extract_money(values, "valuation_low"),
        "valuation_mid": extract_money(values, "valuation_mid"),
        "valuation_high": extract_money(values, "valuation_high"),
        "sell_timeline": get_text(values, "sell_timeline", "sell_timeline"),
        "readiness_score": get_number(values, "readiness_score", "readiness_score"),
        "readiness_band": get_text(values, "readiness_band", "readiness_band"),
        "intake_source": get_text(values, "intake_source", "intake_source"),
        "last_attempt_date": get_date(values, "last_attempt_date", "last_attempt_date"),
        "last_attempt_channel": get_text(
            values, "last_attempt_channel", "last_attempt_channel"
        ),
        "last_attempt_outcome": get_text(
            values, "last_attempt_outcome", "last_attempt_outcome"
        ),
        "lead_quality_score": get_number(values, "lead_quality_score", "lead_quality_score"),
        "re_engage_date": get_date(values, "re_engage_date", "re_engage_date"),
    }


def _extract_buyer_fields(values: dict) -> dict:
    return {
        "model": get_text(values, "model", "model"),
        "mandate_status": get_text(values, "mandate_status", "mandate_status"),
        "ebitda_floor": extract_money(values, "ebitda_floor"),
        "check_size_min": extract_money(values, "check_size_min"),
        "check_size_max": extract_money(values, "check_size_max"),
        "ev_ceiling": extract_money(values, "ev_ceiling"),
        "deal_structure_tolerance": get_text(
            values, "deal_structure_tolerance", "deal_structure_tolerance"
        ),
        "earnout_tolerance": get_text(values, "earnout_tolerance", "earnout_tolerance"),
        "profitable_only": get_bool_select(values, "profitable_only", "profitable_only"),
        "investment_strategy": get_text(values, "investment_strategy", "investment_strategy"),
        "notes": get_text(values, "notes", "notes"),
        "acquisition_enrichment": get_text(
            values, "acquisition_enrichment", "acquisition_enrichment"
        ),
        "deals_introduced": get_number(values, "deals_introduced", "deals_introduced"),
        "deals_converted": get_number(values, "deals_converted", "deals_converted"),
    }
