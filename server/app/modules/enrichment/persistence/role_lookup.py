"""Reads current field values straight off the shared ORM models
(`app.models`, outside `app/modules/` and therefore not subject to the
cross-module architecture fitness tests) — mirrors `meetings`' own
`RoleLookupPort` implementation, which reaches the same models the same
way for the same reason: no owning module exposes a narrow-enough Port for
this read.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.models import BuyerRole, SellerRole
from app.modules.enrichment.domain.field_plans import WriteTarget, enrichable_fields_for
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind
from app.modules.utilities.domain.json_types import JsonObject

_ROLE_MODEL = {
    EnrichmentTargetKind.SELLER: SellerRole,
    EnrichmentTargetKind.BUYER: BuyerRole,
}


class SqlAlchemyRoleReader:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def resolve_target(
        self, *, kind: EnrichmentTargetKind, role_id: uuid.UUID
    ) -> EnrichmentTarget | None:
        """Looks up a role's own organization so a caller (e.g. a Slack
        button carrying only a role id) doesn't need to already have
        `org_attio_id`/`org_name` in hand.
        """
        role_model = _ROLE_MODEL[kind]
        async with self._sessionmaker() as session:
            role = (
                await session.execute(
                    select(role_model)
                    .where(role_model.id == role_id)
                    .options(selectinload(role_model.organization))
                )
            ).scalar_one_or_none()
        if role is None:
            return None
        return EnrichmentTarget(
            kind=kind,
            role_id=role_id,
            org_attio_id=role.organization.attio_id,
            org_name=role.organization.name,
        )

    async def current_values(self, target: EnrichmentTarget) -> JsonObject:
        role_model = BuyerRole if target.kind is EnrichmentTargetKind.BUYER else SellerRole
        role_write_target = (
            WriteTarget.BUYER_ROLE
            if target.kind is EnrichmentTargetKind.BUYER
            else WriteTarget.SELLER_ROLE
        )
        fields = enrichable_fields_for(target.kind.value)

        # One query, not two: the role's own `organization` relationship is
        # always the same row an independent `org_attio_id` lookup would
        # have found (every `EnrichmentTarget` is constructed from this
        # exact role-organization pair — see `resolve_target`/
        # `target_from_resolved`), so `selectinload` avoids a second round
        # trip for no behavioural difference.
        async with self._sessionmaker() as session:
            role = (
                await session.execute(
                    select(role_model)
                    .where(role_model.id == target.role_id)
                    .options(selectinload(role_model.organization))
                )
            ).scalar_one_or_none()

        org = role.organization if role is not None else None
        values: JsonObject = {}
        for field in fields:
            source = role if field.write_target is role_write_target else org
            values[field.name] = getattr(source, field.name, None) if source is not None else None
        return values
