"""Uploads one image to the dataset's asset store, shared by the report and article sources."""

import httpx
from pydantic import BaseModel, ConfigDict

# AVIF and other formats the image pipeline may not accept go up as plain files.
_IMAGE_PIPELINE_MIMES = frozenset(
    {"image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"}
)


class _UploadedAsset(BaseModel):
    model_config = ConfigDict(extra="ignore")

    url: str


class _UploadResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document: _UploadedAsset


async def upload_image(
    *,
    assets_url: str,
    dataset: str,
    write_token: str,
    data: bytes,
    mime: str,
    timeout_s: float,
) -> str:
    """The CDN URL; identical bytes give the same one. Raises on any failure."""
    kind = "images" if mime in _IMAGE_PIPELINE_MIMES else "files"
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.post(
            f"{assets_url}/{kind}/{dataset}",
            content=data,
            headers={"Authorization": f"Bearer {write_token}", "content-type": mime},
        )
    response.raise_for_status()
    return _UploadResponse.model_validate_json(response.content).document.url
