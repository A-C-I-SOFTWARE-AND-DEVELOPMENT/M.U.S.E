"""Reusable decorators for retry logic, caching, and timing."""
from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Retry a function with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts before giving up.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier applied to delay after each failure.
        exceptions: Exception types that should trigger a retry.

    Returns:
        Decorated function that retries on failure.

    Example::

        @retry(max_attempts=3, delay=1.0, exceptions=(ConnectionError, TimeoutError))
        def fetch_data(url):
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.debug(
                            "Attempt %d/%d failed for %s: %s — retrying in %.1fs",
                            attempt, max_attempts, func.__name__, e, current_delay,
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.warning(
                            "All %d attempts exhausted for %s: %s",
                            max_attempts, func.__name__, e,
                        )
            assert last_exception is not None
            raise last_exception

        return wrapper

    return decorator


def cached_property(func: Callable[..., T]) -> property:
    """Like functools.cached_property but returns a proper property descriptor.

    The result is computed once on first access and cached on the instance.
    """
    cached_name = f"_cached_{func.__name__}"

    @functools.wraps(func)
    def getter(self: Any) -> T:
        if not hasattr(self, cached_name):
            setattr(self, cached_name, func(self))
        return getattr(self, cached_name)

    def setter(self: Any, value: T) -> None:
        setattr(self, cached_name, value)

    def deleter(self: Any) -> None:
        if hasattr(self, cached_name):
            delattr(self, cached_name)

    return property(getter, setter, deleter, func.__doc__)


def timed(func: Callable[..., T]) -> Callable[..., T]:
    """Log execution time of a function at DEBUG level.

    Example::

        @timed
        def expensive_operation():
            ...
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.debug("%s completed in %.1fms", func.__name__, elapsed_ms)
        return result

    return wrapper


def safe_call(
    default: Any = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    log: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Wrap a function to return a default value instead of raising.

    Useful for non-critical operations where a failure should not crash
    the caller (e.g., telemetry, metrics, optional features).

    Args:
        default: Value to return if the function raises.
        exceptions: Exception types to catch.
        log: Whether to log the exception at WARNING level.

    Example::

        @safe_call(default=0)
        def get_token_count(text):
            return len(tokenizer.encode(text))
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                if log:
                    logger.warning("safe_call caught %s in %s: %s",
                                   type(e).__name__, func.__name__, e)
                return default

        return wrapper

    return decorator
