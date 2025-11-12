"""Data ingestion service scaffold.

This module should contain functions to fetch and normalize external data
from NBA APIs or commercial providers. For now it provides a small
interface and TODO notes for implementation.
"""
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


def invalidate_player_contexts(player_names: List[str]) -> None:
    """Invalidate cached `player_context:{player}:*` entries for given players.

    Uses the synchronous cache helper so callers don't need an event loop.
    """
    try:
        from backend.services import cache as cache_module
    except Exception:
        logger.debug("cache module not available for invalidation")
        return

    for p in player_names:
        try:
            cache_module.redis_delete_prefix_sync(f"player_context:{p}:")
        except Exception:
            logger.exception("Failed to invalidate player_context cache for %s", p)


def invalidate_all_player_contexts() -> None:
    """Invalidate all `player_context:` keys (use with caution)."""
    try:
        from backend.services import cache as cache_module
        cache_module.redis_delete_prefix_sync("player_context:")
    except Exception:
        logger.exception("Failed to invalidate all player_context caches")


async def fetch_yesterday_game_results() -> List[Dict]:
    """Placeholder: Fetch yesterday's game results from data sources.

    Implementations should return a list of normalized game dicts suitable
    for ingestion into the feature store / DB.
    """
    logger.info("fetch_yesterday_game_results called - not implemented")
    return []


def normalize_raw_game(raw: Dict) -> Dict:
    """Normalize a raw game row into the internal schema.

    This should map external field names to our canonical names.
    """
    # TODO: implement mapping logic
    return raw


def ingest_games(normalized_games: List[Dict]) -> None:
    """Best-effort ingestion helper that persists normalized game rows

    For now this function focuses on calling cache invalidation for the
    players present in `normalized_games`. It expects each game record to
    include a `player` or `player_name` field (best-effort mapping).
    """
    if not normalized_games:
        return

    # Extract player names from the normalized payloads
    players = set()
    for g in normalized_games:
        name = g.get('player') or g.get('player_name') or g.get('name')
        if name:
            players.add(name)

    if not players:
        # nothing to invalidate
        return

    try:
        invalidate_player_contexts(list(players))
    except Exception:
        logger.exception("ingest_games: failed to invalidate player contexts")

