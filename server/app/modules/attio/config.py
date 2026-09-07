"""Every `ATTIO_*` environment variable, declared once.

`AttioSettings` uses `env_prefix="ATTIO_"` so the fields drop the redundant
prefix (`api_key`, not `attio_api_key`), and `ddl_commands`/`meetings`
compose it as a nested field rather than redeclaring the same variables —
the same shape `matching_engine.Settings` already uses for its
`SCORING_WEIGHT_*` and `CONFIDENCE_*` families. Before this, `api_key` was
declared in two `Settings` classes and `note_object_slug` in two more, each
with its own copy of the validation.

`ATTIO_WEBHOOK_SECRET` deliberately stays in `ddl_commands`' own `Settings`:
it has exactly one consumer (the `/webhooks/attio` signature check), and it
is scoped to that route rather than to the client. Requiring it here would
mean any process that merely builds an Attio client — a one-shot script, say
— had to supply a webhook secret it never uses.

There is no `note_object_slug` setting. It existed because DEV Attio had no
`note` object, so dev left it unset to skip note sync entirely; with one
workspace the object always exists, the slug has exactly one legal value,
and `attio_sync.sync_note` was already hardcoding the literal anyway.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.modules.attio.domain.scope import record_scope


class AttioSettings(BaseSettings):
    """Attio settings. Instantiate the module's own via `get_settings()`, or
    compose this class as a field from another module's `Settings`."""

    model_config = SettingsConfigDict(env_prefix="ATTIO_", env_file=".env", extra="ignore")

    # SOURCE Attio workspace write access. One workspace serves both
    # environments; `is_test` below is what separates them.
    api_key: str

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
    is_test: bool = True

    # Expected SOURCE workspace id, checked against inbound webhook
    # deliveries. None skips the check. Worth setting now that one workspace
    # serves both environments: object/list UUIDs are no longer unique per
    # environment, so a misdirected subscription would otherwise sync
    # happily instead of failing on an unknown UUID.
    workspace_id: str | None = None


@lru_cache
def get_settings() -> AttioSettings:
    """Return a cached, process-wide AttioSettings instance."""
    return AttioSettings()


def attio_is_test() -> bool:
    """Whether this process owns the test half of the shared workspace."""
    return get_settings().is_test


def attio_workspace_id() -> str | None:
    """The SOURCE workspace id inbound webhooks are expected to carry, or
    `None` to skip the check."""
    return get_settings().workspace_id


def owns_record(record_is_test: bool | None) -> bool:
    """Whether a SOURCE record belongs to this process's half of the shared
    workspace."""
    return record_scope(record_is_test) is attio_is_test()
