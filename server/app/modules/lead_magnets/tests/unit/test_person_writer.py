"""`AttioPersonWriter.write`'s dedupe/fill-blanks rule.

Fakes only at the network seam (`AttioClientProtocol`) — `entries.py`'s
real `find_people_by_email`/`create_person`/`patch_person` run for real
against it, same "fakes only at network seams" convention as
`test_write_contract_e2e.py`.
"""

import pytest

from app.modules.lead_magnets.providers.attio.person_writer import AttioPersonWriter


def _person(
    record_id: str,
    *,
    name: str | None = None,
    email: str | None = None,
    company: str | None = None,
    linkedin: str | None = None,
    is_test: bool = False,
) -> dict:
    values: dict = {"is_test": [{"active_until": None, "value": is_test}]}
    if name is not None:
        values["name"] = [{"active_until": None, "value": name}]
    if email is not None:
        values["email"] = [{"active_until": None, "value": email}]
    if company is not None:
        values["company"] = [{"active_until": None, "target_record_id": company}]
    if linkedin is not None:
        values["linkedin"] = [{"active_until": None, "value": linkedin}]
    return {"id": {"record_id": record_id}, "values": values}


class _FakeClient:
    def __init__(
        self, *, matches: list[dict] | None = None, created_id: str = "person-new"
    ) -> None:
        self._matches = matches or []
        self._created_id = created_id
        self.create_calls: list[dict] = []
        self.patch_calls: list[tuple[str, dict]] = []
        self.queried = False

    async def post(self, path: str, json_body: dict) -> dict:
        if path == "/objects/person/records/query":
            self.queried = True
            return {"data": self._matches}
        if path == "/objects/person/records":
            self.create_calls.append(json_body["data"]["values"])
            return {"data": {"id": {"record_id": self._created_id}}}
        raise AssertionError(f"unexpected post {path}")

    async def patch(self, path: str, json_body: dict) -> dict:
        self.patch_calls.append((path, json_body["data"]["values"]))
        return {}

    async def get(self, path: str) -> dict:
        raise AssertionError("not used by this test")


async def test_no_email_skips_the_write_entirely() -> None:
    client = _FakeClient()
    writer = AttioPersonWriter(client, is_test=False)

    result = await writer.write(name="Dana", email=None, organization_attio_id="org-1")

    assert result is None
    assert client.queried is False
    assert client.create_calls == []


async def test_no_match_creates_a_new_person() -> None:
    client = _FakeClient(matches=[])
    writer = AttioPersonWriter(client, is_test=False)

    result = await writer.write(name="Dana", email="Dana@Acme.com", organization_attio_id="org-1")

    assert result == ("person-new", "Dana")
    assert client.create_calls == [
        {
            "name": "Dana",
            "email": "dana@acme.com",
            "company": [{"target_object": "organizations", "target_record_id": "org-1"}],
            "is_test": False,
        }
    ]
    assert client.patch_calls == []


async def test_no_name_falls_back_to_the_email_on_create() -> None:
    client = _FakeClient(matches=[])
    writer = AttioPersonWriter(client, is_test=False)

    result = await writer.write(name=None, email="dana@acme.com", organization_attio_id=None)

    assert result == ("person-new", "dana@acme.com")
    assert "company" not in client.create_calls[0]


async def test_linkedin_only_sent_when_given() -> None:
    client = _FakeClient(matches=[])
    writer = AttioPersonWriter(client, is_test=False)

    await writer.write(
        name="Robin",
        email="robin@acme.com",
        organization_attio_id=None,
        linkedin="https://linkedin.com/in/robin",
    )

    assert client.create_calls[0]["linkedin"] == "https://linkedin.com/in/robin"


async def test_match_with_blank_fields_gets_them_patched() -> None:
    client = _FakeClient(matches=[_person("person-1", name="Sam")])
    writer = AttioPersonWriter(client, is_test=False)

    result = await writer.write(
        name="Someone Else",
        email="sam@acme.com",
        organization_attio_id="org-1",
        linkedin="https://linkedin.com/in/sam",
    )

    # The matched record's own name wins — never patched, never relabeled.
    assert result == ("person-1", "Sam")
    path, values = client.patch_calls[0]
    assert path == "/objects/person/records/person-1"
    assert values == {
        "company": [{"target_object": "organizations", "target_record_id": "org-1"}],
        "linkedin": "https://linkedin.com/in/sam",
    }


async def test_match_with_everything_already_filled_writes_nothing() -> None:
    client = _FakeClient(
        matches=[_person("person-1", name="Sam", company="org-existing", linkedin="https://x")]
    )
    writer = AttioPersonWriter(client, is_test=False)

    result = await writer.write(
        name="Someone Else",
        email="sam@acme.com",
        organization_attio_id="org-1",
        linkedin="https://linkedin.com/in/sam",
    )

    assert result == ("person-1", "Sam")
    assert client.patch_calls == []


async def test_ambiguous_match_takes_the_oldest_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    """`find_people_by_email` already sorts oldest-first; this just confirms
    the writer takes the first result rather than the last, and never logs
    the address itself."""
    client = _FakeClient(
        matches=[_person("person-old", name="Old"), _person("person-new-dup", name="New")]
    )
    writer = AttioPersonWriter(client, is_test=False)

    with caplog.at_level("WARNING"):
        result = await writer.write(name="X", email="dup@acme.com", organization_attio_id=None)

    assert result == ("person-old", "Old")
    assert any("lead_magnet_person_email_ambiguous" in r.message for r in caplog.records)
    assert not any("dup@acme.com" in r.message for r in caplog.records)
