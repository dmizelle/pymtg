"""Retry utilities for MTG API requests.

This module provides utilities for automatically retrying failed requests
with exponential backoff and jitter. This is particularly useful for
handling rate limit errors (429) and temporary network issues.
"""

import functools
import logging
import random
import time
from typing import Callable, TypeVar

from pymtg.exceptions import RateLimitError

logger = logging.getLogger(__name__)

# Type variable for generic callable return type
T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior.

    This class stores all configuration options for retry logic including
    maximum retries, backoff factors, jitter, and which exceptions to retry.

    Attributes:
        max_retries: Maximum number of retry attempts. Defaults to 3.
        backoff_factor: Multiplier for exponential backoff. Defaults to 0.5.
        max_backoff: Maximum backoff time in seconds. Defaults to 10.
        jitter: Whether to add random jitter to backoff. Defaults to True.
        retry_exceptions: Tuple of exception types to retry on.
            Defaults to (RateLimitError, ConnectionError).
        retry_on_timeout: Whether to retry on timeout errors.
            Defaults to True.
        respect_retry_after: Whether to respect Retry-After header
            from 429 responses. Defaults to True.
    """

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: float = 10.0,
        jitter: bool = True,
        retry_exceptions: tuple[type[Exception], ...] | None = None,
        retry_on_timeout: bool = True,
        respect_retry_after: bool = True,
    ) -> None:
        """Initialize RetryConfig.

        Args:
            max_retries: Maximum number of retry attempts.
            backoff_factor: Multiplier for exponential backoff.
            max_backoff: Maximum backoff time in seconds.
            jitter: Whether to add random jitter to backoff.
            retry_exceptions: Tuple of exception types to retry on.
            retry_on_timeout: Whether to retry on timeout errors.
            respect_retry_after: Whether to respect Retry-After header.
        """
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.jitter = jitter
        self.retry_exceptions = retry_exceptions or (
            RateLimitError,
            ConnectionError,
        )
        self.retry_on_timeout = retry_on_timeout
        self.respect_retry_after = respect_retry_after

    def __repr__(self) -> str:
        """Return a string representation of the config.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"RetryConfig(max_retries={self.max_retries}, "
            f"backoff_factor={self.backoff_factor}, "
            f"max_backoff={self.max_backoff}, "
            f"jitter={self.jitter})"
        )


# Default retry configuration
DEFAULT_RETRY_CONFIG = RetryConfig()


def calculate_backoff(
    attempt: int,
    backoff_factor: float,
    max_backoff: float,
    jitter: bool = True,
) -> float:
    """Calculate exponential backoff with optional jitter.

    The backoff is calculated as: backoff_factor * (2 ** attempt)
    With jitter, a random factor between 0.5 and 1.5 is applied.

    Args:
        attempt: The current retry attempt number (0-based).
        backoff_factor: The base multiplier for backoff.
        max_backoff: Maximum backoff time in seconds.
        jitter: Whether to add random jitter.

    Returns:
        The calculated backoff time in seconds.
    """
    base_backoff = backoff_factor * (2**attempt)

    if jitter:
        # Add random jitter between 0.5x and 1.5x
        jitter_factor = 0.5 + random.random()
        base_backoff *= jitter_factor

    return min(base_backoff, max_backoff)


def retry_on_rate_limit(
    max_retries: int | None = None,
    backoff_factor: float | None = None,
    max_backoff: float | None = None,
    jitter: bool | None = None,
    retry_on_timeout: bool | None = None,
    respect_retry_after: bool | None = None,
    retry_exceptions: tuple[type[Exception], ...] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying functions on rate limit and network errors.

    This decorator wraps a function and automatically retries it when
    specified exceptions are raised. It uses exponential backoff with
    optional jitter between retry attempts.

    Args:
        max_retries: Maximum number of retry attempts.
            Uses config default if None.
        backoff_factor: Multiplier for exponential backoff.
            Uses config default if None.
        max_backoff: Maximum backoff time in seconds.
            Uses config default if None.
        jitter: Whether to add random jitter.
            Uses config default if None.
        retry_on_timeout: Whether to retry on timeout.
            Uses config default if None.
        respect_retry_after: Whether to respect Retry-After header.
            Uses config default if None.
        retry_exceptions: Tuple of exception types to retry on.
            Uses config default if None.

    Returns:
        A decorator that wraps the function with retry logic.

    Example:
        @retry_on_rate_limit(max_retries=5, backoff_factor=1.0)
        def fetch_card_data(card_id: str) -> Card:
            # This will be automatically retried on rate limit errors
            return scryfall.get_card(card_id)

        # With all defaults
        @retry_on_rate_limit()
        def another_function():
            pass
    """
    # Build configuration from parameters or defaults
    config = RetryConfig(
        max_retries=(
            max_retries if max_retries is not None else DEFAULT_RETRY_CONFIG.max_retries
        ),
        backoff_factor=(
            backoff_factor
            if backoff_factor is not None
            else DEFAULT_RETRY_CONFIG.backoff_factor
        ),
        max_backoff=(
            max_backoff if max_backoff is not None else DEFAULT_RETRY_CONFIG.max_backoff
        ),
        jitter=(jitter if jitter is not None else DEFAULT_RETRY_CONFIG.jitter),
        retry_on_timeout=(
            retry_on_timeout
            if retry_on_timeout is not None
            else DEFAULT_RETRY_CONFIG.retry_on_timeout
        ),
        respect_retry_after=(
            respect_retry_after
            if respect_retry_after is not None
            else DEFAULT_RETRY_CONFIG.respect_retry_after
        ),
        retry_exceptions=(
            retry_exceptions
            if retry_exceptions is not None
            else DEFAULT_RETRY_CONFIG.retry_exceptions
        ),
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """Inner decorator function."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            """Wrapper function with retry logic."""
            last_exception: Exception | None = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except TimeoutError as e:
                    # TimeoutError is handled before retry_exceptions to ensure
                    # retry_on_timeout is respected even if a user includes
                    # TimeoutError in retry_exceptions.
                    if not config.retry_on_timeout:
                        raise

                    last_exception = e

                    if attempt >= config.max_retries:
                        logger.warning(
                            f"Max retries ({config.max_retries}) exceeded "
                            f"for {func.__name__}"
                        )
                        raise

                    backoff = calculate_backoff(
                        attempt=attempt,
                        backoff_factor=config.backoff_factor,
                        max_backoff=config.max_backoff,
                        jitter=config.jitter,
                    )

                    logger.debug(
                        f"{type(e).__name__} in {func.__name__}, "
                        f"retrying in {backoff:.2f}s "
                        f"(attempt {attempt + 1}/{config.max_retries + 1})"
                    )
                    time.sleep(backoff)

                except config.retry_exceptions as e:
                    last_exception = e

                    # Check if we should retry
                    if attempt >= config.max_retries:
                        logger.warning(
                            f"Max retries ({config.max_retries}) exceeded "
                            f"for {func.__name__}"
                        )
                        raise

                    # Calculate backoff
                    backoff = calculate_backoff(
                        attempt=attempt,
                        backoff_factor=config.backoff_factor,
                        max_backoff=config.max_backoff,
                        jitter=config.jitter,
                    )

                    # Check for Retry-After header
                    if config.respect_retry_after and isinstance(e, RateLimitError):
                        retry_after = e.retry_after
                        if retry_after is not None:
                            # Use Retry-After if it's larger than
                            # calculated backoff
                            backoff = max(backoff, float(retry_after))

                    logger.debug(
                        f"{type(e).__name__} in {func.__name__}, "
                        f"retrying in {backoff:.2f}s "
                        f"(attempt {attempt + 1}/{config.max_retries + 1})"
                    )
                    time.sleep(backoff)

                except Exception:
                    # Don't retry on other exceptions
                    raise

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        return wrapper

    return decorator


def retry_with_config(
    config: RetryConfig | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retrying functions with a specific RetryConfig.

    This is a convenience decorator that takes a RetryConfig instance
    instead of individual parameters.

    Args:
        config: The RetryConfig to use. Uses defaults if None.

    Returns:
        A decorator that wraps the function with retry logic.

    Example:
        config = RetryConfig(max_retries=5, backoff_factor=1.0)

        @retry_with_config(config)
        def fetch_data():
            pass
    """
    actual_config = config or DEFAULT_RETRY_CONFIG

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """Inner decorator function."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            """Wrapper function with retry logic."""
            last_exception: Exception | None = None

            for attempt in range(actual_config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except TimeoutError as e:
                    # TimeoutError is handled before retry_exceptions to ensure
                    # retry_on_timeout is respected even if a user includes
                    # TimeoutError in retry_exceptions.
                    if not actual_config.retry_on_timeout:
                        raise

                    last_exception = e

                    if attempt >= actual_config.max_retries:
                        max_retries = actual_config.max_retries
                        logger.warning(
                            f"Max retries ({max_retries}) exceeded for "
                            f"{func.__name__}"
                        )
                        raise

                    backoff = calculate_backoff(
                        attempt=attempt,
                        backoff_factor=actual_config.backoff_factor,
                        max_backoff=actual_config.max_backoff,
                        jitter=actual_config.jitter,
                    )

                    max_retries = actual_config.max_retries
                    func_name = func.__name__
                    logger.debug(
                        f"{type(e).__name__} in {func_name}, "
                        f"retrying in {backoff:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    time.sleep(backoff)

                except actual_config.retry_exceptions as e:
                    last_exception = e

                    if attempt >= actual_config.max_retries:
                        max_retries = actual_config.max_retries
                        logger.warning(
                            f"Max retries ({max_retries}) exceeded for "
                            f"{func.__name__}"
                        )
                        raise

                    backoff = calculate_backoff(
                        attempt=attempt,
                        backoff_factor=actual_config.backoff_factor,
                        max_backoff=actual_config.max_backoff,
                        jitter=actual_config.jitter,
                    )

                    if actual_config.respect_retry_after and isinstance(
                        e, RateLimitError
                    ):
                        retry_after = e.retry_after
                        if retry_after is not None:
                            backoff = max(backoff, float(retry_after))

                    max_retries = actual_config.max_retries
                    func_name = func.__name__
                    logger.debug(
                        f"{type(e).__name__} in {func_name}, "
                        f"retrying in {backoff:.2f}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    time.sleep(backoff)

                except Exception:
                    # Don't retry on other exceptions
                    raise

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry logic")

        return wrapper

    return decorator


class RetryContext:
    """Context manager for retrying operations with configurable retry logic.

    This class provides a context manager interface for retry logic,
    useful when you want more control over the retry behavior or when
    the operation to retry is not a simple function call.

    Typical usage example:

        from pymtg.utils.retry import RetryContext, RetryConfig

        config = RetryConfig(max_retries=3, backoff_factor=0.5)

        with RetryContext(config) as retry:
            while retry.should_continue():
                try:
                    result = make_api_request()
                    break
                except retry.retry_exceptions as e:
                    retry.record_failure(e)
                    retry.wait()

    Attributes:
        config: The RetryConfig being used.
        attempt: Current attempt number (0-based).
        max_attempts: Maximum number of attempts (max_retries + 1).
        last_exception: The last exception that was caught.
    """

    def __init__(self, config: RetryConfig | None = None) -> None:
        """Initialize the RetryContext.

        Args:
            config: The RetryConfig to use. Uses defaults if None.
        """
        self.config = config or DEFAULT_RETRY_CONFIG
        self.attempt = 0
        self.max_attempts = self.config.max_retries + 1
        self.last_exception: Exception | None = None

    def should_continue(self) -> bool:
        """Check if another attempt should be made.

        Returns:
            True if another attempt can be made, False otherwise.
        """
        return self.attempt < self.max_attempts

    def record_failure(self, exception: Exception) -> None:
        """Record that an attempt failed.

        Args:
            exception: The exception that was raised.
        """
        self.last_exception = exception
        self.attempt += 1
        logger.debug(
            f"Recorded failure (attempt {self.attempt}/"
            f"{self.max_attempts}): {exception}"
        )

    def wait(self) -> None:
        """Wait before the next retry attempt.

        This calculates and sleeps for the appropriate backoff time.
        """
        backoff = calculate_backoff(
            attempt=self.attempt - 1,
            backoff_factor=self.config.backoff_factor,
            max_backoff=self.config.max_backoff,
            jitter=self.config.jitter,
        )

        # Check for Retry-After if applicable
        if (
            self.config.respect_retry_after
            and self.last_exception is not None
            and isinstance(self.last_exception, RateLimitError)
        ):
            retry_after = self.last_exception.retry_after
            if retry_after is not None:
                backoff = max(backoff, float(retry_after))

        logger.debug(f"Waiting {backoff:.2f}s before next retry")
        time.sleep(backoff)

    @property
    def retry_exceptions(self) -> tuple[type[Exception], ...]:
        """Get the exception types that should be retried."""
        return self.config.retry_exceptions

    def __enter__(self) -> "RetryContext":
        """Enter the context manager.

        Returns:
            The RetryContext instance.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the context manager."""
        pass

    def __repr__(self) -> str:
        """Return a string representation of the context.

        Returns:
            A string representation suitable for debugging.
        """
        last_exc_name = (
            type(self.last_exception).__name__ if self.last_exception else None
        )
        return (
            f"RetryContext(attempt={self.attempt}/{self.max_attempts}, "
            f"last_exception={last_exc_name})"
        )
