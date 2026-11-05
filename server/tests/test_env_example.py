"""`.env.example` must list every environment variable each module's
`Settings` actually reads, so a fresh checkout never boots into a confusing
missing-required-field error. Uses pydantic-settings' own `model_fields`
introspection rather than hand-maintaining a second list — this is the
mechanical enforcement `attio_webhook_secret` (a *required* field) being
silently absent from `.env.example` should have caught.

A `BaseSettings` field whose annotation is itself a `BaseSettings` subclass
(e.g. `matching_engine.Settings.scoring: ScoringSettings`) is *not* an env
var itself — that nested class reads its own env vars independently (via
its own `env_prefix`), so it's expanded recursively instead of skipped.
A class-level `env_prefix` is applied too, which is how `AttioSettings`'
`api_key` field resolves to `ATTIO_API_KEY`.
"""

import re
from pathlib import Path

from pydantic_settings import BaseSettings

from app.modules.attio.config import AttioSettings
from app.modules.ddl_commands.config import Settings as DdlCommandsSettings
from app.modules.discovery.config import Settings as DiscoverySettings
from app.modules.discrepancies.config import Settings as DiscrepanciesSettings
from app.modules.enrichment.config import Settings as EnrichmentSettings
from app.modules.interactions.config import InteractionsSettings
from app.modules.lead_magnets.config import Settings as LeadMagnetsSettings
from app.modules.matching_engine.config import Settings as MatchingEngineSettings
from app.modules.meetings.config import Settings as MeetingsSettings
from app.modules.utilities.secrets_manager import SecretLocation

_ENV_EXAMPLE = Path(__file__).parent.parent / ".env.example"
_SETTINGS_CLASSES = (
    MatchingEngineSettings,
    DdlCommandsSettings,
    AttioSettings,
    MeetingsSettings,
    EnrichmentSettings,
    DiscoverySettings,
    DiscrepanciesSettings,
    LeadMagnetsSettings,
    InteractionsSettings,
    SecretLocation,
)

# Supplied by Secrets Manager (or the AWS credential chain), so they must not
# appear as live lines: a value in `.env` would shadow the secret.
_SECRETS_MANAGER_KEYS = frozenset(
    {
        "DATABASE_URL",
        "SLACK_BOT_TOKEN",
        "SLACK_SIGNING_SECRET",
        "ATTIO_API_KEY",
        "ATTIO_WEBHOOK_SECRET",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "FIRECRAWL_API_KEY",
        "DESKTOP_API_KEY",
        "WEB_API_KEY",
        "SLACK_CLIENT_SECRET",
        "WEB_SESSION_SECRET",
        "DIFFBOT_API_KEY",
        "PEOPLE_DATA_LABS_API_KEY",
        "APIFY_API_TOKEN",
        "GOOGLE_PLACES_API_KEY",
        "LEAD_MAGNET_SANITY_WEBHOOK_SECRET",
        "LEAD_MAGNET_SANITY_WRITE_TOKEN",
        "LEAD_MAGNET_WEBFLOW_API_TOKEN",
        "LEAD_MAGNET_POSTHOG_API_KEY",
        "ARCHITECTURE_BASIC_AUTH_PASSWORD",
        "INTERACTIONS_GOOGLE_SERVICE_ACCOUNT_JSON",
    }
)


def _env_var_names(settings_cls: type[BaseSettings]) -> set[str]:
    prefix = settings_cls.model_config.get("env_prefix", "") or ""
    names: set[str] = set()
    for field_name, field_info in settings_cls.model_fields.items():
        annotation = field_info.annotation
        if isinstance(annotation, type) and issubclass(annotation, BaseSettings):
            names |= _env_var_names(annotation)
            continue
        names.add((prefix + field_name).upper())
    return names


def test_env_example_covers_every_settings_field() -> None:
    expected = set()
    for settings_cls in _SETTINGS_CLASSES:
        expected |= _env_var_names(settings_cls)

    declared = set(
        re.findall(r"^([A-Z][A-Z0-9_]*)=", _ENV_EXAMPLE.read_text(encoding="utf-8"), re.MULTILINE)
    )

    missing = sorted(expected - _SECRETS_MANAGER_KEYS - declared)
    assert missing == [], f"{_ENV_EXAMPLE.name} is missing: {missing}"


def test_env_example_has_no_live_secret_lines() -> None:
    declared = set(
        re.findall(r"^([A-Z][A-Z0-9_]*)=", _ENV_EXAMPLE.read_text(encoding="utf-8"), re.MULTILINE)
    )

    leaked = sorted(declared & _SECRETS_MANAGER_KEYS)
    assert leaked == [], f"{_ENV_EXAMPLE.name} sets Secrets Manager keys: {leaked}"
