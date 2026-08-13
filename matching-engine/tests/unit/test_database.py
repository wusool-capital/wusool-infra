"""The engine must be constructible without a live database connection."""

from app.shared.database import get_engine, get_sessionmaker


def test_engine_constructs_without_connecting() -> None:
    engine = get_engine()
    assert engine is not None


def test_sessionmaker_constructs_without_connecting() -> None:
    sessionmaker = get_sessionmaker()
    assert sessionmaker is not None
