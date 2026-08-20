"""Every ORM model mapped onto `wusool_crm`, registered onto the one shared
`wusool_db.base.Base`.

Importing this package (or any name from it) is sufficient to register every
model class below onto `Base.metadata` — this is what both `matching-engine`'s
and `ddl-commands`' `import_all_models()` do, and what a future Alembic
`env.py`'s `target_metadata` import must do too (see
`ALEMBIC_MIGRATION_HANDOVER.md` point 2: a model that never gets imported
here is invisible to `--autogenerate`, which then proposes dropping its
table).

The 14 models below `MatchScore`/`Meeting` (from `activity.py` onward,
alphabetically through `vertical_kb.py`) were added as a batch of
static-analysis drafts, not from a live-DB reflection — see
`wusool_db/models/_static_analysis_notice.py` before trusting any of them for
`alembic stamp head`.
"""

from wusool_db.models.activity import Activity
from wusool_db.models.attio_raw_event import AttioRawEvent
from wusool_db.models.attio_sync_state import AttioSyncState
from wusool_db.models.buyer_intel import BuyerIntel
from wusool_db.models.buyer_role import BuyerRole
from wusool_db.models.deal import Deal
from wusool_db.models.deal_stage_event import DealStageEvent
from wusool_db.models.document import Document
from wusool_db.models.graph_edge import GraphEdge
from wusool_db.models.investor_lender_role import InvestorLenderRole
from wusool_db.models.mandate import Mandate
from wusool_db.models.mandate_target import MandateTarget
from wusool_db.models.match_result import MatchResult
from wusool_db.models.match_score import MatchScore
from wusool_db.models.meeting import Meeting

# wusool_db.models.note.Note is a draft model for the proposed (not yet
# built) Notes feature -- deliberately NOT imported here yet. Importing it
# would register `notes` onto Base.metadata, and CI's Alembic drift check
# compares that metadata against the migration history: since there is no
# migration for `notes` yet (on purpose -- DEV Attio's Notes object doesn't
# exist either), the drift check would fail. Import it here only once its
# migration is written.
from wusool_db.models.organization import Organization
from wusool_db.models.person import Person
from wusool_db.models.scorecard import Scorecard
from wusool_db.models.seller_financial import SellerFinancial
from wusool_db.models.seller_role import SellerRole
from wusool_db.models.signal import Signal
from wusool_db.models.user import User
from wusool_db.models.vertical_kb import VerticalKb

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
    "Mandate",
    "MandateTarget",
    "MatchResult",
    "MatchScore",
    "Meeting",
    "Organization",
    "Person",
    "Scorecard",
    "SellerFinancial",
    "SellerRole",
    "Signal",
    "User",
    "VerticalKb",
]
