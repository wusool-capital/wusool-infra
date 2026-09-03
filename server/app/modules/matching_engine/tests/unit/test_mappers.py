"""Mapper-configuration test: catches a typo'd cross-module string
forward-reference (e.g. `Mapped["BuyeRole"]`) or a bad `foreign_keys=`
argument across every model. Needs no database connection — runs in the
default no-tunnel suite. Run this before anything in tests/integration/.
"""

from sqlalchemy.orm import configure_mappers

from app.modules.matching_engine.persistence.database import import_all_models


def test_all_models_configure_without_a_database() -> None:
    import_all_models()
    configure_mappers()
