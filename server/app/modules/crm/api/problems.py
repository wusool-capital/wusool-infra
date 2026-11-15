"""RFC 9457 problem responses for `/api/v1`, one shape for every error."""

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from app.modules.crm.api.schemas import ProblemDetail
from app.modules.crm.domain.roles import (
    InvalidCursorError,
    InvalidRoleFieldsError,
    RoleAlreadyExistsError,
    RoleNotFoundError,
    StaleRoleError,
    WriteLandedPartlyError,
)

PROBLEM_MEDIA_TYPE = "application/problem+json"
API_PREFIX = "/api/v1"


class ProblemError(Exception):
    def __init__(self, problem: ProblemDetail) -> None:
        super().__init__(problem.detail)
        self.problem = problem


def problem(
    status: int,
    code: str,
    title: str,
    detail: str,
    *,
    errors: list[str] | None = None,
    landed: list[str] | None = None,
) -> ProblemError:
    return ProblemError(
        ProblemDetail(
            title=title,
            status=status,
            detail=detail,
            code=code,
            errors=errors or [],
            landed=landed or [],
        )
    )


def _response(problem_detail: ProblemDetail) -> JSONResponse:
    return JSONResponse(
        status_code=problem_detail.status,
        content=jsonable_encoder(problem_detail),
        media_type=PROBLEM_MEDIA_TYPE,
    )


def _partial_write(exc: WriteLandedPartlyError) -> ProblemDetail:
    if not exc.landed:
        detail = f"Couldn't save to Attio, so nothing was saved. Try again. ({exc})"
    else:
        detail = (
            f"Saved only partway ({exc}). Already saved: {'; '.join(exc.landed)}. "
            "Retry the save to finish it."
        )
    return ProblemDetail(
        title="Saved partway",
        status=502,
        detail=detail,
        code="partial_write",
        landed=list(exc.landed),
    )


def install_problem_handlers(app: FastAPI) -> None:
    async def not_found(_request: Request, exc: Exception) -> Response:
        return _response(
            ProblemDetail(
                title="Not found",
                status=404,
                detail=f"No live role has id {exc}",
                code="role_not_found",
            )
        )

    async def stale(_request: Request, _exc: Exception) -> Response:
        return _response(
            ProblemDetail(
                title="Out of date",
                status=412,
                detail="Someone else changed this record. Reload it and apply your edit again.",
                code="stale_version",
            )
        )

    async def exists(_request: Request, _exc: Exception) -> Response:
        return _response(
            ProblemDetail(
                title="Already exists",
                status=409,
                detail="A buyer with this domain and sector already exists.",
                code="buyer_exists",
            )
        )

    async def invalid_fields(_request: Request, exc: Exception) -> Response:
        assert isinstance(exc, InvalidRoleFieldsError)
        return _response(
            ProblemDetail(
                title="Invalid fields",
                status=422,
                detail="Nothing was saved. Fix these fields and try again.",
                code="invalid_fields",
                errors=list(exc.problems),
            )
        )

    async def partial(_request: Request, exc: Exception) -> Response:
        assert isinstance(exc, WriteLandedPartlyError)
        return _response(_partial_write(exc))

    async def invalid_cursor(_request: Request, _exc: Exception) -> Response:
        return _response(
            ProblemDetail(
                title="Invalid cursor",
                status=400,
                detail="The paging cursor is not valid. Reload the list.",
                code="invalid_cursor",
            )
        )

    async def explicit(_request: Request, exc: Exception) -> Response:
        assert isinstance(exc, ProblemError)
        return _response(exc.problem)

    async def validation(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, RequestValidationError)
        if not request.url.path.startswith(API_PREFIX):
            return await request_validation_exception_handler(request, exc)
        errors = [
            f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}".lstrip(": ")
            for error in exc.errors()
        ]
        return _response(
            ProblemDetail(
                title="Invalid request",
                status=422,
                detail="The request was not valid.",
                code="invalid_request",
                errors=errors,
            )
        )

    app.add_exception_handler(RoleNotFoundError, not_found)
    app.add_exception_handler(StaleRoleError, stale)
    app.add_exception_handler(RoleAlreadyExistsError, exists)
    app.add_exception_handler(InvalidRoleFieldsError, invalid_fields)
    app.add_exception_handler(WriteLandedPartlyError, partial)
    app.add_exception_handler(InvalidCursorError, invalid_cursor)
    app.add_exception_handler(ProblemError, explicit)
    app.add_exception_handler(RequestValidationError, validation)
