"""Which `people` fields the "create a key contact" step (`/edit-buyer`
only, so far) may set. `name` is required and handled the same way
`seller_add_form.py`/`buyer_add_form.py` handle an org's `name` — a
dedicated required block, not part of this tuple.

Deliberately excluded: `email`. Postgres's `people.email` is a plain
`text[]`, but Attio's own attribute isn't a select/multiselect (which is
what `multi_select_text` writes) — it's Attio's native `email_addresses`
type, read as `[{"email_address": "..."}, ...]`
(`attio_sync/upsert.py:248-251`). No write-shape precedent for that type
exists anywhere in this repo, only the read shape, and every other
Attio-specific shape here (`select`'s wrapped option array, `key_contact`'s
record-reference) was confirmed against real precedent before shipping —
guessing this one risks a `create_person` call that silently mis-writes or
gets rejected. Add it once a real write payload is confirmed; not needed
for a first cut (`name`/`job_title`/`phone` are enough to reach a contact).

Deliberately a small subset of `people`'s ~20 columns otherwise, matching
the same restraint `ORGANIZATION_FIELDS`/`BUYER_ROLE_FIELDS` already show —
just enough to identify and reach a new contact. Nothing here is gated or
gates anything else.
"""

from ddl_commands.shared.organization_field_spec import FieldSpec

PERSON_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("job_title", "Job title", "text"),
    FieldSpec("phone", "Phone", "text"),
)

PERSON_FIELDS_BY_NAME = {f.name: f for f in PERSON_FIELDS}
