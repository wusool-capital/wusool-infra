# record_filters

One place that knows which buyer, seller and company columns can be filtered, how each
kind of column is filtered, and the SQL for it. The Wusool MCP uses it for `list_buyers`,
`list_sellers`, `get_*` and `list_field_options`. The Engine (`crm`) can build its lists
from the same catalog and conditions; it has not moved yet.

It has no tables and no settings.

## How it works

- **Catalog** (`persistence/catalog.py`). `build_catalog(kind, meta)` reads every data
  column of `BuyerRole` or `SellerRole` and of `Organization`, so a new column is
  filterable with no code here. Ids, links to other tables, `raw_attio`, `removed_at`,
  `legacy_entry_id` and `is_active` are left out. The caller passes `FieldMeta` for the
  fields it already names (`ddl_commands` passes its add and edit fields): those keep
  their keys, labels and select options, and are marked `editable`. Every other column
  gets its column name as key, or `role_<name>` / `org_<name>` when that key is taken.
- **Shapes** (`domain/fields.py`). A column's type gives its shape: `text`, `array`,
  `money` (a JSONB `{amount, currency}`), `number`, `date`, `datetime` or `bool`. A text
  column the caller marks `joined_text` is a ", "-joined multi-select. The shape decides
  the operators (`ALLOWED_OPS`).
- **Filters** (`api/filters.py`). `FieldFilter` is a pydantic union keyed by `op`:
  `eq`, `in`, `contains`, `gte`, `lte`, `is_set`, `is_not_set`. `resolve_filters(catalog,
  filters)` checks each one against its field and returns `FieldCondition`s, or every
  problem found, so the sender fixes them in one go.
- **SQL** (`persistence/sql.py`). `condition_sql(kind, condition)` returns the SQL for one
  condition, for the caller's own query on the role joined to its company.

## Rules worth knowing

- `gte`, `lte` and `eq` never match a record with no value. `is_set` finds those that
  have one. An empty text or array counts as not set.
- A money amount stored as a numeric string counts as a number. One that isn't numeric
  counts as not set.
- `contains` ignores case and treats `%` and `_` as plain text.
- An error never lists a select's options. It tells the sender to call
  `list_field_options`.

## Using it from another module

Import only from `app.modules.record_filters`. Build a catalog once (`ddl_commands` caches
it in `api/filter_catalog.py`), resolve the filters you were sent, and add
`condition_sql(...)` for each condition to your own `WHERE`. Reading values back by
catalog key is the caller's job; `ddl_commands` does it for `get_*`.
