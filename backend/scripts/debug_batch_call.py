import pathlib
import sys

# Ensure repo root is on sys.path so `backend` package can be imported when
# running this script directly.
repo_root = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo_root))

from fastapi.testclient import TestClient

from backend.main import app


def main():
    client = TestClient(app)
    # Inspect the OpenAPI schema for the batch endpoint
    oa = app.openapi()
    print("OpenAPI snippet for /api/batch_player_context:")
    try:
        print(oa["paths"]["/api/batch_player_context"])
    except Exception:
        print("could not find openapi path for /api/batch_player_context")
    try:
        print("\nBatchPlayerRequest schema:")
        print(oa["components"]["schemas"]["BatchPlayerRequest"])
    except Exception:
        print("no BatchPlayerRequest schema available")

    payloads = [
        [{"player_name": "LeBron James", "limit": 3}, {"player_name": "", "limit": 2}],
        [{"player": "LeBron James", "limit": 3}, {"player": "", "limit": 2}],
    ]

    for p in payloads:
        print("\nPosting payload:", p)
        resp = client.post("/api/batch_player_context", json=p)
        print("status", resp.status_code)
        try:
            print("json:", resp.json())
        except Exception:
            print("text:", resp.text)


if __name__ == "__main__":
    main()
