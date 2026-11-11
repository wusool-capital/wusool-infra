"""Slack CRM commands. The only public names are the read-only Person lookup other modules use."""

from app.modules.ddl_commands.persistence.person_emails import (
    PersonEmails,
    list_live_person_emails,
)

__all__ = ["PersonEmails", "list_live_person_emails"]
