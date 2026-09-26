"""split buyer_roles.target_geography into region and country (2026-09-26)

`target_geography` held three different kinds of thing in one array: countries
(`UAE`, `KSA`, `Kuwait`, `Bahrain`, `Qatar`, `Oman`, `Egypt`), a region
(`GCC-wide`) and a no-restriction marker (`Global`). Nothing downstream could
tell them apart, so `discovery` had to guess per value — and guessed wrong:
geocoding `"GCC"` returned Glendale Community College, California, with
`status: OK`, silently narrowing a Gulf search to Glendale (see
`discovery/domain/geography.py`, which exists because of that bug).

Separating them makes the distinction structural rather than inferred:
`target_region` resolves from discovery's fixed region table and is never
geocoded; `target_country` always geocodes, using names Google recognises.

Vocabularies come from the Slack pickers that already exist rather than new
ones: `target_country` is `organizations.hq_country`'s 93 full country names,
`target_region` is `organizations.region`'s 14 plus `Africa`, `Asia` and
`Emerging Markets`, which `organizations.geographic_focus` carries and the
backfill's fallback reads. Both use one canonical name per place, which is why
`KSA` becomes `Saudi Arabia` and `UAE` becomes `United Arab Emirates` — the
workspace currently holds both spellings of the same country as separate
options.

Both old columns are dropped. The Postgres side is a mirror, so this is safe
once the Attio backfill has run — and it must have: `normalize-buyer-geography.ps1`
reads `target_geography` **from Attio**, not from here, and has to complete
before this deploys. The Attio attributes themselves are archived by hand
afterwards, last of all, because archiving one while a reader is still live
would have the mirror write empty arrays over real values.

`buyer_roles.geographic_focus` IS dropped. It was added five days ago
(`a3f19c7d2e64`) as a verbatim text carry-over precisely because no approved
enum could hold `Africa` and `Pakistan` — which is exactly the problem the
region/country split solves, so it has no remaining purpose. It never held a
value: its only writer was the buyer-vertical split, which has not been
applied. The downgrade recreates it empty, which is what it was.

What this migration does, and what it does not:

    ADDS    buyer_roles.target_region   text[] NOT NULL DEFAULT '{}'
            buyer_roles.target_country  text[] NOT NULL DEFAULT '{}'
    DROPS   buyer_roles.target_geography
            buyer_roles.geographic_focus

It moves no data. The values are converted **in Attio** by
`crm-sync/scripts/source-attio/normalize-buyer-geography.ps1`, which reads each
buyer role's own `target_geography` -- or, when that is empty, its parent
organization's `geographic_focus` -- and writes the two new fields. The mirror
then brings the result down here. That script must have run and been verified
before this migration deploys; run in the other order, the columns arrive empty
and the old ones are gone.

Nothing on `organizations` changes: `geographic_focus` there is read as a
fallback source and left exactly as it is.

Revision ID: d8e4b1c60f27
Revises: a3f19c7d2e64
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

from alembic import op

revision: str = "d8e4b1c60f27"
down_revision: str | Sequence[str] | None = "a3f19c7d2e64"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Same shape as `target_geography` (f3a8c1d92b47): NOT NULL with an empty
    # default, because the sync always writes a list, never NULL.
    op.add_column(
        "buyer_roles",
        sa.Column(
            "target_region",
            ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "buyer_roles",
        sa.Column(
            "target_country",
            ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.drop_column("buyer_roles", "geographic_focus")
    op.drop_column("buyer_roles", "target_geography")


def downgrade() -> None:
    op.add_column(
        "buyer_roles",
        sa.Column(
            "target_geography",
            ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column("buyer_roles", sa.Column("geographic_focus", sa.Text(), nullable=True))
    op.drop_column("buyer_roles", "target_country")
    op.drop_column("buyer_roles", "target_region")
