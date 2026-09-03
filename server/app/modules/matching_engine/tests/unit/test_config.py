from app.modules.matching_engine.config import get_settings


def test_settings_load_from_environment() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.stage3_top_n == 3


def test_database_url_scheme_normalizes_plain_postgresql(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost:15432/wusool_crm"
    get_settings.cache_clear()
