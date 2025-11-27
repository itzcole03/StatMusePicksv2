"""Standalone token-bucket implementation for NBA API rate limiting.

This module provides a simple, thread-safe TokenBucket class that can be
injected into clients that need rate-limiting behavior.
"""

from __future__ import annotations

import threading
import time
from typing import Optional


class TokenBucket:
    """A simple thread-safe token bucket implementation.

    - `rpm`: allowed requests per minute.
    - `max_tokens`: bucket capacity (defaults to `rpm`).
    """

    def __init__(self, rpm: int = 20, max_tokens: Optional[float] = None):
        self.rpm = int(rpm)
        self.capacity = float(max_tokens or self.rpm)
        self._tokens = float(self.capacity)
        self._last_refill = time.time()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                now = time.time()
                elapsed = now - self._last_refill
                if elapsed > 0:
                    refill = elapsed * (self.rpm / 60.0)
                    self._tokens = min(self.capacity, self._tokens + refill)
                    self._last_refill = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
            time.sleep(0.05)
        return False


__all__ = ["TokenBucket"]
