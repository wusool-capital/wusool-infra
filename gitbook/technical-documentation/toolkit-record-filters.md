# Record filters

The `record_filters` module is the one place that knows which buyer, seller and company columns can be filtered. The Wusool MCP uses it today. The Engine can build its lists from it later.

## The catalog

- The catalog is read from the models. It holds every data column of a buyer role or seller role and of its company. A new column is filterable with no code.
- Ids, links to other tables, raw Attio payloads, `removed_at`, `legacy_entry_id` and `is_active` are left out.
- The fields the add and edit forms already name keep their keys, labels and options, and are marked editable. Every other column is filterable and readable but not editable, such as benchmark scores, headcount, lead priority and interaction dates.
- Every other column's key is its column name. If a role column and a company column share a name, the company's key starts with `org_`, or the role's with `role_`.
- `list_field_options` returns the catalog: each field's key, type, allowed values, whether it is editable, and the operators it takes. It accepts `fields` to return just those keys.

## Filters

A filter is `{field, op, value}`. Every filter given must match. Each kind of column takes certain operators:

| Column | Operators |
| --- | --- |
| Select, text | `eq`, `in`, and for text `contains` |
| Multi-select | `in` (any value matches), `eq` |
| Money, number, percent, date | `gte`, `lte`, `eq` |
| Date and time | `gte`, `lte` |
| Checkbox | `eq` |
| Any column | `is_set`, `is_not_set` |

- `gte`, `lte` and `eq` never match a record with no value. Ask `is_set` first to see how many have one.
- A check size range that contains a deal size is two filters: `check_size_min` `lte` it, and `check_size_max` `gte` it.
- Money is USD. A stored amount that is a numeric string counts as a number, as `get_*` shows it.
- `contains` ignores case and treats `%` as plain text.
- A company with several HQ countries or regions matches any one of them.
- A date is `YYYY-MM-DD`. A date and time also accepts an ISO time. A bare date means the start of that day, or its end for `lte`.

## Checks

- A field key, operator or value that doesn't fit is refused with every problem named, before any query runs.
- An error never lists a select's options. The agent calls `list_field_options` for the exact values.
- A request holds at most 10 filters, and an `in` at most 20 values.

## Reading the values

`get_buyer` and `get_seller` return the editable fields by default. Pass `fields` with keys from `list_field_options` to read any column, such as a computed score you filtered on.
