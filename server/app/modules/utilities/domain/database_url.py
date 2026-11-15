"""The one rule for turning a configured database URL into one the async engine accepts."""


def asyncpg_url(url: str) -> str:
    """Deploy and CI pass a plain `postgresql://` URL; the async engine needs asyncpg."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url
