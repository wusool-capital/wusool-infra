"""Every editable `FieldSpec` must match the live Attio attribute it writes to.

`test_field_specs_match_schema.py` checks the *Postgres* side; nothing checked
the *Attio* side, and the two drift independently. A field typed `"text"` here
that is really a `select` in Attio fails with a 400 the moment an operator
fills that box in — a bare string is not a valid select value — and a
hardcoded option title Attio no longer has raises `OptionNotFoundError` on
write. Both are invisible to the rest of the suite, which mocks
`build_attio_values` outright. Four such mismatches were live in DEV when this
was first run (2026-08-30): `lead_source`, `employee_range`,
`relationship_warmth` and `funding_stage` were all really `select`.

Read-only — every call here is a GET, nothing is ever written to Attio.

Skips cleanly (like `db_session` does for an unreachable Postgres) unless a
real `ATTIO_API_KEY` is present in this directory's `.env`, so the default
suite stays offline. To run it, put the DEV key in `.env` and:

    uv run pytest tests/integration/test_attio_schema_matches_field_specs.py -v

The key is read from `.env` directly rather than via `get_settings()`:
`conftest.py` sets a dummy `ATTIO_API_KEY` env var for the offline suite, and
environment variables outrank the dotenv file in pydantic-settings.
"""

import pytest
from dotenv import dotenv_values

from app.modules.attio.providers.attio.client import AttioClient, AttioError
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS

_CONFTEST_DUMMY_KEY = "test-attio-key"

# `target_kind` is Attio's own namespace for the attribute endpoints:
# "objects" for organizations, "lists" for the two role tables.
_TARGETS = [
    pytest.param("objects", "organizations", ORGANIZATION_FIELDS, id="organizations"),
    pytest.param("lists", "buyer_role", BUYER_ROLE_FIELDS, id="buyer_role"),
    pytest.param("lists", "seller_role", SELLER_ROLE_FIELDS, id="seller_role"),
]

# What each `FieldSpec.kind` requires Attio's attribute `type` to be.
# `multi_select_text` is a `select` too — it differs only by `is_multiselect`.
_EXPECTED_ATTIO_TYPE = {
    "text": "text",
    "multiline": "text",
    "select": "select",
    "multi_select_text": "select",
    "currency": "currency",
    "date": "date",
    "bool": "checkbox",
    "number": "number",
    "percent": "number",
}


def _attio_key() -> str | None:
    raw = (dotenv_values(".env") or {}).get("ATTIO_API_KEY")
    key = (raw or "").strip()
    return key if key and key != _CONFTEST_DUMMY_KEY else None


@pytest.fixture(scope="session")
async def attio_client():
    key = _attio_key()
    if key is None:
        pytest.skip("no real ATTIO_API_KEY in .env — live Attio schema check skipped")
    async with AttioClient(key) as client:
        try:
            await client.get("/objects/organizations/attributes?limit=1")
        except AttioError as exc:
            pytest.skip(f"Attio unreachable or key rejected: {exc}")
        yield client


async def _attributes(client: AttioClient, target_kind: str, target_slug: str) -> dict[str, dict]:
    """Every attribute on one object/list, keyed by `api_slug`. Paged — Attio
    caps a page at 100 and both role lists are near that.
    """
    out: dict[str, dict] = {}
    offset = 0
    while True:
        path = f"/{target_kind}/{target_slug}/attributes?limit=100&offset={offset}"
        page = (await client.get(path)).get("data", [])
        out.update({a["api_slug"]: a for a in page})
        if len(page) < 100:
            return out
        offset += 100


@pytest.mark.parametrize(("target_kind", "target_slug", "fields"), _TARGETS)
async def test_every_field_matches_its_attio_attribute(
    attio_client, target_kind, target_slug, fields
) -> None:
    """Slug exists, is writable, and its type/multiselect/currency config is
    what the `FieldSpec` kind assumes.
    """
    attributes = await _attributes(attio_client, target_kind, target_slug)

    problems = []
    for spec in fields:
        attribute = attributes.get(spec.name)
        if attribute is None:
            problems.append(f"{spec.name}: no such attribute in Attio")
            continue

        actual = attribute["type"]
        expected = _EXPECTED_ATTIO_TYPE[spec.kind]
        if actual != expected:
            problems.append(
                f"{spec.name}: kind {spec.kind!r} wants {expected!r}, Attio has {actual!r}"
            )
        if not attribute.get("is_writable", True):
            problems.append(f"{spec.name}: not writable in Attio")

        is_multiselect = attribute.get("is_multiselect", False)
        if spec.kind == "multi_select_text" and not is_multiselect:
            problems.append(f"{spec.name}: we send multiple values, Attio accepts one")
        if spec.kind == "select" and is_multiselect:
            problems.append(f"{spec.name}: we send one value, Attio is multi-select")

        if actual == "currency":
            code = (attribute.get("config") or {}).get("currency", {}).get("default_currency_code")
            if code != "USD":
                problems.append(f"{spec.name}: currency is {code!r}, everything here assumes USD")

    assert not problems, f"{target_slug} vs live Attio:\n  " + "\n  ".join(problems)


@pytest.mark.parametrize(("target_kind", "target_slug", "fields"), _TARGETS)
async def test_every_select_option_matches_attio(
    attio_client, target_kind, target_slug, fields
) -> None:
    """Hardcoded option titles must match Attio's live, non-archived set
    exactly, in both directions: one we have that Attio doesn't raises
    `OptionNotFoundError` on write, and one Attio has that we don't is a
    value no operator can pick (`last_attempt_channel` was missing Attio's
    "WhatsApp" this way).

    Fields with no hardcoded options resolve live against Attio at write time
    (`sector_focus`, `target_geography`) and so cannot drift — nothing to check.
    """
    problems = []
    for spec in fields:
        if spec.kind not in ("select", "multi_select_text") or not spec.options:
            continue
        path = f"/{target_kind}/{target_slug}/attributes/{spec.name}/options"
        response = await attio_client.get(path)
        live = {o["title"] for o in response.get("data", []) if not o.get("is_archived")}

        if stale := sorted(set(spec.options) - live):
            problems.append(f"{spec.name}: we offer options Attio doesn't have: {stale}")
        if unexposed := sorted(live - set(spec.options)):
            problems.append(f"{spec.name}: Attio has options we don't offer: {unexposed}")

    assert not problems, f"{target_slug} select options vs live Attio:\n  " + "\n  ".join(problems)
