"""A Slack button `value` (2000-char cap) or a modal's `private_metadata`
(3000-char cap) can't carry a payload whose size scales with how much data
there is to round-trip (more proposed fields, more search candidates, ...) —
see `enrichment`'s `InMemoryProposalStore`, the original motivating case
(`/enrich-buyer Stripe` exceeded the button-value cap once enrichment grew
past ~9 fields). `EphemeralStore` is the general seam: put a short-lived
payload in, carry only the returned token through Slack, resolve it back on
the next interaction.
"""

from typing import Protocol


class EphemeralStore(Protocol):
    def put(self, payload: str) -> str:
        """Returns a fresh opaque token — never the payload itself — safe
        to embed directly in a size-capped Slack field.
        """
        ...

    def get(self, token: str) -> str | None:
        """`None` for an unknown or expired token — the caller decides how
        to surface that, not this store.
        """
        ...
