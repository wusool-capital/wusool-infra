"""Slack CRM commands. Public names: the read-only Person lookup other modules
use, and the find, add, edit and bulk-upload calls the Wusool MCP (`mcp`) makes."""

from app.modules.ddl_commands.api.bulk_columns import Column, columns_for
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
    AddOutcome,
    InvalidFieldsError,
    RecordRef,
    add_one,
    edit_one,
    find_records,
)
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
    "MAX_ROWS",
    "AddOutcome",
    "BuyerNotFoundError",
    "Column",
    "CommitProgress",
    "InvalidFieldsError",
    "InvalidUploadError",
    "OrgMismatchError",
    "OrgRemovedError",
    "PartialWriteError",
    "PersonEmails",
    "PreviewNotFoundError",
    "PreviewResult",
    "RecordRef",
    "RejectedUpload",
    "RowOutcome",
    "RowProblem",
    "SellerNotFoundError",
    "UploadKind",
    "UploadRow",
    "add_one",
    "columns_for",
    "commit",
    "edit_one",
    "find_records",
    "list_live_person_emails",
    "preview_buyers",
    "preview_sellers",
    "status",
]
