"""Shared exception types and FastAPI exception-handling foundation."""

from .exceptions import AppError, NotFoundError, ValidationFailedError
from .handlers import register_exception_handlers

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationFailedError",
    "register_exception_handlers",
]
