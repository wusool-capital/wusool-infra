"""FastAPI exception-handling registration, kept separate from route handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .exceptions import AppError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})
