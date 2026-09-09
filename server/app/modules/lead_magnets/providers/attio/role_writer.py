"""Writes a submission's result to Attio's V2 `seller_role` list.

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
from app.modules.lead_magnets.domain.tool_run import SubjectRefs

logger = logging.getLogger(__name__)

_SELLER_ROLE_LIST = "seller_role"


class AttioRoleWriter:
    def __init__(self, client: AttioClientProtocol, *, is_test: bool) -> None:
        self._client = client
        self._is_test = is_test

    async def write_seller_role(
        self,
        *,
        organization_name: str,
        domain: str | None,
        entry_values: dict[str, object],
        organization_attio_id: str | None = None,
    ) -> SubjectRefs:
        """Creates or updates the organisation, then its `seller_role` entry.

        `organization_attio_id` is passed when the caller's dedup lookup
        already matched an existing organisation; otherwise a new one is
        created. Resolving an existing role entry is done by
        `entries.resolve_role_entry_id`, which pages the list and respects
        the `is_test` half of the shared workspace.
        """
        org_values: dict[str, object] = {"name": organization_name}
        if domain:
            org_values["domains"] = [domain]

        if organization_attio_id is None:
            org_id = await entries.create_organization(
                self._client, org_values, is_test=self._is_test
            )
        else:
            org_id = organization_attio_id
            await entries.assert_organization_in_scope(self._client, org_id, is_test=self._is_test)
            await entries.patch_organization(self._client, org_id, org_values)

        try:
            entry_id = await entries.resolve_role_entry_id(
                self._client, _SELLER_ROLE_LIST, org_id, is_test=self._is_test
            )
            await entries.patch_role_entry(self._client, _SELLER_ROLE_LIST, entry_id, entry_values)
        except entries.RoleEntryNotFoundError:
            entry_id = await entries.create_role_entry(
                self._client, _SELLER_ROLE_LIST, org_id, entry_values, is_test=self._is_test
            )

        return SubjectRefs(
            org_attio_id=org_id,
            org_name=organization_name,
            seller_role_entry_id=entry_id,
        )
