"""Which half of the single shared SOURCE Attio workspace a record belongs to.

One workspace serves both environments, discriminated by an Attio-only
`is_test` checkbox. This module holds the pure rule for reading that flag;
`attio.config` holds the process's own side of the comparison, since that
comes from settings.
"""


def record_scope(record_is_test: bool | None) -> bool:
    """Normalise a record's raw `is_test` value to the half it belongs to.

    The one statement of the null policy: an unset checkbox (`None`) reads
    as production. Every record migrated before 2026-09-07 has `is_test`
    absent from its payload entirely, so requiring an explicit `False`
    would stop the prod sync writing anything until a stamping run had
    walked every entity — a self-inflicted outage in exchange for nothing,
    since every write path now stamps explicitly and an Attio rejection of
    that key is a loud 4xx rather than a silent omission.
    """
    return bool(record_is_test)
