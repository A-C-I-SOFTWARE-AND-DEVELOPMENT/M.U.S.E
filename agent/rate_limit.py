"""Rate limiting utilities for API calls and user actions.

Provides token bucket and sliding window rate limiters.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import TypeVar

T = TypeVar("T")


@dataclass
class TokenBucket:
    """Token bucket rate limiter.

    Tokens accumulate at a fixed rate up to capacity.
    Each consume() takes tokens; returns False if insufficient.

    Example::

        bucket = TokenBucket(rate=10, capacity=100)
        if bucket.consume(5):
            # proceed with request
    """
    rate: float  # tokens per second
    capacity: float  # max tokens
    _tokens: float = field(default=0.0, init=False)
    _last_refill: float = field(default_factory=time.monotonic, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        self._tokens = self.capacity

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if successful."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def wait_time(self, tokens: float = 1.0) -> float:
        """Time in seconds until enough tokens are available."""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                return 0.0
            return (tokens - self._tokens) / self.rate

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now


@dataclass
class SlidingWindowRateLimiter:
    """Sliding window rate limiter using a deque.

    Tracks timestamps of recent calls and rejects if the count
    in the window exceeds the limit.

    Example::

        limiter = SlidingWindowRateLimiter(max_calls=100, window_seconds=60)
        if limiter.allow():
            # proceed
    """
    max_calls: int
    window_seconds: float
    _timestamps: list[float] = field(default_factory=list, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def allow(self) -> bool:
        """Check if a new call is allowed under the rate limit."""
        with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            # Remove expired timestamps
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            if len(self._timestamps) >= self.max_calls:
                return False
            self._timestamps.append(now)
            return True

    @property
    def current_count(self) -> int:
        """Number of calls in the current window."""
        with self._lock:
            cutoff = time.monotonic() - self.window_seconds
            return sum(1 for t in self._timestamps if t > cutoff)
