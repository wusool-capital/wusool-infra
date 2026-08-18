from wusool_db.models import Organization


async def test_retrieve_organization(any_organization: Organization) -> None:
    assert any_organization.attio_id
    assert any_organization.name
