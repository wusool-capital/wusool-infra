import pytest

from app.modules.attio.providers.attio import options
from app.modules.interactions.application.ports.attio_writer import WritesNotAllowedError
from app.modules.interactions.providers.attio_creator import AttioRecordCreator


class _Client:
    def __init__(self, existing_people: int = 0) -> None:
        self.existing_people = existing_people
        self.posts: list[tuple[str, dict]] = []

    async def get(self, path: str) -> dict:
        return {
            "data": [
                {"id": {"option_id": "opt-sync"}, "title": "Email sync", "is_archived": False},
                {"id": {"option_id": "opt-form"}, "title": "Buyer Form", "is_archived": False},
            ]
        }

    async def post(self, path: str, json_body: dict) -> dict:
        self.posts.append((path, json_body))
        if path.endswith("/records/query"):
            return {"data": [{"id": {"record_id": f"p{i}"}} for i in range(self.existing_people)]}
        return {"data": {"id": {"record_id": "new-1"}, "web_url": "https://app.attio.com/x"}}

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used")

    async def delete(self, path: str) -> None:
        raise AssertionError("not used")

    async def put(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used")


@pytest.fixture(autouse=True)
def _fresh_option_cache() -> None:
    options._cache.clear()


def _creator(client: _Client, *, is_test: bool = False) -> AttioRecordCreator:
    return AttioRecordCreator(client, lambda: is_test)


async def test_an_organization_is_created_with_its_domain_and_the_email_sync_tag() -> None:
    client = _Client()

    org_id = await _creator(client).create_organization("Acme", "acme.com")

    assert org_id == "new-1"
    ((path, body),) = client.posts
    assert path == "/objects/organizations/records"
    values = body["data"]["values"]
    assert values["name"] == "Acme"
    assert values["domains"] == ["acme.com"]
    assert values["lead_source_detail"] == [{"option": "opt-sync"}]
    assert values["is_test"] is False


async def test_a_person_is_created_linked_to_its_organization_and_tagged() -> None:
    client = _Client()

    person_id = await _creator(client).create_person("Sara Lee", "sara@acme.com", "org-9")

    assert person_id == "new-1"
    ((path, body),) = client.posts
    assert path == "/objects/person/records"
    values = body["data"]["values"]
    assert (values["name"], values["email"]) == ("Sara Lee", "sara@acme.com")
    assert values["lead_source_detail"] == [{"option": "opt-sync"}]
    assert "org-9" in str(values["company"])


async def test_a_person_without_an_organization_has_no_company_value() -> None:
    client = _Client()

    await _creator(client).create_person("Sara Lee", "sara@acme.com", None)

    assert "company" not in client.posts[0][1]["data"]["values"]


@pytest.mark.parametrize(("existing", "expected"), [(0, False), (1, True)])
async def test_person_exists_asks_attio_by_email(existing: int, expected: bool) -> None:
    client = _Client(existing_people=existing)

    assert await _creator(client).person_exists("sara@acme.com") is expected
    assert client.posts[0][0] == "/objects/person/records/query"


async def test_nothing_is_created_while_the_instance_is_flagged_as_test() -> None:
    client = _Client()

    with pytest.raises(WritesNotAllowedError):
        await _creator(client, is_test=True).create_organization("Acme", "acme.com")
    with pytest.raises(WritesNotAllowedError):
        await _creator(client, is_test=True).create_person("Sara", "sara@acme.com", None)

    assert client.posts == []
