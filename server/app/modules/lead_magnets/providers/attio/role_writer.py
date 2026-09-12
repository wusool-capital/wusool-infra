"""Writes a submission's result to Attio's V2 `seller_role`/`buyer_role` lists.

Attio first, Postgres second — always. A nightly job overwrites Postgres
from Attio, so anything written straight to Postgres is destroyed on the
next run. Nothing here touches the database: the existing
`ddl_commands` webhook mirror already maps every one of these attributes,
so landing them in Attio is enough.

The value mapping lives in `domain/attio_values.py`, not here: it is pure,
and `application/` must be able to build a payload without importing a
provider.

`is_test` is stamped on every create by `entries.create_organization` /
`create_role_entry`. One Attio workspace serves both environments and a
record written without the flag is invisible in both.
"""

import logging

from app.modules.attio import AttioClientProtocol
from app.modules.attio.providers.attio import entries
from app.modules.lead_magnets.domain.buyer_network.buyer_network import (
    validate_org_type,
    validate_sector_focus,
)
from app.modules.lead_magnets.domain.shared.sector_mapping import to_sector_focus
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs

logger = logging.getLogger(__name__)

_SELLER_ROLE_LIST = "seller_role"
_BUYER_ROLE_LIST = "buyer_role"


class AttioRoleWriter:
    def __init__(self, client: AttioClientProtocol, *, is_test: bool) -> None:
        self._client = client
        self._is_test = is_test

    async def _upsert_organization(
        self, *, org_values: dict[str, object], organization_attio_id: str | None
    ) -> str:
        """`organization_attio_id` is passed when the caller's dedup lookup
        already matched an existing organisation; otherwise a new one is
        created."""
        if organization_attio_id is None:
            return await entries.create_organization(
                self._client, org_values, is_test=self._is_test
            )
        org_id = organization_attio_id
        await entries.assert_organization_in_scope(self._client, org_id, is_test=self._is_test)
        await entries.patch_organization(self._client, org_id, org_values)
        return org_id

    async def _upsert_role_entry(
        self, *, list_slug: str, org_id: str, entry_values: dict[str, object]
    ) -> str:
        """Resolving an existing entry is done by
        `entries.resolve_role_entry_id`, which pages the list and respects
        the `is_test` half of the shared workspace."""
        try:
            entry_id = await entries.resolve_role_entry_id(
                self._client, list_slug, org_id, is_test=self._is_test
            )
            await entries.patch_role_entry(self._client, list_slug, entry_id, entry_values)
            return entry_id
        except entries.RoleEntryNotFoundError:
            return await entries.create_role_entry(
                self._client, list_slug, org_id, entry_values, is_test=self._is_test
            )

    async def write_seller_role(
        self,
        *,
        organization_name: str,
        domain: str | None,
        entry_values: dict[str, object],
        sector: str | None = None,
        description: str | None = None,
        hq_country: str | None = None,
        organization_attio_id: str | None = None,
    ) -> SubjectRefs:
        """Creates or updates the organisation, then its `seller_role` entry."""
        org_values: dict[str, object] = {"name": organization_name}
        if domain:
            org_values["domains"] = [domain]
        # Mapped, never raw: `sector_focus` is a select, Attio rejects an
        # undefined option, and the live relay only logs that — so a raw
        # tool value would silently drop the sector. `to_sector_focus`
        # raises instead.
        if (mapped := to_sector_focus(sector)) is not None:
            org_values["sector_focus"] = [mapped]
        if description:
            org_values["description"] = description
        if hq_country:
            org_values["hq_country"] = hq_country

        org_id = await self._upsert_organization(
            org_values=org_values, organization_attio_id=organization_attio_id
        )
        entry_id = await self._upsert_role_entry(
            list_slug=_SELLER_ROLE_LIST, org_id=org_id, entry_values=entry_values
        )

        return SubjectRefs(
            org_attio_id=org_id,
            org_name=organization_name,
            seller_role_entry_id=entry_id,
        )

    async def write_buyer_role(
        self,
        *,
        organization_name: str,
        domain: str | None,
        org_type: list[str],
        sector_focus: list[str],
        entry_values: dict[str, object],
        organization_attio_id: str | None = None,
    ) -> SubjectRefs:
        """Same shape as `write_seller_role`. `org_type`/`sector_focus` are
        already Attio's own option titles — validated, not mapped, since the
        form offers the live vocabulary directly rather than a tool-specific
        one needing translation.
        """
        org_values: dict[str, object] = {"name": organization_name}
        if domain:
            org_values["domains"] = [domain]
        if org_type:
            org_values["type"] = validate_org_type(org_type)
        if sector_focus:
            org_values["sector_focus"] = validate_sector_focus(sector_focus)

        org_id = await self._upsert_organization(
            org_values=org_values, organization_attio_id=organization_attio_id
        )
        entry_id = await self._upsert_role_entry(
            list_slug=_BUYER_ROLE_LIST, org_id=org_id, entry_values=entry_values
        )

        return SubjectRefs(
            org_attio_id=org_id,
            org_name=organization_name,
            buyer_role_entry_id=entry_id,
        )
