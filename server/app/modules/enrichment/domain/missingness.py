"""Whether a field value counts as missing — moved down from
`application/enrich.py` so `discrepancies` can reuse it without a
cross-module `application` import, which the architecture tests forbid.
"""

from app.modules.enrichment.domain.proposals import FieldValue


def is_missing(value: FieldValue | None) -> bool:
    """A field counts as missing only when it's genuinely empty — a
    legitimately-zero number or an already-populated `False` must not be
    re-researched just because they're falsy in Python.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple)):
        return len(value) == 0
    if isinstance(value, dict):
        # Currency fields store `{"amount": ..., "currency": "USD"}` — a
        # legitimate zero amount (e.g. a pre-revenue seller) must not be
        # re-researched, same as the bare-number case below.
        return value.get("amount") is None
    return False
