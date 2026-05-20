from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260519_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()

    sources = sa.Table(
        "sources",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("circuit_open_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    jobs = sa.Table(
        "jobs",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("start_url", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("mode", sa.String(length=40), nullable=False),
        sa.Column("max_pages", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("items_found", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    scraped_items = sa.Table(
        "scraped_items",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("detail_url", sa.String(length=1000), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    job_events = sa.Table(
        "job_events",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    captcha_challenges = sa.Table(
        "captcha_challenges",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("source_host", sa.String(length=250), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("solve_time_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("solved_at", sa.DateTime(), nullable=True),
    )
    antibot_events = sa.Table(
        "antibot_events",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("session_id", sa.String(length=120), nullable=False),
        sa.Column("proxy_id", sa.String(length=120), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    proxy_profiles = sa.Table(
        "proxy_profiles",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("max_concurrent_jobs", sa.Integer(), nullable=False),
        sa.Column("current_active_jobs", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("blocked_count", sa.Integer(), nullable=False),
        sa.Column("rate_limited_count", sa.Integer(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("cooldown_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name", name="uq_proxy_profiles_name"),
    )
    proxy_events = sa.Table(
        "proxy_events",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proxy_profile_id", sa.Integer(), sa.ForeignKey("proxy_profiles.id"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    for table in (
        sources,
        jobs,
        scraped_items,
        job_events,
        captcha_challenges,
        antibot_events,
        proxy_profiles,
        proxy_events,
    ):
        table.create(bind, checkfirst=True)

    for index in (
        sa.Index("ix_sources_name", sources.c.name, unique=True),
        sa.Index("ix_jobs_status", jobs.c.status),
        sa.Index("ix_scraped_items_external_id", scraped_items.c.external_id),
        sa.Index("ix_job_events_event_type", job_events.c.event_type),
        sa.Index("ix_antibot_events_session_id", antibot_events.c.session_id),
        sa.Index("ix_antibot_events_proxy_id", antibot_events.c.proxy_id),
        sa.Index("ix_proxy_events_event_type", proxy_events.c.event_type),
    ):
        index.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(bind=bind)

    for index_name, table_name in (
        ("ix_proxy_events_event_type", "proxy_events"),
        ("ix_antibot_events_proxy_id", "antibot_events"),
        ("ix_antibot_events_session_id", "antibot_events"),
        ("ix_job_events_event_type", "job_events"),
        ("ix_scraped_items_external_id", "scraped_items"),
        ("ix_jobs_status", "jobs"),
        ("ix_sources_name", "sources"),
    ):
        table = metadata.tables.get(table_name)
        if table is not None:
            sa.Index(index_name, table.c[0]).drop(bind, checkfirst=True)

    for table_name in (
        "proxy_events",
        "proxy_profiles",
        "antibot_events",
        "captcha_challenges",
        "job_events",
        "scraped_items",
        "jobs",
        "sources",
    ):
        table = metadata.tables.get(table_name)
        if table is not None:
            table.drop(bind, checkfirst=True)
