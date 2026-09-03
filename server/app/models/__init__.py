"""Every ORM model mapped onto `wusool_crm`, registered onto the one shared
`app.models.base.Base`.

The single source of truth for every table this app maps onto — both the
`ddl_commands` and `matching_engine` modules import every ORM model from
here rather than owning any model file themselves. This package
intentionally has no engine/session/settings wiring of its own — that stays
in each module's own `persistence/` layer (see the app-wide `DATABASE_URL`
config).

Importing this package (or any name from it) is sufficient to register every
model class below onto `Base.metadata` — this is what both `matching_engine`'s
and `ddl_commands`' `import_all_models()` do, and what Alembic's `env.py`'s
`target_metadata` import does too (see `ALEMBIC_MIGRATION_HANDOVER.md` point
2: a model that never gets imported here is invisible to `--autogenerate`,
which then proposes dropping its table).

The 14 models below `MatchScore`/`Meeting` (from `activity.py` onward,
alphabetically through `vertical_kb.py`) were added as a batch of
static-analysis drafts, not from a live-DB reflection — see
`app/models/_static_analysis_notice.py` before trusting any of them for
`alembic stamp head`.
"""

from app.models.activity import Activity
from app.models.attio_raw_event import AttioRawEvent
from app.models.attio_sync_state import AttioSyncState
from app.models.buyer_intel import BuyerIntel
from app.models.buyer_role import BuyerRole
from app.models.deal import Deal
from app.models.deal_stage_event import DealStageEvent
from app.models.document import Document
from app.models.graph_edge import GraphEdge
from app.models.investor_lender_role import InvestorLenderRole
from app.models.match_result import MatchResult
from app.models.match_score import MatchScore
from app.models.meeting import Meeting
from app.models.note import Note
from app.models.organization import Organization
from app.models.person import Person
from app.models.scorecard import Scorecard
from app.models.seller_financial import SellerFinancial
from app.models.seller_role import SellerRole
from app.models.signal import Signal
from app.models.user import User
from app.models.vertical_kb import VerticalKb

__all__ = [
    "Activity",
    "AttioRawEvent",
    "AttioSyncState",
    "BuyerIntel",
    "BuyerRole",
    "Deal",
    "DealStageEvent",
    "Document",
    "GraphEdge",
    "InvestorLenderRole",
    "MatchResult",
    "MatchScore",
    "Meeting",
    "Note",
    "Organization",
    "Person",
    "Scorecard",
    "SellerFinancial",
    "SellerRole",
    "Signal",
    "User",
    "VerticalKb",
]
