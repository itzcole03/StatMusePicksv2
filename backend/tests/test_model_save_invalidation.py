import asyncio
import tempfile

from backend.services import cache


def test_model_save_invalidates_cached_predictions():
    player = "Test Player"
    key_pred = f"predict:{player}:line:100"
    key_ctx = f"player_context:{player}:8"

    async def run():
        # ensure clean
        await cache.redis_delete(key_pred)
        await cache.redis_delete(key_ctx)

        # seed cache entries
        await cache.redis_set_json(key_pred, {"v": 1})
        await cache.redis_set_json(key_ctx, {"v": 2})

        got1 = await cache.redis_get_json(key_pred)
        got2 = await cache.redis_get_json(key_ctx)
        assert got1 is not None
        assert got2 is not None

        # Save a toy model via ModelRegistry which should invalidate prefixes
        from sklearn.dummy import DummyRegressor

        from backend.services.model_registry import ModelRegistry

        with tempfile.TemporaryDirectory() as td:
            mr = ModelRegistry(model_dir=td)
            # Save model; this calls redis_delete_prefix_sync internally
            mr.save_model(player, DummyRegressor())

        # After save, cache entries should be removed
        after1 = await cache.redis_get_json(key_pred)
        after2 = await cache.redis_get_json(key_ctx)
        assert after1 is None
        assert after2 is None

    asyncio.run(run())
