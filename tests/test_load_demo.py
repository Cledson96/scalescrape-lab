import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
LOAD_DEMO_PATH = ROOT / "tools" / "load_demo.py"


def load_demo_module():
    spec = importlib.util.spec_from_file_location("load_demo", LOAD_DEMO_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class LoadDemoTests(unittest.TestCase):
    def test_build_job_payload_uses_requested_source_url_and_max_pages(self) -> None:
        load_demo = load_demo_module()

        payload = load_demo.build_job_payload(
            source="fake-target",
            start_url="http://target-site:4000/protected/items?page=1",
            max_pages=3,
        )

        self.assertEqual(
            payload,
            {
                "source": "fake-target",
                "start_url": "http://target-site:4000/protected/items?page=1",
                "mode": "browser",
                "max_pages": 3,
            },
        )

    def test_summarize_results_reports_throughput_percentiles_and_retries(self) -> None:
        load_demo = load_demo_module()
        results = [
            load_demo.JobResult(1, "success", 12, 1, 4.0, None),
            load_demo.JobResult(2, "success", 8, 2, 8.0, None),
            load_demo.JobResult(3, "dead_lettered", 0, 3, 12.0, "timeout"),
        ]

        summary = load_demo.summarize_results(results, total_seconds=24.0)

        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["status_counts"], {"success": 2, "dead_lettered": 1})
        self.assertEqual(summary["items_found"], 20)
        self.assertEqual(summary["jobs_per_minute"], 7.5)
        self.assertEqual(summary["avg_duration_seconds"], 8.0)
        self.assertEqual(summary["p50_duration_seconds"], 8.0)
        self.assertEqual(summary["p95_duration_seconds"], 12.0)
        self.assertEqual(summary["total_retries"], 3)

    def test_rabbitmq_queue_summary_keeps_demo_queue_fields(self) -> None:
        load_demo = load_demo_module()

        summary = load_demo.summarize_rabbitmq_queues(
            [
                {"name": "scrape.jobs", "messages_ready": 4, "messages_unacknowledged": 2, "consumers": 3},
                {"name": "other", "messages_ready": 99, "messages_unacknowledged": 99, "consumers": 99},
            ]
        )

        self.assertEqual(
            summary,
            {
                "scrape.jobs": {"messages_ready": 4, "messages_unacknowledged": 2, "consumers": 3},
                "scrape.retry": {"messages_ready": 0, "messages_unacknowledged": 0, "consumers": 0},
                "scrape.dead_letter": {"messages_ready": 0, "messages_unacknowledged": 0, "consumers": 0},
            },
        )


if __name__ == "__main__":
    unittest.main()
