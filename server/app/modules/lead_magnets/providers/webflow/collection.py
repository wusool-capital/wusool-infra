"""Webflow CMS plumbing shared by the Reports and Insights providers: one
collection's items, read and written through the v2 API.

Items reach the live site without a Designer publish. An update is written to
the staged item and then published, because the `/live` update 409s ("Item
not published") on an item an earlier sync unpublished.
"""

import httpx
from pydantic import BaseModel, ConfigDict, Field, SerializeAsAny

_API = "https://api.webflow.com/v2"
_PAGE = 100


class _Option(BaseModel):
    id: str
    name: str


class _Validations(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    options: list[_Option] = []
    collection_id: str | None = Field(default=None, alias="collectionId")


class _CollectionField(BaseModel):
    slug: str
    validations: _Validations | None = None


class _Collection(BaseModel):
    fields: list[_CollectionField]


class ItemFields(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    name: str | None = None
    slug: str | None = None
    featured: bool | None = None
    published_date: str | None = Field(default=None, alias="published-date")
    sanity_managed: bool | None = Field(default=None, alias="sanity-managed")


class Item(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    field_data: ItemFields = Field(alias="fieldData")


class _Pagination(BaseModel):
    total: int


class _ItemList(BaseModel):
    items: list[Item]
    pagination: _Pagination


class Image(BaseModel):
    url: str
    alt: str


class _Publish(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    item_ids: list[str] = Field(alias="itemIds")


class _Published(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    published_item_ids: list[str] = Field(default=[], alias="publishedItemIds")


class _Created(BaseModel):
    id: str


class _ItemWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Omitted on live patches: they must not change an item's draft state.
    is_draft: bool | None = Field(default=None, alias="isDraft")
    # Any provider's field model; serialized as its own subclass, not as a bare BaseModel.
    field_data: SerializeAsAny[BaseModel] = Field(alias="fieldData")


class WebflowCollection:
    def __init__(self, *, token: str, collection_id: str, timeout_s: float) -> None:
        self._headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
        self._id = collection_id
        self._timeout_s = timeout_s
        self._fields: list[_CollectionField] | None = None

    async def find(self, slug: str) -> Item | None:
        # Staged items, so an unpublished one is reused rather than clashing on slug.
        page = await self._list(f"/collections/{self._id}/items", slug=slug)
        # Checked here, not trusted: a loose filter must never hand back another item to overwrite.
        return next((i for i in page.items if i.field_data.slug == slug), None)

    async def create_live(self, field_data: BaseModel) -> str:
        body = _ItemWrite(is_draft=False, field_data=field_data)
        response = await self._request("POST", f"/collections/{self._id}/items/live", body=body)
        return _Created.model_validate_json(response.content).id

    async def update_and_publish(self, item_id: str, field_data: BaseModel) -> None:
        body = _ItemWrite(is_draft=False, field_data=field_data)
        await self._request("PATCH", f"/collections/{self._id}/items/{item_id}", body=body)
        response = await self._request(
            "POST", f"/collections/{self._id}/items/publish", body=_Publish(item_ids=[item_id])
        )
        # Per-item failures come back in a 202, not as an HTTP error.
        if item_id not in _Published.model_validate_json(response.content).published_item_ids:
            raise RuntimeError(f"Webflow did not publish item {item_id}")

    async def patch_live(self, item_id: str, field_data: BaseModel) -> None:
        await self._request(
            "PATCH",
            f"/collections/{self._id}/items/{item_id}/live",
            body=_ItemWrite(field_data=field_data),
        )

    async def unpublish(self, item_id: str) -> None:
        try:
            await self._request("DELETE", f"/collections/{self._id}/items/{item_id}/live")
        except httpx.HTTPStatusError as error:
            # Already off the live site, e.g. an earlier sync unpublished it.
            if error.response.status_code != 404:
                raise

    async def live_items(self) -> list[Item]:
        items: list[Item] = []
        offset = 0
        while True:
            page = await self._list(f"/collections/{self._id}/items/live", offset=offset)
            items += page.items
            offset += _PAGE
            if offset >= page.pagination.total:
                return items

    async def options(self, field_slug: str) -> dict[str, str]:
        """An Option field's ids by name, so renaming in Webflow never needs a code change."""
        validations = await self._validations(field_slug)
        return {o.name: o.id for o in validations.options}

    async def referenced_ids(self, field_slug: str) -> dict[str, str]:
        """A Reference field's target item ids by name."""
        target = (await self._validations(field_slug)).collection_id
        if target is None:
            return {}
        items = (await self._list(f"/collections/{target}/items")).items
        return {i.field_data.name: i.id for i in items if i.field_data.name}

    async def _validations(self, field_slug: str) -> _Validations:
        if self._fields is None:
            response = await self._request("GET", f"/collections/{self._id}")
            self._fields = _Collection.model_validate_json(response.content).fields
        field = next((f for f in self._fields if f.slug == field_slug), None)
        if field is None:
            raise ValueError(f"Webflow collection {self._id} has no field {field_slug!r}")
        return field.validations or _Validations()

    async def _list(self, path: str, *, offset: int = 0, slug: str | None = None) -> _ItemList:
        params: dict[str, str | int] = {"limit": _PAGE, "offset": offset}
        if slug is not None:
            params["slug"] = slug
        response = await self._request("GET", path, params=params)
        return _ItemList.model_validate_json(response.content)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        body: _ItemWrite | _Publish | None = None,
    ) -> httpx.Response:
        content = body.model_dump_json(by_alias=True, exclude_none=True) if body else None
        headers = {**self._headers, "content-type": "application/json"} if body else self._headers
        async with httpx.AsyncClient(timeout=self._timeout_s, headers=headers) as client:
            response = await client.request(method, _API + path, params=params, content=content)
        response.raise_for_status()
        return response
