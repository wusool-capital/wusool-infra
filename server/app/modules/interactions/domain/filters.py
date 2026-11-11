"""Which fetched messages and events never count as an interaction."""

from app.modules.interactions.domain.addresses import INTERNAL_DOMAINS, is_internal
from app.modules.interactions.domain.model import Channel, RawItem

_IGNORED_LABELS = frozenset({"SPAM", "TRASH", "DRAFT", "CHAT"})
# Calendar already counts the meeting, so its notification emails would double it.
_CALENDAR_NOTICE_PREFIXES = ("invitation:", "updated invitation:", "accepted:", "declined:")
_OUT_OF_OFFICE_PREFIXES = ("automatic reply", "out of office", "autoreply", "auto-reply")


def is_ignored(item: RawItem, internal_domains: tuple[str, ...] = INTERNAL_DOMAINS) -> bool:
    # Also true for no participants at all: nothing outside to link.
    if all(is_internal(p, internal_domains) for p in item.participants):
        return True
    if item.channel is Channel.MEETING:
        return item.all_day or item.cancelled or item.team_declined
    return bool(item.labels & _IGNORED_LABELS) or item.bulk or _is_notice_or_auto_reply(item)


def _is_notice_or_auto_reply(item: RawItem) -> bool:
    # RFC 3834: any Auto-Submitted value except "no" marks a machine-sent message.
    if item.auto_submitted is not None and item.auto_submitted.strip().lower() != "no":
        return True
    subject = (item.subject or "").strip().lower()
    return subject.startswith(_CALENDAR_NOTICE_PREFIXES + _OUT_OF_OFFICE_PREFIXES)
