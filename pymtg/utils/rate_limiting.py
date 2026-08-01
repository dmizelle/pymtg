"""Rate limiting utilities for MTG API providers.

This module provides utilities for tracking and respecting rate limits
when making requests to MTG API providers. Each provider has different
rate limits that must be respected to avoid being blocked.
"""

import itertools
import logging
import math
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
            If None (the default), the window is auto-selected based on the
            configured rate: 1.0 second for per-second limits and 60.0
            seconds for per-minute limits. This avoids treating per-minute
            limits as extremely restrictive per-second limits.
    """

    requests_per_second: float | None = None
    requests_per_minute: float | None = None
    burst_size: int = 1
    window_seconds: float | None = None


@dataclass
class RateLimitState:
    """State tracking for rate limiting.

    This class tracks the current state of rate limiting for a provider,
    including timestamps of recent requests.

    Attributes:
        timestamps: List of (timestamp, token) tuples for recent requests.
            The token is a unique integer identifying each recorded
            request, used to roll back a specific entry without removing
            a different caller's entry that happens to share the same
            timestamp value.
        lock: Thread lock for thread-safe access.
    """

    timestamps: list[tuple[float, int]] = field(default_factory=list)
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
        # Monotonic counter issuing unique tokens for each recorded
        # request. ``itertools.count.__next__`` is atomic under CPython,
        # so no lock is required to mint tokens. The token identifies a
        # specific recorded entry so rollback removes the correct one
        # even when two callers share an identical ``time.time()`` value.
        self._token_counter = itertools.count()

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
        logger.debug("Added rate limit config for %s: %s", provider, config)

    def remove_config(self, provider: str) -> bool:
        """Remove a rate limit configuration for a provider.

        Also removes any accumulated state entry to avoid retaining stale
        data for providers that are no longer configured.

        Args:
            provider: The provider name.

        Returns:
            True if the configuration was found and removed, False otherwise.
        """
        with self._global_lock:
            if provider in self.configs:
                del self.configs[provider]
                self.states.pop(provider, None)
                logger.debug("Removed rate limit config and state for %s", provider)
                return True
            return False

    def get_config(self, provider: str) -> RateLimitConfig | None:
        """Get the rate limit configuration for a provider.

        Args:
            provider: The provider name.

        Returns:
            The RateLimitConfig for the provider, or None if not configured.
        """
        with self._global_lock:
            return self.configs.get(provider)

    @staticmethod
    def _resolve_window(config: RateLimitConfig) -> float:
        """Resolve the effective sliding-window length for a config.

        If ``config.window_seconds`` is set, it is used directly. Otherwise
        the window is auto-selected: 1.0 second for per-second limits and
        60.0 seconds for per-minute limits.

        Args:
            config: The rate limit configuration.

        Returns:
            The effective window length in seconds.
        """
        if config.window_seconds is not None:
            return config.window_seconds
        if config.requests_per_second is not None:
            return 1.0
        return 60.0

    def _cleanup_and_get_limits(
        self,
        provider: str,
        config: RateLimitConfig,
    ) -> tuple[int, int | None]:
        """Clean up old timestamps and return (count, max_requests).

        WARNING: Must be called while holding ``state.lock``.

        Mutates ``state.timestamps`` by removing entries outside the
        window. The caller must have already resolved the config (and
        acquired ``state.lock``) to avoid re-fetching the config under
        the state lock (which would invert lock ordering against
        ``_global_lock``).

        Args:
            provider: The provider name.
            config: The already-resolved rate limit configuration.

        Returns:
            A tuple of (current_count, max_requests) where max_requests
            is None if no rate limit is configured.
        """
        # Read-only access avoids creating stale state entries for
        # providers that have a config but no recorded requests yet.
        state = self.states.get(provider)
        if state is None:
            return (0, self._compute_max_requests(config))

        now = time.time()
        window = self._resolve_window(config)

        # Remove old timestamps outside the window. Each entry is a
        # (timestamp, token) tuple; filter on the timestamp component.
        state.timestamps = [
            entry for entry in state.timestamps if now - entry[0] < window
        ]

        current_count = len(state.timestamps)
        max_requests = self._compute_max_requests(config)
        if max_requests is None:
            return (current_count, None)

        return (current_count, max_requests)

    @staticmethod
    def _compute_max_requests(config: RateLimitConfig) -> int | None:
        """Compute the effective max requests for a window.

        Uses ``ceil`` to round up so fractional rate limits allow at
        least one request per window (e.g., 1.5 req/s * 1s window = 2,
        not 1). The result is capped by ``burst_size``.

        Args:
            config: The rate limit configuration.

        Returns:
            The max requests allowed in the window, or None if no rate
            limit is configured.
        """
        window = RateLimiter._resolve_window(config)

        if config.requests_per_second is not None:
            max_requests = math.ceil(config.requests_per_second * window)
        elif config.requests_per_minute is not None:
            max_requests = math.ceil(config.requests_per_minute * window / 60)
        else:
            return None

        # Also consider burst size
        return min(max_requests, config.burst_size)

    def check(self, provider: str) -> bool:
        """Check if a request can be made to the specified provider.

        This is a read-only check that does not record a request. It does
        not create a state entry for the provider. Callers that want to
        proceed with a request should use :meth:`check_and_record` to
        perform the check and the recording atomically (avoiding the
        TOCTOU race between a standalone check and a later record).

        Args:
            provider: The provider name.

        Returns:
            True if the request can proceed, False if rate limited.
        """
        config = self.get_config(provider)
        if config is None:
            logger.debug("No rate limit config for %s, allowing request", provider)
            return True

        # Read-only access: do not create a stale state entry for a
        # configured provider that has no recorded requests yet.
        state = self.states.get(provider)
        if state is None:
            return True

        with state.lock:
            current_count, max_requests = self._cleanup_and_get_limits(provider, config)

            if max_requests is None:
                return True

            if current_count >= max_requests:
                logger.debug(
                    "Rate limit exceeded for %s: %d/%d requests",
                    provider,
                    current_count,
                    max_requests,
                )
                return False

            return True

    def check_and_record(self, provider: str) -> bool:
        """Atomically check the rate limit and record a request.

        Performs the check and the timestamp recording under a single
        lock acquisition so that two concurrent callers cannot both pass
        the check and exceed the limit (the TOCTOU race that affects a
        separate ``check()`` followed by ``_record()``).

        Args:
            provider: The provider name.

        Returns:
            True if the request was recorded and may proceed, False if
            rate limited (no timestamp is recorded in that case).
        """
        recorded, _ = self._check_and_record_with_ts(provider)
        return recorded

    def _check_and_record_with_ts(self, provider: str) -> tuple[bool, int | None]:
        """Atomically check the rate limit and record a request.

        Internal variant of :meth:`check_and_record` that also returns
        a token identifying the recorded entry (or ``None`` if nothing
        was recorded) so callers such as :class:`RateLimitGuard` can
        roll it back unambiguously.

        Args:
            provider: The provider name.

        Returns:
            A tuple of (allowed, token). ``allowed`` is True if the
            request was recorded and may proceed; ``token`` is a unique
            integer identifying the recorded entry (or None if rate
            limited / unconfigured).
        """
        config = self.get_config(provider)
        if config is None:
            logger.debug("No rate limit config for %s, allowing request", provider)
            return True, None

        # Accessing states creates an entry on demand here because we are
        # about to record a timestamp for this provider.
        state = self.states[provider]

        with state.lock:
            current_count, max_requests = self._cleanup_and_get_limits(provider, config)

            if max_requests is None:
                ts = time.time()
                token = next(self._token_counter)
                state.timestamps.append((ts, token))
                return True, token

            if current_count >= max_requests:
                logger.debug(
                    "Rate limit exceeded for %s: %d/%d requests",
                    provider,
                    current_count,
                    max_requests,
                )
                return False, None

            ts = time.time()
            token = next(self._token_counter)
            state.timestamps.append((ts, token))
            return True, token

    def _record(self, provider: str) -> None:
        """Record that a request was made to the specified provider.

        This is a private method retained for backward compatibility and
        for test setup. New callers should prefer
        :meth:`check_and_record`, which performs the check and record
        atomically. This method unconditionally appends a timestamp.

        Args:
            provider: The provider name.
        """
        # Guard against creating orphaned state entries for providers
        # that have no RateLimitConfig. Without this, the defaultdict
        # access below would allocate a RateLimitState that is never
        # trimmed by _cleanup_and_get_limits (which uses .get() and
        # returns early when state is None), leaking memory.
        config = self.get_config(provider)
        if config is None:
            logger.debug("No rate limit config for %s, skipping record", provider)
            return
        state = self.states[provider]
        now = time.time()
        token = next(self._token_counter)

        with state.lock:
            state.timestamps.append((now, token))
            logger.debug("Recorded request for %s", provider)

    def record(self, provider: str) -> None:
        """Record that a request was made to the specified provider.

        Public entry point for recording a request against the sliding
        window. This complements ``check()`` for callers that do not use
        the ``guard()`` context manager (e.g. methods that gate on a
        boolean return value from ``check()``).

        Args:
            provider: The provider name.
        """
        self._record(provider)

    def guard(self, provider: str) -> "RateLimitGuard":
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

            # Calculate wait time. Fetch config outside state.lock to
            # avoid inverting lock ordering against _global_lock.
            state = self.states.get(provider)
            if state is None:
                return

            wait_time = 0.0
            with state.lock:
                if not state.timestamps:
                    return

                window = self._resolve_window(config)
                now = time.time()
                oldest = min(entry[0] for entry in state.timestamps)
                elapsed = now - oldest

                if elapsed < window:
                    wait_time = window - elapsed
                else:
                    wait_time = 0.0

            # Avoid a tight spin when the computed wait is zero or
            # very small under contention.
            if wait_time > 0:
                logger.debug(
                    "Waiting %.2fs for rate limit on %s",
                    wait_time,
                    provider,
                )
                time.sleep(wait_time)
            else:
                time.sleep(0.01)

    def get_status(self, provider: str) -> dict[str, Any]:
        """Get the current rate limit status for a provider.

        All values are computed atomically under a single lock acquisition
        to ensure consistency.

        Args:
            provider: The provider name.

        Returns:
            A dictionary containing:
                - "can_request": bool, whether a request can be made
                    (computed as current_count < max_requests)
                - "current_count": int, number of requests in current window
                - "max_requests": int, maximum requests allowed in window
                    (or None if no rate limit is configured)
                - "window_seconds": float, the rate limit window in seconds
                    (defaults to 1.0 if no config exists)
                - "config": RateLimitConfig or None, the rate limit
                  configuration
        """
        # Resolve config outside state.lock to avoid inverting lock
        # ordering against _global_lock.
        config = self.get_config(provider)
        window = self._resolve_window(config) if config else 1.0

        state = self.states.get(provider)
        if state is None:
            max_requests = self._compute_max_requests(config) if config else None
            return {
                "can_request": True,
                "current_count": 0,
                "max_requests": max_requests,
                "window_seconds": window,
                "config": config,
            }

        with state.lock:
            if config is None:
                current_count = len(state.timestamps)
                max_requests = None
            else:
                current_count, max_requests = self._cleanup_and_get_limits(
                    provider, config
                )

            if max_requests is None:
                can_request = True
            else:
                can_request = current_count < max_requests

        return {
            "can_request": can_request,
            "current_count": current_count,
            "max_requests": max_requests,
            "window_seconds": window,
            "config": config,
        }

    def reset(self, provider: str | None = None) -> None:
        """Reset rate limit state for a provider or all providers.

        When resetting all providers, the states collection is
        snapshotted under ``_global_lock`` and each state is then
        cleared while holding only its own lock. This avoids holding
        ``_global_lock`` while acquiring state locks, which keeps the
        lock-ordering contract (``_global_lock`` is never acquired
        while holding a state lock) consistent and deadlock-free.

        Args:
            provider: The provider name to reset. If None, resets all providers.
        """
        if provider is None:
            # Snapshot the states under _global_lock, then clear each
            # state without holding _global_lock to avoid nested lock
            # acquisition (lock-ordering hazard).
            #
            # Note: a concurrent caller that records a request for a
            # *new* provider (one not in the snapshot) via
            # ``self.states[provider]`` (a defaultdict) can insert a
            # fresh state entry after the snapshot is taken but before
            # this method returns; that entry will not be cleared here.
            # A fully atomic full reset would require acquiring
            # ``_global_lock`` for the whole operation and routing all
            # other state creation through it, which is out of scope to
            # avoid reintroducing the lock-ordering hazard above.
            with self._global_lock:
                states_snapshot = list(self.states.values())
            for state in states_snapshot:
                with state.lock:
                    state.timestamps.clear()
            logger.debug("Reset rate limit state for all providers")
        else:
            # Read-only access: do not create a stale state entry for a
            # provider that has no recorded requests.
            state = self.states.get(provider)
            if state is not None:
                with state.lock:
                    state.timestamps.clear()
            logger.debug("Reset rate limit state for %s", provider)

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
        # Unique token identifying the entry recorded optimistically by
        # check_and_record() in __enter__; rolled back in __exit__ if the
        # guarded block raised an exception so failed requests are not
        # counted. Using a token (rather than the raw timestamp) ensures
        # rollback removes exactly this caller's entry even when two
        # callers share an identical time.time() value.
        self._recorded_token: int | None = None

    def __enter__(self) -> bool:
        """Enter the context manager.

        Uses :meth:`RateLimiter.check_and_record` so the check and the
        timestamp recording happen atomically, eliminating the TOCTOU
        race between a standalone check and a later record.

        When the initial check finds the limit reached, this method
        waits and retries the atomic check-and-record until it succeeds
        in reserving a slot. Without the retry, a second caller could
        grab the slot freed by ``wait()`` before us, leaving this caller
        to proceed with no recorded timestamp (silently exceeding the
        limit). The retry guarantees a slot is reserved before yielding.

        Returns:
            True if the request can proceed immediately, False if we
                had to wait.
        """
        allowed, token = self.rate_limiter._check_and_record_with_ts(self.provider)
        self._recorded_token = token
        if allowed:
            return True
        # Rate limited: nothing was recorded. Wait for the limit to
        # reset, then retry the atomic record until we reserve a slot.
        # The retry is required because another caller may grab the slot
        # freed by wait() between wait() returning and our record.
        self.waited = True
        while not allowed:
            self.rate_limiter.wait(self.provider)
            allowed, token = self.rate_limiter._check_and_record_with_ts(self.provider)
        self._recorded_token = token
        return False

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager.

        If an exception occurred inside the guarded block, roll back the
        optimistically-recorded timestamp so failed requests are not
        counted against the rate limit. On success the recorded
        timestamp is left in place.

        Args:
            exc_type: The exception type, or None if no exception occurred.
            exc_val: The exception value, or None if no exception occurred.
            exc_tb: The exception traceback, or None if no exception occurred.
        """
        if exc_type is not None:
            self._rollback_record()

    def _rollback_record(self) -> None:
        """Remove the optimistically-recorded entry if present.

        This restores the rate-limit state when the guarded block raised
        an exception, so failed requests are not counted. Removal is
        performed by matching the unique token (not the raw timestamp),
        so a concurrent caller whose entry shares the same timestamp
        value is never affected.
        """
        token = self._recorded_token
        if token is None:
            return
        state = self.rate_limiter.states.get(self.provider)
        if state is None:
            return
        with state.lock:
            for i, entry in enumerate(state.timestamps):
                if entry[1] == token:
                    del state.timestamps[i]
                    break
        self._recorded_token = None

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
