"""Settings for the interactions engine.

Every field is prefixed `interactions_`: all module `Settings` read unprefixed
env vars, so a bare name could silently collide with another module's.
Lists are space-separated strings, like `lead_magnet_frame_ancestors`.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from app.modules.google_workspace import normalize_address
from app.modules.interactions.domain.attio_fields import WriteMode
from app.modules.interactions.domain.model import ScoringRules
from app.modules.utilities import SecretsManagerSettings
from app.modules.utilities.domain.database_url import asyncpg_url


class InteractionsSettings(SecretsManagerSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    # Off by default: dev and prod share one Attio workspace and one Google tenant.
    interactions_enabled: bool = False
    # At least a minute: a smaller value would hammer Google's quota and the database.
    interactions_poll_interval_s: int = Field(default=900, ge=60)
    # Primary addresses to impersonate. Hugo's mailbox is deliberately not read.
    interactions_mailboxes: str = "jules@wusoolcapital.com ramzy@wusoolcapital.com"
    # The first domain is canonical; the rest are aliases of it.
    interactions_internal_domains: str = "wusoolcapital.com dopaminecap.com"
    interactions_backfill_months: int = Field(default=12, ge=1)
    # At least one month: zero would delete almost every interaction on the next purge.
    interactions_retention_months: int = Field(default=12, ge=1)

    interactions_email_sent_points: float = Field(default=1.0, ge=0)
    interactions_email_received_points: float = Field(default=1.5, ge=0)
    interactions_meeting_points: float = Field(default=4.0, ge=0)
    interactions_half_life_days: float = Field(default=90.0, gt=0)
    interactions_two_way_bonus: float = Field(default=1.5, gt=0)
    interactions_two_way_window_days: int = Field(default=180, ge=1)
    interactions_next_window_days: int = Field(default=180, ge=1)
    # Lower bounds of Weak, Good, Strong and Very strong; tuned in the shadow week.
    interactions_label_cutoffs: str = "1 3 7 15"

    # Writing to Attio is off until the shadow-week gate has passed. `dry_run` only logs counts.
    interactions_attio_write_mode: WriteMode = WriteMode.OFF
    # Attio has no bulk update, and its webhook re-reads each record we touch.
    interactions_attio_writes_per_second: float = Field(default=5.0, gt=0, le=20)
    interactions_attio_max_records_per_round: int = Field(default=500, ge=1)

    # The Deal rollup runs inside the write step, so it needs the write mode on too.
    interactions_deal_rollup_mode: WriteMode = WriteMode.OFF
    interactions_deal_rollup_max_per_round: int = Field(default=500, ge=1)

    # Creating Persons and Organizations from email is off until a canary record checks out.
    interactions_auto_create_mode: WriteMode = WriteMode.OFF
    interactions_auto_create_max_per_round: int = Field(default=20, ge=1)
    # Slack channel id for the daily review digest; empty turns the digest off.
    interactions_review_slack_channel: str = ""
    slack_bot_token: str = ""

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Deploy and CI pass a plain `postgresql://` URL; the async engine needs asyncpg."""
        return asyncpg_url(value)

    @field_validator("interactions_mailboxes")
    @classmethod
    def normalize_mailboxes(cls, value: str) -> str:
        addresses = [normalize_address(raw) for raw in value.split()]
        if None in addresses:
            raise ValueError("interactions_mailboxes must be space-separated email addresses")
        return " ".join(a for a in addresses if a)

    @field_validator("interactions_label_cutoffs")
    @classmethod
    def validate_cutoffs(cls, value: str) -> str:
        cutoffs = [float(part) for part in value.split()]
        if len(cutoffs) != 4 or cutoffs != sorted(cutoffs):
            raise ValueError("interactions_label_cutoffs needs four ascending numbers")
        return value

    @property
    def mailboxes(self) -> tuple[str, ...]:
        return tuple(self.interactions_mailboxes.split())

    @property
    def internal_domains(self) -> tuple[str, ...]:
        return tuple(self.interactions_internal_domains.lower().split())

    def scoring_rules(self) -> ScoringRules:
        weak, good, strong, very_strong = (
            float(part) for part in self.interactions_label_cutoffs.split()
        )
        return ScoringRules(
            email_sent_points=self.interactions_email_sent_points,
            email_received_points=self.interactions_email_received_points,
            meeting_points=self.interactions_meeting_points,
            half_life_days=self.interactions_half_life_days,
            two_way_bonus=self.interactions_two_way_bonus,
            two_way_window_days=self.interactions_two_way_window_days,
            next_window_days=self.interactions_next_window_days,
            cutoffs=(weak, good, strong, very_strong),
        )


@lru_cache
def get_settings() -> InteractionsSettings:
    return InteractionsSettings()
