"""Data ingestion service scaffold.

This module should contain functions to fetch and normalize external data
from NBA APIs or commercial providers. For now it provides a small
interface and TODO notes for implementation.
"""
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


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
