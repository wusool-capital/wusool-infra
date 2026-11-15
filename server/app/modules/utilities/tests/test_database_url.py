import pytest

from app.modules.utilities.domain.database_url import asyncpg_url


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        ("postgresql+asyncpg://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        (
            "postgresql://u:p@host/db?sslmode=require",
            "postgresql+asyncpg://u:p@host/db?sslmode=require",
        ),
        ("sqlite:///x.db", "sqlite:///x.db"),
    ],
)
def test_only_a_plain_postgres_scheme_is_rewritten(given: str, expected: str) -> None:
    assert asyncpg_url(given) == expected


def test_only_the_first_scheme_is_rewritten() -> None:
    assert (
        asyncpg_url("postgresql://h/db?x=postgresql://y")
        == "postgresql+asyncpg://h/db?x=postgresql://y"
    )
