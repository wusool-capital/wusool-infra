"""Ensures every ORM model is imported so cross-module relationship string
forward-references (e.g. `Organization.buyer_roles: Mapped[list["BuyerRole"]]`)
resolve against the shared declarative `Base` registry.

Call once before any query that traverses a cross-module relationship —
each module's `tests/conftest.py` calls this at collection time, its
`bootstrap.py` at `create_app()` time. Pure imports, no I/O.
"""


def import_all_models() -> None:
    import app.models  # noqa: F401
