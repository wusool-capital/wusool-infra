"""One place that knows which buyer, seller and company columns can be filtered, how each
kind of column is filtered, and the SQL for it. The Wusool MCP uses it today; the Engine
(`crm`) can build its lists from the same catalog and conditions.

A caller names the fields it already uses (`FieldMeta`) to `build_catalog`; every other
data column of the models is added automatically. `resolve_filters` checks the filters
an agent or client sent against the catalog, and `condition_sql` turns each checked
condition into SQL for the caller's own query.
"""

from app.modules.record_filters.api.filters import (
    MAX_FILTERS,
    MAX_VALUES,
    FieldFilter,
    resolve_filters,
)
from app.modules.record_filters.domain.fields import (
    ALLOWED_OPS,
    ConditionValue,
    FieldCatalog,
    FieldCondition,
    FieldMeta,
    FieldShape,
    FilterableField,
    FilterOp,
    FilterProblem,
    RecordKind,
)
from app.modules.record_filters.persistence.catalog import build_catalog
from app.modules.record_filters.persistence.sql import condition_sql

__all__ = [
    "ALLOWED_OPS",
    "MAX_FILTERS",
    "MAX_VALUES",
    "ConditionValue",
    "FieldCatalog",
    "FieldCondition",
    "FieldFilter",
    "FieldMeta",
    "FieldShape",
    "FilterOp",
    "FilterProblem",
    "FilterableField",
    "RecordKind",
    "build_catalog",
    "condition_sql",
    "resolve_filters",
]
