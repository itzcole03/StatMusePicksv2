import asyncio
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `backend` package is importable when run as script
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services import cache


async def setup():
    await cache.redis_set_json("predict:Test Player:line:100", {"v": 1})
    await cache.redis_set_json("player_context:Test Player:8", {"v": 2})
    print("async store keys:", list(getattr(cache, "_fallback_store", {}).keys()))
    print("sync store keys:", list(getattr(cache, "_fallback_store_sync", {}).keys()))


setup_done = asyncio.run(setup())

print("calling sync delete")
cache.redis_delete_prefix_sync("predict:Test Player:")
print(
    "after sync delete sync keys:",
    list(getattr(cache, "_fallback_store_sync", {}).keys()),
)

res = asyncio.run(cache.redis_get_json("predict:Test Player:line:100"))
print("async get after delete ->", res)
