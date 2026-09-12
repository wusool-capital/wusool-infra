"""Settings for the lead-magnet tools.

Field names are chosen against `server/.env.example` as a whole, not just
against this class. Every module's root `Settings` reads *unprefixed* env
vars, so two modules declaring `aws_bedrock_model_id` with different
intended values would silently share one — the same collision the Terraform
stacks hit with `instance_type` (see `infrastructure/terraform/README.md`).
Hence `lead_magnet_*` on everything specific to these tools, and bare names
only where the value is genuinely shared: `DATABASE_URL`, `AWS_REGION`,
`FIRECRAWL_API_KEY`.

No AWS key fields. Bedrock is reached through the instance's own IAM role in
both environments (`infrastructure/terraform/modules/bedrock-access`), so
boto3's default credential chain is the whole story — declaring key settings
would create a place for a key to live, which is what this migration exists
to remove.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    aws_region: str = "eu-central-1"

    # Both must be the `eu.` inference-profile id, never the bare model id:
    # every Anthropic model in eu-central-1 reports
    # `inferenceTypesSupported: INFERENCE_PROFILE` and rejects on-demand
    # invocation. Only these two and Sonnet 4.5 are granted on this account
    # (`envs/*.tfvars` `bedrock_models`) — anything else returns
    # AccessDeniedException.
    lead_magnet_model_sonnet: str = "eu.anthropic.claude-sonnet-4-6"
    lead_magnet_model_haiku: str = "eu.anthropic.claude-haiku-4-5-20251001-v1:0"

    # Optional so local dev and the Slack-bot-only deployments boot without
    # it, matching `matching_engine`'s own handling of the same key.
    firecrawl_api_key: str | None = None

    # Space-separated, CSP syntax. Who may *embed* a tool page — the Webflow
    # site, not this host.
    lead_magnet_frame_ancestors: str = "https://wusoolcapital.com https://www.wusoolcapital.com"

    # Space-separated origins allowed to POST the AI endpoints. Different
    # value from `frame_ancestors`: the tool page is served from this host,
    # so its own `fetch` carries this host as `Origin`, not the embedding
    # site's. Empty disables the check (local dev).
    lead_magnet_allowed_origins: str = ""

    # Per-IP, per-hour cap on the endpoints that spend money.
    lead_magnet_rate_per_hour: int = 20

    lead_magnet_sweeper_interval_s: int = 300
    lead_magnet_sweeper_stale_after_s: int = 300

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
    return Settings()
