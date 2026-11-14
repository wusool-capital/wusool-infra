"""Headless Attio-first buyer edit: the write behind `/edit-buyer`'s form
submission, kept out of the Slack handler so callers outside Slack (MCP) share
one Attio-then-Postgres ordering and one `PartialWriteError` shape.
"""

from app.modules.attio import AttioError, attio_is_test, get_attio_client
from app.modules.attio.providers.attio.entries import (
    RoleEntryNotFoundError,
    ScopeMismatchError,
    assert_organization_in_scope,
    patch_organization,
    patch_role_entry,
    resolve_role_entry_id,
)
from app.modules.attio.providers.attio.options import OptionNotFoundError
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.command_tracking import (
    CommandTracker,
    track_command,
    uuid_or_none,
)
from app.modules.ddl_commands.api.dependencies import ddl_commands_service, resolve_buyer_by_id
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.seller_edit import OrgRemovedError
from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.application.buyers import BuyerNotFoundError
from app.modules.ddl_commands.providers.attio.write_payload import (
    build_attio_values,
    build_postgres_values,
)


class OrgMismatchError(Exception):
    pass


async def write_buyer_edit(
    *,
    buyer_role_id: str,
    org_attio_id: str,
    org_extracted: dict[str, PrefillValue | None],
    role_extracted: dict[str, PrefillValue | None],
    requested_by: str | None,
) -> None:
    async with track_command(
        "edit_buyer",
        invoked_via="slack",
        requested_by=requested_by,
        org_attio_id=org_attio_id,
        buyer_role_id=uuid_or_none(buyer_role_id),
    ) as run:
        await _buyer_edit(
            buyer_role_id=buyer_role_id,
            org_attio_id=org_attio_id,
            org_extracted=org_extracted,
            role_extracted=role_extracted,
            run=run,
        )


async def _buyer_edit(
    *,
    buyer_role_id: str,
    org_attio_id: str,
    org_extracted: dict[str, PrefillValue | None],
    role_extracted: dict[str, PrefillValue | None],
    run: CommandTracker,
) -> None:
    role = await resolve_buyer_by_id(buyer_role_id)
    if role is None:
        raise BuyerNotFoundError(buyer_role_id)
    if role.organization.removed_at is not None:
        raise OrgRemovedError(org_attio_id)
    # Callers outside Slack pass both ids separately; never write to another buyer's org.
    if role.organization.attio_id != org_attio_id:
        raise OrgMismatchError(org_attio_id)

    landed: list[str] = []
    run.landed = landed
    attio_client = get_attio_client()
    is_test = attio_is_test()
    try:
        await assert_organization_in_scope(attio_client, org_attio_id, is_test=is_test)
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
                # An org holds several buyer roles now, so the org alone no
                # longer identifies the entry to patch.
                entry_id = await resolve_role_entry_id(
                    attio_client,
                    "buyer_role",
                    org_attio_id,
                    is_test=is_test,
                    only_entry_id=role.legacy_entry_id,
                )
                await patch_role_entry(attio_client, "buyer_role", entry_id, role_attio_values)
                landed.append("buyer profile fields (Attio)")
    except (AttioError, OptionNotFoundError, RoleEntryNotFoundError, ScopeMismatchError) as exc:
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
    run.changed_fields = [*role_postgres_fields, *(org_postgres_fields or {})]
    try:
        await ddl_commands_service().update_buyer(
            buyer_role_id,
            role_postgres_fields,
            context=run.context,
            org_attio_id=org_attio_id,
            org_fields=org_postgres_fields,
        )
    except Exception as exc:
        raise PartialWriteError(landed, exc) from exc
