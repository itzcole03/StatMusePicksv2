"""Check Ollama embeddings endpoint using current environment variables.

Prints masked env vars and attempts a POST to the embeddings endpoint.
"""

import json
import os
import sys


def mask(s: str) -> str:
    if not s:
        return "<missing>"
    if len(s) <= 8:
        return s[:2] + "..." + s[-2:]
    return s[:4] + "..." + s[-4:]


def main():
    url = os.environ.get("OLLAMA_URL") or ""
    key = (
        os.environ.get("OLLAMA_CLOUD_API_KEY") or os.environ.get("OLLAMA_API_KEY") or ""
    )
    model = os.environ.get("OLLAMA_DEFAULT_MODEL") or ""

    print("OLLAMA_URL:", mask(url))
    print("OLLAMA_CLOUD_API_KEY:", mask(key))
    print("OLLAMA_DEFAULT_MODEL:", model or "<not set>")

    if not url:
        print(
            "\nNo OLLAMA_URL set; please set OLLAMA_URL to https://api.ollama.com or your host."
        )
        sys.exit(2)

    base = url.rstrip("/")
    # try multiple common endpoints
    endpoints = [base + "/api/embed", base + "/api/embeddings", base + "/v1/embeddings"]
    payload = {"model": model or "gpt-oss:120b", "input": "test embedding"}

    print("\nProbing embedding endpoints:")

    try:
        import requests
    except Exception as e:
        print("requests not installed in this environment:", e)
        sys.exit(3)

    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    for api_path in endpoints:
        print("\nTesting:", api_path)
        try:
            resp = requests.post(api_path, json=payload, headers=headers, timeout=15)
            print("HTTP", resp.status_code)
            try:
                j = resp.json()
                print("Response JSON (truncated):")
                s = json.dumps(j, indent=2)
                print(s[:4000])
            except Exception:
                print("Response text:", (resp.text or "")[:1000])
        except Exception as e:
            print("Request failed:", e)


if __name__ == "__main__":
    main()
