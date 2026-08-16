"""Typed application configuration, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScoringSettings(BaseSettings):
    """Weights applied when deterministically calculating match scores."""

    model_config = SettingsConfigDict(env_prefix="SCORING_WEIGHT_", extra="ignore")

    strategy: float = 0.4
    size: float = 0.3
    sector: float = 0.3


class ConfidenceSettings(BaseSettings):
    """Multipliers applied when calculating data confidence for a match (§12).

    `crm_field` (1.0) and `unavailable` (0.0) are the fixed endpoints of the
    scale, not configurable. `llm_extracted`/`llm_inferred` sit between them
    and are configurable since they're a product judgment call, not a fact.
    """

    model_config = SettingsConfigDict(env_prefix="CONFIDENCE_", extra="ignore")

    llm_extracted: float = 0.6
    llm_inferred: float = 0.4
    missing_field_penalty: float = 0.1
    stale_data_penalty: float = 0.15


class Settings(BaseSettings):
    """Root application settings. Instantiate via `get_settings()`."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"

    database_url: str

    # Slack incoming webhook the Attio sync guard posts to when it skips a
    # bot-managed row (database/sync-postgres.ps1). Not read by this app
    # directly — kept here only so one shared .env documents it in one place,
    # matching ddl-commands' own Settings.
    sync_alert_webhook_url: str | None = None

    slack_bot_token: str
    slack_signing_secret: str

    # AWS Bedrock. Region/model IDs match what's already provisioned in
    # terraform/environments/dev (terraform/modules/bedrock-access) — not arbitrary placeholders.
    # Access key/secret are optional: the standard AWS credential provider
    # chain (IAM role, ECS/EC2 task role, local profile, env) applies when
    # unset, per the task's instruction not to require long-lived creds.
    aws_region: str = "eu-central-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_bedrock_model_id_extraction: str = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    aws_bedrock_model_id_reasoning: str = "eu.anthropic.claude-sonnet-4-6"

    # Bedrock inference parameters, not hardcoded into the client.
    llm_temperature: float = 0.2
    llm_max_tokens: int = 4096
    llm_top_p: float = 0.9

    stage3_top_n: int = 3

    # Firecrawl web-fallback: shown when no CRM candidate's score clears
    # this threshold. Optional since local dev without a key just never
    # triggers the fallback (falls back to the plain "no candidates"
    # message) rather than requiring a key to boot.
    firecrawl_api_key: str | None = None
    web_fallback_min_score: float = 50.0

    # Meeting-notes enrichment: free-text call/meeting notes (`meetings`
    # table) appended to the buyer/reasoning prompts as unverified context.
    meeting_notes_max_chars: int = 600
    meeting_notes_max_total_chars: int = 4000
    enable_seller_meeting_notes: bool = True

    scoring: ScoringSettings = Field(default_factory=ScoringSettings)
    confidence: ConfidenceSettings = Field(default_factory=ConfidenceSettings)

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Ensure the URL uses the asyncpg driver scheme regardless of input form."""
        if value.startswith("postgresql+asyncpg://"):
            return value
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached, process-wide Settings instance."""
    return Settings()
