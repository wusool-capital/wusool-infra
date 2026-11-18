"""The filterable fields of a buyer or seller. The fields the add and edit forms
already name keep their keys, labels and options; every other data column comes from
`record_filters`, so `list_*` can filter on, and `get_*` can return, any of them."""

from functools import cache

from app.modules.ddl_commands.api.bulk_columns import routes_for
from app.modules.ddl_commands.api.bulk_store import UploadKind
from app.modules.record_filters import FieldCatalog, FieldMeta, build_catalog


@cache
def filter_catalog(kind: UploadKind) -> FieldCatalog:
    meta = [
        FieldMeta(
            key=key,
            target=route.target,
            column=route.name,
            label=route.spec.label,
            options=route.spec.options,
            joined_text=route.spec.kind == "multi_select_as_text",
        )
        for key, route in routes_for(kind).items()
    ]
    return build_catalog(kind, meta)
