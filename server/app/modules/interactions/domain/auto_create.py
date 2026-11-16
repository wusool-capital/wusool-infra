"""Names and tags for a Person and Organization the engine creates from an address."""

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


def person_name(display_name: str | None, email: str) -> str:
    """Attio requires a name. The address stands in when the sender gave none, or one that is
    long, unprintable, or carries an address of its own, since the sender chose that text."""
    name = " ".join((display_name or "").split())
    if not name or len(name) > _MAX_NAME_CHARS or "@" in name or not name.isprintable():
        return email
    return name


def registrable_domain(domain: str) -> str:
    """The company's own domain: mail.acme.com and acme.com both give acme.com."""
    labels = domain.removeprefix("www.").split(".")
    keep = 3 if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL else 2
    return ".".join(labels[-keep:])


def organization_name(domain: str) -> str:
    """A readable name from the domain's first label. Attio users can rename it."""
    return registrable_domain(domain).split(".")[0].replace("-", " ").title()
