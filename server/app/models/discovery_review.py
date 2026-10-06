"""`discovery_reviews` — Google Maps leads `discovery` held back for a human
website review instead of auto-creating (AZM-134).

One row per Google place id: it backs the "Review & Save" button (so the card
survives a restart) and stops later discovery runs re-enriching and re-posting
the same lead for 30 days after its card was posted. Postgres-only
operational state, never synced to Attio, so the Attio-first write rule does
not apply.
"""

from datetime import datetime

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DiscoveryReview(Base):
    __tablename__ = "discovery_reviews"

    place_id: Mapped[str] = mapped_column(Text, primary_key=True)
    org_name: Mapped[str] = mapped_column(Text, nullable=False)
    # The prefilled `SellerDraft`, parsed by `discovery.persistence` on read.
    draft: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Reset on every re-flag, so expiry counts from the latest card.
    flagged_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    # Set once the card reached Slack; an unposted row never suppresses a lead.
    posted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
