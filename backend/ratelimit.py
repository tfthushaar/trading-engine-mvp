"""
In-process sliding-window rate limiter.

Serverless instances each keep their own counters, so limits are per instance (a soft cap). That is enough
to stop a single visitor from exhausting the shared AI quota or monopolising CPU for model training.
"""
from __future__ import annotations

import contextvars
import threading
import time
from collections import defaultdict, deque

client_ip: contextvars.ContextVar[str] = contextvars.ContextVar("client_ip", default="unknown")

_lock = threading.Lock()
_events: dict[str, deque] = defaultdict(deque)


class RateLimited(Exception):
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


def _prune(q: deque, now: float, window: float) -> None:
    while q and q[0] <= now - window:
        q.popleft()


def hit(bucket: str, limit: int, window_s: float, consume: bool = True) -> None:
    """Record one event in `bucket`; raise RateLimited if more than `limit` happened within `window_s`."""
    now = time.time()
    with _lock:
        q = _events[bucket]
        _prune(q, now, window_s)
        if len(q) >= limit:
            raise RateLimited("rate limit reached", int(q[0] + window_s - now) + 1)
        if consume:
            q.append(now)
        if len(_events) > 20000:  # bound memory under abuse: drop buckets with no recent activity
            for k in [k for k, v in _events.items() if not v or v[-1] <= now - 86400]:
                _events.pop(k, None)


def check_all(rules: list[tuple[str, int, float]]) -> None:
    """Check every rule first, then consume from all of them, so a rejected call costs nothing."""
    for bucket, limit, window in rules:
        hit(bucket, limit, window, consume=False)
    for bucket, limit, window in rules:
        hit(bucket, limit, window)


def remaining(bucket: str, limit: int, window_s: float) -> int:
    now = time.time()
    with _lock:
        q = _events[bucket]
        _prune(q, now, window_s)
        return max(0, limit - len(q))
