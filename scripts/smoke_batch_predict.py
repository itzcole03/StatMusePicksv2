"""Smoke test: send 20 concurrent requests to the FastAPI batch_predict endpoint

This script runs against the in-process ASGI app (no external HTTP server needed)
using httpx.AsyncClient with `app=`. It measures per-request latency and reports
partial results / errors so we can validate concurrency, timeouts, and partial
result semantics.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from fastapi.testclient import TestClient

from backend import fastapi_nba


def _post_batch(client: TestClient, payload: List[dict], max_concurrency: int = 6, timeout_seconds: int = 10):
    url = f"/api/batch_predict?max_concurrency={max_concurrency}&timeout_seconds={timeout_seconds}"
    t0 = time.perf_counter()
    r = client.post(url, json=payload)
    elapsed = time.perf_counter() - t0
    try:
        data = r.json()
    except Exception:
        data = {"error": "invalid json", "text": r.text}
    return r.status_code, elapsed, data


def make_payload(n: int):
    out = []
    for i in range(n):
        out.append({
            "player": f"Player_{i}",
            "stat": "points",
            "line": float(20 + (i % 5)),
        })
    return out


def run_concurrent_requests(num_requests: int = 20, items_per_request: int = 1, max_concurrency: int = 6, timeout_seconds: int = 10):
    client = TestClient(fastapi_nba.app)
    payloads = [make_payload(items_per_request) for _ in range(num_requests)]

    results = []
    with ThreadPoolExecutor(max_workers=min(32, num_requests)) as ex:
        futures = [ex.submit(_post_batch, client, p, max_concurrency, timeout_seconds) for p in payloads]
        for fut in as_completed(futures):
            results.append(fut.result())

    # Summarize
    success = sum(1 for s, _, d in results if s == 200 and isinstance(d, dict) and d.get('predictions') is not None)
    errors = [d for s, _, d in results if (s != 200) or (isinstance(d, dict) and d.get('predictions') is None)]
    times = [t for _, t, _ in results]
    print(f"Total requests: {len(results)}, success: {success}, errors: {len(errors)}")
    print(f"Avg latency: {sum(times)/len(times):.2f}s, min: {min(times):.2f}s, max: {max(times):.2f}s")
    if errors:
        print("Sample error:", errors[0])


if __name__ == "__main__":
    # Send 20 concurrent requests, each with 1 item (so total 20 predictions)
    run_concurrent_requests(num_requests=20, items_per_request=1, max_concurrency=8, timeout_seconds=5)
