import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.auth import AccessClaims, AccessKeysUnavailableError, AccessSignInError
from app.modules.crm.api import dependencies, router
from app.modules.crm.api.problems import install_problem_handlers
from app.modules.crm.application.service import CrmService
from app.modules.crm.bootstrap import crm_service
from app.modules.crm.domain.roles import (
    InvalidCursorError,
    InvalidRoleFieldsError,
    WriteLandedPartlyError,
)
from app.modules.crm.tests.unit.crm_fakes import JULES, FakeReader, FakeWriter

_TOKEN = {"Cf-Access-Jwt-Assertion": "token"}


@pytest.fixture
def parts(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, FakeReader, FakeWriter]:
    reader = FakeReader()
    writer = FakeWriter(reader)
    app = FastAPI()
    app.include_router(router.router)
    install_problem_handlers(app)
    app.dependency_overrides[crm_service] = lambda: CrmService(reader, writer)

    async def verify(token: str) -> AccessClaims:
        if token != "token":
            raise AccessSignInError("bad")
        return AccessClaims(email=JULES.email, sub="s")

    monkeypatch.setattr(dependencies, "access_configured", lambda: True)
    monkeypatch.setattr(dependencies, "verify_access_jwt", verify)
    return TestClient(app), reader, writer


def test_a_request_without_a_token_is_401_problem_json(parts) -> None:
    client, _, _ = parts

    response = client.get("/api/v1/buyer-roles")

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "unauthenticated"


def test_a_bad_token_is_401(parts) -> None:
    client, _, _ = parts

    response = client.get("/api/v1/me", headers={"Cf-Access-Jwt-Assertion": "nope"})

    assert (response.status_code, response.json()["code"]) == (401, "invalid_token")


def test_an_unknown_email_is_403(parts) -> None:
    client, reader, _ = parts
    reader.members.clear()

    response = client.get("/api/v1/me", headers=_TOKEN)

    assert (response.status_code, response.json()["code"]) == (403, "unknown_user")


def test_an_unconfigured_server_is_503(parts, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _ = parts
    monkeypatch.setattr(dependencies, "access_configured", lambda: False)

    assert client.get("/api/v1/me", headers=_TOKEN).status_code == 503


def test_me_returns_the_signed_in_person(parts) -> None:
    client, _, _ = parts

    assert client.get("/api/v1/me", headers=_TOKEN).json() == {
        "id": JULES.id,
        "name": "Jules",
        "email": JULES.email,
    }


def test_the_list_uses_camel_case_and_passes_filters(parts) -> None:
    client, reader, _ = parts

    response = client.get("/api/v1/buyer-roles?sector=Dental&checkSize=1-5&q=acme", headers=_TOKEN)

    body = response.json()
    assert response.status_code == 200
    assert (body["matched"], body["total"], body["nextCursor"]) == (1, 1, None)
    assert body["rows"][0]["checkSizeMinUsd"] == 1e6
    # Attio's allowed statuses, not just the ones the rows hold.
    assert body["options"]["statuses"] == ["Active", "Dormant"]
    assert reader.seen_filters[0].text == "acme"


def test_a_bad_filter_is_a_422_problem(parts) -> None:
    client, _, _ = parts

    response = client.get("/api/v1/buyer-roles?checkSize=abc", headers=_TOKEN)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "invalid_request"


def test_a_bad_cursor_is_a_400(parts, monkeypatch: pytest.MonkeyPatch) -> None:
    client, reader, _ = parts

    async def boom(*_args: object) -> None:
        raise InvalidCursorError("x")

    monkeypatch.setattr(reader, "buyers_page", boom)

    assert (
        client.get("/api/v1/buyer-roles?cursor=zzz", headers=_TOKEN).json()["code"]
        == "invalid_cursor"
    )


def test_a_duplicate_buyer_is_409(parts) -> None:
    client, _, writer = parts
    writer.add_outcome = "existing"

    response = client.post(
        "/api/v1/buyer-roles",
        json={"name": "Acme", "website": "acme.com", "sector": "Dental"},
        headers=_TOKEN,
    )

    assert (response.status_code, response.json()["code"]) == (409, "buyer_exists")


def test_a_new_buyer_is_201_with_location_and_etag(parts) -> None:
    client, _, _ = parts

    response = client.post(
        "/api/v1/buyer-roles",
        json={"name": "Newco", "website": "newco.com", "sector": "Dental"},
        headers=_TOKEN,
    )

    assert response.status_code == 201
    assert response.headers["location"] == "/api/v1/buyer-roles/b2"
    assert response.headers["etag"] == '"v1"'
    assert response.json()["name"] == "Newco"


def test_a_patch_without_if_match_is_428(parts) -> None:
    client, _, _ = parts

    response = client.patch("/api/v1/buyer-roles/b1", json={"notes": "x"}, headers=_TOKEN)

    assert (response.status_code, response.json()["code"]) == (428, "if_match_required")


def test_a_stale_patch_is_412_and_writes_nothing(parts) -> None:
    client, _, writer = parts

    response = client.patch(
        "/api/v1/buyer-roles/b1", json={"notes": "x"}, headers={**_TOKEN, "If-Match": '"old"'}
    )

    assert (response.status_code, response.json()["code"]) == (412, "stale_version")
    assert writer.edits == []


def test_a_patch_returns_the_new_version(parts) -> None:
    client, _, writer = parts

    response = client.patch(
        "/api/v1/seller-roles/s1",
        json={"openToSelling": "Interested"},
        headers={**_TOKEN, "If-Match": '"v1"'},
    )

    assert response.status_code == 200
    assert response.headers["etag"] == '"v2"'
    assert writer.edits == [("s1", JULES.id)]


def test_an_unknown_role_is_404(parts) -> None:
    client, _, _ = parts

    assert (
        client.get("/api/v1/seller-roles/missing", headers=_TOKEN).json()["code"]
        == "role_not_found"
    )


def test_refused_fields_come_back_as_422_with_each_problem(parts) -> None:
    client, _, writer = parts
    writer.error = InvalidRoleFieldsError(("notes: too long",))

    response = client.patch(
        "/api/v1/buyer-roles/b1", json={"notes": "x"}, headers={**_TOKEN, "If-Match": '"v1"'}
    )

    assert (response.status_code, response.json()["errors"]) == (422, ["notes: too long"])


def test_a_write_that_landed_partly_is_502_and_says_what_saved(parts) -> None:
    client, _, writer = parts
    writer.error = WriteLandedPartlyError(("Attio organization",), "db down")

    response = client.patch(
        "/api/v1/buyer-roles/b1", json={"notes": "x"}, headers={**_TOKEN, "If-Match": '"v1"'}
    )

    body = response.json()
    assert (response.status_code, body["code"], body["landed"]) == (
        502,
        "partial_write",
        ["Attio organization"],
    )
    assert "Retry" in body["detail"]


def test_a_key_fetch_outage_is_a_503_not_a_401(parts, monkeypatch: pytest.MonkeyPatch) -> None:
    client, _, _ = parts

    async def down(_token: str) -> AccessClaims:
        raise AccessKeysUnavailableError("down")

    monkeypatch.setattr(dependencies, "verify_access_jwt", down)

    response = client.get("/api/v1/me", headers=_TOKEN)

    assert (response.status_code, response.json()["code"]) == (503, "access_keys_unavailable")
