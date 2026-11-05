"""Address normalisation and matching helpers."""

from email.utils import parseaddr

# The first domain is canonical: every other one is treated as an alias of it.
INTERNAL_DOMAINS: tuple[str, ...] = ("wusoolcapital.com", "dopaminecap.com")


def normalize_address(raw: str) -> str | None:
    """Lowercased bare address from a header value, or None if it isn't one."""
    address = parseaddr(raw)[1].strip().lower()
    local, _, domain = address.partition("@")
    return address if local and "." in domain else None


def domain_of(address: str) -> str:
    return address.rpartition("@")[2]


def is_internal(address: str, internal_domains: tuple[str, ...] = INTERNAL_DOMAINS) -> bool:
    return domain_of(address) in internal_domains


def team_member_of(address: str, internal_domains: tuple[str, ...] = INTERNAL_DOMAINS) -> str:
    """One identity per person across alias domains, so strength isn't split in two."""
    if not is_internal(address, internal_domains):
        return address
    return f"{address.rpartition('@')[0]}@{internal_domains[0]}"


def org_domain_candidates(domain: str) -> tuple[str, ...]:
    """The domain and each parent, so news.example.com also tries example.com."""
    labels = domain.lower().split(".")
    # shortcut: no public-suffix list, so co.uk is tried as a parent; upgrade if an org stores one.
    return tuple(".".join(labels[i:]) for i in range(len(labels) - 1))
