from datetime import datetime
from pydantic import BaseModel, Field


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

