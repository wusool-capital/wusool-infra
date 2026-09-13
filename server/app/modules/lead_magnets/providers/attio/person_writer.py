"""Writes a submission's contact to Attio's `person` object.

Matches `role_writer.py`'s shape (a thin class over `entries.py`'s
low-level helpers), but a different dedupe rule: `person.email` on this
workspace is a plain `text` attribute, single-valued and **not** unique
(see `entries.find_people_by_email`'s docstring) — there is no atomic
upsert, so this is query-then-create-or-patch rather than a `PUT
?matching_attribute=`.

Fill-blanks-only on a match, never overwrite: a lead magnet only ever adds
a `company`/`linkedin` a hand-curated contact never had. `name` is never
touched on a match — it's the field most likely to carry a human's
deliberate correction, and it's `is_required` on the object so it's never
genuinely blank. This is deliberately more conservative than
`role_writer.py`'s organisation writes, which do patch on every match:
an organisation's fields (sector, domains, description) are this bot's own
business data; a person's `name` is not.

Failure here is the caller's call, not this class's: see
`bootstrap.py::_RoleAttioWriter.write` for why a person-write failure is
swallowed rather than raised.
"""

import logging

from app.modules.attio import AttioClientProtocol
from app.modules.attio.providers.attio import entries
from app.modules.attio.providers.attio import values as v
from app.modules.lead_magnets.domain.shared.attio_values import display_name, person_values
from app.modules.lead_magnets.domain.shared.dedup import normalise_email

logger = logging.getLogger(__name__)

_COMPANY_FIELD = "company"
_LINKEDIN_FIELD = "linkedin"


class AttioPersonWriter:
    def __init__(self, client: AttioClientProtocol, *, is_test: bool) -> None:
        self._client = client
        self._is_test = is_test

    async def write(
        self,
        *,
        name: str | None,
        email: str | None,
        organization_attio_id: str | None,
        linkedin: str | None = None,
    ) -> tuple[str, str] | None:
        """Returns `(person_attio_id, person_name)`, or `None` if there is
        no email to write against — not an error, since not every stored
        payload predates this change (see `AttioIdentityPayload`'s
        `extra="ignore"`) and a resumed pre-change run legitimately has
        nothing here to write.
        """
        normalised_email = normalise_email(email)
        if not normalised_email:
            return None

        matches = await entries.find_people_by_email(
            self._client, normalised_email, is_test=self._is_test
        )
        if not matches:
            resolved_name = display_name(name, normalised_email)
            values = person_values(
                name=resolved_name,
                email=normalised_email,
                organization_attio_id=organization_attio_id,
                linkedin=linkedin,
            )
            person_id = await entries.create_person(self._client, values, is_test=self._is_test)
            return person_id, resolved_name

        # Oldest wins on an ambiguous match — `find_people_by_email` already
        # sorts `created_at asc`, so this is simply the first result. Never
        # log the address itself: these logs are not CRM-access-controlled.
        if len(matches) > 1:
            logger.warning(
                "lead_magnet_person_email_ambiguous matches=%d is_test=%s",
                len(matches),
                self._is_test,
            )
        matched = matches[0]
        matched_values = v.vals(matched)
        matched_name = v.first(matched_values, "name") or display_name(name, normalised_email)
        patch: dict[str, object] = {}
        if organization_attio_id and not v.ref(matched_values, _COMPANY_FIELD):
            patch[_COMPANY_FIELD] = [
                {"target_object": "organizations", "target_record_id": organization_attio_id}
            ]
        if linkedin and not v.first(matched_values, _LINKEDIN_FIELD):
            patch[_LINKEDIN_FIELD] = linkedin
        if patch:
            await entries.patch_person(self._client, v.record_id(matched), patch)
        return v.record_id(matched), str(matched_name)
