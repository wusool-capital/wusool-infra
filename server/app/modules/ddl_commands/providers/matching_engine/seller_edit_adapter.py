"""Implements `matching_engine.SellerEditPort`: saves the research fields an
advisor picked in the web app through the same `/edit-seller` write the Slack
form uses (Attio first, then Postgres), after the same validation. Research
only proposes empty fields, so one filled in since is a conflict, not
something to overwrite.
"""

from pydantic import ValidationError

from app.modules.ddl_commands.api.dependencies import resolve_seller_by_id
from app.modules.ddl_commands.api.organizations import (
    ORGANIZATION_FIELDS_BY_NAME,
    OrganizationUpdate,
)
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.seller_edit import OrgRemovedError, write_seller_edit
from app.modules.ddl_commands.api.sellers import (
    GATED_SELLER_ROLE_FIELDS,
    SELLER_ROLE_FIELDS_BY_NAME,
    SellerUpdate,
)
from app.modules.ddl_commands.api.slack.views.dynamic_fields import normalize_prefill
from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.application.sellers import SellerNotFoundError
from app.modules.matching_engine import (
    SellerEditOutcome,
    SellerEditResult,
    SellerFieldEdit,
)


def _is_empty(value: PrefillValue | None) -> bool:
    return value is None or value == "" or value == [] or value == {}


class DdlCommandsSellerEditAdapter:
    async def apply(
        self, *, seller_role_id: str, edits: tuple[SellerFieldEdit, ...], requested_by: str
    ) -> SellerEditResult:
        role = await resolve_seller_by_id(seller_role_id)
        if role is None or role.organization.removed_at is not None:
            return SellerEditResult(outcome=SellerEditOutcome.NOT_FOUND)

        org_edits = {e.name: e.value for e in edits if e.target == "organization"}
        role_edits = {e.name: e.value for e in edits if e.target == "seller_role"}
        unknown = [
            *(n for n in org_edits if n not in ORGANIZATION_FIELDS_BY_NAME),
            *(n for n in role_edits if n not in SELLER_ROLE_FIELDS_BY_NAME),
        ]
        # Corrections need a human's confirmation the web review doesn't ask for.
        gated = [n for n in role_edits if n in GATED_SELLER_ROLE_FIELDS]
        if unknown or gated:
            return SellerEditResult(
                outcome=SellerEditOutcome.INVALID,
                message=f"Can't save {', '.join([*unknown, *gated])} from here.",
            )

        conflicts = tuple(
            [n for n in org_edits if not _is_empty(getattr(role.organization, n, None))]
            + [n for n in role_edits if not _is_empty(getattr(role, n, None))]
        )
        if conflicts:
            return SellerEditResult(outcome=SellerEditOutcome.CONFLICT, conflicts=conflicts)

        org_values = normalize_prefill(org_edits, ORGANIZATION_FIELDS_BY_NAME)
        role_values = normalize_prefill(role_edits, SELLER_ROLE_FIELDS_BY_NAME)
        # A trimmed list would save less than the advisor saw, so it counts as invalid too.
        dropped = [n for n, v in org_edits.items() if org_values.get(n) != v] + [
            n for n, v in role_edits.items() if role_values.get(n) != v
        ]
        if dropped:
            return SellerEditResult(
                outcome=SellerEditOutcome.INVALID,
                message=f"Not an allowed value for {', '.join(dropped)}.",
            )
        try:
            org_extracted = OrganizationUpdate.model_validate(org_values).model_dump(
                exclude_unset=True
            )
            role_extracted = SellerUpdate.model_validate(role_values).model_dump(exclude_unset=True)
        except ValidationError as exc:
            return SellerEditResult(
                outcome=SellerEditOutcome.INVALID,
                message=f"{exc.error_count()} value(s) didn't pass the seller form's checks.",
            )

        try:
            await write_seller_edit(
                seller_role_id=seller_role_id,
                org_attio_id=role.organization.attio_id,
                org_extracted=org_extracted,
                role_extracted=role_extracted,
                requested_by=requested_by,
            )
        except (SellerNotFoundError, OrgRemovedError):
            return SellerEditResult(outcome=SellerEditOutcome.NOT_FOUND)
        except PartialWriteError as exc:
            return SellerEditResult(
                outcome=SellerEditOutcome.PARTIAL,
                landed=tuple(exc.landed),
                message=str(exc.cause),
            )
        return SellerEditResult(outcome=SellerEditOutcome.SAVED)
