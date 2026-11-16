"""Implements `RecordCreatorPort`: creates Persons and Organizations in Attio, tagged "Email sync".

`attio` is a full-access module, so its entry helpers are used directly, as in `attio_writer.py`.
"""

from collections.abc import Callable

from app.modules.attio import AttioClientProtocol, attio_is_test
from app.modules.attio.providers.attio import entries
from app.modules.attio.providers.attio.options import get_option_id
from app.modules.attio.providers.attio.write_values import RecordReferenceValue
from app.modules.interactions.application.ports.attio_writer import WritesNotAllowedError
from app.modules.interactions.domain.auto_create import LEAD_SOURCE_DETAIL

_ORGANIZATIONS = "organizations"
_PERSON = "person"


class AttioRecordCreator:
    def __init__(
        self, client: AttioClientProtocol, is_test: Callable[[], bool] = attio_is_test
    ) -> None:
        self._client = client
        self._is_test = is_test

    async def person_exists(self, email: str) -> bool:
        # `is_test=False`: only the production half of the shared workspace counts.
        return bool(await entries.find_people_by_email(self._client, email, is_test=False))

    async def create_organization(self, name: str, domain: str) -> str:
        self._guard()
        values: dict[str, object] = {
            "name": name,
            "domains": [domain],
            "lead_source_detail": await self._lead_source(_ORGANIZATIONS),
        }
        org_id, _ = await entries.create_organization(self._client, values, is_test=False)
        return org_id

    async def create_person(self, name: str, email: str, organization_id: str | None) -> str:
        self._guard()
        values: dict[str, object] = {
            "name": name,
            "email": email,
            "lead_source_detail": await self._lead_source(_PERSON),
        }
        if organization_id:
            values["company"] = RecordReferenceValue(
                target_object=_ORGANIZATIONS, target_record_id=organization_id
            ).as_value()
        return await entries.create_person(self._client, values, is_test=False)

    def _guard(self) -> None:
        if self._is_test():
            raise WritesNotAllowedError("ATTIO_IS_TEST is set; the engine creates in prod only")

    async def _lead_source(self, object_slug: str) -> list[dict[str, str]]:
        option_id = await get_option_id(
            self._client,
            target_kind="objects",
            target_slug=object_slug,
            attribute_slug="lead_source_detail",
            title=LEAD_SOURCE_DETAIL,
        )
        return [{"option": option_id}]
