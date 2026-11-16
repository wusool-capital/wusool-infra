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

# Second-level labels under a country code, as in acme.co.uk.
_SECOND_LEVEL = frozenset({"co", "com", "org", "net", "ac", "gov", "edu"})


def person_name(display_name: str | None, email: str) -> str:
    """Attio requires a name; the address stands in when the sender gave none or repeated it."""
    name = (display_name or "").strip()
    return email if not name or name.lower() == email else name


def registrable_domain(domain: str) -> str:
    """The company's own domain: mail.acme.com and acme.com both give acme.com."""
    labels = domain.removeprefix("www.").split(".")
    keep = 3 if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL else 2
    return ".".join(labels[-keep:])


def organization_name(domain: str) -> str:
    """A readable name from the domain's first label. Attio users can rename it."""
    return registrable_domain(domain).split(".")[0].replace("-", " ").title()
