"""OAuth scopes a caller may ask the delegation for.

Each consumer passes only what it needs. The admin's domain-wide delegation
grant has to list every scope any consumer uses.
"""

GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"
CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
