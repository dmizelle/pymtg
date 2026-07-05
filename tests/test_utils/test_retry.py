"""Tests for pymtg.utils.retry module.

This module tests the retry configuration, backoff calculation, and retry
decorators to ensure correct behavior including the specific scenario where
TimeoutError is included in retry_exceptions (issue #171).
"""

import unittest
from unittest.mock import MagicMock, patch

from pymtg.exceptions import RateLimitError
from pymtg.utils.retry import (
    DEFAULT_RETRY_CONFIG,
    RetryConfig,
    RetryContext,
    calculate_backoff,
    retry_on_rate_limit,
    retry_with_config,
)


class TestRetryConfig(unittest.TestCase):
    """Tests for RetryConfig configuration class."""

    def test_default_config(self) -> None:
        """Tests that default configuration has expected values."""
        config = RetryConfig()
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.backoff_factor, 0.5)
        self.assertEqual(config.max_backoff, 10.0)
        self.assertTrue(config.jitter)
        self.assertEqual(config.retry_exceptions, (RateLimitError, ConnectionError))
        self.assertTrue(config.retry_on_timeout)
        self.assertTrue(config.respect_retry_after)

    def test_custom_config(self) -> None:
        """Tests that custom configuration values are stored correctly."""
        config = RetryConfig(
            max_retries=5,
            backoff_factor=1.0,
            max_backoff=30.0,
            jitter=False,
            retry_on_timeout=False,
            respect_retry_after=False,
        )
        self.assertEqual(config.max_retries, 5)
        self.assertEqual(config.backoff_factor, 1.0)
        self.assertEqual(config.max_backoff, 30.0)
        self.assertFalse(config.jitter)
        self.assertFalse(config.retry_on_timeout)
        self.assertFalse(config.respect_retry_after)

    def test_custom_retry_exceptions(self) -> None:
        """Tests that custom retry_exceptions are stored correctly."""
        config = RetryConfig(retry_exceptions=(ValueError, KeyError))
        self.assertEqual(config.retry_exceptions, (ValueError, KeyError))

    def test_repr(self) -> None:
        """Tests that __repr__ returns a useful string."""
        config = RetryConfig(max_retries=5, backoff_factor=1.0)
        repr_str = repr(config)
        self.assertIn("max_retries=5", repr_str)
        self.assertIn("backoff_factor=1.0", repr_str)


class TestCalculateBackoff(unittest.TestCase):
    """Tests for calculate_backoff function."""

    def test_backoff_without_jitter(self) -> None:
        """Tests backoff calculation without jitter."""
        # backoff_factor * (2 ** attempt)
        self.assertEqual(calculate_backoff(0, 1.0, 10.0, jitter=False), 1.0)
        self.assertEqual(calculate_backoff(1, 1.0, 10.0, jitter=False), 2.0)
        self.assertEqual(calculate_backoff(2, 1.0, 10.0, jitter=False), 4.0)
        self.assertEqual(calculate_backoff(3, 1.0, 10.0, jitter=False), 8.0)

    def test_backoff_respects_max(self) -> None:
        """Tests that backoff is capped at max_backoff."""
        self.assertEqual(calculate_backoff(10, 1.0, 5.0, jitter=False), 5.0)

    def test_backoff_with_jitter(self) -> None:
        """Tests that jitter produces a value within expected range."""
        with patch("pymtg.utils.retry.random.random", return_value=0.5):
            # jitter_factor = 0.5 + 0.5 = 1.0, so no change
            result = calculate_backoff(0, 1.0, 10.0, jitter=True)
            self.assertEqual(result, 1.0)

        with patch("pymtg.utils.retry.random.random", return_value=1.0):
            # jitter_factor = 0.5 + 1.0 = 1.5
            result = calculate_backoff(0, 1.0, 10.0, jitter=True)
            self.assertEqual(result, 1.5)


class TestRetryOnRateLimit(unittest.TestCase):
    """Tests for retry_on_rate_limit decorator."""

    def test_successful_call_no_retry(self) -> None:
        """Tests that a successful call does not retry."""
        call_count = 0

        @retry_on_rate_limit(max_retries=3)
        def successful_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)

    def test_retry_on_rate_limit_error(self) -> None:
        """Tests that RateLimitError triggers retry."""
        call_count = 0

        @retry_on_rate_limit(max_retries=3, backoff_factor=0.0, jitter=False)
        def flaky_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("Rate limited")
            return "success"

        result = flaky_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 3)

    def test_retry_on_timeout(self) -> None:
        """Tests that TimeoutError triggers retry when retry_on_timeout=True."""
        call_count = 0

        @retry_on_rate_limit(
            max_retries=3, backoff_factor=0.0, jitter=False, retry_on_timeout=True
        )
        def timeout_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timed out")
            return "success"

        result = timeout_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)

    def test_no_retry_on_timeout_when_disabled(self) -> None:
        """Tests that TimeoutError is not retried when retry_on_timeout=False."""
        call_count = 0

        @retry_on_rate_limit(
            max_retries=3, backoff_factor=0.0, jitter=False, retry_on_timeout=False
        )
        def timeout_func() -> str:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Timed out")

        with self.assertRaises(TimeoutError):
            timeout_func()
        self.assertEqual(call_count, 1)

    def test_timeout_in_retry_exceptions_respects_retry_on_timeout(self) -> None:
        """Tests that TimeoutError respects retry_on_timeout even when
        included in retry_exceptions.

        This is the core scenario from issue #171: if TimeoutError is in
        retry_exceptions, it should still be handled by the TimeoutError
        handler (respecting retry_on_timeout), not the retry_exceptions
        handler.
        """
        call_count = 0

        @retry_on_rate_limit(
            max_retries=3,
            backoff_factor=0.0,
            jitter=False,
            retry_on_timeout=False,
            retry_exceptions=(RateLimitError, ConnectionError, TimeoutError),
        )
        def timeout_func() -> str:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Timed out")

        with self.assertRaises(TimeoutError):
            timeout_func()
        self.assertEqual(call_count, 1)

    def test_timeout_in_retry_exceptions_retries_when_enabled(self) -> None:
        """Tests that TimeoutError is retried when included in
        retry_exceptions and retry_on_timeout=True.

        Verifies the TimeoutError handler is used (not retry_exceptions),
        ensuring consistent retry behavior.
        """
        call_count = 0

        @retry_on_rate_limit(
            max_retries=3,
            backoff_factor=0.0,
            jitter=False,
            retry_on_timeout=True,
            retry_exceptions=(RateLimitError, ConnectionError, TimeoutError),
        )
        def timeout_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timed out")
            return "success"

        result = timeout_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)

    def test_max_retries_exceeded(self) -> None:
        """Tests that max retries is respected."""
        call_count = 0

        @retry_on_rate_limit(max_retries=2, backoff_factor=0.0, jitter=False)
        def always_fails() -> str:
            nonlocal call_count
            call_count += 1
            raise RateLimitError("Rate limited")

        with self.assertRaises(RateLimitError):
            always_fails()
        self.assertEqual(call_count, 3)  # initial + 2 retries

    def test_non_retry_exception_not_retried(self) -> None:
        """Tests that non-retry exceptions are not retried."""
        call_count = 0

        @retry_on_rate_limit(max_retries=3, backoff_factor=0.0, jitter=False)
        def value_error_func() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a retry error")

        with self.assertRaises(ValueError):
            value_error_func()
        self.assertEqual(call_count, 1)

    def test_respect_retry_after_header(self) -> None:
        """Tests that Retry-After header is respected."""
        call_count = 0

        @retry_on_rate_limit(
            max_retries=3,
            backoff_factor=0.0,
            jitter=False,
            respect_retry_after=True,
        )
        def rate_limited_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("Rate limited", retry_after=5)
            return "success"

        with patch("pymtg.utils.retry.time.sleep") as mock_sleep:
            result = rate_limited_func()

        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)
        mock_sleep.assert_called_once_with(5.0)


class TestRetryWithConfig(unittest.TestCase):
    """Tests for retry_with_config decorator."""

    def test_successful_call(self) -> None:
        """Tests that a successful call does not retry."""
        config = RetryConfig(max_retries=3, backoff_factor=0.0, jitter=False)

        @retry_with_config(config)
        def successful_func() -> str:
            return "success"

        result = successful_func()
        self.assertEqual(result, "success")

    def test_retry_on_timeout_with_config(self) -> None:
        """Tests that TimeoutError triggers retry with config."""
        call_count = 0
        config = RetryConfig(
            max_retries=3, backoff_factor=0.0, jitter=False, retry_on_timeout=True
        )

        @retry_with_config(config)
        def timeout_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise TimeoutError("Timed out")
            return "success"

        result = timeout_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 2)

    def test_timeout_in_retry_exceptions_with_config(self) -> None:
        """Tests that TimeoutError respects retry_on_timeout when included
        in retry_exceptions, using retry_with_config.

        Verifies the fix for issue #171 applies to retry_with_config as well.
        """
        call_count = 0
        config = RetryConfig(
            max_retries=3,
            backoff_factor=0.0,
            jitter=False,
            retry_on_timeout=False,
            retry_exceptions=(RateLimitError, ConnectionError, TimeoutError),
        )

        @retry_with_config(config)
        def timeout_func() -> str:
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Timed out")

        with self.assertRaises(TimeoutError):
            timeout_func()
        self.assertEqual(call_count, 1)

    def test_default_config_used_when_none(self) -> None:
        """Tests that default config is used when None is passed."""
        call_count = 0

        @retry_with_config(None)
        def successful_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()
        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)


class TestRetryContext(unittest.TestCase):
    """Tests for RetryContext context manager."""

    def test_initial_state(self) -> None:
        """Tests that RetryContext initializes correctly."""
        config = RetryConfig(max_retries=3)
        ctx = RetryContext(config)
        self.assertEqual(ctx.attempt, 0)
        self.assertEqual(ctx.max_attempts, 4)
        self.assertIsNone(ctx.last_exception)

    def test_should_continue(self) -> None:
        """Tests that should_continue returns True when attempts remain."""
        ctx = RetryContext(RetryConfig(max_retries=3))
        self.assertTrue(ctx.should_continue())

    def test_should_continue_false_when_exhausted(self) -> None:
        """Tests that should_continue returns False when exhausted."""
        ctx = RetryContext(RetryConfig(max_retries=1))
        ctx.attempt = 2
        self.assertFalse(ctx.should_continue())

    def test_record_failure(self) -> None:
        """Tests that record_failure updates state."""
        ctx = RetryContext(RetryConfig(max_retries=3))
        exc = ValueError("test error")
        ctx.record_failure(exc)
        self.assertEqual(ctx.attempt, 1)
        self.assertIs(ctx.last_exception, exc)

    def test_retry_exceptions_property(self) -> None:
        """Tests that retry_exceptions property returns config value."""
        config = RetryConfig(retry_exceptions=(ValueError,))
        ctx = RetryContext(config)
        self.assertEqual(ctx.retry_exceptions, (ValueError,))

    def test_wait_with_rate_limit_error(self) -> None:
        """Tests that wait respects Retry-After header."""
        config = RetryConfig(
            max_retries=3, backoff_factor=0.0, jitter=False, respect_retry_after=True
        )
        ctx = RetryContext(config)
        ctx.record_failure(RateLimitError("Rate limited", retry_after=5))

        with patch("pymtg.utils.retry.time.sleep") as mock_sleep:
            ctx.wait()

        mock_sleep.assert_called_once_with(5.0)

    def test_context_manager_protocol(self) -> None:
        """Tests that RetryContext works as a context manager."""
        config = RetryConfig(max_retries=3)
        with RetryContext(config) as ctx:
            self.assertIsInstance(ctx, RetryContext)

    def test_repr(self) -> None:
        """Tests that __repr__ returns a useful string."""
        ctx = RetryContext(RetryConfig(max_retries=3))
        repr_str = repr(ctx)
        self.assertIn("attempt=0/4", repr_str)
        self.assertIn("last_exception=None", repr_str)


class TestDefaultRetryConfig(unittest.TestCase):
    """Tests for the module-level DEFAULT_RETRY_CONFIG."""

    def test_default_config_exists(self) -> None:
        """Tests that DEFAULT_RETRY_CONFIG is a RetryConfig instance."""
        self.assertIsInstance(DEFAULT_RETRY_CONFIG, RetryConfig)

    def test_default_config_values(self) -> None:
        """Tests that DEFAULT_RETRY_CONFIG has expected default values."""
        self.assertEqual(DEFAULT_RETRY_CONFIG.max_retries, 3)
        self.assertTrue(DEFAULT_RETRY_CONFIG.retry_on_timeout)
        self.assertEqual(
            DEFAULT_RETRY_CONFIG.retry_exceptions,
            (RateLimitError, ConnectionError),
        )

    def test_default_config_excludes_timeout_error(self) -> None:
        """Tests that default retry_exceptions does not include TimeoutError."""
        self.assertNotIn(TimeoutError, DEFAULT_RETRY_CONFIG.retry_exceptions)


if __name__ == "__main__":
    unittest.main()
