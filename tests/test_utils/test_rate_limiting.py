"""Tests for pymtg.utils.rate_limiting module.

This module tests the RateLimiter class including configuration management,
state tracking, and resource cleanup when configurations are removed.
"""

import unittest

from pymtg.utils.rate_limiting import (
    RateLimitConfig,
    RateLimiter,
)


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


if __name__ == "__main__":
    unittest.main()
