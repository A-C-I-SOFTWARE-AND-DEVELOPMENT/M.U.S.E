"""HTTP client utilities with connection pooling, retry, and timeout.

Provides a shared httpx.Client with sensible defaults for the agent,
avoiding the overhead of creating a new client per request.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from agent.constants import (
    CONNECTION_POOL_SIZE,
    DEFAULT_API_TIMEOUT_SECONDS,
    MAX_API_RETRIES,
    API_RETRY_BASE_DELAY,
    API_RETRY_MAX_DELAY,
    RETRYABLE_STATUS_CODES,
)

logger = logging.getLogger(__name__)

# Shared client instance (lazy-initialized)
_client: httpx.Client | None = None


def get_http_client() -> httpx.Client:
    """Get the shared HTTP client with connection pooling.

    Returns a singleton httpx.Client configured with:
    - Connection pooling (keep-alive)
    - Default timeout
    - HTTP/2 support
    """
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            timeout=httpx.Timeout(DEFAULT_API_TIMEOUT_SECONDS),
            limits=httpx.Limits(
                max_connections=CONNECTION_POOL_SIZE,
                max_keepalive_connections=CONNECTION_POOL_SIZE // 2,
                keepalive_expiry=30.0,
            ),
            http2=True,
            follow_redirects=True,
        )
    return _client


def close_http_client() -> None:
    """Close the shared HTTP client. Call on shutdown."""
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
        _client = None


def is_retryable_status(status_code: int) -> bool:
    """Check if an HTTP status code warrants a retry."""
    return status_code in RETRYABLE_STATUS_CODES


def is_retryable_exception(exc: Exception) -> bool:
    """Check if an exception is a transient network error worth retrying."""
    return isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout,
                            httpx.ConnectError, httpx.RemoteProtocolError))
