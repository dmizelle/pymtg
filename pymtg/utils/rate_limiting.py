"""Rate limiting utilities for MTG API providers.

This module provides utilities for tracking and respecting rate limits
when making requests to MTG API providers. Each provider has different
rate limits that must be respected to avoid being blocked.
"""

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for a provider's rate limit.

    This class stores the rate limit configuration for a specific provider
    or endpoint type.

    Attributes:
        requests_per_second: Maximum requests allowed per second.
            If None, no per-second limit.
        requests_per_minute: Maximum requests allowed per minute.
            If None, no per-minute limit.
        burst_size: Maximum number of requests that can be made in a burst.
            Defaults to 1 if not specified.
        window_seconds: Time window in seconds for rate limit tracking.
            Defaults to 1 second for per-second limits, 60 for per-minute.
    """

    requests_per_second: float | None = None
    requests_per_minute: float | None = None
    burst_size: int = 1
    window_seconds: float = 1.0


@dataclass
class RateLimitState:
    """State tracking for rate limiting.

    This class tracks the current state of rate limiting for a provider,
    including timestamps of recent requests.

    Attributes:
        timestamps: List of timestamps for recent requests.
        lock: Thread lock for thread-safe access.
    """

    timestamps: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)


class RateLimiter:
    """Rate limiter for tracking request timing across multiple providers.

    This class provides a centralized way to track and enforce rate limits
    for multiple MTG API providers. It supports both per-second and
    per-minute rate limits with configurable burst sizes.

    The rate limiter uses a sliding window algorithm to track requests
    and can be used as a context manager or called directly.

    Typical usage example:

        from pymtg.utils.rate_limiting import RateLimiter, RateLimitConfig

        # Create rate limiter with provider configs
        rate_limiter = RateLimiter({
            "scryfall": RateLimitConfig(
                requests_per_second=2,
                requests_per_minute=None,
            ),
            "archidekt": RateLimitConfig(
                requests_per_minute=60,
                burst_size=10,
            ),
        })

        # Use as context manager
        with rate_limiter.guard("scryfall") as should_proceed:
            if should_proceed:
                # Make request
                pass

        # Or check manually
        if rate_limiter.check("scryfall"):
            # Make request
            pass

    Attributes:
        configs: Dictionary mapping provider names to RateLimitConfig.
        states: Dictionary mapping provider names to RateLimitState.
    """

    def __init__(
        self,
        configs: dict[str, RateLimitConfig] | None = None,
    ) -> None:
        """Initialize the RateLimiter.

        Args:
            configs: Optional dictionary of rate limit configurations
                for providers. Keys are provider names, values are
                RateLimitConfig instances.
        """
        self.configs: dict[str, RateLimitConfig] = configs or {}
        self.states: dict[str, RateLimitState] = defaultdict(lambda: RateLimitState())
        self._global_lock = threading.Lock()

    def add_config(
        self,
        provider: str,
        config: RateLimitConfig,
    ) -> None:
        """Add or update a rate limit configuration for a provider.

        Args:
            provider: The provider name.
            config: The rate limit configuration.
        """
        with self._global_lock:
            self.configs[provider] = config
        logger.debug(f"Added rate limit config for {provider}: {config}")

    def remove_config(self, provider: str) -> bool:
        """Remove a rate limit configuration for a provider.

        Args:
            provider: The provider name.

        Returns:
            True if the configuration was found and removed, False otherwise.
        """
        with self._global_lock:
            if provider in self.configs:
                del self.configs[provider]
                logger.debug(f"Removed rate limit config for {provider}")
                return True
            return False

    def get_config(self, provider: str) -> RateLimitConfig | None:
        """Get the rate limit configuration for a provider.

        Args:
            provider: The provider name.

        Returns:
            The RateLimitConfig for the provider, or None if not configured.
        """
        return self.configs.get(provider)

    def check(self, provider: str) -> bool:
        """Check if a request can be made to the specified provider.

        This method checks the current rate limit state for the provider
        and determines if a new request can be made without exceeding
        the rate limits.

        Args:
            provider: The provider name.

        Returns:
            True if the request can proceed, False if rate limited.
        """
        config = self.get_config(provider)
        if config is None:
            # No rate limit configured, allow all requests
            logger.debug(f"No rate limit config for {provider}, " "allowing request")
            return True

        state = self.states[provider]
        now = time.time()

        with state.lock:
            # Remove old timestamps outside the window
            window = config.window_seconds
            state.timestamps = [t for t in state.timestamps if now - t < window]

            # Check if we can make another request
            current_count = len(state.timestamps)

            # Calculate max requests based on config
            if config.requests_per_second is not None:
                max_requests = int(config.requests_per_second * window)
            elif config.requests_per_minute is not None:
                max_requests = int(config.requests_per_minute * window / 60)
            else:
                # No rate limit
                return True

            # Also consider burst size
            max_requests = min(max_requests, config.burst_size)

            if current_count >= max_requests:
                logger.debug(
                    f"Rate limit exceeded for {provider}: "
                    f"{current_count}/{max_requests} requests"
                )
                return False

            return True

    def _record(self, provider: str) -> None:
        """Record that a request was made to the specified provider.

        This is a private method called by RateLimitGuard.__exit__() to
        update the rate limit state after a request completes.

        Args:
            provider: The provider name.
        """
        state = self.states[provider]
        now = time.time()

        with state.lock:
            state.timestamps.append(now)
            logger.debug(f"Recorded request for {provider}")

    def guard(self, provider: str):
        """Context manager for rate limiting a provider.

        This method can be used as a context manager to automatically
        check and record requests. It also supports waiting for
        rate limits to reset.

        Args:
            provider: The provider name.

        Yields:
            bool: True if the request can proceed immediately, False if
                the context manager had to wait for rate limits.

        Example:
            with rate_limiter.guard("scryfall") as should_proceed:
                if should_proceed:
                    # Request can proceed immediately
                    pass
                # else: rate limiter waited and we can now proceed
        """
        return RateLimitGuard(self, provider)

    def wait(self, provider: str) -> None:
        """Wait until a request can be made to the specified provider.

        This method blocks until the rate limit allows another request
        to be made. Use this for providers where you want to wait
        instead of failing.

        Args:
            provider: The provider name.
        """
        while not self.check(provider):
            config = self.get_config(provider)
            if config is None:
                return

            # Calculate wait time
            state = self.states[provider]
            with state.lock:
                if not state.timestamps:
                    return

                # Find the oldest timestamp in the window
                config = self.get_config(provider)
                if config is None:
                    return

                window = config.window_seconds
                now = time.time()
                oldest = min(state.timestamps)
                elapsed = now - oldest

                if elapsed < window:
                    wait_time = window - elapsed
                    logger.debug(
                        f"Waiting {wait_time:.2f}s for rate limit on {provider}"
                    )
                    time.sleep(wait_time)

    def get_status(self, provider: str) -> dict[str, Any]:
        """Get the current rate limit status for a provider.

        Args:
            provider: The provider name.

        Returns:
            A dictionary containing:
                - "can_request": bool, whether a request can be made
                - "current_count": int, number of requests in current window
                - "max_requests": int, maximum requests allowed in window
                - "window_seconds": float, the rate limit window in seconds
                - "config": RateLimitConfig or None, the rate limit
                  configuration
        """
        config = self.get_config(provider)
        state = self.states[provider]
        now = time.time()

        with state.lock:
            window = config.window_seconds if config else 1.0
            state.timestamps = [t for t in state.timestamps if now - t < window]
            current_count = len(state.timestamps)

        if config is None:
            max_requests = None
        elif config.requests_per_second is not None:
            max_requests = int(config.requests_per_second * window)
        elif config.requests_per_minute is not None:
            max_requests = int(config.requests_per_minute * window / 60)
        else:
            max_requests = None

        if max_requests is not None and config is not None:
            max_requests = min(max_requests, config.burst_size)

        return {
            "can_request": self.check(provider),
            "current_count": current_count,
            "max_requests": max_requests,
            "window_seconds": window,
            "config": config,
        }

    def reset(self, provider: str | None = None) -> None:
        """Reset rate limit state for a provider or all providers.

        Args:
            provider: The provider name to reset. If None, resets all providers.
        """
        if provider is None:
            with self._global_lock:
                for state in self.states.values():
                    with state.lock:
                        state.timestamps.clear()
            logger.debug("Reset rate limit state for all providers")
        else:
            state = self.states[provider]
            with state.lock:
                state.timestamps.clear()
            logger.debug(f"Reset rate limit state for {provider}")

    def __repr__(self) -> str:
        """Return a string representation of the rate limiter.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"RateLimiter(configs={list(self.configs.keys())}, "
            f"states={list(self.states.keys())})"
        )


class RateLimitGuard:
    """Context manager for rate limiting a single provider.

    This class is used internally by RateLimiter.guard() to provide
    context manager functionality.

    Attributes:
        rate_limiter: The parent RateLimiter instance.
        provider: The provider name being guarded.
        waited: Whether the guard had to wait for rate limits.
    """

    def __init__(self, rate_limiter: RateLimiter, provider: str) -> None:
        """Initialize the rate limit guard.

        Args:
            rate_limiter: The parent RateLimiter instance.
            provider: The provider name being guarded.
        """
        self.rate_limiter = rate_limiter
        self.provider = provider
        self.waited = False

    def __enter__(self) -> bool:
        """Enter the context manager.

        Returns:
            True if the request can proceed immediately, False if we
                had to wait.
        """
        if not self.rate_limiter.check(self.provider):
            self.rate_limiter.wait(self.provider)
            self.waited = True
            return False
        return True

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager.

        Records the request regardless of whether an exception occurred.
        """
        self.rate_limiter._record(self.provider)

    def __repr__(self) -> str:
        """Return a string representation of the guard.

        Returns:
            A string representation suitable for debugging.
        """
        return f"RateLimitGuard(provider={self.provider!r}, waited={self.waited})"


# Default rate limiter instance with common provider configs
def get_default_rate_limiter() -> RateLimiter:
    """Get a default RateLimiter instance with common provider configurations.

    Returns:
        A RateLimiter instance pre-configured with rate limits for
        Scryfall, Archidekt, and other common providers.
    """
    return RateLimiter(
        {
            "scryfall": RateLimitConfig(
                requests_per_second=2,
                requests_per_minute=None,
                burst_size=2,
            ),
            "archidekt": RateLimitConfig(
                requests_per_second=None,
                requests_per_minute=60,
                burst_size=10,
            ),
            "moxfield": RateLimitConfig(
                requests_per_second=None,
                requests_per_minute=100,
                burst_size=20,
            ),
            "tcgplayer": RateLimitConfig(
                requests_per_second=10,
                requests_per_minute=None,
                burst_size=10,
            ),
            "cardmarket": RateLimitConfig(
                requests_per_second=None,
                requests_per_minute=10,
                # Cardmarket: 600 req/min hard limit, daily limits vary
                # (5K private, 100K commercial, 1M powerseller)
                burst_size=5,
            ),
        }
    )
