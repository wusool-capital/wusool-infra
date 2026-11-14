"""Headless Attio-first buyer add — the write behind `/add-buyer`'s form
submission, kept out of the Slack handler so every caller shares one
Attio-then-Postgres ordering and one `PartialWriteError` shape. Mirrors
`seller_write.write_seller_add`.
"""

import asyncio
from contextlib import nullcontext
from typing import Literal
from weakref import WeakValueDictionary

from app.models import BuyerRole
from app.modules.attio import AttioError, attio_is_test, get_attio_client
from app.modules.attio.providers.attio.entries import (
    ScopeMismatchError,
    assert_organization_in_scope,
    create_organization,
    create_role_entry,
    patch_organization,
)
from app.modules.attio.providers.attio.options import OptionNotFoundError
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.command_tracking import CommandTracker, track_command
from app.modules.ddl_commands.api.dependencies import ddl_commands_service
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.application.buyers import BuyerAlreadyExistsError
from app.modules.ddl_commands.providers.attio.write_payload import (
    build_attio_values,
    build_postgres_values,
)

# One lock per (org, vertical) being added. Process-local, which is enough
# while the toolkit runs as a single instance (ASG min=max=1); weakly held so
# a lock disappears once no add is waiting on it.
_buyer_add_locks: WeakValueDictionary[tuple[str, str | None], asyncio.Lock] = WeakValueDictionary()


async def write_buyer_add(
    *,
    is_new_org: bool,
    org_attio_id: str | None,
    org_name: str | None,
    org_extracted: dict[str, PrefillValue | None],
    role_extracted: dict[str, PrefillValue | None],
    requested_by: str | None,
    invoked_via: Literal["slack", "mcp"],
) -> BuyerRole:
    """Serializes the duplicate check with the Attio create, so a second
    add for the same (org, vertical) sees the first one's role instead of
    creating a second Attio entry that the reconcile would demote. A new
    organization can't have a role yet, so it needs no lock.
    """
    guard = (
        nullcontext()
        if is_new_org
        else _buyer_add_locks.setdefault(
            (org_attio_id or "", _target_vertical(role_extracted)), asyncio.Lock()
        )
    )
    async with (
        guard,
        track_command(
            "add_buyer",
            invoked_via=invoked_via,
            requested_by=requested_by,
            org_attio_id=None if is_new_org else org_attio_id,
        ) as run,
    ):
        return await _write_buyer_add_locked(
            is_new_org=is_new_org,
            org_attio_id=org_attio_id,
            org_name=org_name,
            org_extracted=org_extracted,
            role_extracted=role_extracted,
            run=run,
        )


def _target_vertical(role_extracted: dict[str, PrefillValue | None]) -> str | None:
    vertical = role_extracted.get("target_vertical")
    return vertical if isinstance(vertical, str) else None


async def _write_buyer_add_locked(
    *,
    is_new_org: bool,
    org_attio_id: str | None,
    org_name: str | None,
    org_extracted: dict[str, PrefillValue | None],
    role_extracted: dict[str, PrefillValue | None],
    run: CommandTracker,
) -> BuyerRole:
    """Mirrors `_write_seller_add`, buyer-typed."""
    if not is_new_org:
        assert org_attio_id is not None  # caller supplies it when not creating one
        # Before any Attio write: a duplicate entry would make Attio's
        # newest-wins reconcile demote the existing role for this vertical.
        if await ddl_commands_service().buyer_exists(
            org_attio_id, _target_vertical(role_extracted)
        ):
            raise BuyerAlreadyExistsError(org_attio_id)

    landed: list[str] = []
    run.landed = landed
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
            target_slug="buyer_role",
            table="buyer_role",
            fields=BUYER_ROLE_FIELDS_BY_NAME,
            extracted=role_extracted,
        )
        entry_id = await create_role_entry(
            attio_client, "buyer_role", org_attio_id, role_attio_values, is_test=is_test
        )
        landed.append("buyer role entry (Attio)")
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
        table="buyer_role", fields=BUYER_ROLE_FIELDS_BY_NAME, extracted=role_extracted
    )
    run.changed_fields = [*role_postgres_fields, *(org_postgres_fields or {})]
    try:
        role = await ddl_commands_service().create_buyer(
            org_attio_id=org_attio_id,
            entry_id=entry_id,
            is_new_org=is_new_org,
            context=run.context,
            org_name=org_name if is_new_org else None,
            org_fields=org_postgres_fields,
            role_fields=role_postgres_fields,
        )
    except BuyerAlreadyExistsError:
        raise
    except Exception as exc:
        raise PartialWriteError(landed, exc) from exc
    run.org_attio_id = org_attio_id
    run.buyer_role_id = role.id
    return role
