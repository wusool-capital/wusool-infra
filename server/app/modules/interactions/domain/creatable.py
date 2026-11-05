"""Whether an unknown address may become a new Person and Organization."""

from app.modules.interactions.domain.addresses import (
    INTERNAL_DOMAINS,
    domain_of,
    is_internal,
)

_NO_REPLY_LOCAL_PARTS = frozenset({"noreply", "no-reply", "donotreply", "do-not-reply"})


def is_no_reply_address(address: str) -> bool:
    return address.partition("@")[0] in _NO_REPLY_LOCAL_PARTS


def is_creatable(
    address: str,
    *,
    free_email_domains: frozenset[str],
    has_list_unsubscribe: bool,
    two_way_thread: bool,
    attended_meeting: bool,
    internal_domains: tuple[str, ...] = INTERNAL_DOMAINS,
) -> bool:
    """Mail one-way from a stranger never creates a record; a reply or a meeting does."""
    if is_internal(address, internal_domains) or domain_of(address) in free_email_domains:
        return False
    if has_list_unsubscribe or is_no_reply_address(address):
        return False
    return two_way_thread or attended_meeting
