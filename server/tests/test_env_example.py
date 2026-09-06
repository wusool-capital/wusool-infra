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
"""

import re
from pathlib import Path

from pydantic_settings import BaseSettings

from app.modules.attio.config import Settings as AttioSettings
from app.modules.ddl_commands.config import Settings as DdlCommandsSettings
from app.modules.matching_engine.config import Settings as MatchingEngineSettings
from app.modules.meetings.config import Settings as MeetingsSettings

_ENV_EXAMPLE = Path(__file__).parent.parent / ".env.example"
_SETTINGS_CLASSES = (MatchingEngineSettings, DdlCommandsSettings, AttioSettings, MeetingsSettings)


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

    missing = sorted(expected - declared)
    assert missing == [], f"{_ENV_EXAMPLE.name} is missing: {missing}"
