from app.modules.discovery.config import Settings


def test_database_url_gets_the_asyncpg_driver() -> None:
    """Deploy and CI pass a plain `postgresql://` URL; the async engine needs asyncpg."""
    settings = Settings(
        database_url="postgresql://u:p@db:5432/x", slack_bot_token="x", slack_signing_secret="x"
    )

    assert settings.database_url == "postgresql+asyncpg://u:p@db:5432/x"
