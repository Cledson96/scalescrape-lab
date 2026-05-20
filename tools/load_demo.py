from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import base64
import json
import math
import sys
import time
from typing import Any, NamedTuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

TERMINAL_STATUSES = {
    "success",
    "failed",
    "blocked",
    "rate_limited",
    "blocked_by_policy",
    "dead_lettered",
}
DEMO_QUEUES = ("scrape.jobs", "scrape.retry", "scrape.dead_letter")


class JobResult(NamedTuple):
    job_id: int
    status: str
    items_found: int
    attempts: int
    duration_seconds: float
    error_message: str | None


def build_job_payload(*, source: str, start_url: str, max_pages: int) -> dict:
    return {
        "source": source,
        "start_url": start_url,
        "mode": "browser",
        "max_pages": max_pages,
    }


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil((percent / 100) * len(ordered)) - 1)
    return float(ordered[min(index, len(ordered) - 1)])


def summarize_results(results: list[JobResult], total_seconds: float) -> dict:
    durations = [result.duration_seconds for result in results]
    total = len(results)
    status_counts = dict(Counter(result.status for result in results))
    items_found = sum(result.items_found for result in results)
    total_retries = sum(max(0, result.attempts - 1) for result in results)
    return {
        "total": total,
        "status_counts": status_counts,
        "items_found": items_found,
        "jobs_per_minute": round((total / total_seconds) * 60, 2) if total_seconds > 0 else 0.0,
        "avg_duration_seconds": round(sum(durations) / total, 2) if total else 0.0,
        "p50_duration_seconds": round(percentile(durations, 50), 2),
        "p95_duration_seconds": round(percentile(durations, 95), 2),
        "total_retries": total_retries,
    }


def summarize_rabbitmq_queues(queues: list[dict]) -> dict:
    summary = {
        name: {"messages_ready": 0, "messages_unacknowledged": 0, "consumers": 0}
        for name in DEMO_QUEUES
    }
    for queue in queues:
        name = str(queue.get("name", ""))
        if name not in summary:
            continue
        summary[name] = {
            "messages_ready": int(queue.get("messages_ready") or 0),
            "messages_unacknowledged": int(queue.get("messages_unacknowledged") or 0),
            "consumers": int(queue.get("consumers") or 0),
        }
    return summary


def request_json(
    *,
    method: str,
    url: str,
    payload: dict | None = None,
    basic_auth: tuple[str, str] | None = None,
    timeout: int = 20,
) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if basic_auth is not None:
        token = base64.b64encode(f"{basic_auth[0]}:{basic_auth[1]}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {token}"

    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} em {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Falha de rede em {url}: {exc.reason}") from exc

    if not body:
        return {}
    return json.loads(body)


async def run_single_job(index: int, args: argparse.Namespace, semaphore: asyncio.Semaphore) -> JobResult:
    async with semaphore:
        started = time.monotonic()
        payload = build_job_payload(source=args.source, start_url=args.start_url, max_pages=args.max_pages)
        try:
            created = await asyncio.to_thread(
                request_json,
                method="POST",
                url=f"{args.api_url.rstrip('/')}/jobs",
                payload=payload,
                timeout=args.request_timeout,
            )
            job_id = int(created["id"])
            deadline = started + args.timeout
            last_job = created

            while time.monotonic() < deadline:
                last_job = await asyncio.to_thread(
                    request_json,
                    method="GET",
                    url=f"{args.api_url.rstrip('/')}/jobs/{job_id}",
                    timeout=args.request_timeout,
                )
                status = str(last_job.get("status") or "unknown")
                if status in TERMINAL_STATUSES:
                    return _job_result_from_payload(job_id, status, started, last_job)
                await asyncio.sleep(args.poll_interval)

            return _job_result_from_payload(job_id, "timeout", started, last_job)
        except Exception as exc:
            return JobResult(
                job_id=0 - index,
                status="client_error",
                items_found=0,
                attempts=0,
                duration_seconds=round(time.monotonic() - started, 2),
                error_message=str(exc),
            )


async def run_benchmark(args: argparse.Namespace) -> list[JobResult]:
    semaphore = asyncio.Semaphore(args.concurrency)
    tasks = [run_single_job(index, args, semaphore) for index in range(1, args.jobs + 1)]
    return await asyncio.gather(*tasks)


def fetch_rabbitmq_queues(*, rabbitmq_url: str, user: str, password: str, timeout: int = 20) -> dict:
    queues = request_json(
        method="GET",
        url=f"{rabbitmq_url.rstrip('/')}/api/queues/{quote('/', safe='')}",
        basic_auth=(user, password),
        timeout=timeout,
    )
    if not isinstance(queues, list):
        return summarize_rabbitmq_queues([])
    return summarize_rabbitmq_queues(queues)


def format_report(summary: dict, results: list[JobResult], rabbitmq_summary: dict | None = None) -> str:
    lines = [
        "ScaleScrape Load Demo",
        "=====================",
        f"Jobs enviados: {summary['total']}",
        f"Status: {json.dumps(summary['status_counts'], ensure_ascii=False, sort_keys=True)}",
        f"Itens coletados: {summary['items_found']}",
        f"Throughput: {summary['jobs_per_minute']} jobs/min",
        f"Duração média: {summary['avg_duration_seconds']}s",
        f"P50/P95: {summary['p50_duration_seconds']}s / {summary['p95_duration_seconds']}s",
        f"Retries totais: {summary['total_retries']}",
    ]
    failures = [result for result in results if result.status != "success"]
    if failures:
        lines.append("")
        lines.append("Jobs não finalizados com sucesso:")
        for result in failures[:10]:
            lines.append(f"- #{result.job_id}: {result.status} ({result.error_message or 'sem erro detalhado'})")
    if rabbitmq_summary is not None:
        lines.append("")
        lines.append("RabbitMQ:")
        for queue_name in DEMO_QUEUES:
            queue = rabbitmq_summary[queue_name]
            lines.append(
                f"- {queue_name}: ready={queue['messages_ready']} "
                f"unacked={queue['messages_unacknowledged']} consumers={queue['consumers']}"
            )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dispara jobs de scraping e mede throughput da pipeline.")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--jobs", type=positive_int, default=20)
    parser.add_argument("--concurrency", type=positive_int, default=5)
    parser.add_argument("--source", default="fake-target")
    parser.add_argument("--start-url", default="http://target-site:4000/protected/items?page=1")
    parser.add_argument("--max-pages", type=positive_int, default=1)
    parser.add_argument("--timeout", type=positive_int, default=300)
    parser.add_argument("--poll-interval", type=positive_float, default=2.0)
    parser.add_argument("--request-timeout", type=positive_int, default=20)
    parser.add_argument("--rabbitmq-url", default="")
    parser.add_argument("--rabbitmq-user", default="guest")
    parser.add_argument("--rabbitmq-password", default="guest")
    return parser.parse_args(argv)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("valor deve ser maior que zero")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("valor deve ser maior que zero")
    return parsed


def _job_result_from_payload(job_id: int, status: str, started: float, payload: dict) -> JobResult:
    return JobResult(
        job_id=job_id,
        status=status,
        items_found=int(payload.get("items_found") or 0),
        attempts=int(payload.get("attempts") or 0),
        duration_seconds=round(time.monotonic() - started, 2),
        error_message=payload.get("error_message"),
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.monotonic()
    results = asyncio.run(run_benchmark(args))
    total_seconds = time.monotonic() - started
    summary = summarize_results(results, total_seconds=total_seconds)
    rabbitmq_summary = None
    if args.rabbitmq_url:
        rabbitmq_summary = fetch_rabbitmq_queues(
            rabbitmq_url=args.rabbitmq_url,
            user=args.rabbitmq_user,
            password=args.rabbitmq_password,
            timeout=args.request_timeout,
        )
    print(format_report(summary, results, rabbitmq_summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
