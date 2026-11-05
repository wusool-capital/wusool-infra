"""Settings for the interactions engine.

Every field is prefixed `interactions_`: all module `Settings` read unprefixed
env vars, so a bare name could silently collide with another module's.
Lists are space-separated strings, like `lead_magnet_frame_ancestors`.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import SettingsConfigDict

from app.modules.interactions.domain.addresses import normalize_address
from app.modules.interactions.domain.model import ScoringRules
from app.modules.utilities import SecretsManagerSettings


class InteractionsSettings(SecretsManagerSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Off by default: dev and prod share one Attio workspace and one Google tenant.
    interactions_enabled: bool = False
    interactions_poll_interval_s: int = 900
    # Primary addresses to impersonate. Hugo's is added once the admin confirms it.
    interactions_mailboxes: str = "jules@wusoolcapital.com ramzy@wusoolcapital.com"
    # The first domain is canonical; the rest are aliases of it.
    interactions_internal_domains: str = "wusoolcapital.com dopaminecap.com"
    interactions_backfill_months: int = 12
    interactions_retention_months: int = 12

    interactions_email_sent_points: float = 1.0
    interactions_email_received_points: float = 1.5
    interactions_meeting_points: float = 4.0
    interactions_half_life_days: float = 90.0
    interactions_two_way_bonus: float = 1.5
    interactions_two_way_window_days: int = 180
    interactions_next_window_days: int = 180
    # Lower bounds of Weak, Good, Strong and Very strong; tuned in the shadow week.
    interactions_label_cutoffs: str = "1 3 7 15"

    # The service-account key lives in Secrets Manager, never in `.env`.
    interactions_google_service_account_json: str | None = None

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
