"""Utility modules for the pymtg library.

This module contains various utilities including HTTP client, rate limiting,
retry logic, and HAR logging.
"""

from pymtg.utils.har_logger import HARLogger
from pymtg.utils.http import HTTPClient
from pymtg.utils.rate_limiting import (
    RateLimitConfig,
    RateLimitState,
    RateLimiter,
    RateLimitGuard,
    get_default_rate_limiter,
)
from pymtg.utils.retry import (
    DEFAULT_RETRY_CONFIG,
    RetryConfig,
    RetryContext,
    calculate_backoff,
    retry_on_rate_limit,
    retry_with_config,
)

__all__ = [
    "HTTPClient",
    "HARLogger",
    "RateLimitConfig",
    "RateLimitState",
    "RateLimiter",
    "RateLimitGuard",
    "get_default_rate_limiter",
    "RetryConfig",
    "RetryContext",
    "DEFAULT_RETRY_CONFIG",
    "calculate_backoff",
    "retry_on_rate_limit",
    "retry_with_config",
]
