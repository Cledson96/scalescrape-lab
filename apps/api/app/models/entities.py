from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.clock import utc_now_naive
from app.database import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    base_url: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(40), default="active")
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    jobs: Mapped[list["Job"]] = relationship(back_populates="source")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    start_url: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(60), default="pending", index=True)
    mode: Mapped[str] = mapped_column(String(40), default="browser")
    max_pages: Mapped[int] = mapped_column(Integer, default=10)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    items_found: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)

    source: Mapped[Source] = relationship(back_populates="jobs")
    events: Mapped[list["JobEvent"]] = relationship(back_populates="job")
    items: Mapped[list["ScrapedItem"]] = relationship(back_populates="job")


class ScrapedItem(Base):
    __tablename__ = "scraped_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    external_id: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(500))
    detail_url: Mapped[str] = mapped_column(String(1000))
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    job: Mapped[Job] = relationship(back_populates="items")

    @property
    def extracted_at(self) -> datetime:
        return self.created_at


class JobEvent(Base):
    __tablename__ = "job_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

    job: Mapped[Job] = relationship(back_populates="events")


class CaptchaChallenge(Base):
    __tablename__ = "captcha_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    source_host: Mapped[str] = mapped_column(String(250))
    provider: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(60))
    solve_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AntibotEvent(Base):
    __tablename__ = "antibot_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    session_id: Mapped[str] = mapped_column(String(120), index=True)
    proxy_id: Mapped[str] = mapped_column(String(120), index=True)
    risk_score: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(80))
    reason: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)


class ProxyProfile(Base):
    __tablename__ = "proxy_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    endpoint: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(60), default="active")
    max_concurrent_jobs: Mapped[int] = mapped_column(Integer, default=3)
    current_active_jobs: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    blocked_count: Mapped[int] = mapped_column(Integer, default=0)
    rate_limited_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)


class ProxyEvent(Base):
    __tablename__ = "proxy_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    proxy_profile_id: Mapped[int] = mapped_column(ForeignKey("proxy_profiles.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now_naive)

