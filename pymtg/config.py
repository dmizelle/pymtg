"""Configuration classes for the pymtg library.

This module provides configuration classes used throughout the library for
managing provider settings, rate limits, and other configuration options.
"""

from typing import Any

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """Base configuration for a provider.

    Attributes:
        name: The provider name (e.g., 'scryfall', 'archidekt').
        base_url: The base URL for the provider's API.
        rate_limit: Rate limit information for the provider.
        timeout: Request timeout in seconds.
        user_agent: User agent string to use for requests.
    """

    name: str = Field(..., description="Provider name")
    base_url: str = Field(..., description="Base URL for the provider API")
    rate_limit: dict[str, Any] = Field(
        default_factory=dict, description="Rate limit configuration"
    )
    timeout: int = Field(default=30, description="Request timeout in seconds")
    user_agent: str = Field(default="pymtg/0.1.0", description="User agent string")


class RateLimitConfig(BaseModel):
    """Rate limit configuration for a provider.

    Attributes:
        requests_per_second: Maximum requests per second.
        requests_per_minute: Maximum requests per minute.
        burst_size: Maximum burst size for rate limiting.
    """

    requests_per_second: float | None = Field(
        default=None, description="Maximum requests per second"
    )
    requests_per_minute: float | None = Field(
        default=None, description="Maximum requests per minute"
    )
    burst_size: int = Field(default=10, description="Maximum burst size")


# Pre-defined provider configurations
PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "scryfall": ProviderConfig(
        name="scryfall",
        base_url="https://api.scryfall.com",
        rate_limit={
            "search": {"requests_per_second": 2},
            "other": {"requests_per_second": 10},
        },
        timeout=30,
        user_agent="pymtg/0.1.0 (+https://github.com/pymtg/pymtg)",
    ),
    "archidekt": ProviderConfig(
        name="archidekt",
        base_url="https://archidekt.com",
        rate_limit={"requests_per_minute": 60},
        timeout=30,
        user_agent="pymtg/0.1.0 (+https://github.com/pymtg/pymtg)",
    ),
    "moxfield": ProviderConfig(
        name="moxfield",
        base_url="https://api.parse.bot/scraper/55189296-4a3a-4cd2-a006-802b22cd2b73/",
        rate_limit={"requests_per_minute": 100},
        timeout=30,
        user_agent="pymtg/0.1.0 (+https://github.com/pymtg/pymtg)",
    ),
    "tcgplayer": ProviderConfig(
        name="tcgplayer",
        base_url="https://api.tcgplayer.com",
        rate_limit={"requests_per_second": 10},
        timeout=30,
        user_agent="pymtg/0.1.0 (+https://github.com/pymtg/pymtg)",
    ),
    "cardmarket": ProviderConfig(
        name="cardmarket",
        base_url="https://apiv2.cardmarket.com",
        rate_limit={"requests_per_day": 100000},
        timeout=30,
        user_agent="pymtg/0.1.0 (+https://github.com/pymtg/pymtg)",
    ),
}
