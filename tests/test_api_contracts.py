from datetime import datetime, timezone
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
API_PATH = ROOT / "apps" / "api"


class NoopMetric:
    def labels(self, **kwargs):  # noqa: ANN001
        return self

    def inc(self, amount: int = 1) -> None:
        return None

    def set(self, value: int) -> None:
        return None

    def observe(self, value: float) -> None:
        return None


sys.modules["prometheus_client"] = types.SimpleNamespace(
    Counter=lambda *args, **kwargs: NoopMetric(),
    Gauge=lambda *args, **kwargs: NoopMetric(),
    Histogram=lambda *args, **kwargs: NoopMetric(),
    CONTENT_TYPE_LATEST="text/plain; version=0.0.4",
    generate_latest=lambda: b"",
)


class ApiContractTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import sqlalchemy  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("SQLAlchemy is not installed in the lightweight local test environment")

        self.temp_dir = tempfile.TemporaryDirectory()
        self.previous_env = {
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "MEDIA_ROOT": os.environ.get("MEDIA_ROOT"),
        }
        db_path = Path(self.temp_dir.name) / "api-test.db"
        media_root = Path(self.temp_dir.name) / "media"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
        os.environ["MEDIA_ROOT"] = str(media_root)

        self.saved_modules = {
            name: module
            for name, module in sys.modules.items()
            if name == "app" or name.startswith("app.")
        }
        for name in list(self.saved_modules):
            sys.modules.pop(name, None)
        sys.path.insert(0, str(API_PATH))

        from app.database import Base, SessionLocal, engine
        from app.models import AntibotEvent, Job, JobEvent, ProxyProfile, ScrapedItem, Source
        from app.schemas import JobCreate
        import app.services.antibot as antibot_service
        import app.services.items as item_service
        import app.services.jobs as job_service
        import app.services.proxies as proxy_service
        import app.services.sources as source_service

        Base.metadata.create_all(bind=engine)
        self.engine = engine
        self.SessionLocal = SessionLocal
        self.JobCreate = JobCreate
        self.services = types.SimpleNamespace(
            antibot=antibot_service,
            items=item_service,
            jobs=job_service,
            proxies=proxy_service,
            sources=source_service,
        )
        self.models = types.SimpleNamespace(
            AntibotEvent=AntibotEvent,
            Job=Job,
            JobEvent=JobEvent,
            ProxyProfile=ProxyProfile,
            ScrapedItem=ScrapedItem,
            Source=Source,
        )
        self.enqueued_jobs: list[int] = []
        job_service.enqueue_scrape_job = self.enqueued_jobs.append

    def tearDown(self) -> None:
        engine = getattr(self, "engine", None)
        if engine is not None:
            engine.dispose()
        for name in [name for name in sys.modules if name == "app" or name.startswith("app.")]:
            sys.modules.pop(name, None)
        sys.modules.update(self.saved_modules)
        while str(API_PATH) in sys.path:
            sys.path.remove(str(API_PATH))
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp_dir.cleanup()

    def test_create_scrape_job_creates_job_event_and_enqueues(self) -> None:
        with self.SessionLocal() as session:
            source = self.models.Source(
                name="fake-target",
                base_url="http://target-site:4000/protected/items?page=1",
                status="active",
            )
            session.add(source)
            session.commit()

            job = self.services.jobs.create_scrape_job(
                session,
                self.JobCreate(
                    source="fake-target",
                    start_url="http://target-site:4000/protected/items?page=1",
                    mode="browser",
                    max_pages=1,
                ),
            )
            job_id = job.id

        self.assertEqual(job.status, "pending")
        self.assertEqual(self.enqueued_jobs, [job_id])
        with self.SessionLocal() as session:
            events = session.query(self.models.JobEvent).all()
            self.assertEqual(events[0].event_type, "job_created")
            self.assertEqual(events[0].metadata_json["source"], "fake-target")

    def test_create_scrape_job_raises_for_missing_source(self) -> None:
        from app.errors import ApiError

        with self.SessionLocal() as session:
            with self.assertRaises(ApiError) as caught:
                self.services.jobs.create_scrape_job(
                    session,
                    self.JobCreate(
                        source="missing",
                        start_url="http://target-site:4000/protected/items?page=1",
                        mode="browser",
                        max_pages=1,
                    ),
                )

        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(caught.exception.detail, "source_not_found")

    def test_create_scrape_job_raises_for_paused_source(self) -> None:
        from app.errors import ApiError

        with self.SessionLocal() as session:
            session.add(
                self.models.Source(
                    name="fake-target",
                    base_url="http://target-site:4000/protected/items?page=1",
                    status="paused",
                )
            )
            session.commit()

            with self.assertRaises(ApiError) as caught:
                self.services.jobs.create_scrape_job(
                    session,
                    self.JobCreate(
                        source="fake-target",
                        start_url="http://target-site:4000/protected/items?page=1",
                        mode="browser",
                        max_pages=1,
                    ),
                )

        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(caught.exception.detail["reason"], "source_paused")

    def test_items_page_filters_by_source(self) -> None:
        with self.SessionLocal() as session:
            source_a = self.models.Source(name="fake-target", base_url="http://target-site:4000", status="active")
            source_b = self.models.Source(name="books-to-scrape", base_url="https://books.toscrape.com", status="active")
            session.add_all([source_a, source_b])
            session.flush()
            job_a = self.models.Job(source_id=source_a.id, start_url=source_a.base_url, status="success")
            job_b = self.models.Job(source_id=source_b.id, start_url=source_b.base_url, status="success")
            session.add_all([job_a, job_b])
            session.flush()
            session.add_all(
                [
                    self.models.ScrapedItem(
                        job_id=job_a.id,
                        external_id="fake-1",
                        title="Fake Item",
                        detail_url="http://target-site:4000/items/fake-1",
                        raw_data={"source": "fake-target"},
                    ),
                    self.models.ScrapedItem(
                        job_id=job_b.id,
                        external_id="book-1",
                        title="Book Item",
                        detail_url="https://books.toscrape.com/book-1",
                        raw_data={"source": "books-to-scrape"},
                    ),
                ]
            )
            session.commit()

            page = self.services.items.list_items_page(
                session,
                source="books-to-scrape",
                page=1,
                page_size=10,
            )

        self.assertEqual(page.total, 1)
        self.assertEqual(page.items[0].title, "Book Item")

    def test_retry_job_resets_state_and_enqueues(self) -> None:
        with self.SessionLocal() as session:
            source = self.models.Source(name="fake-target", base_url="http://target-site:4000", status="active")
            session.add(source)
            session.flush()
            job = self.models.Job(
                source_id=source.id,
                start_url=source.base_url,
                status="failed",
                attempts=3,
                error_message="timeout",
                finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(job)
            session.commit()
            job_id = job.id

            retried = self.services.jobs.retry_scrape_job(session, job_id)

        self.assertEqual(retried.status, "pending")
        self.assertEqual(retried.attempts, 0)
        self.assertIsNone(retried.error_message)
        self.assertEqual(self.enqueued_jobs, [job_id])

    def test_sources_pause_and_resume_preserve_public_contract(self) -> None:
        with self.SessionLocal() as session:
            source = self.models.Source(name="fake-target", base_url="http://target-site:4000", status="active")
            session.add(source)
            session.commit()
            source_id = source.id

            paused = self.services.sources.pause_source(session, source_id)
            self.assertEqual(paused.status, "paused")
            resumed = self.services.sources.resume_source(session, source_id)

        self.assertEqual(resumed.status, "active")
        self.assertIsNone(resumed.circuit_open_until)

    def test_proxy_cooldown_sets_status_and_deadline(self) -> None:
        with self.SessionLocal() as session:
            proxy = self.models.ProxyProfile(name="proxy-a", endpoint="lab://proxy-a", status="active")
            session.add(proxy)
            session.commit()
            proxy_id = proxy.id

            updated = self.services.proxies.cooldown_proxy(session, proxy_id)

        self.assertEqual(updated.status, "cooldown")
        self.assertIsNotNone(updated.cooldown_until)

    def test_antibot_events_keep_response_shape(self) -> None:
        with self.SessionLocal() as session:
            session.add(
                self.models.AntibotEvent(
                    session_id="session-1",
                    proxy_id="proxy-a",
                    risk_score=42,
                    action="challenge",
                    reason="high_velocity",
                )
            )
            session.commit()

            payload = self.services.antibot.list_antibot_events(session)

        self.assertEqual(payload[0]["session_id"], "session-1")
        self.assertEqual(payload[0]["proxy_id"], "proxy-a")
        self.assertEqual(payload[0]["risk_score"], 42)
        self.assertEqual(payload[0]["action"], "challenge")
        self.assertEqual(payload[0]["reason"], "high_velocity")
        self.assertIn("created_at", payload[0])

    def test_routers_register_public_paths(self) -> None:
        try:
            import fastapi  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("FastAPI is not installed in the lightweight local test environment")
        from app.routers import api_routers

        paths = {
            route.path
            for router in api_routers
            for route in router.routes
            if hasattr(route, "path")
        }

        self.assertIn("/health", paths)
        self.assertIn("/metrics", paths)
        self.assertIn("/jobs", paths)
        self.assertIn("/jobs/{job_id}", paths)
        self.assertIn("/jobs/{job_id}/retry", paths)
        self.assertIn("/items", paths)
        self.assertIn("/items/page", paths)
        self.assertIn("/jobs/{job_id}/items", paths)
        self.assertIn("/sources", paths)
        self.assertIn("/sources/{source_id}/pause", paths)
        self.assertIn("/sources/{source_id}/resume", paths)
        self.assertIn("/proxies", paths)
        self.assertIn("/proxies/{proxy_id}/enable", paths)
        self.assertIn("/proxies/{proxy_id}/disable", paths)
        self.assertIn("/proxies/{proxy_id}/cooldown", paths)
        self.assertIn("/antibot/events", paths)


class ApiStaticArchitectureTests(unittest.TestCase):
    def test_main_py_is_only_application_bootstrap(self) -> None:
        main_py = (API_PATH / "app" / "main.py").read_text()

        self.assertIn("include_router", main_py)
        self.assertNotIn("@app.get", main_py)
        self.assertNotIn("@app.post", main_py)
        self.assertLess(len(main_py), 5000)

    def test_api_layers_are_grouped_by_responsibility(self) -> None:
        expected_files = [
            "app/api_metadata.py",
            "app/errors.py",
            "app/routers/jobs.py",
            "app/routers/items.py",
            "app/routers/sources.py",
            "app/routers/proxies.py",
            "app/routers/antibot.py",
            "app/repositories/jobs.py",
            "app/repositories/items.py",
            "app/repositories/sources.py",
            "app/repositories/proxies.py",
            "app/services/jobs.py",
            "app/services/items.py",
            "app/services/sources.py",
            "app/services/proxies.py",
            "app/services/source_circuit.py",
        ]

        missing = [path for path in expected_files if not (API_PATH / path).exists()]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
