"""Typed Attio configuration, loaded from environment variables / .env —
independent of `ddl_commands`' own `Settings` (which reads the same
`ATTIO_API_KEY` env var for its own settings object, plus
`ATTIO_WEBHOOK_SECRET` for its `/webhooks/attio` route, which stays in
`ddl_commands` and isn't this module's concern) so this module has no
import-time dependency back on its one consumer.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Attio settings. Instantiate via `get_settings()`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SOURCE Attio workspace write access — one workspace serves both
    # environments since 2026-09-07; `attio_is_test` below is what separates
    # them.
    attio_api_key: str

    # Which half of the single shared SOURCE workspace this process owns.
    # True stamps every record it creates `is_test = true` and makes it
    # ignore production records; False is the inverse.
    #
    # Defaults to True because the two failure directions are not
    # symmetric. A prod deploy that forgets this marks real records as test:
    # they vanish from prod views and the prod mirror, which is loud,
    # bounded to records created after the mistake, and fixed by flipping a
    # checkbox. A dev deploy that forgets it writes test data into
    # production indistinguishably from real CRM data — silent, unbounded,
    # and only undoable by hand.
    attio_is_test: bool = True

    # Expected SOURCE workspace id, checked against inbound webhook
    # deliveries. None skips the check. Worth setting now that one workspace
    # serves both environments: object/list UUIDs are no longer unique per
    # environment, so a misdirected subscription would otherwise sync
    # happily instead of failing on an unknown UUID.
    attio_workspace_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance."""
    return Settings()


def attio_is_test() -> bool:
    """Whether this process owns the test half of the shared workspace."""
    return get_settings().attio_is_test


def attio_workspace_id() -> str | None:
    """The SOURCE workspace id inbound webhooks are expected to carry, or
    `None` to skip the check."""
    return get_settings().attio_workspace_id


def record_scope(record_is_test: bool | None) -> bool:
    """Normalise a record's raw `is_test` value to the half it belongs to.

    The one statement of the null policy: an unset checkbox (`None`) reads
    as production. Every record migrated before 2026-09-07 has `is_test`
    absent from its payload entirely, so requiring an explicit `False` would
    stop the prod sync writing anything until a stamping run had walked
    every entity — a self-inflicted outage in exchange for nothing, since
    every write path now stamps explicitly and an Attio rejection of that
    key is a loud 4xx rather than a silent omission.
    """
    return bool(record_is_test)


def owns_record(record_is_test: bool | None) -> bool:
    """Whether a SOURCE record belongs to this process's half of the shared
    workspace."""
    return record_scope(record_is_test) is attio_is_test()
