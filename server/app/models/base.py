"""The single declarative base every ORM model in `wusool_crm` attaches to.

Both `matching-engine` and `ddl-commands` import this same `Base` — previously
each had its own independent `Base`/registry; the merge here is what makes a
future Alembic `--autogenerate` see every mapped table in one `metadata`
instead of two disjoint ones (see `ALEMBIC_MIGRATION_HANDOVER.md` point 2).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
