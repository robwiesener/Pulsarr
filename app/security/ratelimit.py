"""Pulsarr - Rate limiter.

Sliding window per key (IP + bucket). Houdt een deque van
timestamps bij per key en telt hoeveel er in het venster vallen.
In-memory, verliest state bij container-restart.
"""

from collections import deque
import threading
import time


class RateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, max_keys: int = 10000):
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}
        self._max_keys = max_keys

    def check(
        self,
        key: str,
        limit: int,
        window: float,
    ) -> tuple[bool, int, int]:
        """Check of key onder limit zit.

        Returns:
            (allowed, remaining, retry_after)
            retry_after is 0 als allowed=True.
        """
        now = time.monotonic()
        cutoff = now - window

        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = deque()
                self._hits[key] = hits

            while hits and hits[0] < cutoff:
                hits.popleft()

            if len(hits) >= limit:
                retry_after = max(
                    1, int(hits[0] + window - now) + 1
                )
                return False, 0, retry_after

            hits.append(now)
            remaining = limit - len(hits)

            if len(self._hits) > self._max_keys:
                oldest = next(iter(self._hits))
                del self._hits[oldest]

            return True, remaining, 0

    def reset(self) -> None:
        """Voor tests: wis alle state."""
        with self._lock:
            self._hits.clear()
