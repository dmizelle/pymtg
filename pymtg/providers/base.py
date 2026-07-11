"""Base provider class for all MTG API providers.

This module provides the BaseProvider abstract base class that all provider
implementations must inherit from, ensuring a consistent interface across
all MTG API providers.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Generator

import requests

from pymtg.config import PROVIDER_CONFIGS, ProviderConfig
from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    InvalidQueryError,
    NotFoundError,
    RateLimitError,
)
from pymtg.models.card import Card
from pymtg.models.deck import Deck
from pymtg.models.enums import Color
from pymtg.utils.http import HTTPClient

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """Abstract base class for all MTG API providers.

    This class defines the common interface that all provider implementations
    must implement. It provides consistent methods for searching, retrieving
    cards and decks, and handling authentication and rate limiting.

    Attributes:
        name: Provider name (e.g., 'scryfall', 'archidekt').
        base_url: Base URL for the provider's API.
        config: Provider configuration.
        http_client: HTTP client for making requests.
        rate_limit: Rate limit information.
    """

    name: str = ""
    base_url: str | None = None
    config: ProviderConfig = None  # type: ignore[assignment]
    http_client: HTTPClient = None  # type: ignore[assignment]
    rate_limit: dict[str, Any] = {}

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the base provider.

        Args:
            **kwargs: Provider-specific initialization parameters.
        """
        self.name = self.__class__.__name__.lower()
        self.config = PROVIDER_CONFIGS.get(
            self.name,
            ProviderConfig(
                name=self.name,
            ),
        )
        self.base_url = self.config.base_url
        self.rate_limit = self.config.rate_limit or {}

        # Initialize HTTP client (only if not already set by test patching)
        if not hasattr(self, "http_client") or self.http_client is None:
            self.http_client = HTTPClient(
                base_url=self.base_url or "",
                timeout=self.config.timeout,
                user_agent=self.config.user_agent,
            )

        # Provider-specific initialization
        self._initialize(**kwargs)

    def _initialize(self, **kwargs: Any) -> None:
        """Provider-specific initialization.

        Args:
            **kwargs: Provider-specific initialization parameters.
        """
        pass

    @abstractmethod
    def search(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
        **kwargs: Any,
    ) -> list[Card]:
        """Search for cards with generic parameters.

        This method provides a consistent interface for searching cards across
        all providers using generic parameters that are common to most MTG
        APIs.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include.
            identity: List of colors the card's identity must include.
            type_line: Type line the card must include.
            limit: Maximum number of results to return.
            page: Page number for pagination.
            order: Sort order for results.
            **kwargs: Provider-specific search parameters.

        Returns:
            A list of Card objects matching the search criteria.

        Raises:
            InvalidQueryError: If the search parameters are invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
        """
        pass

    @abstractmethod
    def search_syntax(self, query: str, limit: int = 20, **kwargs: Any) -> list[Card]:
        """Search for cards using provider-specific query syntax.

        This method provides an escape hatch for power users who need to use
        provider-specific query syntax that is not available through the
        generic search() method.

        Args:
            query: The provider-specific query string.
            limit: Maximum number of results to return.
            **kwargs: Provider-specific parameters.

        Returns:
            A list of Card objects matching the query.

        Raises:
            InvalidQueryError: If the query is invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
        """
        pass

    @abstractmethod
    def get_card(self, card_id: str, **kwargs: Any) -> Card:
        """Get a specific card by its ID.

        Args:
            card_id: The provider-specific card ID.
            **kwargs: Provider-specific parameters.

        Returns:
            A Card object for the specified card.

        Raises:
            NotFoundError: If the card is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
        """
        pass

    def get_deck(self, deck_id: str, **kwargs: Any) -> Deck:
        """Get a specific deck by its ID.

        This is an optional method that providers can override if they
        support deck retrieval.

        Args:
            deck_id: The provider-specific deck ID.
            **kwargs: Provider-specific parameters.

        Returns:
            A Deck object for the specified deck.

        Raises:
            NotFoundError: If the deck is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            NotImplementedError: If the provider doesn't support deck retrieval.
        """
        raise NotImplementedError(f"{self.name} does not support deck retrieval")

    def get_user_decks(self, user_id: str | None = None, **kwargs: Any) -> list[Deck]:
        """Get all decks for a specific user.

        This is an optional method that providers can override if they
        support user deck retrieval.

        Args:
            user_id: The user ID, or None for the authenticated user.
            **kwargs: Provider-specific parameters.

        Returns:
            A list of Deck objects for the user's decks.

        Raises:
            AuthenticationError: If authentication is required but not provided.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            NotImplementedError: If the provider doesn't support user deck retrieval.
        """
        raise NotImplementedError(f"{self.name} does not support user deck retrieval")

    def autocomplete(self, query: str, limit: int = 10, **kwargs: Any) -> list[str]:
        """Get autocomplete suggestions for a query.

        This is an optional method that providers can override if they
        support autocomplete.

        Args:
            query: The partial query string.
            limit: Maximum number of suggestions to return.
            **kwargs: Provider-specific parameters.

        Returns:
            A list of autocomplete suggestions.

        Raises:
            NotImplementedError: If the provider doesn't support
                autocomplete.
        """
        raise NotImplementedError(f"{self.name} does not support autocomplete")

    def is_authenticated(self) -> bool:
        """Check if the provider is currently authenticated.

        This is an optional method that providers can override if they
        support authentication.

        Returns:
            True if the provider is authenticated, False otherwise.

        Raises:
            NotImplementedError: If the provider doesn't support
                authentication.
        """
        raise NotImplementedError(f"{self.name} does not support authentication")

    def refresh_auth(self) -> None:
        """Refresh the provider's authentication.

        This is an optional method that providers can override if they
        support authentication refresh.

        Raises:
            NotImplementedError: If the provider doesn't support
                authentication refresh.
        """
        raise NotImplementedError(
            f"{self.name} does not support authentication refresh"
        )

    def get_rate_limit_status(self) -> dict[str, Any]:
        """Get the current rate limit status.

        Returns:
            A dictionary containing rate limit information.
        """
        return self.rate_limit

    def iter_search(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        limit: int = 100,
        page_size: int = 50,
        **kwargs: Any,
    ) -> Generator[Card, None, None]:
        """Iterate through all search results page by page.

        This method provides a convenient way to iterate through all results
        of a search query, automatically handling pagination.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include.
            identity: List of colors the card's identity must include.
            type_line: Type line the card must include.
            limit: Maximum total number of results to return.
            page_size: Number of results per page.
            **kwargs: Provider-specific search parameters.

        Yields:
            Card objects matching the search criteria.

        Raises:
            InvalidQueryError: If the search parameters are invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
        """
        if limit < 1:
            raise InvalidQueryError("limit must be a positive integer (>= 1)")
        if page_size < 1:
            raise InvalidQueryError("page_size must be a positive integer (>= 1)")

        page = 1
        total_yielded = 0

        while total_yielded < limit:
            results = self.search(
                name=name,
                colors=colors,
                identity=identity,
                type_line=type_line,
                limit=page_size,
                page=page,
                **kwargs,
            )

            if not results:
                break

            for card in results:
                if total_yielded >= limit:
                    return
                yield card
                total_yielded += 1

            page += 1

    def _handle_response(
        self, response: requests.Response, resource_type: str | None = None
    ) -> Any:
        """Handle an HTTP response and raise appropriate exceptions.

        Args:
            response: The requests.Response object.
            resource_type: The type of resource being retrieved (for NotFoundError).

        Returns:
            The parsed response data.

        Raises:
            NotFoundError: If the response status is 404.
            RateLimitError: If the response status is 429.
            AuthenticationError: If the response status is 401 or 403.
            APIError: If the response status is 4xx or 5xx.
        """
        if response.status_code == 404:
            raise NotFoundError(
                "Resource not found",
                provider=self.name,
                status_code=404,
                resource_type=resource_type or "unknown",
            )

        if response.status_code == 429:
            retry_after_header = response.headers.get("Retry-After", "0")
            try:
                retry_after = int(retry_after_header)
            except ValueError:
                try:
                    from email.utils import parsedate_to_datetime

                    retry_after_date = parsedate_to_datetime(retry_after_header)
                    if retry_after_date is None:
                        raise ValueError("Invalid date format")
                    retry_after_date = retry_after_date.replace(tzinfo=timezone.utc)
                    retry_after = int(
                        (retry_after_date - datetime.now(timezone.utc)).total_seconds()
                    )
                except (ValueError, TypeError, ImportError):
                    retry_after = 0
            raise RateLimitError(
                "Rate limit exceeded",
                provider=self.name,
                status_code=429,
                retry_after=retry_after if retry_after > 0 else None,
            )

        if response.status_code in (401, 403):
            raise AuthenticationError(
                "Authentication failed",
                provider=self.name,
                status_code=response.status_code,
                auth_type="unknown",
            )

        if response.status_code >= 400:
            raise APIError(
                f"API error: {response.status_code}",
                provider=self.name,
                status_code=response.status_code,
                details={"response": response.text[:500]},
            )

        try:
            return response.json()
        except ValueError:
            return response.text

    def close(self) -> None:
        """Close the provider's resources."""
        self.http_client.close()

    def __enter__(self) -> "BaseProvider":
        """Enter a context manager.

        Returns:
            The provider instance.
        """
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit a context manager.

        Args:
            exc_type: The exception type.
            exc_val: The exception value.
            exc_tb: The exception traceback.
        """
        self.close()

    def __repr__(self) -> str:
        """Return a string representation of the provider.

        Returns:
            A string representation suitable for debugging.
        """
        return (
            f"{self.__class__.__name__}(name={self.name!r}, base_url={self.base_url!r})"
        )
