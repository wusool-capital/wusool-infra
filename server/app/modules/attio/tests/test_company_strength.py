"""The calibration's Attio reads, against a fake client that returns Attio-shaped replies."""

from app.modules.attio.providers.attio import company_strength
from app.modules.attio.providers.attio.company_strength import (
    CompanyStrength,
    list_company_strengths,
    list_workspace_members,
)


class _FakeClient:
    def __init__(self, pages: list[dict], members: dict | None = None) -> None:
        self._pages = pages
        self._members = members or {"data": []}
        self.bodies: list[dict] = []

    async def post(self, path: str, json_body: dict) -> dict:
        assert path == "/objects/companies/records/query"
        self.bodies.append(json_body)
        return self._pages.pop(0)

    async def get(self, path: str) -> dict:
        assert path == "/workspace_members"
        return self._members

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("read-only")

    async def delete(self, path: str) -> None:
        raise AssertionError("read-only")

    async def put(self, path: str, json_body: dict) -> dict:
        raise AssertionError("read-only")


def _company(record: str, domain: str, strength: str | None, user: str | None) -> dict:
    values: dict[str, list[dict]] = {"domains": [{"domain": domain, "active_until": None}]}
    if strength:
        values["strongest_connection_strength"] = [
            {"option": {"title": strength}, "active_until": None}
        ]
    if user:
        values["strongest_connection_user"] = [{"referenced_actor_id": user, "active_until": None}]
    return {"id": {"record_id": record}, "values": values}


async def test_companies_are_parsed_and_paging_stops_on_a_short_page(monkeypatch) -> None:
    monkeypatch.setattr(company_strength, "_PAGE_SIZE", 2)
    client = _FakeClient(
        [
            {
                "data": [
                    _company("c1", "acme.com", "Strong", "u1"),
                    _company("c2", "beta.io", None, None),
                ]
            },
            {"data": [_company("c3", "gamma.co", "Very weak", "u2")]},
        ]
    )

    companies = await list_company_strengths(client)

    assert [b["offset"] for b in client.bodies] == [0, 2]
    assert companies == [
        CompanyStrength(
            record_id="c1", domains=("acme.com",), strength="Strong", strongest_user_id="u1"
        ),
        CompanyStrength(
            record_id="c2", domains=("beta.io",), strength=None, strongest_user_id=None
        ),
        CompanyStrength(
            record_id="c3", domains=("gamma.co",), strength="Very weak", strongest_user_id="u2"
        ),
    ]


async def test_workspace_members_map_an_id_to_an_email() -> None:
    client = _FakeClient(
        [],
        {
            "data": [
                {
                    "id": {"workspace_id": "w", "workspace_member_id": "m1"},
                    "email_address": "tech@wusoolcapital.com",
                }
            ]
        },
    )

    (member,) = await list_workspace_members(client)

    assert (member.member_id, member.email) == ("m1", "tech@wusoolcapital.com")
