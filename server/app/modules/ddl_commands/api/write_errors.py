"""Errors shared by every Attio-first write path (Slack handlers and the
headless seller and buyer writers)."""

from app.models.organization import Organization


class OrgRemovedError(Exception):
    pass


class OrgMismatchError(Exception):
    pass


def check_role_organization(organization: Organization, org_attio_id: str) -> None:
    """Run before any Attio write. Callers outside Slack pass the role and org
    ids separately, so never write to an org the role does not belong to.
    """
    if organization.removed_at is not None:
        raise OrgRemovedError(org_attio_id)
    if organization.attio_id != org_attio_id:
        raise OrgMismatchError(org_attio_id)


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


def partial_write_message(exc: PartialWriteError) -> str:
    if not exc.landed:
        return f"*Couldn't write to Attio* — nothing was saved. _{exc.cause}_"
    landed_text = "; ".join(exc.landed)
    return f"*Write failed partway through.* Already saved: {landed_text}. _{exc.cause}_"
