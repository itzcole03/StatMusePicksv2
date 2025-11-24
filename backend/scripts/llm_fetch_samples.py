#!/usr/bin/env python3
"""Fetch sample texts using the file-backed fetcher and extract LLM features.

Usage:
  python backend/scripts/llm_fetch_samples.py --dry-run
  python backend/scripts/llm_fetch_samples.py --out backend/models_store/llm_samples.json

The script uses `backend.services.news_fetcher.file_text_fetcher` by default.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from backend.services.news_fetcher import file_text_fetcher
from backend.services.llm_feature_service import create_default_service


DEFAULT_PLAYERS = [
    "LeBron James",
    "Stephen Curry",
    "Kevin Durant",
    "Giannis Antetokounmpo",
    "Luka Doncic",
    "Joel Embiid",
    "Jayson Tatum",
    "Jimmy Butler",
    "Nikola Jokic",
    "Kawhi Leonard",
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="backend/models_store/llm_samples.json", help="Output JSON file")
    p.add_argument("--players", default=None, help="Optional newline-separated file with player names")
    p.add_argument("--base-dir", default="backend/data/news_samples", help="Sample files base dir")
    p.add_argument("--dry-run", action="store_true", help="Only print results, don't write file")
    args = p.parse_args()

    if args.players:
        players = [l.strip() for l in Path(args.players).read_text(encoding="utf-8").splitlines() if l.strip()]
    else:
        players = DEFAULT_PLAYERS

    fetcher = file_text_fetcher(base_dir=args.base_dir)
    svc = create_default_service()

    results = {}
    for pl in players:
        text = fetcher(pl)
        features = svc.fetch_news_and_extract(pl, source_id="file_v1", text_fetcher=fetcher)
        results[pl] = {"text_sample_len": len(text or ""), "features": features}
        print(pl, results[pl])

    if not args.dry_run:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print("Wrote", outp)


if __name__ == "__main__":
    main()
