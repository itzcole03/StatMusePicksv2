"""Simple web search tool used as a callable tool by the LLM.

Behaviour:
- If `BING_API_KEY` env var is set, performs a Bing Web Search request and
  returns concatenated top snippet results.
- Otherwise returns a deterministic stub indicating no live search is
  configured (useful for tests and CI).
"""
from __future__ import annotations

import os
import logging
from typing import List

logger = logging.getLogger(__name__)


def _bing_search(query: str, count: int = 3) -> str:
    try:
        import requests
    except Exception:
        logger.debug("requests not available for web search")
        return f"[web_search disabled: requests not installed] {query}"

    key = os.environ.get('BING_API_KEY')
    if not key:
        return f"[web_search not configured] {query}"

    headers = {'Ocp-Apim-Subscription-Key': key}
    params = {'q': query, 'count': str(count)}
    try:
        resp = requests.get('https://api.bing.microsoft.com/v7.0/search', headers=headers, params=params, timeout=5)
        resp.raise_for_status()
        j = resp.json()
        snippets: List[str] = []
        # gather top webPages snippets
        web = j.get('webPages', {}).get('value', [])
        for item in web[:count]:
            title = item.get('name') or ''
            snippet = item.get('snippet') or item.get('snippet') or ''
            url = item.get('url') or ''
            snippets.append(f"- {title}: {snippet} ({url})")
        if snippets:
            return "\n".join(snippets)
        return f"[bing returned no results] {query}"
    except Exception as e:
        logger.exception("Bing search failed")
        return f"[bing error] {str(e)}"


def web_search(query: str) -> str:
    """Public tool function: returns a short plain-text summary for `query`."""
    # First try DuckDuckGo Instant Answer API (no key required)
    try:
        import requests
        ddg_url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1, "skip_disambig": 1}
        resp = requests.get(ddg_url, params=params, timeout=5)
        resp.raise_for_status()
        j = resp.json()
        parts = []
        abstract = j.get("AbstractText") or ""
        if abstract:
            parts.append(abstract)

        # RelatedTopics is often a list of dicts or nested lists
        rt = j.get("RelatedTopics") or []
        count = 0
        for item in rt:
            if isinstance(item, dict):
                text = item.get("Text") or item.get("Result") or ""
                if text:
                    parts.append(text)
                    count += 1
            if count >= 3:
                break

        # If we collected useful parts, return them
        if parts:
            return "\n".join(parts[:5])
    except Exception:
        logger.debug("DuckDuckGo instant answer failed or unavailable, falling back to Bing or stub")

    # Fall back to Bing if API key present, otherwise return deterministic stub
    key = os.environ.get('BING_API_KEY')
    if key:
        return _bing_search(query)
    return f"[web_search not configured] {query}"
