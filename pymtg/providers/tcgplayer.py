"""TCGPlayer provider implementation for the pymtg library.

This module provides the TCGPlayer class which implements the BaseProvider interface
for interacting with the TCGPlayer API (https://docs.tcgplayer.com).

TCGPlayer is a major marketplace for trading card games including Magic: The Gathering.
Their API provides access to catalog data, pricing information, and more.

Note:
    New developer access to the TCGPlayer API is currently closed.
    Requires pre-approved application at https://docs.tcgplayer.com
    This implementation uses the OAuth2 client credentials flow.
"""

import logging
from typing import Any, Generator

import requests

from pymtg.auth.oauth2 import OAuth2ClientCredentialsHandler
from pymtg.config import PROVIDER_CONFIGS
from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    InvalidQueryError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from pymtg.models.card import Card
from pymtg.models.deck import Deck
from pymtg.models.enums import Color, Rarity
from pymtg.models.pricing import Pricing, TCGPlayerPricing
from pymtg.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class TCGPlayer(BaseProvider):
    """TCGPlayer API provider implementation.

    This class provides access to the TCGPlayer API, which is a marketplace
    for trading card games including Magic: The Gathering.

    TCGPlayer uses OAuth2 client credentials flow for authentication.
    New developer access is currently closed and requires pre-approval.

    Attributes:
        name: Provider name ("tcgplayer").
        base_url: Base URL for the TCGPlayer API ("https://api.tcgplayer.com").
        config: Provider configuration.
        http_client: HTTP client for making requests.
        rate_limit: Rate limit information.
        auth_handler: OAuth2 authentication handler.
        client_id: OAuth2 client ID (if provided).
        client_secret: OAuth2 client secret (if provided).

    Note:
        To use this provider, you must have pre-approved access from TCGPlayer.
        Apply at https://docs.tcgplayer.com

    Example:
        # Initialize with OAuth2 credentials
        tcgplayer = TCGPlayer(client_id="your_client_id", client_secret="your_client_secret")

        # Get a card by ID
        card = tcgplayer.get_card(product_id=12345)

        # Search for cards
        cards = tcgplayer.search(query="Black Lotus", limit=5)

        # Get pricing for a card
        pricing = tcgplayer.get_pricing(product_id=12345)
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        scope: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the TCGPlayer provider.

        Args:
            client_id: OAuth2 client ID for TCGPlayer API.
            client_secret: OAuth2 client secret for TCGPlayer API.
            scope: OAuth2 scope for token requests.
            **kwargs: Additional initialization parameters.

        Raises:
            AuthenticationError: If authentication fails during initialization.
        """
        # Store OAuth2 credentials before calling super().__init__()
        # This is needed because _initialize() is called during super().__init__()
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope

        super().__init__(**kwargs)
        self.name = "tcgplayer"
        self.config = PROVIDER_CONFIGS.get("tcgplayer", self.config)
        self.base_url = self.config.base_url
        self.rate_limit = self.config.rate_limit or {}

        # Initialize OAuth2 handler
        # TCGPlayer OAuth uses /token endpoint implicitly
        self.auth_handler = OAuth2ClientCredentialsHandler(
            token_url=f"{self.base_url}/token",
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
        )

        # Note: Authentication is lazy - it happens on first API call or explicit authenticate()
        # This avoids initialization order issues and allows setting credentials later

    def _initialize_auth(self, **kwargs: Any) -> None:
        """TCGPlayer-specific authentication initialization.

        Authenticates with OAuth2 if credentials are provided.

        Args:
            **kwargs: Additional initialization parameters.

        Raises:
            AuthenticationError: If authentication fails.
        """
        if self.client_id and self.client_secret:
            self.authenticate()

    def authenticate(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        scope: str | None = None,
    ) -> None:
        """Authenticate with TCGPlayer using OAuth2 client credentials.

        Args:
            client_id: OAuth2 client ID (overrides stored value).
            client_secret: OAuth2 client secret (overrides stored value).
            scope: OAuth2 scope (overrides stored value).

        Raises:
            AuthenticationError: If authentication fails.
            NetworkError: If there is a network error during authentication.
        """
        # Update stored credentials if provided
        if client_id:
            self.client_id = client_id
        if client_secret:
            self.client_secret = client_secret
        if scope:
            self.scope = scope

        # Update auth handler credentials
        self.auth_handler._client_id = self.client_id or self.auth_handler._client_id
        self.auth_handler._client_secret = (
            self.client_secret or self.auth_handler._client_secret
        )
        self.auth_handler._scope = self.scope or self.auth_handler._scope

        # Authenticate using the handler
        self.auth_handler.authenticate(
            client_id=self.client_id,
            client_secret=self.client_secret,
            scope=self.scope,
        )

        # Apply authentication to HTTP client's session
        self.auth_handler.apply_auth(self.http_client.session)

        logger.info("TCGPlayer authentication successful")

    def is_authenticated(self) -> bool:
        """Check if the provider is currently authenticated.

        Returns:
            True if OAuth2 token is present and valid, False otherwise.
        """
        return self.auth_handler.is_authenticated()

    def refresh_auth(self) -> None:
        """Refresh the OAuth2 access token.

        Raises:
            AuthenticationError: If refresh fails or no credentials stored.
        """
        self.auth_handler.refresh()
        self.auth_handler.apply_auth(self.http_client.session)
        logger.info("TCGPlayer token refreshed successfully")

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

        This method searches for Magic: The Gathering cards using the TCGPlayer
        catalog endpoint. It maps generic parameters to TCGPlayer-specific
        query parameters.

        Args:
            name: Card name to search for.
            colors: List of colors the card must include.
            identity: List of colors the card must be exactly.
            type_line: Card type line to filter by.
            limit: Maximum number of results to return (default: 20).
            page: Page number for pagination (default: 1).
            order: Sort order for results.
            **kwargs: Additional search parameters.

        Returns:
            List of Card objects matching the search criteria.

        Raises:
            AuthenticationError: If not authenticated.
            InvalidQueryError: If the search parameters are invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            RateLimitError: If rate limit is exceeded.
        """
        self._check_authenticated()

        # Build search parameters
        params: dict[str, Any] = {
            "limit": limit,
            "offset": (page - 1) * limit,
        }

        # Map generic parameters to TCGPlayer-specific parameters
        if name:
            params["search"] = name

        # TCGPlayer uses different parameter names
        # Build the query string for the search endpoint
        query_string = self._build_search_query(
            name=name,
            colors=colors,
            identity=identity,
            type_line=type_line,
            **kwargs,
        )

        if query_string:
            params["search"] = query_string

        # Handle sorting
        if order:
            # Map generic order to TCGPlayer sort parameters
            sort_mapping = {
                "name_asc": "ProductName Ascending",
                "name_desc": "ProductName Descending",
                "price_asc": "PriceLowToHigh",
                "price_desc": "PriceHighToLow",
                "released_asc": "ReleaseDate Ascending",
                "released_desc": "ReleaseDate Descending",
            }
            if order in sort_mapping:
                params["sort"] = sort_mapping[order]
            else:
                params["sort"] = order

        # Add any additional kwargs as parameters
        for key, value in kwargs.items():
            if value is not None and key not in params:
                params[key] = value

        endpoint = "/v2/catalog/products"
        try:
            response = self._make_request("GET", endpoint, params=params)

            # Parse response
            cards = self._parse_card_list_response(response.json())
            return cards

        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, endpoint)
            # _handle_http_error always raises, but pyright doesn't know this
            raise  # This should never be reached
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during search: {e}")
            raise NetworkError(
                "Network error during TCGPlayer search", original_exception=e
            ) from e

    def search_syntax(self, query: str, limit: int = 20, **kwargs: Any) -> list[Card]:
        """Search for cards using TCGPlayer-specific query syntax.

        TCGPlayer uses a custom search syntax for the catalog endpoint.
        This method allows passing raw query strings.

        Args:
            query: Search query string in TCGPlayer syntax.
            **kwargs: Additional search parameters (limit, offset, sort, etc.).

        Returns:
            List of Card objects matching the query.

        Raises:
            AuthenticationError: If not authenticated.
            InvalidQueryError: If the query syntax is invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
        """
        self._check_authenticated()

        params: dict[str, Any] = {"search": query}

        # Add standard pagination and sorting
        limit = kwargs.get("limit", 20)
        page = kwargs.get("page", 1)
        params["limit"] = limit
        params["offset"] = (page - 1) * limit

        if "order" in kwargs:
            sort_mapping = {
                "name_asc": "ProductName Ascending",
                "name_desc": "ProductName Descending",
                "price_asc": "PriceLowToHigh",
                "price_desc": "PriceHighToLow",
            }
            order = kwargs["order"]
            params["sort"] = sort_mapping.get(order, order)

        # Add any additional parameters
        for key, value in kwargs.items():
            if value is not None and key not in ["limit", "page", "order"]:
                params[key] = value

        endpoint = "/v2/catalog/products"
        try:
            response = self._make_request("GET", endpoint, params=params)
            cards = self._parse_card_list_response(response.json())
            return cards

        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, endpoint)
            # _handle_http_error always raises, but pyright doesn't know this
            raise  # This should never be reached
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during syntax search: {e}")
            raise NetworkError(
                "Network error during TCGPlayer syntax search",
                original_exception=e,
            ) from e

    def get_card(self, card_id: str, **kwargs: Any) -> Card:
        """Get a single card by its TCGPlayer product ID.

        Args:
            product_id: TCGPlayer product ID for the card.
            **kwargs: Additional parameters (e.g., include=pricing for additional data).

        Returns:
            Card object with full details.

        Raises:
            AuthenticationError: If not authenticated.
            NotFoundError: If the card is not found.
            NetworkError: If there is a network error.
            InvalidQueryError: If product_id is not provided.
        """
        self._check_authenticated()

        if not card_id:
            raise InvalidQueryError(
                "card_id is required for TCGPlayer.get_card()",
                provider=self.name,
            )

        # Build include parameter for additional data
        include = kwargs.get("include", "")
        if "pricing" in kwargs and kwargs["pricing"]:
            include = f"{include},pricing" if include else "pricing"

        params: dict[str, Any] = {}
        if include:
            params["include"] = include

        endpoint = f"/v2/catalog/products/{card_id}"
        try:
            response = self._make_request("GET", endpoint, params=params)

            card_data = response.json()
            card = self._parse_card_response(card_data)
            return card

        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, endpoint)
            # _handle_http_error always raises, but pyright doesn't know this
            raise  # This should never be reached
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during get_card: {e}")
            raise NetworkError(
                "Network error during TCGPlayer get_card",
                original_exception=e,
            ) from e

    def get_deck(self, deck_id: str | int | None = None, **kwargs: Any) -> Deck:
        """Get a deck by its TCGPlayer deck ID.

        Note:
            TCGPlayer API may not have a dedicated deck endpoint.
            This method is a placeholder and may raise NotImplementedError.

        Args:
            deck_id: TCGPlayer deck ID.
            **kwargs: Additional parameters.

        Returns:
            Deck object with deck details.

        Raises:
            NotImplementedError: If deck retrieval is not supported.
            AuthenticationError: If not authenticated.
            NotFoundError: If the deck is not found.
            NetworkError: If there is a network error.
        """
        self._check_authenticated()

        # TCGPlayer primarily focuses on catalog and pricing
        # Deck functionality may not be available in their public API
        raise NotImplementedError(
            "TCGPlayer provider does not currently support deck retrieval. "
            "TCGPlayer API focuses on catalog and pricing data."
        )

    def get_user_decks(self, user_id: str | None = None, **kwargs: Any) -> list[Deck]:
        """Get decks for the authenticated user.

        Note:
            TCGPlayer API may not support user deck retrieval.
            This method is a placeholder and may raise NotImplementedError.

        Args:
            **kwargs: Additional parameters.

        Returns:
            List of Deck objects for the authenticated user.

        Raises:
            NotImplementedError: If user deck retrieval is not supported.
            AuthenticationError: If not authenticated.
        """
        self._check_authenticated()

        raise NotImplementedError(
            "TCGPlayer provider does not currently support user deck retrieval. "
            "TCGPlayer API focuses on catalog and pricing data."
        )

    def get_pricing(self, product_id: int, **kwargs: Any) -> Pricing:
        """Get pricing information for a card by its product ID.

        Args:
            product_id: TCGPlayer product ID for the card.
            **kwargs: Additional parameters.

        Returns:
            Pricing object containing price data from TCGPlayer.

        Raises:
            AuthenticationError: If not authenticated.
            NotFoundError: If the card or pricing data is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
        """
        self._check_authenticated()

        if not product_id:
            raise InvalidQueryError(
                "product_id is required for TCGPlayer.get_pricing()",
                provider=self.name,
            )

        endpoint = f"/v2/pricing/product/{product_id}"
        try:
            response = self._make_request("GET", endpoint)

            pricing_data = response.json()
            pricing = self._parse_pricing_response(pricing_data)
            return pricing

        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, endpoint)
            # _handle_http_error always raises, but pyright doesn't know this
            raise  # This should never be reached
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during get_pricing: {e}")
            raise NetworkError(
                "Network error during TCGPlayer get_pricing",
                original_exception=e,
            ) from e

    def autocomplete(self, query: str, limit: int = 10, **kwargs: Any) -> list[str]:
        """Get autocomplete suggestions for a search query.

        Args:
            query: Partial card name to get suggestions for.
            **kwargs: Additional parameters.

        Returns:
            List of suggested card names.

        Raises:
            AuthenticationError: If not authenticated.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
        """
        self._check_authenticated()

        params: dict[str, Any] = {
            "autoComplete": query,
            "limit": kwargs.get("limit", 10),
        }

        endpoint = "/v2/catalog/products"
        try:
            response = self._make_request("GET", endpoint, params=params)

            data = response.json()
            results = data.get("results", [])
            suggestions = [r.get("name", "") for r in results if r.get("name")]
            return suggestions

        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, endpoint)
            # _handle_http_error always raises, but pyright doesn't know this
            raise  # This should never be reached
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during autocomplete: {e}")
            raise NetworkError(
                "Network error during TCGPlayer autocomplete",
                original_exception=e,
            ) from e

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
        """Iterate through search results page by page.

        This is a generator that yields lists of Card objects, one page at a time.
        It automatically handles pagination until all results are exhausted.

        Args:
            name: Card name to search for.
            **kwargs: Additional search parameters passed to search().

        Yields:
            Card objects one at a time.

        Raises:
            AuthenticationError: If not authenticated.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
        """
        self._check_authenticated()

        page = 1
        limit = kwargs.get("limit", 100)  # Use larger page size for iteration

        while True:
            # Get one page of results
            kwargs["limit"] = limit
            kwargs["page"] = page

            try:
                cards = self.search(name=name, **kwargs)

                # Check if we got any results
                if not cards:
                    break

                for card in cards:
                    yield card
                page += 1

            except (NetworkError, APIError) as e:
                logger.error(f"Error during paginated search on page {page}: {e}")
                raise

    def _check_authenticated(self) -> None:
        """Check if the provider is authenticated.

        If credentials are provided but not yet authenticated, attempts to authenticate.

        Raises:
            AuthenticationError: If not authenticated and cannot authenticate.
        """
        if not self.is_authenticated():
            # If we have credentials, try to authenticate
            if self.client_id and self.client_secret:
                try:
                    self.authenticate()
                except (AuthenticationError, NetworkError):
                    # If auto-authentication fails, raise AuthenticationError
                    raise AuthenticationError(
                        "Authentication required for TCGPlayer API. "
                        "Please provide valid client_id and client_secret. "
                        "Apply for access at https://docs.tcgplayer.com",
                        auth_type="oauth2",
                        provider=self.name,
                    )
            else:
                raise AuthenticationError(
                    "Authentication required for TCGPlayer API. "
                    "Please provide client_id and client_secret. "
                    "Apply for access at https://docs.tcgplayer.com",
                    auth_type="oauth2",
                    provider=self.name,
                )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an authenticated HTTP request to the TCGPlayer API.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path.
            params: Query parameters.
            data: Form data.
            json: JSON body.
            **kwargs: Additional request parameters.

        Returns:
            requests.Response object.

        Raises:
            requests.exceptions.HTTPError: If the response has a non-2xx status.
            requests.exceptions.RequestException: If there is a network error.
        """
        # Check rate limiting before making request
        self._check_rate_limit()

        # Apply authentication if needed
        if not self.is_authenticated():
            raise AuthenticationError(
                "Not authenticated. Call authenticate() first.",
                auth_type="oauth2",
                provider=self.name,
            )

        # Make request through HTTP client
        # Map method to HTTPClient method
        http_method = getattr(self.http_client, method.lower(), None)
        if http_method is None:
            raise ValueError(f"Unsupported HTTP method: {method}")

        try:
            response = http_method(
                endpoint, params=params, data=data, json=json, **kwargs
            )

            # TCGPlayer uses specific error handling
            if response.status_code == 401:
                # Token might have expired, try to refresh
                logger.info("Received 401, attempting to refresh token...")
                self.refresh_auth()
                # Apply new auth to session
                self.auth_handler.apply_auth(self.http_client.session)
                # Retry the request
                response = http_method(
                    endpoint, params=params, data=data, json=json, **kwargs
                )

            # Raise for other errors
            response.raise_for_status()

            return response

        except requests.exceptions.HTTPError as e:
            # Re-raise with context
            raise e

    def _build_search_query(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Build a TCGPlayer search query string from generic parameters.

        Args:
            name: Card name.
            colors: Colors the card must include.
            identity: Colors the card must be exactly.
            type_line: Card type line.
            **kwargs: Additional filter parameters.

        Returns:
            Query string for TCGPlayer search.
        """
        query_parts = []

        if name:
            query_parts.append(f"name:{name}")

        # Handle colors - TCGPlayer uses color codes: W, U, B, R, G
        if colors:
            color_codes = [c.value for c in colors]
            if len(color_codes) == 1:
                query_parts.append(f"color:{color_codes[0]}")
            else:
                # Multiple colors - use colors: exact match
                query_parts.append(f"colors:{''.join(sorted(color_codes))}")

        if identity:
            # Exact color identity match
            color_codes = [c.value for c in identity]
            if color_codes:
                query_parts.append(f"colors:{''.join(sorted(color_codes))}")

        if type_line:
            # TCGPlayer uses type filtering
            query_parts.append(f"type:{type_line}")

        # Handle additional filters from kwargs
        for key, value in kwargs.items():
            if value is not None and key not in [
                "name",
                "colors",
                "identity",
                "type_line",
            ]:
                query_parts.append(f"{key}:{value}")

        return ",".join(query_parts)

    def _parse_card_list_response(self, data: dict[str, Any]) -> list[Card]:
        """Parse a TCGPlayer card list response into Card objects.

        Args:
            data: JSON response data from TCGPlayer API.

        Returns:
            List of Card objects.
        """
        results = data.get("results", [])
        cards = []

        for item in results:
            try:
                card = self._parse_card_data(item)
                cards.append(card)
            except Exception as e:
                logger.warning(f"Failed to parse card data: {e}")
                continue

        return cards

    def _parse_card_response(self, data: dict[str, Any]) -> Card:
        """Parse a TCGPlayer single card response into a Card object.

        Args:
            data: JSON response data for a single card.

        Returns:
            Card object with normalized data.
        """
        return self._parse_card_data(data)

    def _parse_card_data(self, data: dict[str, Any]) -> Card:
        """Parse TCGPlayer card data into a normalized Card object.

        Args:
            data: Raw card data from TCGPlayer API.

        Returns:
            Normalized Card object.

        Note:
            TCGPlayer data needs to be mapped to the normalized Card model.
            This method handles the mapping from TCGPlayer-specific fields.
        """
        # Extract basic information
        name = data.get("name", "")
        product_id = (
            data.get("productId") or data.get("id") or str(data.get("productId", ""))
        )

        # Extract set information
        # TCGPlayer uses categoryName for set code
        set_code = data.get("categoryName", "")
        set_name = data.get("categoryName", "")

        # Extract card number - TCGPlayer uses number field
        card_number = data.get("number", "")

        # Extract rarity - TCGPlayer uses rarity field
        # Map TCGPlayer rarity strings to Rarity enum
        rarity_str = data.get("rarity", "")
        rarity_map = {
            "Common": Rarity.COMMON,
            "Uncommon": Rarity.UNCOMMON,
            "Rare": Rarity.RARE,
            "Mythic Rare": Rarity.MYTHIC,
            "Special": Rarity.SPECIAL,
            "Bonus": Rarity.BONUS,
        }
        rarity = rarity_map.get(rarity_str, None)

        # Extract prices from extended data if available
        extended_data = data.get("extendedData", [])
        pricing_dict: dict[str, float] = {}

        for ext in extended_data:
            if isinstance(ext, dict):
                if "price" in ext and "condition" in ext:
                    condition = ext.get("condition", "").lower()
                    price = ext.get("price", 0)
                    if isinstance(price, (int, float)):
                        pricing_dict[condition] = float(price)

        # Map TCGPlayer category to MTG set types
        set_type_map = {
            "Core Sets": "core",
            "Expansions": "expansion",
            "Reprint Sets": "reprint",
            "Commander": "commander",
            "Promos": "promo",
            "Boxes": "box",
        }

        category = data.get("categoryGroupName", "")
        set_type = set_type_map.get(category, "unknown")

        # Extract color information
        # TCGPlayer provides color data in various ways
        color_data = data.get("color", "")
        color_identity_str = data.get("colorIdentity", "")

        # Parse color string (e.g., "WUBRG" or "White, Blue, Black")
        colors: list[Color] = []
        color_identity: list[Color] = []

        if color_data:
            colors = self._parse_tcgplayer_color_string(color_data)
        if color_identity_str:
            color_identity = self._parse_tcgplayer_color_string(color_identity_str)

        # Extract mana cost
        mana_cost_str = data.get("convertedManaCost")
        cmc = None
        if mana_cost_str is not None:
            try:
                cmc = float(mana_cost_str)
            except (ValueError, TypeError):
                mana_cost_str = str(mana_cost_str)
                cmc = None

        # Extract image URL
        image_url = data.get("imageUrl", "")
        image_uris = {"tcgplayer": image_url} if image_url else None

        # Extract artist
        artist = data.get("artist", "")

        # Extract flavor text
        flavor_text = data.get("flavorText", "")
        flavors = [flavor_text] if flavor_text else None

        # Extract card type
        card_type = data.get("productType", "")

        # Extract power/toughness
        power = data.get("power", "") or None
        toughness = data.get("toughness", "") or None

        # Extract loyalty
        loyalty = data.get("loyalty", "") or None

        # Build the Card object
        try:
            card = Card(
                id=str(product_id) if product_id else "",
                name=name,
                set_code=set_code if set_code else None,
                set_name=set_name if set_name else None,
                set_type=set_type if set_type else None,
                collector_number=card_number if card_number else None,
                rarity=rarity,
                type_line=card_type if card_type else None,
                mana_cost=mana_cost_str,
                cmc=cmc,
                colors=colors if colors else None,
                color_identity=color_identity if color_identity else None,
                power=power,
                toughness=toughness,
                loyalty=loyalty,
                scryfall_id=None,  # TCGPlayer doesn't use Scryfall IDs
                oracle_id=None,
                oracle_text=None,  # Not available in TCGPlayer
                flavors=flavors,
                artist=artist if artist else None,
                image_uris=image_uris,
                tcgplayer_id=int(product_id) if product_id else None,
                source="tcgplayer",
                pricing=(
                    Pricing(tcgplayer=TCGPlayerPricing(**pricing_dict))
                    if pricing_dict
                    else None
                ),
            )
            return card

        except Exception as e:
            logger.error(f"Failed to create Card object: {e}")
            # Return a minimal card with required fields
            return Card(
                id=str(product_id) if product_id else "",
                name=name,
                source="tcgplayer",
            )

    def _parse_tcgplayer_color_string(self, color_str: str) -> list[Color]:
        """Parse a TCGPlayer color string into Color enum values.

        Args:
            color_str: Color string from TCGPlayer (e.g., "WUBRG", "White, Blue").

        Returns:
            List of Color enum values.
        """
        from pymtg.models.enums import Color

        if not color_str:
            return []

        # Handle comma-separated color names
        if "," in color_str:
            color_names = [c.strip().lower() for c in color_str.split(",")]
            color_map = {
                "white": Color.WHITE,
                "blue": Color.BLUE,
                "black": Color.BLACK,
                "red": Color.RED,
                "green": Color.GREEN,
                "colorless": Color.COLORLESS,
            }
            return [color_map.get(c, Color.COLORLESS) for c in color_names]

        # Handle single character codes
        color_map = {
            "W": Color.WHITE,
            "U": Color.BLUE,
            "B": Color.BLACK,
            "R": Color.RED,
            "G": Color.GREEN,
            "C": Color.COLORLESS,
        }

        colors = []
        for char in color_str.upper():
            if char in color_map:
                colors.append(color_map[char])

        return colors

    def _parse_pricing_response(self, data: dict[str, Any]) -> Pricing:
        """Parse a TCGPlayer pricing response into a Pricing object.

        Args:
            data: JSON response data from TCGPlayer pricing endpoint.

        Returns:
            Pricing object with TCGPlayer-specific pricing data.
        """
        # TCGPlayer pricing data structure:
        # {
        #     "productId": 12345,
        #     "skus": [
        #         {
        #             "skuId": 67890,
        #             "price": 1.23,
        #             "conditionId": 1,
        #             "conditionName": "Near Mint",
        #             ...
        #         }
        #     ]
        # }

        results = data.get("results", [])
        tcgplayer_pricing_data: dict[str, float] = {}

        for sku in results:
            condition = sku.get("conditionName", "").lower().replace(" ", "_")
            price = sku.get("price", 0)
            if isinstance(price, (int, float)):
                tcgplayer_pricing_data[condition] = float(price)

        tcgplayer_pricing = TCGPlayerPricing(**tcgplayer_pricing_data)

        return Pricing(tcgplayer=tcgplayer_pricing)

    def _check_rate_limit(self) -> None:
        """Check if the rate limit has been exceeded.

        TCGPlayer has a rate limit of 10 requests per second.

        Raises:
            RateLimitError: If rate limit is exceeded.
        """
        # For now, we'll rely on the HTTP client's rate limiting
        # and the API's own rate limit responses
        pass

    def _handle_http_error(
        self, error: requests.exceptions.HTTPError, endpoint: str
    ) -> None:
        """Handle HTTP errors from the TCGPlayer API.

        Args:
            error: The HTTPError exception.
            endpoint: The API endpoint that caused the error.

        Raises:
            RateLimitError: If rate limit is exceeded.
            NotFoundError: If the resource is not found.
            AuthenticationError: If authentication fails.
            APIError: For other API errors.
        """
        response = error.response

        if response is None:
            raise NetworkError(f"Network error for endpoint {endpoint}") from error

        status_code = response.status_code

        if status_code == 404:
            raise NotFoundError(
                f"Resource not found at {endpoint}",
                provider=self.name,
                status_code=status_code,
            ) from error

        if status_code == 401:
            raise AuthenticationError(
                f"Authentication failed for {endpoint}",
                auth_type="oauth2",
                provider=self.name,
                status_code=status_code,
            ) from error

        if status_code == 429:
            # Parse retry-after header if available
            retry_after = response.headers.get("Retry-After", "0")
            try:
                retry_seconds = int(retry_after)
            except ValueError:
                retry_seconds = 60

            raise RateLimitError(
                f"Rate limit exceeded for TCGPlayer API. Retry after {retry_seconds} seconds.",
                provider=self.name,
                retry_after=retry_seconds,
                status_code=status_code,
            ) from error

        if status_code == 400:
            raise InvalidQueryError(
                f"Invalid query for TCGPlayer API at {endpoint}",
                provider=self.name,
                status_code=status_code,
            ) from error

        # For other errors, raise APIError
        try:
            error_data = response.json()
            error_message = error_data.get("message", "") or error_data.get("error", "")
        except Exception:
            error_message = response.text or "Unknown error"

        raise APIError(
            f"TCGPlayer API error: {error_message}",
            provider=self.name,
            status_code=status_code,
        ) from error

    def get_rate_limit_status(self) -> dict[str, Any]:
        """Get the current rate limit status for this provider.

        Returns:
            Dictionary with rate limit information.
        """
        return {
            "provider": self.name,
            "rate_limit": self.rate_limit,
            "authenticated": self.is_authenticated(),
        }

    def __repr__(self) -> str:
        """Return a string representation of the TCGPlayer provider.

        Returns:
            String representation.
        """
        auth_status = (
            "authenticated" if self.is_authenticated() else "not authenticated"
        )
        return (
            f"TCGPlayer(provider={self.name}, base_url={self.base_url}, {auth_status})"
        )
