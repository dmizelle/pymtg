"""Tests for pymtg.utils.rate_limiting module.

This module tests the RateLimiter class including configuration management,
state tracking, resource cleanup when configurations are removed, and the
RateLimitGuard context manager behavior for recording requests.
"""

import unittest

from pymtg.utils.rate_limiting import (
    RateLimitConfig,
    RateLimiter,
)


class _TestError(Exception):
    """Custom exception for testing guard exception handling."""

    pass


class TestRateLimiterConfigManagement(unittest.TestCase):
    """Tests for RateLimiter configuration add/remove/get operations."""

    def setUp(self) -> None:
        """Set up a fresh RateLimiter for each test."""
        self.limiter = RateLimiter()

    def test_add_config(self) -> None:
        """Tests that add_config stores a configuration for a provider."""
        config = RateLimitConfig(requests_per_second=5)
        self.limiter.add_config("test_provider", config)
        retrieved = self.limiter.get_config("test_provider")
        assert retrieved is not None
        self.assertEqual(retrieved.requests_per_second, 5)

    def test_remove_config_returns_true_when_found(self) -> None:
        """Tests that remove_config returns True when provider exists."""
        config = RateLimitConfig(requests_per_second=5)
        self.limiter.add_config("test_provider", config)
        result = self.limiter.remove_config("test_provider")
        self.assertTrue(result)

    def test_remove_config_returns_false_when_not_found(self) -> None:
        """Tests that remove_config returns False when provider is absent."""
        result = self.limiter.remove_config("nonexistent")
        self.assertFalse(result)

    def test_remove_config_cleans_up_config(self) -> None:
        """Tests that remove_config removes the configuration entry."""
        config = RateLimitConfig(requests_per_second=5)
        self.limiter.add_config("test_provider", config)
        self.limiter.remove_config("test_provider")
        self.assertIsNone(self.limiter.get_config("test_provider"))

    def test_remove_config_cleans_up_state(self) -> None:
        """Tests that remove_config also removes accumulated state.

        Verifies the fix for issue #138: stale state entries should not
        accumulate for providers whose configs have been removed.
        """
        config = RateLimitConfig(requests_per_second=5)
        self.limiter.add_config("test_provider", config)

        # Access the provider to create a state entry via defaultdict
        self.limiter.check("test_provider")
        self.assertIn("test_provider", self.limiter.states)

        # Remove config should also clean up state
        self.limiter.remove_config("test_provider")
        self.assertNotIn("test_provider", self.limiter.states)

    def test_remove_config_cleans_up_state_after_record(self) -> None:
        """Tests state cleanup after requests have been recorded.

        Ensures state with recorded timestamps is properly removed when
        the config is removed, preventing memory leaks.
        """
        config = RateLimitConfig(requests_per_second=5, burst_size=5)
        self.limiter.add_config("test_provider", config)

        # Record some requests to populate state timestamps
        self.limiter._record("test_provider")
        self.limiter._record("test_provider")
        self.assertEqual(len(self.limiter.states["test_provider"].timestamps), 2)

        # Remove config should clean up state entirely
        self.limiter.remove_config("test_provider")
        self.assertNotIn("test_provider", self.limiter.states)

    def test_remove_config_does_not_affect_other_providers(self) -> None:
        """Tests that removing one provider's config doesn't affect others."""
        config1 = RateLimitConfig(requests_per_second=5)
        config2 = RateLimitConfig(requests_per_minute=30)
        self.limiter.add_config("provider_a", config1)
        self.limiter.add_config("provider_b", config2)

        # Access both to create state entries
        self.limiter.check("provider_a")
        self.limiter.check("provider_b")

        # Remove only provider_a
        self.limiter.remove_config("provider_a")

        # provider_b should be unaffected
        self.assertIsNone(self.limiter.get_config("provider_a"))
        self.assertIsNotNone(self.limiter.get_config("provider_b"))
        self.assertNotIn("provider_a", self.limiter.states)
        self.assertIn("provider_b", self.limiter.states)

    def test_remove_config_idempotent_for_state(self) -> None:
        """Tests that removing a config twice does not raise errors."""
        config = RateLimitConfig(requests_per_second=5)
        self.limiter.add_config("test_provider", config)
        self.limiter.check("test_provider")

        self.limiter.remove_config("test_provider")
        # Second removal should return False and not raise
        result = self.limiter.remove_config("test_provider")
        self.assertFalse(result)


class TestRateLimiterCheckAndRecord(unittest.TestCase):
    """Tests for RateLimiter check and record operations."""

    def setUp(self) -> None:
        """Set up a RateLimiter with a test provider config."""
        self.limiter = RateLimiter(
            {
                "test_provider": RateLimitConfig(
                    requests_per_second=2,
                    burst_size=2,
                ),
            }
        )

    def test_check_allows_request_under_limit(self) -> None:
        """Tests that check returns True when under the rate limit."""
        self.assertTrue(self.limiter.check("test_provider"))

    def test_check_blocks_request_over_limit(self) -> None:
        """Tests that check returns False when rate limit is exceeded."""
        self.limiter._record("test_provider")
        self.limiter._record("test_provider")
        # Now at burst_size limit
        self.assertFalse(self.limiter.check("test_provider"))

    def test_check_allows_unconfigured_provider(self) -> None:
        """Tests that check returns True for providers without config."""
        self.assertTrue(self.limiter.check("unconfigured"))

    def test_check_does_not_create_state_for_unconfigured(self) -> None:
        """Tests that check() does not create state for unconfigured providers.

        Verifies that calling check() for a provider without a config does
        not create a stale state entry, preventing memory leaks.
        """
        self.assertTrue(self.limiter.check("unconfigured"))
        self.assertNotIn("unconfigured", self.limiter.states)

    def test_record_creates_state_entry(self) -> None:
        """Tests that _record creates a state entry for the provider."""
        self.limiter._record("test_provider")
        self.assertIn("test_provider", self.limiter.states)
        self.assertEqual(len(self.limiter.states["test_provider"].timestamps), 1)


class TestRateLimiterFractionalLimits(unittest.TestCase):
    """Tests for fractional rate limit handling.

    Verifies that fractional rate limits are rounded up using math.ceil
    so that fractional rates allow at least one request per window,
    per issue #133.
    """

    def test_fractional_requests_per_second_rounds_up(self) -> None:
        """Tests that 1.5 req/s with 1s window allows 2 requests.

        Without ceil, int(1.5 * 1) = 1, which would under-limit. With
        ceil, math.ceil(1.5 * 1) = 2, the correct upper bound.
        """
        limiter = RateLimiter(
            {
                "frac": RateLimitConfig(
                    requests_per_second=1.5,
                    burst_size=10,
                ),
            }
        )
        # Should allow 2 requests (ceil(1.5)) before blocking
        self.assertTrue(limiter.check("frac"))
        limiter._record("frac")
        self.assertTrue(limiter.check("frac"))
        limiter._record("frac")
        # Third request should be blocked (at limit of 2)
        self.assertFalse(limiter.check("frac"))

    def test_fractional_requests_per_minute_rounds_up(self) -> None:
        """Tests that 1.5 req/min with 60s window allows 2 requests.

        Without ceil, int(1.5 * 60 / 60) = 1. With ceil,
        math.ceil(1.5 * 60 / 60) = 2.
        """
        limiter = RateLimiter(
            {
                "frac": RateLimitConfig(
                    requests_per_minute=1.5,
                    burst_size=10,
                    window_seconds=60,
                ),
            }
        )
        self.assertTrue(limiter.check("frac"))
        limiter._record("frac")
        self.assertTrue(limiter.check("frac"))
        limiter._record("frac")
        self.assertFalse(limiter.check("frac"))

    def test_sub_one_per_second_allows_one_request(self) -> None:
        """Tests that 0.5 req/s with 1s window allows 1 request.

        Without ceil, int(0.5 * 1) = 0, blocking all requests. With
        ceil, math.ceil(0.5 * 1) = 1, allowing a single request.
        """
        limiter = RateLimiter(
            {
                "sub": RateLimitConfig(
                    requests_per_second=0.5,
                    burst_size=10,
                ),
            }
        )
        self.assertTrue(limiter.check("sub"))
        limiter._record("sub")
        self.assertFalse(limiter.check("sub"))

    def test_integer_rate_limit_unchanged_by_ceil(self) -> None:
        """Tests that integer rate limits are unaffected by ceil.

        math.ceil(5 * 1) = 5, same as int(5 * 1) = 5.
        """
        limiter = RateLimiter(
            {
                "int": RateLimitConfig(
                    requests_per_second=5,
                    burst_size=10,
                ),
            }
        )
        # Should allow 5 requests
        for _ in range(5):
            self.assertTrue(limiter.check("int"))
            limiter._record("int")
        self.assertFalse(limiter.check("int"))

    def test_burst_size_caps_rounded_up_max_requests(self) -> None:
        """Tests that burst_size caps the rounded-up max_requests.

        With requests_per_second=1.5 (ceil=2) but burst_size=1, the
        effective limit should be 1, not 2. The min(max_requests,
        burst_size) logic must still apply after ceil.
        """
        limiter = RateLimiter(
            {
                "frac": RateLimitConfig(
                    requests_per_second=1.5,
                    burst_size=1,
                ),
            }
        )
        self.assertTrue(limiter.check("frac"))
        limiter._record("frac")
        # Second request blocked by burst_size cap, not ceil result
        self.assertFalse(limiter.check("frac"))

    def test_fractional_rate_with_custom_window(self) -> None:
        """Tests ceil with a non-standard window_seconds.

        With requests_per_second=1.5 and window_seconds=2,
        max_requests = ceil(1.5 * 2) = 3.
        """
        limiter = RateLimiter(
            {
                "frac": RateLimitConfig(
                    requests_per_second=1.5,
                    burst_size=10,
                    window_seconds=2,
                ),
            }
        )
        for _ in range(3):
            self.assertTrue(limiter.check("frac"))
            limiter._record("frac")
        self.assertFalse(limiter.check("frac"))


class TestRateLimitGuard(unittest.TestCase):
    """Tests for the RateLimitGuard context manager.

    Verifies that the guard records requests only on successful completion
    and skips recording when an exception occurs within the context block,
    per issue #135.
    """

    def setUp(self) -> None:
        """Set up a RateLimiter with a test provider config."""
        self.limiter = RateLimiter(
            {
                "test_provider": RateLimitConfig(
                    requests_per_second=2,
                    burst_size=2,
                ),
            }
        )

    def test_guard_records_on_success(self) -> None:
        """Tests that the guard records a request when no exception occurs."""
        with self.limiter.guard("test_provider"):
            pass
        self.assertEqual(len(self.limiter.states["test_provider"].timestamps), 1)

    def test_guard_does_not_record_on_exception(self) -> None:
        """Tests that the guard skips recording when an exception occurs.

        Verifies the fix for issue #135: failed requests should not be
        counted against the rate limit.
        """
        with self.assertRaises(_TestError):
            with self.limiter.guard("test_provider"):
                raise _TestError("simulated failure")
        self.assertEqual(len(self.limiter.states["test_provider"].timestamps), 0)

    def test_guard_enter_returns_true_when_allowed(self) -> None:
        """Tests that __enter__ returns True when the request can proceed."""
        guard = self.limiter.guard("test_provider")
        result = guard.__enter__()
        self.assertTrue(result)
        guard.__exit__(None, None, None)

    def test_guard_enter_returns_false_when_rate_limited(self) -> None:
        """Tests that __enter__ returns False when rate limit is exceeded.

        When the rate limit is already at capacity, __enter__ should wait
        and return False to indicate the caller had to wait.
        """
        # Fill the burst capacity
        self.limiter._record("test_provider")
        self.limiter._record("test_provider")
        guard = self.limiter.guard("test_provider")
        result = guard.__enter__()
        self.assertFalse(result)
        self.assertTrue(guard.waited)
        guard.__exit__(None, None, None)

    def test_guard_waited_flag_default_false(self) -> None:
        """Tests that the waited flag defaults to False."""
        guard = self.limiter.guard("test_provider")
        self.assertFalse(guard.waited)

    def test_guard_records_only_once_per_context(self) -> None:
        """Tests that the guard records exactly one request per context."""
        with self.limiter.guard("test_provider"):
            pass
        with self.limiter.guard("test_provider"):
            pass
        self.assertEqual(len(self.limiter.states["test_provider"].timestamps), 2)

    def test_guard_does_not_record_multiple_exceptions(self) -> None:
        """Tests that the guard records zero requests on repeated failures."""
        for _ in range(3):
            with self.assertRaises(_TestError):
                with self.limiter.guard("test_provider"):
                    raise _TestError("simulated failure")
        self.assertEqual(len(self.limiter.states["test_provider"].timestamps), 0)


if __name__ == "__main__":
    unittest.main()
