"""LLM-derived qualitative feature extraction service.

Lightweight, single-file implementation that requests structured JSON from
the pluggable LLM client (`backend.services.ollama_client.get_default_client()`)
and validates it with Pydantic. Falls back to simple heuristics on failure.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError

from backend.services.ollama_client import get_default_client
from backend.services.vector_store import InMemoryVectorStore

try:
    from backend.services import metrics
except Exception:
    metrics = None
import time

logger = logging.getLogger(__name__)


class QualitativeFeatures(BaseModel):
    injury_status: str = Field(
        ...,
        description="Short label for injury status, e.g. 'questionable', 'out', 'healthy'",
    )
    morale_score: int = Field(
        ..., ge=0, le=100, description="Player morale as integer 0-100"
    )
    news_sentiment: float = Field(
        ..., ge=-1.0, le=1.0, description="Normalized sentiment -1..1"
    )
    trade_sentiment: float = Field(0.0, description="Trade rumor sentiment, -1..1")
    motivation: float = Field(0.0, description="Motivation score 0..1")


class LLMFeatureService:
    def __init__(
        self,
        default_model: Optional[str] = None,
        redis_client: Optional[object] = None,
        ttl_seconds: int = 24 * 3600,
        vector_store: Optional[InMemoryVectorStore] = None,
    ):
        self.client = get_default_client()
        self.default_model = (
            default_model or os.environ.get("OLLAMA_DEFAULT_MODEL") or "llama3"
        )
        # optional Redis client for caching; fall back to in-process cache
        self.redis = redis_client
        self.ttl = int(ttl_seconds)
        self._cache: Dict[str, Dict[str, float]] = {}
        self._ollama_last_call = 0.0
        # allow injection of a vector store (useful for tests / production swap)
        self.vector_store = (
            vector_store if vector_store is not None else InMemoryVectorStore()
        )
        # last embedding source used: 'live'|'fallback'|None
        self._last_embedding_source: Optional[str] = None

    def _build_prompt(self, player_name: str, text: str) -> str:
        return (
            "You are a sports analyst. Given the following short news summary or context,\n"
            "produce a JSON object only (no extra text) with the keys: injury_status (string), morale_score (int 0-100), news_sentiment (float -1.0..1.0), trade_sentiment (float -1.0..1.0), motivation (float 0.0..1.0).\n"
            "Respond using valid JSON only.\n\nContext:\n"
            f"{text}\n\nReturn JSON."
        )

    def extract_from_text(
        self,
        player_name: str,
        text: str,
        model: Optional[str] = None,
        max_attempts: int = 2,
    ) -> Dict[str, Any]:
        """Request JSON from the client and return validated features or {}.

        Uses `response_format='json'` when calling the client.generate API and
        accepts dict/list or text containing JSON. On validation failure the
        method will attempt a best-effort coercion and otherwise fall back to
        simple heuristics.
        """
        model = model or self.default_model
        prompt = self._build_prompt(player_name, text)

        # define a lightweight tool descriptor for the LLM to call when it
        # needs fresh web information. Ollama tool-calling expects a small
        # JSON schema describing the tool; we keep it minimal here.
        # Tool descriptor compatible with common tool-calling formats (name + JSON Schema `parameters`).
        tools = [
            {
                "name": "web_search",
                "description": "Search the web for recent news or quotes; returns plain-text summary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    },
                    "required": ["query"],
                },
            }
        ]

        for _ in range(max_attempts):
            try:
                # pass both `response_format` and `format` to support different client APIs
                if metrics is not None:
                    try:
                        metrics.llm_tool_calls_total.inc()
                    except Exception:
                        pass
                start = time.time()
                resp = self.client.generate(
                    model=model,
                    prompt=prompt,
                    timeout=30,
                    response_format="json",
                    format="json",
                    tools=tools,
                )
                dur = time.time() - start
                try:
                    if metrics is not None:
                        metrics.llm_tool_call_latency_seconds.observe(dur)
                except Exception:
                    pass
                if resp is not None:
                    try:
                        if metrics is not None:
                            metrics.llm_tool_calls_success.inc()
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("LLM client.generate failed: %s", e)
                resp = None

            if not resp:
                continue

            parsed = None
            if isinstance(resp, (dict, list)):
                parsed = resp
            else:
                try:
                    parsed = json.loads(str(resp))
                except Exception:
                    # try to find a JSON object substring
                    try:
                        s = str(resp)
                        start = s.find("{")
                        end = s.rfind("}")
                        if start != -1 and end != -1 and end > start:
                            parsed = json.loads(s[start : end + 1])
                    except Exception:
                        parsed = None

            if parsed is None:
                continue

            # tool-calling helper: if the model returned an explicit tool call
            # shape, execute it and supply the result back to the model.
            if isinstance(parsed, dict) and (
                parsed.get("tool_call")
                or parsed.get("tool")
                or parsed.get("web_search")
                or parsed.get("call_tool")
            ):
                try:
                    # support multiple possible shapes; expect a query string
                    query = None
                    # shape: {"tool_call": {"name": "web_search", "arguments": {"query": "..."}}}
                    tc = (
                        parsed.get("tool_call")
                        or parsed.get("tool")
                        or parsed.get("call_tool")
                        or parsed
                    )
                    if isinstance(tc, dict):
                        args = tc.get("arguments") or tc.get("args") or tc
                        if isinstance(args, dict):
                            query = (
                                args.get("query") or args.get("q") or args.get("search")
                            )
                    if query is None:
                        # fallback: if top-level web_search key present, use it
                        query = parsed.get("web_search")

                    if query:
                        # import local web search and call it
                        from backend.services.web_search import web_search

                        # telemetry for tool call
                        try:
                            if metrics is not None:
                                metrics.llm_tool_calls_total.inc()
                        except Exception:
                            pass
                        t0 = time.time()
                        result = None
                        try:
                            result = web_search(str(query))
                            if metrics is not None:
                                try:
                                    metrics.llm_tool_calls_success.inc()
                                    metrics.llm_tool_call_latency_seconds.observe(
                                        time.time() - t0
                                    )
                                except Exception:
                                    pass
                        except Exception as e:
                            logger.exception("web_search tool call failed: %s", e)
                            if metrics is not None:
                                try:
                                    metrics.llm_tool_calls_failed.inc()
                                except Exception:
                                    pass
                            result = ""
                        # append tool result to prompt and retry generation
                        prompt = prompt + "\n\n[web_search result]\n" + str(result)
                        continue
                except Exception:
                    # on any failure, ignore and continue parsing attempt
                    pass

            if isinstance(parsed, list) and parsed:
                if isinstance(parsed[0], dict):
                    parsed = parsed[0]

            if not isinstance(parsed, dict):
                continue

            try:
                vf = QualitativeFeatures.parse_obj(parsed)
                try:
                    if metrics is not None:
                        metrics.llm_structured_accepted.inc()
                except Exception:
                    pass
                return vf.dict()
            except ValidationError as ve:
                # structured logging for validation failures (truncated parsed sample)
                try:
                    sample = str(parsed)
                    if len(sample) > 1000:
                        sample = sample[:1000] + "..."
                except Exception:
                    sample = "<unserializable>"
                logger.warning(
                    {
                        "event": "llm_schema_validation",
                        "player": player_name,
                        "sample": sample,
                        "error": str(ve),
                    }
                )
                try:
                    if metrics is not None:
                        metrics.llm_schema_validation_failures.inc()
                except Exception:
                    pass
                coerced = self._coerce_partial(parsed)
                if coerced:
                    try:
                        vf = QualitativeFeatures.parse_obj(coerced)
                        try:
                            if metrics is not None:
                                metrics.llm_structured_coerced.inc()
                        except Exception:
                            pass
                        return vf.dict()
                    except ValidationError:
                        try:
                            if metrics is not None:
                                metrics.llm_structured_invalid.inc()
                        except Exception:
                            pass
                continue

        # fallback heuristics
        lower = (text or "").lower()
        injury = (
            -0.5
            if any(
                k in lower
                for k in (
                    "injur",
                    "sprain",
                    "strain",
                    "out",
                    "questionable",
                    "doubtful",
                )
            )
            else 0.0
        )
        morale = (
            50 if any(k in lower for k in ("morale", "confidence", "motivated")) else 50
        )
        motivation = (
            1.0
            if any(k in lower for k in ("contract", "extension", "contract year"))
            else 0.5
        )
        trade = 0.0
        return {
            "injury_status": "healthy" if injury == 0.0 else "questionable",
            "morale_score": int(morale),
            "news_sentiment": float(injury),
            "trade_sentiment": float(trade),
            "motivation": float(motivation),
        }

    def _coerce_partial(self, j: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            out = {
                "injury_status": str(
                    j.get("injury_status")
                    or j.get("injury")
                    or j.get("injuryStatus")
                    or "healthy"
                ),
                "morale_score": int(
                    float(
                        j.get("morale_score")
                        or j.get("morale")
                        or j.get("moraleScore")
                        or 50
                    )
                ),
                "news_sentiment": float(
                    j.get("news_sentiment") or j.get("sentiment") or 0.0
                ),
                "trade_sentiment": float(
                    j.get("trade_sentiment") or j.get("tradeSentiment") or 0.0
                ),
                "motivation": float(
                    j.get("motivation") or j.get("motivation_score") or 0.5
                ),
            }
            return out
        except Exception:
            return None

    def _cache_key(self, player_name: str, source_id: str) -> str:
        return f"llm_feat:{player_name}:{source_id}"

    def _get_cached(self, key: str) -> Optional[Dict[str, float]]:
        if self.redis:
            try:
                v = self.redis.get(key)
                if v:
                    return json.loads(v)
            except Exception:
                logger.exception("Redis read failed for %s", key)
        return self._cache.get(key)

    def _set_cached(self, key: str, value: Dict[str, float]) -> None:
        if self.redis:
            try:
                self.redis.set(key, json.dumps(value), ex=self.ttl)
                return
            except Exception:
                logger.exception("Redis write failed for %s", key)
        self._cache[key] = value

    def _ollama_request_with_retries(
        self, prompt: str, max_attempts: int = 3, backoff_factor: float = 1.0
    ) -> Optional[str]:
        """Call Ollama HTTP endpoint with optional streaming and retries.

        This mirrors the helper used in earlier versions and is exercised by
        tests that monkeypatch `requests.post` to return streaming lines.
        """
        try:
            import requests
        except Exception:
            logger.debug("requests not available; skipping ollama provider")
            return None

        url = os.environ.get("OLLAMA_URL")
        api_key = os.environ.get("OLLAMA_CLOUD_API_KEY") or os.environ.get(
            "OLLAMA_API_KEY"
        )
        if api_key and not url:
            url = "https://api.ollama.com"
        if not url:
            url = "http://localhost:11434"

        stream_enabled = os.environ.get("OLLAMA_STREAM", "false").lower() in (
            "1",
            "true",
            "yes",
        )

        attempts = 0
        max_wait = float(os.environ.get("OLLAMA_MAX_WAIT_SECONDS", "60"))
        while attempts < max_attempts:
            try:
                base = url.rstrip("/")
                if "ollama.com" in base:
                    api_path = base + "/api/chat"
                    payload = {
                        "model": self.default_model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": stream_enabled,
                    }
                else:
                    # local Ollama HTTP API uses /api/generate (not /v1/generate)
                    api_path = base + "/api/generate"
                    # include both keys for compatibility and expose stream flag
                    payload = {
                        "model": self.default_model,
                        "input": prompt,
                        "prompt": prompt,
                        "stream": stream_enabled,
                    }

                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                timeout = float(os.environ.get("OLLAMA_TIMEOUT", "10"))

                if stream_enabled:
                    resp = requests.post(
                        api_path,
                        json=payload,
                        headers=headers or None,
                        timeout=timeout,
                        stream=True,
                    )
                    resp.raise_for_status()
                    collected = []
                    for raw_line in resp.iter_lines(decode_unicode=True):
                        if raw_line is None:
                            continue
                        line = raw_line.strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            line = line[len("data:") :].strip()
                        if line == "[DONE]":
                            break
                        try:
                            chunk = json.loads(line)
                        except Exception:
                            chunk = line
                        if isinstance(chunk, str):
                            collected.append(chunk)
                        elif isinstance(chunk, dict):
                            if "content" in chunk:
                                collected.append(str(chunk.get("content") or ""))
                            elif "text" in chunk:
                                collected.append(str(chunk.get("text") or ""))
                            elif "output" in chunk and isinstance(
                                chunk["output"], list
                            ):
                                for item in chunk["output"]:
                                    if isinstance(item, dict):
                                        collected.append(
                                            item.get("content")
                                            or item.get("text")
                                            or ""
                                        )
                                    elif isinstance(item, str):
                                        collected.append(item)
                    if collected:
                        return "\n".join([c for c in collected if c])
                    # fallthrough

                resp = requests.post(
                    api_path, json=payload, headers=headers or None, timeout=timeout
                )
                resp.raise_for_status()
                # prefer JSON when available
                try:
                    data = resp.json()
                except Exception:
                    data = None

                if isinstance(data, dict):
                    if "outputs" in data and isinstance(data["outputs"], list):
                        out0 = data["outputs"][0]
                        if isinstance(out0, dict):
                            return (
                                out0.get("content")
                                or out0.get("text")
                                or json.dumps(out0)
                            )
                        return str(out0)
                    if "output" in data and isinstance(data["output"], list):
                        pieces = []
                        for it in data["output"]:
                            if isinstance(it, dict):
                                pieces.append(it.get("content") or it.get("text") or "")
                            elif isinstance(it, str):
                                pieces.append(it)
                        return "\n".join(pieces).strip()
                    if "text" in data:
                        return data.get("text")

                    # find nested text
                    def _find_text(obj):
                        if isinstance(obj, str):
                            return obj
                        if isinstance(obj, dict):
                            for v in obj.values():
                                t = _find_text(v)
                                if t:
                                    return t
                        if isinstance(obj, list):
                            for v in obj:
                                t = _find_text(v)
                                if t:
                                    return t
                        return None

                    t = _find_text(data)
                    if t:
                        return t

                if resp.text:
                    return resp.text
            except Exception as e:
                attempts += 1
                import random
                import time

                base_wait = backoff_factor * (2 ** (attempts - 1))
                jitter = random.uniform(0, min(1.0, base_wait))
                wait = min(max_wait, base_wait + jitter)
                logger.warning(
                    "Ollama request failed (attempt %s/%s): %s — retrying in %.1fs",
                    attempts,
                    max_attempts,
                    e,
                    wait,
                )
                time.sleep(wait)
        logger.error("Ollama request failed after %s attempts", max_attempts)
        return None

    # -------------------- Embedding + Similarity helpers --------------------
    def generate_embedding(
        self, text: str, model: Optional[str] = None
    ) -> Optional[List[float]]:
        """Generate an embedding vector for `text` using the Ollama client.

        Returns a single vector (list of floats) or None.
        """
        import time as _time

        try:
            from backend.services import metrics
        except Exception:
            metrics = None

        model = model or self.default_model
        _start = _time.time()
        emb = None
        try:
            # try live embeddings via the client wrapper
            if hasattr(self.client, "embeddings"):
                emb = self.client.embeddings(model=model, input=text)
            else:
                # attempt to call underlying client directly
                try:
                    emb = self.client._client.embeddings(model=model, input=text)  # type: ignore
                except Exception:
                    try:
                        emb = self.client._client.embed(text)  # type: ignore
                    except Exception:
                        emb = None

            # if API returns nested shapes, extract vector
            if emb is not None:
                logger.info(
                    "generate_embedding: obtained live embedding from client for model=%s (text len=%d)",
                    model,
                    len(text or ""),
                )
                # Some clients return plain lists, dicts with `embedding`, or
                # custom response objects (e.g. EmbedResponse) with `embedding`,
                # `data` or `embeddings` attributes. Normalize these shapes.
                try:
                    # Empty list -> treat as failure so fallback can run
                    if isinstance(emb, list) and len(emb) == 0:
                        emb = None

                    # Dict shape: {'embedding': [...]} or [{'embedding': [...]}, ...]
                    if (
                        isinstance(emb, dict)
                        and "embedding" in emb
                        and isinstance(emb["embedding"], (list, tuple))
                    ):
                        self._last_embedding_source = "live"
                        return emb["embedding"]

                    if (
                        isinstance(emb, list)
                        and emb
                        and isinstance(emb[0], (int, float))
                    ):
                        self._last_embedding_source = "live"
                        return emb

                    if (
                        isinstance(emb, list)
                        and emb
                        and isinstance(emb[0], dict)
                        and "embedding" in emb[0]
                    ):
                        self._last_embedding_source = "live"
                        return emb[0]["embedding"]

                    # Object-like shapes: try common attributes
                    if not isinstance(emb, (dict, list, tuple)):
                        # try `.embedding` attribute
                        vec = None
                        if hasattr(emb, "embedding"):
                            try:
                                tmp = getattr(emb, "embedding")
                                if isinstance(tmp, (list, tuple)) and tmp:
                                    vec = list(tmp)
                            except Exception:
                                pass

                        # try `.data` -> list of {"embedding": [...]}
                        if vec is None and hasattr(emb, "data"):
                            try:
                                d = getattr(emb, "data")
                                if isinstance(d, list) and d:
                                    first = d[0]
                                    if isinstance(first, dict) and "embedding" in first:
                                        vec = first["embedding"]
                            except Exception:
                                pass

                        # try `.embeddings` attribute
                        if vec is None and hasattr(emb, "embeddings"):
                            try:
                                e = getattr(emb, "embeddings")
                                if (
                                    isinstance(e, list)
                                    and e
                                    and isinstance(e[0], (list, tuple))
                                ):
                                    vec = list(e[0])
                            except Exception:
                                pass

                        # last resort: if emb is iterable of numbers, coerce to list
                        if vec is None:
                            try:
                                it = list(emb)
                                if it and all(isinstance(x, (int, float)) for x in it):
                                    vec = it
                            except Exception:
                                vec = None

                        if vec is not None:
                            self._last_embedding_source = "live"
                            return vec
                except Exception:
                    # normalization shouldn't crash the main flow
                    pass
        except Exception:
            emb = None

        # If live embeddings failed, optionally fall back to deterministic local embedding.
        # Production-safe default: if `OLLAMA_EMBEDDINGS_FALLBACK` is not set and
        # the runtime environment indicates production, disable fallback.
        try:
            fb_env = os.environ.get("OLLAMA_EMBEDDINGS_FALLBACK")
            if fb_env is not None:
                allow_fb = str(fb_env).lower() in ("1", "true", "yes")
            else:
                # infer from common environment vars
                env = (
                    os.environ.get("ENV")
                    or os.environ.get("APP_ENV")
                    or os.environ.get("FLASK_ENV")
                    or os.environ.get("PYTHON_ENV")
                    or ""
                ).lower()
                allow_fb = False if env in ("production", "prod") else True
        except Exception:
            allow_fb = True

        if (emb is None) and allow_fb:
            try:
                import hashlib
                import random

                dim = int(os.environ.get("OLLAMA_EMBEDDING_DIM", "384"))
                h = hashlib.sha256(text.encode("utf-8")).hexdigest()
                seed = int(h[:16], 16)
                rnd = random.Random(seed)
                vec = [rnd.uniform(-1.0, 1.0) for _ in range(dim)]
                logger.info(
                    "generate_embedding: using deterministic fallback embedding (dim=%d)",
                    dim,
                )
                self._last_embedding_source = "fallback"
                return vec
            except Exception:
                return None

        # record metrics
        _dur = _time.time() - _start
        try:
            if metrics is not None:
                metrics.embedding_requests_total.inc()
                metrics.embedding_latency_seconds.observe(_dur)
                if emb is not None:
                    metrics.embedding_success_total.inc()
        except Exception:
            # metrics should never break main logic
            pass

        if emb is None and not allow_fb:
            # In production we prefer failing fast and logging when live embeddings
            # are unavailable rather than silently using deterministic vectors.
            logger.error(
                "generate_embedding: live embedding failed and fallback disabled (production mode)"
            )
            self._last_embedding_source = None
            return None

        return None

    def index_texts(
        self,
        items: List[Tuple[str, str, Optional[Dict[str, Any]]]],
        model: Optional[str] = None,
    ) -> List[str]:
        """Index a list of items into the vector store.

        `items` is a list of tuples: (id, text, metadata).
        Returns list of ids successfully indexed.
        """
        indexed = []
        for id, text, meta in items:
            try:
                emb = self.generate_embedding(text, model=model)
                if emb:
                    self.vector_store.add(id, emb, meta or {})
                    indexed.append(id)
            except Exception:
                continue
        return indexed

    def similarity_with_history(
        self, current_text: str, top_k: int = 3, model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Compute similarity features between `current_text` and indexed history.

        Returns a dict with `top_matches` list and summary features.
        """
        emb = self.generate_embedding(current_text, model=model)
        if emb is None:
            return {
                "top_matches": [],
                "max_similarity": 0.0,
                "avg_topk_similarity": 0.0,
            }
        results = self.vector_store.search(emb, top_k=top_k)
        scores = [r["score"] for r in results]
        max_sim = float(scores[0]) if scores else 0.0
        avg_sim = float(sum(scores) / len(scores)) if scores else 0.0
        return {
            "top_matches": results,
            "max_similarity": max_sim,
            "avg_topk_similarity": avg_sim,
        }

    def fetch_news_and_extract(
        self, player_name: str, source_id: str, text_fetcher
    ) -> Dict[str, float]:
        """Fetch text via `text_fetcher` and return numeric features.

        Uses structured extraction when available; otherwise falls back to
        deterministic heuristics. Results are cached in-process keyed by
        `(player_name, source_id)` to make repeated calls stable for tests.
        """
        key = f"{player_name}::{source_id}"
        if key in self._cache:
            return self._cache[key]

        try:
            text = text_fetcher(player_name)
        except Exception:
            text = ""

        # Try structured extraction first
        structured = {}
        try:
            structured = self.extract_from_text(player_name, text)
        except Exception:
            structured = {}

        if structured:
            # normalize morale_score (schema uses 0-100) to [-1.0, 1.0]
            ms = structured.get("morale_score")
            try:
                msf = float(ms) if ms is not None else 50.0
                morale_norm = max(-1.0, min(1.0, (msf - 50.0) / 50.0))
            except Exception:
                morale_norm = 0.0
            out = {
                "injury_sentiment": float(structured.get("news_sentiment") or 0.0),
                "morale_score": float(morale_norm),
                "motivation": float(structured.get("motivation") or 0.0),
                "coaching_change_impact": 0.0,
            }
            self._cache[key] = out
            return out

        # Deterministic heuristic fallback
        lower = (text or "").lower()
        injury = (
            -1.0
            if any(
                k in lower
                for k in (
                    "injur",
                    "sprain",
                    "strain",
                    "out",
                    "questionable",
                    "doubtful",
                )
            )
            else 0.0
        )
        morale = (
            1.0
            if any(k in lower for k in ("morale", "confidence", "motivated"))
            else 0.0
        )
        motivation = (
            1.0
            if any(k in lower for k in ("contract", "extension", "contract year"))
            else 0.0
        )
        coaching = (
            1.0
            if any(
                k in lower
                for k in ("coach", "coaching change", "coach fired", "coach hired")
            )
            else 0.0
        )

        out = {
            "injury_sentiment": float(injury),
            "morale_score": float(morale),
            "motivation": float(motivation),
            "coaching_change_impact": float(coaching),
        }
        self._cache[key] = out
        return out


_default_llm_service: Optional[LLMFeatureService] = None


def create_default_service(default_model: Optional[str] = None) -> LLMFeatureService:
    global _default_llm_service
    if _default_llm_service is None:
        # allow selecting a production vector store via env var VECTOR_STORE=chroma
        vector_store = None
        try:
            vs = os.environ.get("VECTOR_STORE", "").lower()
            if vs == "chroma":
                try:
                    from backend.services.chroma_vector_store import ChromaVectorStore

                    persist = os.environ.get("CHROMA_PERSIST_DIR")
                    vector_store = ChromaVectorStore(persist_directory=persist)
                except Exception:
                    logger.exception(
                        "ChromaVectorStore requested but failed to initialize; falling back to InMemoryVectorStore"
                    )
                    vector_store = None
        except Exception:
            vector_store = None
        _default_llm_service = LLMFeatureService(
            default_model=default_model, vector_store=vector_store
        )
    return _default_llm_service


if __name__ == "__main__":
    svc = create_default_service()
    sample = "Player suffered a minor ankle sprain but is listed as questionable; trade rumors are low; morale seems high."
    print(svc.extract_from_text("Test Player", sample))
