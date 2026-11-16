"""Slack CRM commands. Public names: the read-only Person lookup other modules
use, and the find, get, list, add, edit and bulk-upload calls the Wusool MCP (`mcp`) makes."""

from app.modules.ddl_commands.api.bulk_columns import Column, columns_for, routes_for
from app.modules.ddl_commands.api.bulk_store import (
    MAX_ROWS,
    CommitProgress,
    RowOutcome,
    UploadKind,
)
from app.modules.ddl_commands.api.bulk_upload import (
    InvalidUploadError,
    PreviewNotFoundError,
    PreviewResult,
    RejectedUpload,
    RowProblem,
    UploadRow,
    commit,
    preview_buyers,
    preview_sellers,
    status,
)
from app.modules.ddl_commands.api.flat_records import (
    LIST_LIMIT_MAX,
    AddOutcome,
    InvalidFieldsError,
    InvalidFiltersError,
    RecordDetail,
    RecordList,
    RecordRef,
    add_one,
    edit_one,
    find_records,
    get_record,
    list_buyer_records,
    list_seller_records,
)
from app.modules.ddl_commands.api.schemas import can_clear
from app.modules.ddl_commands.api.write_errors import (
    OrgMismatchError,
    OrgRemovedError,
    PartialWriteError,
)
from app.modules.ddl_commands.application.buyers import BuyerNotFoundError
from app.modules.ddl_commands.application.sellers import SellerNotFoundError
from app.modules.ddl_commands.persistence.person_emails import (
    PersonEmails,
    list_live_person_emails,
)

__all__ = [
    "LIST_LIMIT_MAX",
    "MAX_ROWS",
    "AddOutcome",
    "BuyerNotFoundError",
    "Column",
    "CommitProgress",
    "InvalidFieldsError",
    "InvalidFiltersError",
    "InvalidUploadError",
    "OrgMismatchError",
    "OrgRemovedError",
    "PartialWriteError",
    "PersonEmails",
    "PreviewNotFoundError",
    "PreviewResult",
    "RecordDetail",
    "RecordList",
    "RecordRef",
    "RejectedUpload",
    "RowOutcome",
    "RowProblem",
    "SellerNotFoundError",
    "UploadKind",
    "UploadRow",
    "add_one",
    "can_clear",
    "columns_for",
    "commit",
    "edit_one",
    "find_records",
    "get_record",
    "list_buyer_records",
    "list_live_person_emails",
    "list_seller_records",
    "routes_for",
    "preview_buyers",
    "preview_sellers",
    "status",
]
