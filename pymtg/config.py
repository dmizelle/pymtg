"""Configuration classes for the pymtg library.

This module provides configuration classes used throughout the library for
managing provider settings, rate limits, and other configuration options.
"""

import os
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


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
    base_url: str | None = Field(
        default=None, description="Base URL for the provider API"
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Validate that base_url is a valid HTTP(S) URL.

        Args:
            v: The base_url value to validate.

        Returns:
            The validated base_url string, or None if not set.

        Raises:
            ValueError: If the URL is not valid or does not use http/https.
        """
        if v is None:
            return v
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"base_url must be a valid HTTP(S) URL, got: {v}")
        return v

    rate_limit: dict[str, Any] = Field(
        default_factory=dict, description="Rate limit configuration"
    )
    timeout: int = Field(default=30, description="Request timeout in seconds", gt=0)
    user_agent: str = Field(default="pymtg/0.1.0", description="User agent string")


# Pre-defined provider configurations
PROVIDER_CONFIGS: dict[str, ProviderConfig] = {
    "scryfall": ProviderConfig(
        name="scryfall",
        base_url="https://api.scryfall.com",
        rate_limit={"requests_per_second": 2},
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
        # NOTE: Moxfield has no public HTTP API. Requests are proxied through
        # the third-party Parse.bot scraper wrapper service, whose embedded
        # UUID path segment may be revoked or rotated by parse.bot at any
        # time. Override via the MOXFIELD_BASE_URL environment variable so a
        # rotation does not require a code change or release; alternatively
        # construct a custom ProviderConfig with a different endpoint.
        base_url=os.environ.get(
            "MOXFIELD_BASE_URL",
            "https://api.parse.bot/scraper/55189296-4a3a-4cd2-a006-802b22cd2b73/",
        ),
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
        rate_limit={"requests_per_minute": 10},
        timeout=30,
        user_agent="pymtg/0.1.0 (+https://github.com/pymtg/pymtg)",
    ),
}
