"""Selection-modal, field-picker, edit-form, and add-form submissions for
sellers and buyers. Every write goes to DEV Attio *first*, then Postgres, in
the same submission — if the Attio write fails, nothing is written to
Postgres at all (see `_write_seller_edit`/`_write_buyer_edit` and
`_write_seller_add`/`_write_buyer_add`). Slack payload state is never
trusted on its own; the write targets (org record ID, role entry ID) are
always re-resolved from the currently-loaded row, not from the payload.
"""

import json
from typing import Any

from pydantic import ValidationError
from slack_bolt.async_app import AsyncApp
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_sdk.web.async_client import AsyncWebClient

from app.modules.attio import AttioError, get_attio_client
from app.modules.attio.providers.attio.entries import (
    RoleEntryNotFoundError,
    create_organization,
    create_role_entry,
    patch_organization,
    patch_role_entry,
    resolve_role_entry_id,
)
from app.modules.attio.providers.attio.options import OptionNotFoundError
from app.modules.ddl_commands.api.buyers import (
    BUYER_ROLE_FIELDS,
    BUYER_ROLE_FIELDS_BY_NAME,
    GATED_BUYER_ROLE_FIELDS,
    BuyerUpdate,
)
from app.modules.ddl_commands.api.dependencies import (
    build_create_buyer_use_case,
    build_create_seller_use_case,
    build_update_buyer_use_case,
    build_update_seller_use_case,
    resolve_buyer_by_id,
    resolve_organization,
    resolve_seller_by_id,
)
from app.modules.ddl_commands.api.organizations import (
    ORGANIZATION_FIELDS,
    ORGANIZATION_FIELDS_BY_NAME,
    OrganizationUpdate,
)
from app.modules.ddl_commands.api.sellers import (
    GATED_SELLER_ROLE_FIELDS,
    SELLER_ROLE_FIELDS,
    SELLER_ROLE_FIELDS_BY_NAME,
    SellerUpdate,
)
from app.modules.ddl_commands.api.slack.views.buyer_add_form import build_buyer_add_form_modal
from app.modules.ddl_commands.api.slack.views.buyer_form import build_buyer_edit_form_modal
from app.modules.ddl_commands.api.slack.views.dynamic_fields import extract_field_value
from app.modules.ddl_commands.api.slack.views.field_picker import (
    build_field_picker_modal,
    extract_selected_fields,
)
from app.modules.ddl_commands.api.slack.views.form_values import (
    get_checkbox_selected,
    get_text,
    pydantic_errors_to_slack,
)
from app.modules.ddl_commands.api.slack.views.organization_selection import (
    NEW_ORGANIZATION_VALUE,
)
from app.modules.ddl_commands.api.slack.views.seller_add_form import build_seller_add_form_modal
from app.modules.ddl_commands.api.slack.views.seller_form import build_seller_edit_form_modal
from app.modules.ddl_commands.application.buyers import (
    BuyerAlreadyExistsError,
    BuyerNotFoundError,
)
from app.modules.ddl_commands.application.sellers import (
    SellerAlreadyExistsError,
    SellerNotFoundError,
)
from app.modules.ddl_commands.providers.attio.write_payload import (
    build_attio_values,
    build_postgres_values,
)
from app.modules.notifications import SlackInteractionBody, SlackViewSubmissionPayload


def register(app: AsyncApp) -> None:
    @app.view("seller_role_selection_modal")
    async def handle_seller_selection_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata.get("channel_id")
        if not channel_id:
            await ack()
            return

        selected = view["state"]["values"]["seller_role_id"]["selected_seller"]["selected_option"]
        seller_role_id = selected["value"]

        # No database call before `ack()`: Slack abandons a view submission
        # after 3s, and Bolt's runner reports that by returning an empty 200
        # rather than raising, so an overrun here fails silently. The name is
        # carried in `private_metadata` by the modal that produced this
        # submission; the role's existence is re-checked by the field-picker
        # handler below, which does have to load it anyway.
        org_name = (metadata.get("org_names") or {}).get(seller_role_id)
        if org_name is None:
            await ack()
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="This *seller* could not be found."
            )
            return
        await ack(
            response_action="update",
            view=build_field_picker_modal(
                kind="seller",
                role_id=seller_role_id,
                org_name=org_name,
                requested_by=requested_by,
                channel_id=channel_id,
                role_fields=SELLER_ROLE_FIELDS,
            ),
        )

    @app.view("buyer_role_selection_modal")
    async def handle_buyer_selection_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata.get("channel_id")
        if not channel_id:
            await ack()
            return

        selected = view["state"]["values"]["buyer_role_id"]["selected_buyer"]["selected_option"]
        buyer_role_id = selected["value"]

        # See the seller handler above — no database call before `ack()`.
        org_name = (metadata.get("org_names") or {}).get(buyer_role_id)
        if org_name is None:
            await ack()
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="This *buyer* could not be found."
            )
            return
        await ack(
            response_action="update",
            view=build_field_picker_modal(
                kind="buyer",
                role_id=buyer_role_id,
                org_name=org_name,
                requested_by=requested_by,
                channel_id=channel_id,
                role_fields=BUYER_ROLE_FIELDS,
            ),
        )

    @app.view("seller_field_picker_modal")
    async def handle_seller_field_picker_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata["channel_id"]
        seller_role_id = metadata["seller_role_id"]

        org_fields, role_fields = extract_selected_fields(view["state"]["values"])
        if not org_fields and not role_fields:
            await ack()
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="Pick at least *one field* to edit."
            )
            return

        role = await resolve_seller_by_id(seller_role_id)
        if role is None:
            await ack()
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="This *seller* could not be found."
            )
            return
        await ack(
            response_action="update",
            view=build_seller_edit_form_modal(
                role,
                role.organization,
                selected_org_fields=org_fields,
                selected_role_fields=role_fields,
                requested_by=requested_by,
                channel_id=channel_id,
            ),
        )

    @app.view("buyer_field_picker_modal")
    async def handle_buyer_field_picker_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata["channel_id"]
        buyer_role_id = metadata["buyer_role_id"]

        org_fields, role_fields = extract_selected_fields(view["state"]["values"])
        if not org_fields and not role_fields:
            await ack()
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="Pick at least *one field* to edit."
            )
            return

        role = await resolve_buyer_by_id(buyer_role_id)
        if role is None:
            await ack()
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="This *buyer* could not be found."
            )
            return
        await ack(
            response_action="update",
            view=build_buyer_edit_form_modal(
                role,
                role.organization,
                selected_org_fields=org_fields,
                selected_role_fields=role_fields,
                requested_by=requested_by,
                channel_id=channel_id,
            ),
        )

    @app.view("seller_edit_form_modal")
    async def handle_seller_edit_form_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata["channel_id"]
        seller_role_id = metadata["seller_role_id"]
        org_attio_id = metadata["org_attio_id"]
        org_name = metadata["org_name"]
        selected_org_fields: list[str] = metadata["selected_org_fields"]
        selected_role_fields: list[str] = metadata["selected_role_fields"]

        values = view["state"]["values"]
        org_extracted = {
            name: extract_field_value(
                ORGANIZATION_FIELDS_BY_NAME[name], values, block_id_prefix="org_"
            )
            for name in selected_org_fields
        }
        role_extracted = {
            name: extract_field_value(SELLER_ROLE_FIELDS_BY_NAME[name], values)
            for name in selected_role_fields
        }

        errors: dict[str, str] = {}
        org_validated: OrganizationUpdate | None = None
        role_validated: SellerUpdate | None = None
        try:
            org_validated = OrganizationUpdate.model_validate(org_extracted)
        except ValidationError as exc:
            for block_id, msg in pydantic_errors_to_slack(exc.errors()).items():
                errors[f"org_{block_id}"] = msg
        try:
            role_validated = SellerUpdate.model_validate(role_extracted)
        except ValidationError as exc:
            errors.update(pydantic_errors_to_slack(exc.errors()))

        gated_selected = GATED_SELLER_ROLE_FIELDS & set(selected_role_fields)
        if gated_selected and not get_checkbox_selected(
            values, "gated_field_confirmation", "confirm_correction"
        ):
            errors["gated_field_confirmation"] = (
                "You must confirm this is a correction, not a routine edit."
            )

        if errors:
            await ack(response_action="errors", errors=errors)
            return

        assert org_validated is not None
        assert role_validated is not None
        org_extracted = org_validated.model_dump(exclude_unset=True)
        role_extracted = role_validated.model_dump(exclude_unset=True)

        await ack()
        try:
            await _write_seller_edit(
                seller_role_id=seller_role_id,
                org_attio_id=org_attio_id,
                org_extracted=org_extracted,
                role_extracted=role_extracted,
            )
        except SellerNotFoundError:
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="This *seller* could not be found."
            )
            return
        except _OrgRemovedError:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=requested_by,
                text=f"*{org_name}*'s Attio record is gone or was merged — can't write to it.",
            )
            return
        except PartialWriteError as exc:
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text=_partial_write_message(exc)
            )
            return

        await client.chat_postEphemeral(
            channel=channel_id,
            user=requested_by,
            text=f"*Updated* seller profile for *{org_name}*.",
        )

    @app.view("buyer_edit_form_modal")
    async def handle_buyer_edit_form_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata["channel_id"]
        buyer_role_id = metadata["buyer_role_id"]
        org_attio_id = metadata["org_attio_id"]
        org_name = metadata["org_name"]
        selected_org_fields: list[str] = metadata["selected_org_fields"]
        selected_role_fields: list[str] = metadata["selected_role_fields"]

        values = view["state"]["values"]
        org_extracted = {
            name: extract_field_value(
                ORGANIZATION_FIELDS_BY_NAME[name], values, block_id_prefix="org_"
            )
            for name in selected_org_fields
        }
        role_extracted = {
            name: extract_field_value(BUYER_ROLE_FIELDS_BY_NAME[name], values)
            for name in selected_role_fields
        }

        errors: dict[str, str] = {}
        org_validated: OrganizationUpdate | None = None
        role_validated: BuyerUpdate | None = None
        try:
            org_validated = OrganizationUpdate.model_validate(org_extracted)
        except ValidationError as exc:
            for block_id, msg in pydantic_errors_to_slack(exc.errors()).items():
                errors[f"org_{block_id}"] = msg
        try:
            role_validated = BuyerUpdate.model_validate(role_extracted)
        except ValidationError as exc:
            errors.update(pydantic_errors_to_slack(exc.errors()))

        gated_selected = GATED_BUYER_ROLE_FIELDS & set(selected_role_fields)
        if gated_selected and not get_checkbox_selected(
            values, "gated_field_confirmation", "confirm_correction"
        ):
            errors["gated_field_confirmation"] = (
                "You must confirm this is a correction, not a routine edit."
            )

        if errors:
            await ack(response_action="errors", errors=errors)
            return

        assert org_validated is not None
        assert role_validated is not None
        org_extracted = org_validated.model_dump(exclude_unset=True)
        role_extracted = role_validated.model_dump(exclude_unset=True)

        await ack()
        try:
            await _write_buyer_edit(
                buyer_role_id=buyer_role_id,
                org_attio_id=org_attio_id,
                org_extracted=org_extracted,
                role_extracted=role_extracted,
            )
        except BuyerNotFoundError:
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text="This *buyer* could not be found."
            )
            return
        except _OrgRemovedError:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=requested_by,
                text=f"*{org_name}*'s Attio record is gone or was merged — can't write to it.",
            )
            return
        except PartialWriteError as exc:
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text=_partial_write_message(exc)
            )
            return

        await client.chat_postEphemeral(
            channel=channel_id, user=requested_by, text=f"*Updated* buyer profile for *{org_name}*."
        )

    @app.view("organization_selection_modal")
    async def handle_organization_selection_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata["channel_id"]
        kind = metadata["kind"]
        search_term = metadata["search_term"]
        build_form = build_seller_add_form_modal if kind == "seller" else build_buyer_add_form_modal

        selected = view["state"]["values"]["organization_id"]["selected_organization"][
            "selected_option"
        ]
        selected_value = selected["value"]

        if selected_value == NEW_ORGANIZATION_VALUE:
            await ack(
                response_action="update",
                view=build_form(
                    org=None,
                    requested_by=requested_by,
                    channel_id=channel_id,
                    prefill_name=search_term,
                    duplicate_candidates=metadata.get("candidate_names") or [],
                ),
            )
            return

        org = await resolve_organization(selected_value)
        if org is None:
            await ack()
            await client.chat_postEphemeral(
                channel=channel_id,
                user=requested_by,
                text="This *organization* could not be found.",
            )
            return

        roles = org.seller_roles if kind == "seller" else org.buyer_roles
        has_role = any(r.is_active for r in roles)
        if has_role:
            await ack()
            await client.chat_postEphemeral(
                channel=channel_id,
                user=requested_by,
                text=(
                    f"*{org.name}* already has a {kind} role — "
                    f"_use `/edit-{kind} {org.name}` instead_."
                ),
            )
            return

        await ack(
            response_action="update",
            view=build_form(org=org, requested_by=requested_by, channel_id=channel_id),
        )

    @app.view("seller_add_form_modal")
    async def handle_seller_add_form_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata["channel_id"]
        is_new_org: bool = metadata["is_new_org"]
        org_attio_id: str | None = metadata["org_attio_id"]
        existing_org_name: str | None = metadata["org_name"]

        values = view["state"]["values"]
        org_extracted = {
            spec.name: extract_field_value(spec, values, block_id_prefix="org_")
            for spec in ORGANIZATION_FIELDS
        }
        role_extracted = {
            spec.name: extract_field_value(spec, values) for spec in SELLER_ROLE_FIELDS
        }

        errors: dict[str, str] = {}
        org_name = get_text(values, "name", "name") if is_new_org else existing_org_name
        if is_new_org and not org_name:
            errors["name"] = "Organization name is required."
        org_validated: OrganizationUpdate | None = None
        role_validated: SellerUpdate | None = None
        try:
            org_validated = OrganizationUpdate.model_validate(org_extracted)
        except ValidationError as exc:
            for block_id, msg in pydantic_errors_to_slack(exc.errors()).items():
                errors[f"org_{block_id}"] = msg
        try:
            role_validated = SellerUpdate.model_validate(role_extracted)
        except ValidationError as exc:
            errors.update(pydantic_errors_to_slack(exc.errors()))

        if errors:
            await ack(response_action="errors", errors=errors)
            return

        assert org_validated is not None
        assert role_validated is not None
        org_extracted = org_validated.model_dump(exclude_unset=True)
        role_extracted = role_validated.model_dump(exclude_unset=True)

        await ack()
        try:
            await _write_seller_add(
                is_new_org=is_new_org,
                org_attio_id=org_attio_id,
                org_name=org_name,
                org_extracted=org_extracted,
                role_extracted=role_extracted,
            )
        except SellerAlreadyExistsError:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=requested_by,
                text="A seller role already exists for this organization — "
                "_use `/edit-seller` instead_.",
            )
            return
        except PartialWriteError as exc:
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text=_partial_write_message(exc)
            )
            return

        await client.chat_postEphemeral(
            channel=channel_id, user=requested_by, text=f"*Added* seller profile for *{org_name}*."
        )

    @app.view("buyer_add_form_modal")
    async def handle_buyer_add_form_submission(
        ack: AsyncAck,
        body: SlackInteractionBody,
        view: SlackViewSubmissionPayload,
        client: AsyncWebClient,
    ) -> None:
        metadata = json.loads(view.get("private_metadata") or "{}")
        requested_by = metadata.get("requested_by") or body["user"]["id"]
        channel_id = metadata["channel_id"]
        is_new_org: bool = metadata["is_new_org"]
        org_attio_id: str | None = metadata["org_attio_id"]
        existing_org_name: str | None = metadata["org_name"]

        values = view["state"]["values"]
        org_extracted = {
            spec.name: extract_field_value(spec, values, block_id_prefix="org_")
            for spec in ORGANIZATION_FIELDS
        }
        role_extracted = {
            spec.name: extract_field_value(spec, values) for spec in BUYER_ROLE_FIELDS
        }

        errors: dict[str, str] = {}
        org_name = get_text(values, "name", "name") if is_new_org else existing_org_name
        if is_new_org and not org_name:
            errors["name"] = "Organization name is required."
        org_validated: OrganizationUpdate | None = None
        role_validated: BuyerUpdate | None = None
        try:
            org_validated = OrganizationUpdate.model_validate(org_extracted)
        except ValidationError as exc:
            for block_id, msg in pydantic_errors_to_slack(exc.errors()).items():
                errors[f"org_{block_id}"] = msg
        try:
            role_validated = BuyerUpdate.model_validate(role_extracted)
        except ValidationError as exc:
            errors.update(pydantic_errors_to_slack(exc.errors()))

        if errors:
            await ack(response_action="errors", errors=errors)
            return

        assert org_validated is not None
        assert role_validated is not None
        org_extracted = org_validated.model_dump(exclude_unset=True)
        role_extracted = role_validated.model_dump(exclude_unset=True)

        await ack()
        try:
            await _write_buyer_add(
                is_new_org=is_new_org,
                org_attio_id=org_attio_id,
                org_name=org_name,
                org_extracted=org_extracted,
                role_extracted=role_extracted,
            )
        except BuyerAlreadyExistsError:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=requested_by,
                text="A buyer role already exists for this organization — "
                "_use `/edit-buyer` instead_.",
            )
            return
        except PartialWriteError as exc:
            await client.chat_postEphemeral(
                channel=channel_id, user=requested_by, text=_partial_write_message(exc)
            )
            return

        await client.chat_postEphemeral(
            channel=channel_id, user=requested_by, text=f"*Added* buyer profile for *{org_name}*."
        )


class _OrgRemovedError(Exception):
    pass


class PartialWriteError(Exception):
    """Raised when a write fails after one or more earlier steps already
    landed — an org PATCH that succeeded before a role PATCH then failed, an
    org create that succeeded before the role-entry create failed, or an
    Attio write that succeeded before the Postgres write then failed (a
    plain DB error, not the expected `*AlreadyExistsError`). Carries exactly
    what already landed so the Slack message can tell the truth instead of
    assuming nothing was saved.
    """

    def __init__(self, landed: list[str], cause: Exception) -> None:
        self.landed = landed
        self.cause = cause
        super().__init__(str(cause))


def _partial_write_message(exc: PartialWriteError) -> str:
    if not exc.landed:
        return f"*Couldn't write to Attio* — nothing was saved. _{exc.cause}_"
    landed_text = "; ".join(exc.landed)
    return f"*Write failed partway through.* Already saved: {landed_text}. _{exc.cause}_"


async def _write_seller_edit(
    *,
    seller_role_id: str,
    org_attio_id: str,
    org_extracted: dict[str, Any],
    role_extracted: dict[str, Any],
) -> None:
    """Attio first, then Postgres — see module docstring. Re-resolves the
    seller (and its organization) fresh rather than trusting anything from
    the Slack payload beyond which fields were selected.
    """
    role = await resolve_seller_by_id(seller_role_id)
    if role is None:
        raise SellerNotFoundError(seller_role_id)
    if role.organization.removed_at is not None:
        raise _OrgRemovedError(org_attio_id)

    landed: list[str] = []
    attio_client = get_attio_client()
    try:
        if org_extracted:
            org_attio_values = await build_attio_values(
                attio_client,
                target_kind="objects",
                target_slug="organizations",
                table="organizations",
                fields=ORGANIZATION_FIELDS_BY_NAME,
                extracted=org_extracted,
            )
            if org_attio_values:
                await patch_organization(attio_client, org_attio_id, org_attio_values)
                landed.append("organization fields (Attio)")
        if role_extracted:
            role_attio_values = await build_attio_values(
                attio_client,
                target_kind="lists",
                target_slug="seller_role",
                table="seller_role",
                fields=SELLER_ROLE_FIELDS_BY_NAME,
                extracted=role_extracted,
            )
            if role_attio_values:
                entry_id = await resolve_role_entry_id(attio_client, "seller_role", org_attio_id)
                await patch_role_entry(attio_client, "seller_role", entry_id, role_attio_values)
                landed.append("seller profile fields (Attio)")
    except (AttioError, OptionNotFoundError, RoleEntryNotFoundError) as exc:
        raise PartialWriteError(landed, exc) from exc

    org_postgres_fields = (
        build_postgres_values(
            table="organizations", fields=ORGANIZATION_FIELDS_BY_NAME, extracted=org_extracted
        )
        if org_extracted
        else None
    )
    role_postgres_fields = (
        build_postgres_values(
            table="seller_role", fields=SELLER_ROLE_FIELDS_BY_NAME, extracted=role_extracted
        )
        if role_extracted
        else {}
    )
    try:
        await build_update_seller_use_case().execute(
            seller_role_id,
            role_postgres_fields,
            org_attio_id=org_attio_id,
            org_fields=org_postgres_fields,
        )
    except Exception as exc:
        raise PartialWriteError(landed, exc) from exc


async def _write_buyer_edit(
    *,
    buyer_role_id: str,
    org_attio_id: str,
    org_extracted: dict[str, Any],
    role_extracted: dict[str, Any],
) -> None:
    role = await resolve_buyer_by_id(buyer_role_id)
    if role is None:
        raise BuyerNotFoundError(buyer_role_id)
    if role.organization.removed_at is not None:
        raise _OrgRemovedError(org_attio_id)

    landed: list[str] = []
    attio_client = get_attio_client()
    try:
        if org_extracted:
            org_attio_values = await build_attio_values(
                attio_client,
                target_kind="objects",
                target_slug="organizations",
                table="organizations",
                fields=ORGANIZATION_FIELDS_BY_NAME,
                extracted=org_extracted,
            )
            if org_attio_values:
                await patch_organization(attio_client, org_attio_id, org_attio_values)
                landed.append("organization fields (Attio)")
        if role_extracted:
            role_attio_values = await build_attio_values(
                attio_client,
                target_kind="lists",
                target_slug="buyer_role",
                table="buyer_role",
                fields=BUYER_ROLE_FIELDS_BY_NAME,
                extracted=role_extracted,
            )
            if role_attio_values:
                entry_id = await resolve_role_entry_id(attio_client, "buyer_role", org_attio_id)
                await patch_role_entry(attio_client, "buyer_role", entry_id, role_attio_values)
                landed.append("buyer profile fields (Attio)")
    except (AttioError, OptionNotFoundError, RoleEntryNotFoundError) as exc:
        raise PartialWriteError(landed, exc) from exc

    org_postgres_fields = (
        build_postgres_values(
            table="organizations", fields=ORGANIZATION_FIELDS_BY_NAME, extracted=org_extracted
        )
        if org_extracted
        else None
    )
    role_postgres_fields = (
        build_postgres_values(
            table="buyer_role", fields=BUYER_ROLE_FIELDS_BY_NAME, extracted=role_extracted
        )
        if role_extracted
        else {}
    )
    try:
        await build_update_buyer_use_case().execute(
            buyer_role_id,
            role_postgres_fields,
            org_attio_id=org_attio_id,
            org_fields=org_postgres_fields,
        )
    except Exception as exc:
        raise PartialWriteError(landed, exc) from exc


async def _write_seller_add(
    *,
    is_new_org: bool,
    org_attio_id: str | None,
    org_name: str | None,
    org_extracted: dict[str, Any],
    role_extracted: dict[str, Any],
) -> None:
    """Attio first, then Postgres — same principle as `_write_seller_edit`,
    extended to creates: when `is_new_org`, the organization itself is
    created in Attio before anything else, and its server-generated
    `record_id` becomes `org_attio_id` for the rest of the write (see
    `ddl-commands/README.md`, "Why Attio-first").
    """
    landed: list[str] = []
    attio_client = get_attio_client()

    try:
        if is_new_org:
            org_attio_values = await build_attio_values(
                attio_client,
                target_kind="objects",
                target_slug="organizations",
                table="organizations",
                fields=ORGANIZATION_FIELDS_BY_NAME,
                extracted=org_extracted,
            )
            org_attio_values["name"] = org_name
            org_attio_values["is_active"] = True
            org_attio_id = await create_organization(attio_client, org_attio_values)
            landed.append(f"organization '{org_name}' created in Attio (record_id={org_attio_id})")
        elif org_extracted:
            org_attio_values = await build_attio_values(
                attio_client,
                target_kind="objects",
                target_slug="organizations",
                table="organizations",
                fields=ORGANIZATION_FIELDS_BY_NAME,
                extracted=org_extracted,
            )
            if org_attio_values:
                assert org_attio_id is not None  # not is_new_org: caller already supplied it
                await patch_organization(attio_client, org_attio_id, org_attio_values)
                landed.append("organization fields (Attio)")

        assert org_attio_id is not None
        role_attio_values = await build_attio_values(
            attio_client,
            target_kind="lists",
            target_slug="seller_role",
            table="seller_role",
            fields=SELLER_ROLE_FIELDS_BY_NAME,
            extracted=role_extracted,
        )
        entry_id = await create_role_entry(
            attio_client, "seller_role", org_attio_id, role_attio_values
        )
        landed.append("seller role entry (Attio)")
    except (AttioError, OptionNotFoundError) as exc:
        raise PartialWriteError(landed, exc) from exc

    org_postgres_fields = (
        build_postgres_values(
            table="organizations", fields=ORGANIZATION_FIELDS_BY_NAME, extracted=org_extracted
        )
        if org_extracted
        else None
    )
    role_postgres_fields = build_postgres_values(
        table="seller_role", fields=SELLER_ROLE_FIELDS_BY_NAME, extracted=role_extracted
    )
    try:
        await build_create_seller_use_case().execute(
            org_attio_id=org_attio_id,
            entry_id=entry_id,
            is_new_org=is_new_org,
            org_name=org_name if is_new_org else None,
            org_fields=org_postgres_fields,
            role_fields=role_postgres_fields,
        )
    except SellerAlreadyExistsError:
        raise
    except Exception as exc:
        raise PartialWriteError(landed, exc) from exc


async def _write_buyer_add(
    *,
    is_new_org: bool,
    org_attio_id: str | None,
    org_name: str | None,
    org_extracted: dict[str, Any],
    role_extracted: dict[str, Any],
) -> None:
    """Mirrors `_write_seller_add` exactly, buyer-typed."""
    landed: list[str] = []
    attio_client = get_attio_client()

    try:
        if is_new_org:
            org_attio_values = await build_attio_values(
                attio_client,
                target_kind="objects",
                target_slug="organizations",
                table="organizations",
                fields=ORGANIZATION_FIELDS_BY_NAME,
                extracted=org_extracted,
            )
            org_attio_values["name"] = org_name
            org_attio_values["is_active"] = True
            org_attio_id = await create_organization(attio_client, org_attio_values)
            landed.append(f"organization '{org_name}' created in Attio (record_id={org_attio_id})")
        elif org_extracted:
            org_attio_values = await build_attio_values(
                attio_client,
                target_kind="objects",
                target_slug="organizations",
                table="organizations",
                fields=ORGANIZATION_FIELDS_BY_NAME,
                extracted=org_extracted,
            )
            if org_attio_values:
                assert org_attio_id is not None  # not is_new_org: caller already supplied it
                await patch_organization(attio_client, org_attio_id, org_attio_values)
                landed.append("organization fields (Attio)")

        assert org_attio_id is not None
        role_attio_values = await build_attio_values(
            attio_client,
            target_kind="lists",
            target_slug="buyer_role",
            table="buyer_role",
            fields=BUYER_ROLE_FIELDS_BY_NAME,
            extracted=role_extracted,
        )
        entry_id = await create_role_entry(
            attio_client, "buyer_role", org_attio_id, role_attio_values
        )
        landed.append("buyer role entry (Attio)")
    except (AttioError, OptionNotFoundError) as exc:
        raise PartialWriteError(landed, exc) from exc

    org_postgres_fields = (
        build_postgres_values(
            table="organizations", fields=ORGANIZATION_FIELDS_BY_NAME, extracted=org_extracted
        )
        if org_extracted
        else None
    )
    role_postgres_fields = build_postgres_values(
        table="buyer_role", fields=BUYER_ROLE_FIELDS_BY_NAME, extracted=role_extracted
    )
    try:
        await build_create_buyer_use_case().execute(
            org_attio_id=org_attio_id,
            entry_id=entry_id,
            is_new_org=is_new_org,
            org_name=org_name if is_new_org else None,
            org_fields=org_postgres_fields,
            role_fields=role_postgres_fields,
        )
    except BuyerAlreadyExistsError:
        raise
    except Exception as exc:
        raise PartialWriteError(landed, exc) from exc
