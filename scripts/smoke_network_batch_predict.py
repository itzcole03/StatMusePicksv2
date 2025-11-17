"""Network smoke test: post 20 concurrent requests to the running uvicorn server

Targets: http://localhost:8001/api/batch_predict (adjustable)

Usage:
  & .venv\Scripts\Activate.ps1; python scripts\smoke_network_batch_predict.py
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import requests


URL = "http://localhost:8000/api/batch_predict"


def make_payload_single(idx: int):
    return [{
        "player": f"Player_{idx}",
        "stat": "points",
        "line": float(20 + (idx % 5)),
    }]


def post_once(payload, max_concurrency=8, timeout_seconds=5):
    params = {"max_concurrency": max_concurrency, "timeout_seconds": timeout_seconds}
    t0 = time.perf_counter()
    try:
        r = requests.post(URL, params=params, json=payload, timeout=timeout_seconds + 2)
        elapsed = time.perf_counter() - t0
        try:
            data = r.json()
        except Exception:
            data = {"error": "invalid json", "text": r.text}
        return r.status_code, elapsed, data
    except Exception as e:
        return None, time.perf_counter() - t0, {"error": str(e)}


def run_concurrent(num_requests: int = 20, max_workers: int = 20):
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(post_once, make_payload_single(i)) for i in range(num_requests)]
        results = []
        for fut in as_completed(futures):
            results.append(fut.result())

    success = sum(1 for s, _, d in results if s == 200 and isinstance(d, dict) and d.get('predictions') is not None)
    errors = [d for s, _, d in results if not (s == 200 and isinstance(d, dict) and d.get('predictions') is not None)]
    times = [t for _, t, _ in results if t is not None]
    print(f"Total: {len(results)}, success: {success}, errors: {len(errors)}")
    if times:
        print(f"Avg latency: {sum(times)/len(times):.3f}s, min: {min(times):.3f}s, max: {max(times):.3f}s")
    if errors:
        print("Sample error:", errors[0])
    # Print a sample prediction
    for s, t, d in results[:3]:
        print(s, f"{t:.3f}s", json.dumps(d)[:200])


if __name__ == "__main__":
    print("Running network smoke test to", URL)
    run_concurrent(num_requests=20, max_workers=20)
