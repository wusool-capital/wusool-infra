"""Headless Attio-first seller add — the write behind `/add-seller`'s form
submission and behind discovery's auto-created sellers. Kept out of the Slack
handler so both callers share one Attio-then-Postgres ordering and one
`PartialWriteError` shape.
"""

from app.models import SellerRole
from app.modules.attio import AttioError, attio_is_test, get_attio_client
from app.modules.attio.providers.attio.entries import (
    ScopeMismatchError,
    assert_organization_in_scope,
    create_organization,
    create_role_entry,
    patch_organization,
)
from app.modules.attio.providers.attio.options import OptionNotFoundError
from app.modules.ddl_commands.api.dependencies import ddl_commands_service
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.application.sellers import SellerAlreadyExistsError
from app.modules.ddl_commands.providers.attio.write_payload import (
    build_attio_values,
    build_postgres_values,
)


async def write_seller_add(
    *,
    is_new_org: bool,
    org_attio_id: str | None,
    org_name: str | None,
    org_extracted: dict[str, PrefillValue | None],
    role_extracted: dict[str, PrefillValue | None],
    source_place_id: str | None = None,
) -> SellerRole:
    """Attio first, then Postgres — same principle as `_write_seller_edit`,
    extended to creates: when `is_new_org`, the organization itself is
    created in Attio before anything else, and its server-generated
    `record_id` becomes `org_attio_id` for the rest of the write (see
    `ddl-commands/README.md`, "Why Attio-first").
    """
    landed: list[str] = []
    attio_client = get_attio_client()
    is_test = attio_is_test()

    try:
        if not is_new_org:
            assert org_attio_id is not None  # caller supplies it when not creating one
            await assert_organization_in_scope(attio_client, org_attio_id, is_test=is_test)
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
            org_attio_id, _ = await create_organization(
                attio_client, org_attio_values, is_test=is_test
            )
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
            attio_client, "seller_role", org_attio_id, role_attio_values, is_test=is_test
        )
        landed.append("seller role entry (Attio)")
    except (AttioError, OptionNotFoundError, ScopeMismatchError) as exc:
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
        return await ddl_commands_service().create_seller(
            org_attio_id=org_attio_id,
            entry_id=entry_id,
            is_new_org=is_new_org,
            org_name=org_name if is_new_org else None,
            org_fields=org_postgres_fields,
            role_fields=role_postgres_fields,
            source_place_id=source_place_id,
        )
    except SellerAlreadyExistsError:
        raise
    except Exception as exc:
        raise PartialWriteError(landed, exc) from exc
