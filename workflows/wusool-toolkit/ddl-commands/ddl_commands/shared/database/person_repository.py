"""Person persistence — write-only for now: `/edit-buyer`'s "create a key
contact" step is the only caller, and it only ever creates a brand-new
person, never searches or updates an existing one. Mirrors
`organization_repository.py`'s `create` exactly. `add()`/`flush()` only —
never `commit()`; the caller owns the transaction boundary.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from wusool_db.models import Person


class PersonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, attio_id: str, name: str, **fields) -> Person:
        """`attio_id` is always Attio's own `record_id` from a create that
        already succeeded there — this method never invents one."""
        person = Person(attio_id=attio_id, name=name, **fields)
        self._session.add(person)
        await self._session.flush()
        return person
