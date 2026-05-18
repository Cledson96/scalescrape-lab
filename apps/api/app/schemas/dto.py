from datetime import datetime
from math import ceil
import os
from pydantic import BaseModel, Field, computed_field


def public_url_for(url: str):  # noqa: ANN201
    public_base = os.getenv("PUBLIC_TARGET_SITE_URL", "http://localhost:4000").rstrip("/")
    internal_base = "http://target-site:4000"
    if url.startswith(internal_base):
        return f"{public_base}{url.removeprefix(internal_base)}"
    return url


def public_api_url_for(path: str) -> str:
    public_base = os.getenv("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    return f"{public_base}/{path.lstrip('/')}"


def public_media_url(raw_data: dict) -> str | None:
    public_path = raw_data.get("image_public_path")
    if isinstance(public_path, str) and public_path:
        return public_api_url_for(public_path)

    image_path = raw_data.get("image_path")
    if not isinstance(image_path, str) or not image_path:
        return None

    media_root = os.getenv("MEDIA_ROOT", "/app/media").rstrip("/\\")
    normalized_image = image_path.replace("\\", "/")
    normalized_root = media_root.replace("\\", "/").rstrip("/")
    if normalized_image.startswith(normalized_root):
        relative_path = normalized_image.removeprefix(normalized_root).lstrip("/")
        return public_api_url_for(f"/media/{relative_path}")
    return None


class JobCreate(BaseModel):
    source: str = Field(default="fake-target")
    start_url: str
    mode: str = Field(default="browser")
    max_pages: int = Field(default=10, ge=1, le=100)


class JobRead(BaseModel):
    id: int
    source_id: int
    start_url: str
    status: str
    mode: str
    max_pages: int
    attempts: int
    items_found: int
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def public_url(self) -> str:
        return public_url_for(self.start_url)


class ScrapedItemRead(BaseModel):
    id: int
    job_id: int
    external_id: str
    title: str
    detail_url: str
    raw_data: dict
    created_at: datetime
    extracted_at: datetime

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def public_detail_url(self) -> str:
        return public_url_for(self.detail_url)

    @computed_field
    @property
    def public_image_url(self) -> str | None:
        return public_media_url(self.raw_data)


class ScrapedItemPageRead(BaseModel):
    items: list[ScrapedItemRead]
    total: int
    page: int
    page_size: int

    @computed_field
    @property
    def total_pages(self) -> int:
        if self.total == 0:
            return 0
        return ceil(self.total / self.page_size)


class SourceRead(BaseModel):
    id: int
    name: str
    base_url: str
    status: str
    circuit_open_until: datetime | None

    model_config = {"from_attributes": True}


class ProxyRead(BaseModel):
    id: int
    name: str
    status: str
    current_active_jobs: int
    max_concurrent_jobs: int
    cooldown_until: datetime | None

    model_config = {"from_attributes": True}

