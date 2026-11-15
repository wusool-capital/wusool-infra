"""Who is calling: the person behind the Cloudflare Access token."""

from typing import Annotated

from fastapi import Depends, Header

from app.modules.auth import (
    AccessKeysUnavailableError,
    AccessSignInError,
    access_configured,
    verify_access_jwt,
)
from app.modules.crm.api.problems import problem
from app.modules.crm.application.service import CrmService
from app.modules.crm.bootstrap import crm_service
from app.modules.crm.domain.roles import SignedInUser

Service = Annotated[CrmService, Depends(crm_service)]


async def require_user(
    service: Service,
    # Added by Cloudflare Access, never by the Engine's own code, so it stays out of the spec.
    cf_access_jwt_assertion: Annotated[str | None, Header(include_in_schema=False)] = None,
) -> SignedInUser:
    if not access_configured():
        raise problem(
            503, "api_disabled", "Unavailable", "The Engine API is not configured on this server."
        )
    if not cf_access_jwt_assertion:
        raise problem(
            401, "unauthenticated", "Sign in required", "Sign in through Cloudflare Access."
        )
    try:
        claims = await verify_access_jwt(cf_access_jwt_assertion)
    except AccessKeysUnavailableError as exc:
        raise problem(
            503,
            "access_keys_unavailable",
            "Unavailable",
            "Sign-in checks are unavailable. Try again.",
        ) from exc
    except AccessSignInError as exc:
        raise problem(
            401, "invalid_token", "Sign in required", "The sign-in token is not valid."
        ) from exc
    user = await service.sign_in(claims.email)
    if user is None:
        raise problem(
            403,
            "unknown_user",
            "Not allowed",
            "This email is not a Wusool team member. Ask an admin to add it in Attio.",
        )
    return user


CurrentUser = Annotated[SignedInUser, Depends(require_user)]
