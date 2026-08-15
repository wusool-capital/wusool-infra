"""Base application exceptions. Modules should raise these, not HTTPException,
so that domain/application code stays independent of FastAPI."""


class AppError(Exception):
    """Base class for all application-raised errors."""

    status_code: int = 500

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    status_code = 404


class ValidationFailedError(AppError):
    status_code = 422
