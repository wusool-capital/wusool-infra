"""Schema-drift detection: this application expects a schema; the database
must already satisfy it. If not, fail clearly here — never modify the
database to "fix" it (see `app/shared/database/schema_check.py`).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database import get_engine, import_all_models
from app.shared.database.base import Base
from app.shared.database.schema_check import find_schema_drift


async def test_declared_models_match_live_schema(db_session: AsyncSession) -> None:
    import_all_models()
    expected = {
        table.name: {column.name for column in table.columns}
        for table in Base.metadata.tables.values()
    }

    drift = await find_schema_drift(get_engine(), expected)

    assert drift == [], f"schema drift detected: {drift}"
