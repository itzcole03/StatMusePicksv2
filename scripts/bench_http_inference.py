"""Create a toy model, load it into the running server, and benchmark HTTP inference.

Steps:
- Writes `backend/models_store/LeBron_James.pkl` using `backend/scripts/create_test_model.py` logic
- Calls `POST /api/models/load?player=LeBron%20James` to ask server to load the model
- Sends N requests to `/api/predict` for `LeBron James` and measures per-request latency
"""
import os
import time
import joblib
import requests

from backend.services.test_models import DummyModel


MODEL_PLAYER = "LeBron James"
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "models_store", "LeBron_James.pkl")
SERVER_URL = "http://localhost:8000"


def write_model():
    d = os.path.dirname(MODEL_PATH)
    os.makedirs(d, exist_ok=True)
    joblib.dump(DummyModel(), MODEL_PATH)
    print("Wrote test model to", MODEL_PATH)


def load_model_on_server():
    url = f"{SERVER_URL}/api/models/load"
    print("Requesting server to load model for", MODEL_PLAYER)
    r = requests.post(url, params={"player": MODEL_PLAYER}, timeout=10)
    print("load response:", r.status_code, r.text[:200])
    return r.status_code == 200


def run_benchmark(n=50):
    url = f"{SERVER_URL}/api/predict"
    payload = {"player": MODEL_PLAYER, "stat": "points", "line": 20.0}
    times = []
    successes = 0
    for i in range(n):
        t0 = time.perf_counter()
        try:
            r = requests.post(url, json=payload, timeout=10)
            elapsed = time.perf_counter() - t0
            times.append(elapsed)
            if r.status_code == 200:
                successes += 1
            else:
                print("non-200", r.status_code, r.text)
        except Exception as e:
            elapsed = time.perf_counter() - t0
            times.append(elapsed)
            print("request error", e)
    if times:
        print(f"Ran {n} requests: success={successes}, avg={sum(times)/len(times):.3f}s, min={min(times):.3f}s, max={max(times):.3f}s")
    return times


if __name__ == '__main__':
    write_model()
    ok = load_model_on_server()
    if not ok:
        print("Server did not accept load request; continuing to benchmark (server may auto-load on predict)")
    run_benchmark(50)
