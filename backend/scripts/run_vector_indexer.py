"""CLI entry to run the periodic vector indexer.

Usage: `python backend/scripts/run_vector_indexer.py`

Environment variables:
 - INDEXER_SOURCE_FILE: path to JSONL file with items to index (id,text,meta)
 - INDEXER_INTERVAL_SECONDS: seconds between runs (default 300)
 - DATABASE_URL: database connection URL
"""

import logging
import os

from backend.services.vector_indexer import run_periodic_indexer

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


def main():
    run_periodic_indexer()


if __name__ == "__main__":
    main()
