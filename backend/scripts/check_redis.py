import importlib.util
import json
import os


def main():
    out = {}
    out["REDIS_URL"] = os.environ.get("REDIS_URL")
    out["redis_installed"] = bool(importlib.util.find_spec("redis"))
    out["can_connect"] = False
    out["error"] = None

    if out["redis_installed"]:
        try:
            import redis

            url = out["REDIS_URL"] or "redis://127.0.0.1:6379"
            r = redis.from_url(url, socket_connect_timeout=1)
            out["can_connect"] = r.ping()
        except Exception as e:
            out["error"] = str(e)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
