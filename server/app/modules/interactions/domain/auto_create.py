"""Names and tags for a Person and Organization the engine creates from an address."""

import re

from app.modules.lead_magnets.domain.benchmark.benchmark_routing import FREE_MAIL

# The benchmark's free-mail list, plus providers that rarely carry business mail.
FREE_EMAIL_DOMAINS = FREE_MAIL | frozenset(
    {
        "googlemail.com",
        "proton.me",
        "pm.me",
        "gmx.com",
        "zoho.com",
        "mail.com",
        "fastmail.com",
        "hey.com",
    }
)

LEAD_SOURCE_DETAIL = "Email sync"

_MAX_NAME_CHARS = 100

# Second-level labels under a country code, as in acme.co.uk.
_SECOND_LEVEL = frozenset({"co", "com", "org", "net", "ac", "gov", "edu"})


# A shared mailbox says nothing about who it is, so these keep the full address as the name.
_GENERIC_LOCAL_PARTS = frozenset(
    {
        "admin", "info", "team", "sales", "contact", "hello", "hi", "hey", "office", "mail",
        "accounts", "billing", "finance", "legal", "hr", "careers", "jobs", "press", "media",
        "marketing", "service", "support", "help", "invite", "reception", "desk", "enquiries",
        "inquiries", "general", "notifications", "notification", "news", "updates", "events",
        "community", "connect", "welcome", "founders", "partners", "partnerships", "growth",
        "success", "feedback", "studio", "ops", "operations",
    }
)  # fmt: skip
_NAME_SEPARATORS = re.compile(r"[._+\-]+")


def person_name(display_name: str | None, email: str) -> str:
    """Attio requires a name. A sender's display name is used when it is sensible, and otherwise
    one is built from the address: sinan@ becomes Sinan, abhishek.bajaj@ Abhishek Bajaj."""
    name = " ".join((display_name or "").split())
    if name and len(name) <= _MAX_NAME_CHARS and "@" not in name and name.isprintable():
        return name
    return _name_from_address(email)


def _name_from_address(email: str) -> str:
    """The address itself when it is a shared mailbox or has digits, which would read as junk."""
    local = email.partition("@")[0]
    words = [w for w in _NAME_SEPARATORS.split(local) if w]
    if local in _GENERIC_LOCAL_PARTS or not words or not all(w.isalpha() for w in words):
        return email
    return " ".join(w.capitalize() for w in words)


def registrable_domain(domain: str) -> str:
    """The company's own domain: mail.acme.com and acme.com both give acme.com."""
    labels = domain.removeprefix("www.").split(".")
    keep = 3 if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL else 2
    return ".".join(labels[-keep:])


def organization_name(domain: str) -> str:
    """A readable name from the domain's first label. Attio users can rename it."""
    return registrable_domain(domain).split(".")[0].replace("-", " ").title()
