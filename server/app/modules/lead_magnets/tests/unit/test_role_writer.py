"""`AttioRoleWriter`'s vertical-aware writes: one `buyer_role` per vertical,
found again by vertical on a resubmission, and the seller's `sector` on its
own role rather than only on the organisation.
"""

from app.modules.lead_magnets.providers.attio.role_writer import AttioRoleWriter


class _FakeAttioClient:
    """Keeps list entries in Attio's read shape so `resolve_role_entry_id`
    finds what an earlier write created."""

    def __init__(self) -> None:
        self.entries: dict[str, list[dict]] = {"buyer_role": [], "seller_role": []}
        self.org_values: list[dict] = []
        self.patched: list[tuple[str, dict]] = []
        self.put_paths: list[str] = []
        self.queries = 0

    async def post(self, path: str, json_body: dict) -> dict:
        if path == "/objects/organizations/records":
            self.org_values.append(json_body["data"]["values"])
            return {"data": {"id": {"record_id": "org-1"}}}
        list_slug = path.split("/")[2]
        if path.endswith("/entries/query"):
            self.queries += 1
            return {"data": self.entries[list_slug]}
        entry_id = f"{list_slug}-{len(self.entries[list_slug]) + 1}"
        values = json_body["data"]["entry_values"]
        entry_values: dict = {
            "is_active": [{"active_until": None, "value": True}],
            "is_test": [{"active_until": None, "value": True}],
        }
        if "target_vertical" in values:
            entry_values["target_vertical"] = [
                {"active_until": None, "option": {"title": values["target_vertical"]}}
            ]
        self.entries[list_slug].append(
            {
                "id": {"entry_id": entry_id},
                "parent_record_id": {"record_id": json_body["data"]["parent_record_id"]},
                "entry_values": entry_values,
                "sent": values,
            }
        )
        return {"data": {"id": {"entry_id": entry_id}}}

    async def get(self, path: str) -> dict:
        return {"data": {"values": {"is_test": [{"active_until": None, "value": True}]}}}

    async def patch(self, path: str, json_body: dict) -> dict:
        self.patched.append((path, json_body))
        return {}

    async def put(self, path: str, json_body: dict) -> dict:
        self.put_paths.append(path)
        return {}


async def _write_buyer(writer: AttioRoleWriter, verticals: list[str], org_id: str | None = None):
    return await writer.write_buyer_role(
        organization_name="Gulf Capital",
        domain="gulfcap.ae",
        org_type=[],
        target_verticals=verticals,
        entry_values={"check_size_min": 1},
        organization_attio_id=org_id,
    )


async def test_one_buyer_role_per_vertical_and_no_org_sector_focus() -> None:
    client = _FakeAttioClient()

    subjects = await _write_buyer(
        AttioRoleWriter(client, is_test=True), ["Fintech", "Mobility", "Fintech"]
    )

    sent = [e["sent"] for e in client.entries["buyer_role"]]
    assert [s["target_vertical"] for s in sent] == ["Fintech", "Mobility"]
    assert all(s["check_size_min"] == 1 for s in sent)
    assert "sector_focus" not in client.org_values[0]
    assert subjects.buyer_role_entry_ids == ("buyer_role-1", "buyer_role-2")
    assert subjects.buyer_role_entry_id == "buyer_role-1"
    assert client.queries == 1, "one list scan for every vertical, not one each"


async def test_resubmission_patches_its_vertical_and_adds_the_new_one() -> None:
    client = _FakeAttioClient()
    writer = AttioRoleWriter(client, is_test=True)
    await _write_buyer(writer, ["Fintech", "Mobility"])

    subjects = await _write_buyer(writer, ["Mobility", "Garage"], org_id="org-1")

    # PUT, so a resubmission replaces multiselects (geography) rather than appending.
    assert client.put_paths == ["/lists/buyer_role/entries/buyer_role-2"]
    assert not [p for p, _ in client.patched if "/lists/" in p]
    assert len(client.entries["buyer_role"]) == 3
    assert subjects.buyer_role_entry_ids == ("buyer_role-2", "buyer_role-3")


async def test_no_verticals_writes_one_unclassified_role() -> None:
    client = _FakeAttioClient()

    subjects = await _write_buyer(AttioRoleWriter(client, is_test=True), [])

    assert len(client.entries["buyer_role"]) == 1
    assert "target_vertical" not in client.entries["buyer_role"][0]["sent"]
    assert subjects.buyer_role_entry_ids == ("buyer_role-1",)


async def test_seller_role_carries_the_mapped_sector() -> None:
    client = _FakeAttioClient()

    await AttioRoleWriter(client, is_test=True).write_seller_role(
        organization_name="Clinic Co",
        domain=None,
        entry_values={"readiness_score": 70},
        sector="Healthcare Services / Clinics",
    )

    sent = client.entries["seller_role"][0]["sent"]
    assert sent["sector"] == ["Healthcare Services / Clinics"]
    assert sent["readiness_score"] == 70
    assert client.org_values[0]["sector_focus"] == ["Healthcare Services / Clinics"]


async def test_seller_resubmission_replaces_the_sector() -> None:
    client = _FakeAttioClient()
    writer = AttioRoleWriter(client, is_test=True)
    await writer.write_seller_role(
        organization_name="Clinic Co", domain=None, entry_values={}, sector="Fintech"
    )

    await writer.write_seller_role(
        organization_name="Clinic Co",
        domain=None,
        entry_values={},
        sector="Healthcare Services / Clinics",
        organization_attio_id="org-1",
    )

    assert client.put_paths == ["/lists/seller_role/entries/seller_role-1"]
