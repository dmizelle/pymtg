"""Universal search aggregator for querying multiple MTG API providers.

This module provides the Aggregator class which allows searching across
multiple providers simultaneously with unified query syntax. It returns
results keyed by provider name in a dictionary format.
"""

import logging
import threading
import time
from typing import Any

from pymtg.models.card import Card
from pymtg.models.enums import Color
from pymtg.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class Aggregator:
    """Universal search aggregator for MTG API providers.

    This class provides a unified interface for searching across multiple MTG
    API providers simultaneously. It queries each provider with the same
    parameters and returns results organized by provider name.

    The aggregator handles:
    - Querying multiple providers in parallel (or sequentially)
    - Tracking timing for each provider's response
    - Capturing and including errors from failed providers
    - Respecting each provider's rate limits

    All methods that read or modify the provider list or provider_map are
    thread-safe, using an internal reentrant lock (RLock) to protect shared
    state. Methods like search and search_syntax are thread-safe via
    _get_providers_to_query, which acquires the lock and returns a snapshot.

    Typical usage example:

        from pymtg import Scryfall
        from pymtg.search import Aggregator

        aggregator = Aggregator(providers=[Scryfall()])
        results = aggregator.search(name="Black Lotus", limit=5)
        # results is a dict: {"scryfall": [Card(...), ...], ...}

        # With specific providers
        results = aggregator.search(
            name="Black Lotus",
            sources=["scryfall"],
            limit=5
        )

    Attributes:
        providers: List of BaseProvider instances to query.
        provider_map: Dictionary mapping provider names to provider instances.
        _lock: Reentrant lock protecting providers and provider_map access.
    """

    def __init__(self, providers: list[BaseProvider] | None = None) -> None:
        """Initialize the Aggregator.

        Args:
            providers: Optional list of BaseProvider instances to include.
                If None, an empty list is used and providers must be added
                via add_provider() before searching.
        """
        self.providers: list[BaseProvider] = providers or []
        self.provider_map: dict[str, BaseProvider] = {p.name: p for p in self.providers}
        self._lock = threading.RLock()

    def add_provider(self, provider: BaseProvider) -> None:
        """Add a provider to the aggregator.

        Args:
            provider: A BaseProvider instance to add.

        Raises:
            ValueError: If a provider with the same name already exists.

        Note:
            This method is thread-safe and acquires an internal lock.
        """
        with self._lock:
            if provider.name in self.provider_map:
                raise ValueError(
                    f"Provider with name '{provider.name}' already exists "
                    f"in aggregator"
                )
            self.providers.append(provider)
            self.provider_map[provider.name] = provider
            logger.info(f"Added provider: {provider.name}")

    def remove_provider(self, provider_name: str) -> bool:
        """Remove a provider from the aggregator.

        Args:
            provider_name: Name of the provider to remove.

        Returns:
            True if the provider was found and removed, False otherwise.

        Note:
            This method is thread-safe and acquires an internal lock.
        """
        with self._lock:
            if provider_name not in self.provider_map:
                return False

            provider = self.provider_map[provider_name]
            self.providers.remove(provider)
            del self.provider_map[provider_name]
            logger.info(f"Removed provider: {provider_name}")
        return True

    def get_provider(self, provider_name: str) -> BaseProvider:
        """Get a specific provider by name.

        Args:
            provider_name: Name of the provider to retrieve.

        Returns:
            The BaseProvider instance.

        Raises:
            KeyError: If the provider name is not found.

        Note:
            This method is thread-safe and acquires an internal lock.
        """
        with self._lock:
            if provider_name not in self.provider_map:
                raise KeyError(f"Provider '{provider_name}' not found in aggregator")
            return self.provider_map[provider_name]

    def search(
        self,
        name: str | None = None,
        colors: list[str] | None = None,
        identity: list[str] | None = None,
        type_line: str | None = None,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
        sources: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, dict[str, Any]]:
        """Search for cards across all configured providers.

        This method queries all (or specified) providers with the given
        search parameters and returns results organized by provider name.
        Each provider's results are returned in a dictionary containing
        either the list of cards or an error dictionary.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include.
            identity: List of colors the card's identity must include.
            type_line: Type line the card must include.
            limit: Maximum number of results to return per provider.
            page: Page number for pagination (1-based).
            order: Sort order for results.
            sources: Optional list of provider names to query. If None, all
                configured providers are queried.
            **kwargs: Additional provider-specific search parameters.

        Returns:
            A dictionary mapping provider names to result dictionaries.
            Each result dictionary contains:
                - "cards": List of Card objects (on success)
                - "error": Error details (on failure)
                - "timing": Dictionary with timing information:
                    - "start_time": When the query started
                    - "end_time": When the query completed
                    - "duration": Query duration in seconds

        Example:
            aggregator = Aggregator(providers=[Scryfall()])
            results = aggregator.search(name="Black Lotus", limit=5)
            # results = {
            #     "scryfall": {
            #         "cards": [Card(name="Black Lotus", ...), ...],
            #         "error": None,
            #         "timing": {"duration": 0.25, ...}
            #     }
            # }

        Note:
            This method is thread-safe. It uses a snapshot of the providers
            list (via _get_providers_to_query) for consistent iteration.
        """
        result_dict: dict[str, dict[str, Any]] = {}

        # Determine which providers to query
        providers_to_query = self._get_providers_to_query(sources)

        if not providers_to_query:
            logger.warning("No providers configured or matching sources")
            return result_dict

        # Query each provider
        for provider in providers_to_query:
            provider_name = provider.name
            result_dict[provider_name] = self._query_provider(
                provider=provider,
                name=name,
                colors=colors,
                identity=identity,
                type_line=type_line,
                limit=limit,
                page=page,
                order=order,
                **kwargs,
            )

        return result_dict

    def search_syntax(
        self,
        query: str,
        limit: int = 20,
        sources: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, dict[str, Any]]:
        """Search for cards using provider-specific query syntax across all providers.

        This method uses each provider's search_syntax() method, allowing
        provider-specific query syntax to be used. Results are organized
        by provider name.

        Args:
            query: The provider-specific query string.
            limit: Maximum number of results to return per provider.
            sources: Optional list of provider names to query. If None, all
                configured providers are queried.
            **kwargs: Additional provider-specific parameters.

        Returns:
            A dictionary mapping provider names to result dictionaries.
            Each result dictionary follows the same format as search().

        Example:
            aggregator = Aggregator(providers=[Scryfall()])
            results = aggregator.search_syntax("c:U type:creature", limit=10)

        Note:
            This method is thread-safe. It uses a snapshot of the providers
            list (via _get_providers_to_query) for consistent iteration.
        """
        result_dict: dict[str, dict[str, Any]] = {}

        providers_to_query = self._get_providers_to_query(sources)

        if not providers_to_query:
            logger.warning("No providers configured or matching sources")
            return result_dict

        for provider in providers_to_query:
            provider_name = provider.name
            result_dict[provider_name] = self._query_provider_syntax(
                provider=provider,
                query=query,
                limit=limit,
                **kwargs,
            )

        return result_dict

    def _get_providers_to_query(self, sources: list[str] | None) -> list[BaseProvider]:
        """Get the list of providers to query based on sources parameter.

        Args:
            sources: Optional list of provider names to include.

        Returns:
            List of BaseProvider instances to query.

        Note:
            This method is thread-safe and acquires an internal lock.
            Returns a snapshot copy of the providers list, which is safe
            to iterate over without holding the lock.
        """
        with self._lock:
            if sources is None:
                return list(self.providers)

            return [
                self.provider_map[name] for name in sources if name in self.provider_map
            ]

    def _query_provider(
        self,
        provider: BaseProvider,
        name: str | None = None,
        colors: list[str] | None = None,
        identity: list[str] | None = None,
        type_line: str | None = None,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Query a single provider and return results with timing.

        Args:
            provider: The provider to query.
            name: Card name or name fragment to search for.
            colors: List of colors the card must include.
            identity: List of colors the card's identity must include.
            type_line: Type line the card must include.
            limit: Maximum number of results to return.
            page: Page number for pagination.
            order: Sort order for results.
            **kwargs: Additional provider-specific parameters.

        Returns:
            A dictionary containing the query results and timing information.
        """
        start_time = time.time()
        error: dict[str, Any] | None = None
        cards: list[Card] = []

        try:
            # Convert string colors to enum if needed
            def convert_colors(color_list: list[str] | None) -> list[Color] | None:
                """Convert a list of color strings to Color enum values."""
                if color_list is None:
                    return None
                return [Color(c.upper()) for c in color_list]

            cards = provider.search(
                name=name,
                colors=convert_colors(colors),
                identity=convert_colors(identity),
                type_line=type_line,
                limit=limit,
                page=page,
                order=order,
                **kwargs,
            )
        except Exception as e:
            error = {
                "type": type(e).__name__,
                "message": str(e),
                "exception": e,
            }
            logger.error(
                f"Error querying provider {provider.name}: {type(e).__name__}: {e}"
            )

        end_time = time.time()
        duration = end_time - start_time

        return {
            "cards": cards,
            "error": error,
            "timing": {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
            },
        }

    def _query_provider_syntax(
        self,
        provider: BaseProvider,
        query: str,
        limit: int = 20,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Query a single provider using query syntax and return results with timing.

        Args:
            provider: The provider to query.
            query: The provider-specific query string.
            limit: Maximum number of results to return.
            **kwargs: Additional provider-specific parameters.

        Returns:
            A dictionary containing the query results and timing information.
        """
        start_time = time.time()
        error: dict[str, Any] | None = None
        cards: list[Card] = []

        try:
            cards = provider.search_syntax(query=query, limit=limit, **kwargs)
        except Exception as e:
            error = {
                "type": type(e).__name__,
                "message": str(e),
                "exception": e,
            }
            logger.error(
                f"Error querying provider {provider.name} with syntax: "
                f"{type(e).__name__}: {e}"
            )

        end_time = time.time()
        duration = end_time - start_time

        return {
            "cards": cards,
            "error": error,
            "timing": {
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
            },
        }

    def get_available_providers(self) -> list[str]:
        """Get a list of available provider names.

        Returns:
            List of provider names that are configured in the aggregator.

        Note:
            This method is thread-safe and acquires an internal lock.
        """
        with self._lock:
            return list(self.provider_map.keys())

    def clear(self) -> None:
        """Clear all providers from the aggregator.

        Note:
            This method is thread-safe and acquires an internal lock.
        """
        with self._lock:
            self.providers.clear()
            self.provider_map.clear()
            logger.info("Cleared all providers from aggregator")

    def __repr__(self) -> str:
        """Return a string representation of the aggregator.

        Returns:
            A string representation suitable for debugging.

        Note:
            This method is thread-safe and acquires an internal lock.
            It may block if another thread holds the lock.
        """
        with self._lock:
            return (
                f"Aggregator(providers={len(self.providers)}, "
                f"provider_names={list(self.provider_map.keys())})"
            )
