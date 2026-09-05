"""Application-level exception types, one per concept until this file is
large enough to split. Vendor/provider-specific exceptions instead go in
`provider_errors.py`.

Subclasses `app.modules.utilities.domain.errors.AppError` (a shared-kernel,
framework-free exception `utilities` is a documented full-access module for)
so `register_exception_handlers` in main.py turns these into the right HTTP
status without this module ever importing FastAPI.
"""

from app.modules.utilities.domain.errors import AppError, NotFoundError


class MeetingAlreadyExistsError(AppError):
    """Raised when a desktop push is retried for an (install_id,
    local_recording_id) pair that was already ingested. Never silently
    discard a re-push — the caller may have made local edits since the
    first push, so a quiet no-op would drop them (§ ingest.py dedup).
    """

    status_code = 409


class MeetingNotFoundError(NotFoundError):
    """Raised when a meeting_id has no matching row."""


class UnknownCompanyReferenceError(AppError):
    """Raised when a role selection looks like a bare local-company UUID
    (Scribe-era desktop session data) rather than an `attio:<id>` reference
    or free-text query — this module has no local `companies` table to
    resolve it against.
    """

    status_code = 422
