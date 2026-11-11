"""Read access to Gmail and Google Calendar through one service account with
domain-wide delegation: delegated tokens, typed Gmail and Calendar clients,
and the plain data they return. `interactions` is the first consumer; Scribe's
calendar logic is next, which is why this is its own module.

Callers pass the scopes they need (`domain/scopes.py`) and use the Protocols in
`application/ports/` to fake the clients in tests. This module owns no tables
and no HTTP surface, and it imports nothing from its consumers.

Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here.
"""

from app.modules.google_workspace.application.errors import CursorExpired
from app.modules.google_workspace.application.ports.calendar_source import (
    CalendarPage,
    CalendarSourcePort,
)
from app.modules.google_workspace.application.ports.mail_source import MailPage, MailSourcePort
from app.modules.google_workspace.application.ports.token_source import TokenSource
from app.modules.google_workspace.config import GoogleWorkspaceSettings, get_settings
from app.modules.google_workspace.domain.addresses import normalize_address, parse_address_list
from app.modules.google_workspace.domain.model import Attendee, CalendarEvent, MailMessage
from app.modules.google_workspace.domain.scopes import CALENDAR_READONLY, GMAIL_READONLY
from app.modules.google_workspace.providers.google.auth import (
    DelegatedTokenSource,
    GoogleAuthError,
    ServiceAccountKey,
)
from app.modules.google_workspace.providers.google.calendar import CalendarClient
from app.modules.google_workspace.providers.google.gmail import GmailClient
from app.modules.google_workspace.providers.google.http import GoogleApiError

__all__ = [
    "CALENDAR_READONLY",
    "GMAIL_READONLY",
    "Attendee",
    "CalendarClient",
    "CalendarEvent",
    "CalendarPage",
    "CalendarSourcePort",
    "CursorExpired",
    "DelegatedTokenSource",
    "GmailClient",
    "GoogleApiError",
    "GoogleAuthError",
    "GoogleWorkspaceSettings",
    "MailMessage",
    "MailPage",
    "MailSourcePort",
    "ServiceAccountKey",
    "TokenSource",
    "get_settings",
    "normalize_address",
    "parse_address_list",
]
