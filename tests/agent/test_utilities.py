"""Tests for agent utility modules — decorators, constants, validation, rate_limit."""
from __future__ import annotations

import time
import pytest

from agent.decorators import retry, timed, safe_call, cached_property
from agent.validation import (
    validate_non_empty_string,
    validate_positive_int,
    validate_url,
    validate_semver,
    validate_dataclass,
    ValidationResult,
)
from agent.rate_limit import TokenBucket, SlidingWindowRateLimiter
from agent.stage_errors import StageResult, StageError, Severity, stage_handler, summarize_stages
from agent.constants import RETRYABLE_STATUS_CODES, DEFAULT_MAX_ITERATIONS


# ── Decorators ────────────────────────────────────────────────

class TestRetry:
    def test_succeeds_first_try(self):
        call_count = 0
        @retry(max_attempts=3, delay=0.01)
        def func():
            nonlocal call_count
            call_count += 1
            return "ok"
        assert func() == "ok"
        assert call_count == 1

    def test_retries_on_failure(self):
        call_count = 0
        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"
        assert func() == "ok"
        assert call_count == 3

    def test_raises_after_max_attempts(self):
        @retry(max_attempts=2, delay=0.01)
        def func():
            raise ValueError("always fails")
        with pytest.raises(ValueError, match="always fails"):
            func()


class TestTimed:
    def test_returns_result(self):
        @timed
        def func():
            return 42
        assert func() == 42


class TestSafeCall:
    def test_returns_default_on_error(self):
        @safe_call(default="fallback")
        def func():
            raise RuntimeError("oops")
        assert func() == "fallback"

    def test_returns_result_on_success(self):
        @safe_call(default="fallback")
        def func():
            return "success"
        assert func() == "success"


class TestCachedProperty:
    def test_caches_result(self):
        class MyClass:
            call_count = 0
            @cached_property
            def value(self):
                self.call_count += 1
                return 42
        obj = MyClass()
        assert obj.value == 42
        assert obj.value == 42  # cached
        assert obj.call_count == 1


# ── Validation ────────────────────────────────────────────────

class TestValidation:
    def test_non_empty_string_ok(self):
        assert validate_non_empty_string("hello", "field") == "hello"

    def test_non_empty_string_fail(self):
        with pytest.raises(ValueError):
            validate_non_empty_string("", "field")

    def test_positive_int_ok(self):
        assert validate_positive_int(5, "field") == 5

    def test_positive_int_fail(self):
        with pytest.raises(ValueError):
            validate_positive_int(-1, "field")

    def test_url_ok(self):
        assert validate_url("https://example.com", "url") == "https://example.com"

    def test_url_fail(self):
        with pytest.raises(ValueError):
            validate_url("not-a-url", "url")

    def test_semver_ok(self):
        assert validate_semver("1.2.3", "version") == "1.2.3"

    def test_semver_fail(self):
        with pytest.raises(ValueError):
            validate_semver("1.2", "version")


# ── Rate Limiting ─────────────────────────────────────────────

class TestTokenBucket:
    def test_allows_within_capacity(self):
        bucket = TokenBucket(rate=10, capacity=5)
        for _ in range(5):
            assert bucket.consume(1) is True

    def test_rejects_over_capacity(self):
        bucket = TokenBucket(rate=0.1, capacity=2)
        assert bucket.consume(1) is True
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False

    def test_refills_over_time(self):
        bucket = TokenBucket(rate=100, capacity=1)
        assert bucket.consume(1) is True
        assert bucket.consume(1) is False
        time.sleep(0.05)  # 50ms → 5 tokens at rate=100
        assert bucket.consume(1) is True


class TestSlidingWindow:
    def test_allows_within_limit(self):
        limiter = SlidingWindowRateLimiter(max_calls=3, window_seconds=10)
        assert limiter.allow() is True
        assert limiter.allow() is True
        assert limiter.allow() is True

    def test_rejects_over_limit(self):
        limiter = SlidingWindowRateLimiter(max_calls=2, window_seconds=10)
        limiter.allow()
        limiter.allow()
        assert limiter.allow() is False


# ── Stage Errors ──────────────────────────────────────────────

class TestStageErrors:
    def test_stage_handler_success(self):
        @stage_handler("test_stage")
        def func():
            return "done"
        assert func() == "done"

    def test_stage_handler_failure_reraise(self):
        @stage_handler("test_stage", reraise=True)
        def func():
            raise ValueError("fail")
        with pytest.raises(ValueError):
            func()

    def test_stage_handler_failure_no_reraise(self):
        @stage_handler("test_stage", reraise=False, default="fallback")
        def func():
            raise ValueError("fail")
        assert func() == "fallback"

    def test_summarize_stages(self):
        results = [
            StageResult(stage="a", success=True, duration_s=1.0),
            StageResult(stage="b", success=False, duration_s=2.0,
                       error=StageError(stage="b", message="oops")),
        ]
        summary = summarize_stages(results)
        assert summary["total_stages"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["pass_rate"] == "50.0%"
        assert len(summary["errors"]) == 1


# ── Constants ─────────────────────────────────────────────────

class TestConstants:
    def test_retryable_codes_include_429(self):
        assert 429 in RETRYABLE_STATUS_CODES

    def test_default_max_iterations(self):
        assert DEFAULT_MAX_ITERATIONS == 90

    def test_retryable_codes_are_frozenset(self):
        assert isinstance(RETRYABLE_STATUS_CODES, frozenset)
