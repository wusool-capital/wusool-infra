"""grant scribe_pub privileges

Grants the `scribe_pub` role (created as a NOLOGIN placeholder in
d982478fc6e3, before any table existed) the least-privilege access it needs:
write access to `meetings`, read access to `organizations` — mirrors
database/sql/005_meetings.sql's commented-out GRANT lines exactly. Split
into its own revision, after "create all tables", because `meetings` and
`organizations` do not exist until that revision runs — granting on a
table that doesn't exist yet fails outright (verified: an earlier attempt
at putting these GRANTs in d982478fc6e3 failed with
`asyncpg.exceptions.UndefinedTableError: relation "meetings" does not
exist` against a genuinely empty database).

*** SECURITY NOTE — same reasoning as d982478fc6e3, read that revision's
docstring first. *** These GRANTs never create, alter, or reference a
password. They are idempotent: re-granting a privilege a role already holds
is a no-op in Postgres, so running this against a database where the real,
human-provisioned `scribe_pub` LOGIN role already holds these exact grants
(every real dev/prod environment) changes nothing and errors on nothing.

Revision ID: eec9dde1cfbb
Revises: 87320bb9dc8d
Create Date: 2026-08-18 00:21:02.629480

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eec9dde1cfbb"
down_revision: str | Sequence[str] | None = "87320bb9dc8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("GRANT SELECT, INSERT, UPDATE ON meetings TO scribe_pub;")
    op.execute("GRANT SELECT ON organizations TO scribe_pub;")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("REVOKE SELECT ON organizations FROM scribe_pub;")
    op.execute("REVOKE SELECT, INSERT, UPDATE ON meetings FROM scribe_pub;")
