"""Implements `AttioWriterPort`: PATCHes the engine's fields onto one Attio record.

Attio has no bulk update, so each record is one request. Requests are spaced to stay well
inside Attio's rate limit, and the webhook re-reads every record we touch, which counts too.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable, Sequence

from app.modules.attio import AttioClientProtocol, AttioError, attio_is_test
from app.modules.attio.providers.attio.options import get_option_id
from app.modules.attio.providers.attio.retry import patch_with_retry
from app.modules.attio.providers.attio.write_values import ActorReferenceValue
from app.modules.interactions.application.ports.attio_writer import (
    RecordGoneError,
    WritesNotAllowedError,
)
from app.modules.interactions.domain.attio_fields import (
    FIELDS,
    AttioObject,
    FieldKind,
    FieldValue,
)

AttioValues = dict[str, list[dict[str, str]]]
_KIND_OF = {spec.slug: spec.kind for spec in FIELDS}
_NOT_FOUND = 404


class AttioRecordWriter:
    def __init__(
        self,
        client: AttioClientProtocol,
        writes_per_second: float,
        is_test: Callable[[], bool] = attio_is_test,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._interval = 1.0 / writes_per_second
        self._is_test = is_test
        self._clock = clock
        self._sleep = sleep
        self._next_at = 0.0

    async def patch(self, obj: AttioObject, record_id: str, fields: Sequence[FieldValue]) -> None:
        if self._is_test():
            raise WritesNotAllowedError("ATTIO_IS_TEST is set; the engine writes to prod only")
        values = await self._values(obj, fields)
        wait = self._next_at - self._clock()
        if wait > 0:
            await self._sleep(wait)
        self._next_at = max(self._clock(), self._next_at) + self._interval
        try:
            await patch_with_retry(
                self._client,
                f"/objects/{obj.value}/records/{record_id}",
                {"data": {"values": values}},
            )
        except AttioError as err:
            if err.status == _NOT_FOUND:
                raise RecordGoneError(record_id) from err
            raise

    async def _values(self, obj: AttioObject, fields: Sequence[FieldValue]) -> AttioValues:
        values: AttioValues = {}
        for field in fields:
            if field.value is None:
                # Verified on live Attio: an empty list empties any of the four field kinds.
                values[field.slug] = []
                continue
            match _KIND_OF[field.slug]:
                case FieldKind.SELECT:
                    option_id = await get_option_id(
                        self._client,
                        target_kind="objects",
                        target_slug=obj.value,
                        attribute_slug=field.slug,
                        title=field.value,
                    )
                    values[field.slug] = [{"option": option_id}]
                case FieldKind.ACTOR:
                    values[field.slug] = ActorReferenceValue(
                        referenced_actor_type="workspace-member", referenced_actor_id=field.value
                    ).as_value()
                case FieldKind.TIMESTAMP | FieldKind.TEXT:
                    values[field.slug] = [{"value": field.value}]
        return values
