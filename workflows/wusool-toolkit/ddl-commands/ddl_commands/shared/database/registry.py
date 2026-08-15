"""Ensures every ORM model is imported so cross-module relationship string
forward-references (e.g. `Organization.buyer_role: Mapped["BuyerRole | None"]`)
resolve against the shared declarative `Base` registry.

Call once before any query that traverses a cross-module relationship —
`tests/conftest.py` calls this at collection time, `ddl_commands/main.py` at
import time. Pure imports, no I/O.
"""


def import_all_models() -> None:
    import ddl_commands.modules.buyers.infrastructure.models  # noqa: F401
    import ddl_commands.modules.sellers.infrastructure.models  # noqa: F401
    import ddl_commands.shared.database.models  # noqa: F401
