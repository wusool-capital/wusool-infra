"""Email address parsing shared by everything that reads mail or calendars."""

from email.utils import getaddresses, parseaddr


def normalize_address(raw: str) -> str | None:
    """Lowercased bare address from a header value, or None if it isn't one."""
    address = parseaddr(raw)[1].strip().lower()
    local, _, domain = address.partition("@")
    return address if local and "." in domain else None


def parse_address_list(value: str) -> tuple[str, ...]:
    """Every valid address in a To or Cc header, deduplicated, in header order."""
    found = (normalize_address(pair[1]) for pair in getaddresses([value]))
    return tuple(dict.fromkeys(a for a in found if a))
