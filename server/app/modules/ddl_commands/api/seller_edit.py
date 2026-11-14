"""Headless Attio-first seller edit: the write behind `/edit-seller`'s form
submission and behind the web app's saved research. Kept out of the Slack
handler so both callers share one Attio-then-Postgres ordering and one
`PartialWriteError` shape.
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
from app.modules.ddl_commands.api.command_tracking import (
    CommandTracker,
    track_command,
    uuid_or_none,
)
from app.modules.ddl_commands.api.dependencies import ddl_commands_service, resolve_seller_by_id
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.write_errors import PartialWriteError, check_role_organization
from app.modules.ddl_commands.application.sellers import SellerNotFoundError
from app.modules.ddl_commands.providers.attio.write_payload import (
    build_attio_values,
    build_postgres_values,
)


async def write_seller_edit(
    *,
    seller_role_id: str,
    org_attio_id: str,
    org_extracted: dict[str, PrefillValue | None],
    role_extracted: dict[str, PrefillValue | None],
    requested_by: str | None,
) -> None:
    async with track_command(
        "edit_seller",
        invoked_via="slack",
        requested_by=requested_by,
        org_attio_id=org_attio_id,
        seller_role_id=uuid_or_none(seller_role_id),
    ) as run:
        await _seller_edit(
            seller_role_id=seller_role_id,
            org_attio_id=org_attio_id,
            org_extracted=org_extracted,
            role_extracted=role_extracted,
            run=run,
        )


async def _seller_edit(
    *,
    seller_role_id: str,
    org_attio_id: str,
    org_extracted: dict[str, PrefillValue | None],
    role_extracted: dict[str, PrefillValue | None],
    run: CommandTracker,
) -> None:
    """Attio first, then Postgres — see module docstring. Re-resolves the
    seller (and its organization) fresh rather than trusting anything from
    the Slack payload beyond which fields were selected.
    """
    role = await resolve_seller_by_id(seller_role_id)
    if role is None:
        raise SellerNotFoundError(seller_role_id)
    check_role_organization(role.organization, org_attio_id)

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
                target_slug="seller_role",
                table="seller_role",
                fields=SELLER_ROLE_FIELDS_BY_NAME,
                extracted=role_extracted,
            )
            if role_attio_values:
                entry_id = await resolve_role_entry_id(
                    attio_client, "seller_role", org_attio_id, is_test=is_test
                )
                await patch_role_entry(attio_client, "seller_role", entry_id, role_attio_values)
                landed.append("seller profile fields (Attio)")
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
            table="seller_role", fields=SELLER_ROLE_FIELDS_BY_NAME, extracted=role_extracted
        )
        if role_extracted
        else {}
    )
    run.changed_fields = [*role_postgres_fields, *(org_postgres_fields or {})]
    try:
        await ddl_commands_service().update_seller(
            seller_role_id,
            role_postgres_fields,
            context=run.context,
            org_attio_id=org_attio_id,
            org_fields=org_postgres_fields,
        )
    except Exception as exc:
        raise PartialWriteError(landed, exc) from exc
