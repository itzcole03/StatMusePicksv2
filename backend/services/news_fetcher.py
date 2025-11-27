"""File-backed news/text fetcher for local/dev testing.

Usage:
    from backend.services.news_fetcher import file_text_fetcher
    fetcher = file_text_fetcher(base_dir="backend/data/news_samples")
    text = fetcher("LeBron James")

The fetcher looks for files named after the player (several extensions supported)
and returns the file contents (or aggregated contents if multiple matches).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable

_EXTS = [".txt", ".md", ".json", ".csv", ".html"]


def _normalize_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("/", "_").replace("\\", "_")


def _read_text_file(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        try:
            return p.read_text(encoding="latin-1")
        except Exception:
            return ""


def _read_json_file(p: Path) -> str:
    try:
        j = json.loads(p.read_text(encoding="utf-8"))
        # accept str, list[str], or dict with 'text' key
        if isinstance(j, str):
            return j
        if isinstance(j, list):
            return "\n\n".join(str(x) for x in j)
        if isinstance(j, dict):
            for k in ("text", "body", "content"):
                if k in j and isinstance(j[k], str):
                    return j[k]
        return json.dumps(j)
    except Exception:
        return ""


def _read_csv_file(p: Path) -> str:
    try:
        rows = []
        with p.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            for r in reader:
                if r:
                    rows.append(" ".join(r))
        return "\n".join(rows)
    except Exception:
        return ""


def file_text_fetcher(
    base_dir: str = "backend/data/news_samples",
) -> Callable[[str], str]:
    """Return a `text_fetcher(player_name)` callable that reads local sample files.

    The callable returns an empty string when no sample is found.
    """
    base = Path(base_dir)

    def fetcher(player_name: str) -> str:
        if not player_name:
            return ""
        name_variants = [
            player_name,
            _normalize_name(player_name),
            player_name.replace(" ", "_"),
        ]
        candidates = []
        for nv in name_variants:
            for ext in _EXTS:
                p = base / (nv + ext)
                if p.exists():
                    candidates.append(p)

        # also try prefix matches (e.g., 'lebron' matching 'lebron_james.txt')
        if not candidates and base.exists():
            pref = _normalize_name(player_name).split("_")[0]
            for p in base.glob(f"{pref}*"):
                if p.is_file() and p.suffix in _EXTS:
                    candidates.append(p)

        if not candidates:
            return ""

        parts = []
        for p in sorted(candidates):
            if p.suffix == ".json":
                parts.append(_read_json_file(p))
            elif p.suffix == ".csv":
                parts.append(_read_csv_file(p))
            else:
                parts.append(_read_text_file(p))

        return "\n\n".join([x for x in parts if x])

    return fetcher


__all__ = ["file_text_fetcher"]
