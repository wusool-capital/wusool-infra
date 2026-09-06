"""GET /desktop/companies/search?query= — buyer/seller/investor autocomplete
for the desktop app's Push UI. Built directly on
`bootstrap.build_organization_lookup` rather than through `MeetingsService`:
`organization_lookup` is a private attribute of `ServiceBase`, and this is
the only read-only lookup in this module that doesn't need anything else
`MeetingsService` composes.

Always appends a final "create new" candidate — per the desktop schema's
documented contract that this response always includes one, even though
the domain lookup itself has no reason to know about that UI affordance.
"""

from fastapi import APIRouter, Depends, Query

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import SessionDep
from app.modules.meetings.api.schemas import (
    DesktopCompanyCandidate,
    DesktopCompanySearchResponse,
    to_company_candidate,
)
from app.modules.meetings.bootstrap import build_organization_lookup

_CREATE_NEW_VALUE = "__create_new__"
_SEARCH_LIMIT = 10

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)


@router.get("/companies/search")
async def search_companies(
    session: SessionDep,
    query: str = Query(..., min_length=1),
) -> DesktopCompanySearchResponse:
    organizations = await build_organization_lookup(session).search_by_name(
        query, limit=_SEARCH_LIMIT
    )
    candidates = [to_company_candidate(org) for org in organizations]
    candidates.append(
        DesktopCompanyCandidate(label=f'Create new: "{query}"', value=_CREATE_NEW_VALUE)
    )
    org_names = {org.attio_id: org.name for org in organizations}
    return DesktopCompanySearchResponse(candidates=candidates, org_names=org_names)
