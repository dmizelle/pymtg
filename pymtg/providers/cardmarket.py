"""Cardmarket provider implementation for the pymtg library.

This module provides the Cardmarket class which implements the
BaseProvider interface for interacting with the Cardmarket API
(https://apiv2.cardmarket.com).

Cardmarket is an official European marketplace for trading card games
including Magic: The Gathering. Their API provides access to catalog
data, pricing information, and marketplace data.

Note:
    New developer access to the Cardmarket API is currently closed.
    Requires a pre-approved application at https://api.cardmarket.com

Cardmarket uses OAuth 1.0a for authentication.
"""

import logging
from typing import Any

import requests

from pymtg.auth.oauth1 import OAuth1Handler
from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    InvalidQueryError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from pymtg.models.card import Card, CardFace
from pymtg.models.enums import Color, Format, Rarity
from pymtg.models.pricing import CardmarketPricing, Pricing
from pymtg.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class Cardmarket(BaseProvider):
    """Cardmarket API provider implementation.

    This class provides access to the official Cardmarket API, which
    offers comprehensive catalog, pricing, and marketplace data for
    Magic: The Gathering cards, primarily serving the European market.

    Authentication is required and uses OAuth 1.0a flow.
    New developer access is currently closed - requires pre-approved application
    at https://api.cardmarket.com.

    Attributes:
        name: Provider name ("cardmarket").
        base_url: Base URL for the Cardmarket API ("https://apiv2.cardmarket.com").
        config: Provider configuration.
        http_client: HTTP client for making requests.
        rate_limit: Rate limit information.
        auth_handler: OAuth1 authentication handler.

    Example:
        # Note: Requires pre-approved Cardmarket developer credentials
        # Create provider with OAuth1 credentials
        cardmarket = Cardmarket(
            consumer_key="your_consumer_key",
            consumer_secret="your_consumer_secret",
            access_token="your_access_token",
            access_token_secret="your_access_token_secret"
        )

        # Get a specific card
        card = cardmarket.get_card(card_id="card-id-here")
        print(card.name, card.set_name)

        # Search for cards
        cards = cardmarket.search(name="Black Lotus", limit=5)
        for card in cards:
            print(card.name)

    Warning:
        New Cardmarket developer applications are currently closed. You must
        have pre-approved credentials to use this provider. See
        https://api.cardmarket.com for more information.
    """

    def __init__(
        self,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        access_token: str | None = None,
        access_token_secret: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Cardmarket provider.

        Args:
            consumer_key: OAuth1 consumer key for Cardmarket API.
            consumer_secret: OAuth1 consumer secret for Cardmarket API.
            access_token: OAuth1 access token for Cardmarket API.
            access_token_secret: OAuth1 access token secret for Cardmarket API.
            **kwargs: Additional initialization parameters.

        Raises:
            AuthenticationError: If authentication fails during initialization.

        Note:
            Requires pre-approved Cardmarket developer credentials.
            New access is currently closed to new developers.
            All four OAuth1 credentials are required for authentication.
        """
        # Store OAuth1 credentials before calling super().__init__
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._access_token = access_token
        self._access_token_secret = access_token_secret

        # Call parent constructor which will call _initialize
        super().__init__(**kwargs)

        # Initialize OAuth1 auth handler
        self.auth_handler = OAuth1Handler(
            consumer_key=self._consumer_key,
            consumer_secret=self._consumer_secret,
            access_token=self._access_token,
            access_token_secret=self._access_token_secret,
            signature_method="HMAC-SHA1",
        )

        # Apply authentication if credentials were provided
        if consumer_key and consumer_secret and access_token and access_token_secret:
            self.auth_handler.authenticate(
                consumer_key,
                consumer_secret,
                access_token,
                access_token_secret,
            )
            self._apply_auth_to_http_client()

    def _initialize(self, **kwargs: Any) -> None:
        """Cardmarket-specific initialization.

        Args:
            **kwargs: Additional initialization parameters.
        """
        # This is called by BaseProvider.__init__ before auth_handler is set
        # So we just need to make sure the base class initialization is complete
        pass

    def _apply_auth_to_http_client(self) -> None:
        """Apply OAuth1 authentication to the HTTP client."""
        # Apply OAuth1 signing to the HTTP client's session
        if self.auth_handler.is_authenticated():
            self.auth_handler.apply_auth(self.http_client.session)

    def is_authenticated(self) -> bool:
        """Check if the provider is currently authenticated.

        Returns:
            True if OAuth1 credentials are present and valid, False otherwise.
        """
        return self.auth_handler.is_authenticated()

    def refresh_auth(self) -> None:
        """Refresh the provider's authentication.

        For OAuth1, this requires obtaining new access token/secret through
        the full OAuth1 flow, which is not supported automatically.

        Raises:
            AuthenticationError: Always, as OAuth1 does not support
                automatic refresh.
        """
        # OAuth1 doesn't have automatic refresh
        # Users need to obtain new access token/secret and re-authenticate
        raise AuthenticationError(
            "OAuth1 does not support automatic token refresh. "
            "Please obtain new access token and secret from Cardmarket "
            "and re-instantiate the provider.",
            auth_type="oauth1",
            provider=self.name,
        )

    def authenticate(
        self,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        access_token: str | None = None,
        access_token_secret: str | None = None,
    ) -> None:
        """Authenticate with Cardmarket using OAuth1 credentials.

        Args:
            consumer_key: The OAuth1 consumer key
                (overrides initialization value).
            consumer_secret: The OAuth1 consumer secret
                (overrides initialization value).
            access_token: The OAuth1 access token
                (overrides initialization value).
            access_token_secret: The OAuth1 access token secret
                (overrides initialization value).

        Raises:
            AuthenticationError: If authentication fails.

        Note:
            Requires pre-approved Cardmarket developer credentials.
            All four OAuth1 parameters are required.
        """
        # Update stored credentials
        self._consumer_key = consumer_key or self._consumer_key
        self._consumer_secret = consumer_secret or self._consumer_secret
        self._access_token = access_token or self._access_token
        self._access_token_secret = access_token_secret or self._access_token_secret

        # Recreate auth handler with new credentials
        self.auth_handler = OAuth1Handler(
            consumer_key=self._consumer_key,
            consumer_secret=self._consumer_secret,
            access_token=self._access_token,
            access_token_secret=self._access_token_secret,
            signature_method="HMAC-SHA1",
        )

        # Authenticate
        self.auth_handler.authenticate(
            self._consumer_key,
            self._consumer_secret,
            self._access_token,
            self._access_token_secret,
        )
        self._apply_auth_to_http_client()
        logger.info("Cardmarket OAuth1 authentication successful")

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

        This method searches for Magic: The Gathering cards using the Cardmarket
        /products endpoint. It maps generic parameters to Cardmarket-specific
        query parameters.

        Note:
            Cardmarket API supports JSON output by appending /output.json/ to
            endpoints. This is handled automatically.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include in its color identity.
            identity: List of colors the card's color identity must exactly
                match.
            type_line: Type line the card must include.
            limit: Maximum number of results to return (default 20).
            page: Page number for pagination (1-based, default 1).
            order: Sort order for results.
            **kwargs: Additional Cardmarket-specific parameters.

        Returns:
            A list of Card objects matching the search criteria.

        Raises:
            InvalidQueryError: If the search parameters are invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If authentication is required but not provided.
        """
        try:
            # Validate authentication
            if not self.is_authenticated():
                raise AuthenticationError(
                    "Authentication required for Cardmarket API",
                    provider=self.name,
                    auth_type="oauth1",
                )

            # Build query parameters for Cardmarket /products endpoint
            params: dict[str, Any] = {}

            # Map generic parameters to Cardmarket-specific parameters
            if name:
                params["search"] = name

            # Cardmarket uses: name, game, category, etc.
            # For MTG, game would be "Magic" or similar
            params["game"] = kwargs.get("game", "Magic")

            # Handle limit and pagination
            # Cardmarket uses limit and offset
            if limit:
                params["limit"] = limit
            if page > 1:
                params["offset"] = (page - 1) * limit

            # Add additional kwargs as query parameters
            for key, value in kwargs.items():
                if value is not None and key not in [
                    "name",
                    "colors",
                    "identity",
                    "type_line",
                    "game",
                ]:
                    params[key] = value

            # Cardmarket endpoints require /output.json/ suffix for JSON output
            endpoint = "/ws/v2.0/products/output.json/"

            response = self.http_client.get(endpoint, params=params)
            data = self._handle_response(response, "cards")

            if not data:
                return []

            # Parse card results - Cardmarket API wraps results in a "results" key
            results = data.get("results", []) if isinstance(data, dict) else data

            # Parse card results
            cards = []
            for card_data in results:
                cards.append(self._parse_card(card_data))

            return cards

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Cardmarket search: {e}")
            raise NetworkError(
                "Network error during search", original_exception=e
            ) from e

    def search_syntax(self, query: str, limit: int = 20, **kwargs: Any) -> list[Card]:
        """Search for cards using Cardmarket-specific query syntax.

        This method provides an escape hatch for power users who need to use
        Cardmarket-specific query syntax that is not available through the
        generic search() method.

        Note:
            Cardmarket uses parameter-based search rather than a query string,
            but this method accepts the query as a name parameter.

        Args:
            query: The Cardmarket-specific query string.
            limit: Maximum number of results to return (default 20).
            **kwargs: Additional Cardmarket-specific parameters.

        Returns:
            A list of Card objects matching the query.

        Raises:
            InvalidQueryError: If the query is invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If authentication is required but not provided.
            InvalidQueryError: If query or limit is invalid.
        """
        if not query or not isinstance(query, str):
            raise InvalidQueryError("Query must be a non-empty string")

        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise InvalidQueryError("limit must be a positive integer (>= 1)")

        try:
            # Validate authentication
            if not self.is_authenticated():
                raise AuthenticationError(
                    "Authentication required for Cardmarket API",
                    provider=self.name,
                    auth_type="oauth1",
                )

            # Build parameters
            params: dict[str, Any] = {"search": query}

            if limit:
                params["limit"] = limit

            # Add standard pagination
            page = kwargs.get("page", 1)
            if page > 1:
                params["offset"] = (page - 1) * limit

            # Add any additional parameters
            for key, value in kwargs.items():
                if value is not None and key not in ["limit", "page"]:
                    params[key] = value

            # Cardmarket endpoints require /output.json/ suffix for JSON output
            endpoint = "/ws/v2.0/products/output.json/"

            response = self.http_client.get(endpoint, params=params)
            data = self._handle_response(response, "cards")

            if not data:
                return []

            # Parse card results - Cardmarket API wraps results in a "results" key
            results = data.get("results", []) if isinstance(data, dict) else data

            # Parse card results
            cards = []
            for card_data in results:
                cards.append(self._parse_card(card_data))

            return cards

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Cardmarket search_syntax: {e}")
            raise NetworkError(
                "Network error during search_syntax", original_exception=e
            ) from e

    def get_card(self, card_id: str, **kwargs: Any) -> Card:
        """Get a specific card by its Cardmarket product ID.

        Cardmarket uses product IDs to identify cards. The
        /products/find endpoint can be used to find cards by various
        identifiers.

        Note:
            Cardmarket API may use different ID formats than other providers.
            This method attempts to handle various ID types.

        Args:
            card_id: The Cardmarket product ID or other identifier for the card.
            **kwargs: Additional parameters.

        Returns:
            A Card object for the specified card.

        Raises:
            NotFoundError: If the card is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If authentication is required but not provided.
        """
        try:
            # Validate authentication
            if not self.is_authenticated():
                raise AuthenticationError(
                    "Authentication required for Cardmarket API",
                    provider=self.name,
                    auth_type="oauth1",
                )

            # Try to use /products/find endpoint first
            # Cardmarket /products/find endpoint accepts various identifiers
            find_params: dict[str, Any] = {}

            # Try to determine the ID type
            # Cardmarket uses numeric IDs, but also accepts other identifiers
            try:
                # If it's a numeric ID, use it directly
                product_id = int(card_id)
                find_params["idProduct"] = product_id
            except ValueError:
                # Not a numeric ID, try other fields
                find_params["name"] = card_id

            # Add game filter
            find_params["game"] = kwargs.get("game", "Magic")

            # Cardmarket endpoints require /output.json/ suffix for JSON output
            endpoint = "/ws/v2.0/products/find/output.json/"

            response = self.http_client.get(endpoint, params=find_params)
            data = self._handle_response(response, "card")

            if not data:
                raise NotFoundError(
                    f"Card with ID {card_id} not found",
                    provider=self.name,
                    resource_id=card_id,
                    resource_type="card",
                )

            # Parse and return the first card from results - Cardmarket API wraps results in a "results" key
            results = data.get("results", []) if isinstance(data, dict) else data

            # Parse and return the first card from results
            cards = [self._parse_card(card_data) for card_data in results]
            if cards:
                return cards[0]
            else:
                raise NotFoundError(
                    f"Card with ID {card_id} not found",
                    provider=self.name,
                    resource_id=card_id,
                    resource_type="card",
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Cardmarket get_card: {e}")
            raise NetworkError(
                "Network error during get_card", original_exception=e
            ) from e

    def get_pricing(self, product_id: int | str, **kwargs: Any) -> Pricing:
        """Get pricing information for a card by its product ID.

        Cardmarket provides comprehensive pricing data through the
        /marketplace/prices endpoint.

        Note:
            Requires authentication. Returns pricing data for various
            conditions and marketplaces.

        Args:
            product_id: The Cardmarket product ID for the card.
            **kwargs: Additional parameters.

        Returns:
            A Pricing object containing Cardmarket-specific pricing data.

        Raises:
            NotFoundError: If the card or pricing data is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If authentication is required but not provided.
        """
        try:
            # Validate authentication
            if not self.is_authenticated():
                raise AuthenticationError(
                    "Authentication required for Cardmarket API",
                    provider=self.name,
                    auth_type="oauth1",
                )

            # Ensure product_id is an integer
            try:
                product_id_int = int(product_id)
            except (ValueError, TypeError):
                raise InvalidQueryError(
                    f"Invalid product_id: {product_id}. Must be numeric.",
                    provider=self.name,
                )

            # Cardmarket marketplace/prices endpoint
            endpoint = f"/ws/v2.0/marketplace/prices/{product_id_int}/output.json/"

            response = self.http_client.get(endpoint)
            data = self._handle_response(response, "pricing")

            if not data:
                raise NotFoundError(
                    f"Pricing for product ID {product_id} not found",
                    provider=self.name,
                    resource_id=str(product_id),
                    resource_type="pricing",
                )

            return self._parse_pricing(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Cardmarket get_pricing: {e}")
            raise NetworkError(
                "Network error during get_pricing", original_exception=e
            ) from e

    def _build_search_query(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Build a Cardmarket-specific query string from generic parameters.

        Args:
            name: Card name.
            colors: Colors the card must include.
            identity: Colors the card must be exactly.
            type_line: Card type line.
            **kwargs: Additional filter parameters.

        Returns:
            Query string for Cardmarket search.
        """
        query_parts = []

        if name:
            query_parts.append(name)

        # Handle colors - Cardmarket uses color codes: W, U, B, R, G
        if colors:
            color_codes = [c.value for c in colors]
            if len(color_codes) == 1:
                query_parts.append(f"color:{color_codes[0]}")
            else:
                query_parts.append(f"colors:{''.join(sorted(color_codes))}")

        if identity:
            color_codes = [c.value for c in identity]
            if color_codes:
                query_parts.append(f"identity:{''.join(sorted(color_codes))}")

        if type_line:
            query_parts.append(f"type:{type_line}")

        # Add any additional filters from kwargs
        for key, value in kwargs.items():
            if value is not None and key not in [
                "name",
                "colors",
                "identity",
                "type_line",
            ]:
                query_parts.append(f"{key}:{value}")

        return " ".join(query_parts)

    def _parse_card(self, card_data: dict[str, Any]) -> Card:
        """Parse Cardmarket card data into a normalized Card model.

        Args:
            card_data: Raw card data from Cardmarket API.

        Returns:
            A normalized Card object.

        Note:
            Cardmarket data structure may differ from other providers.
            This method maps Cardmarket-specific fields to the normalized
            Card model fields.
        """
        # Cardmarket card data mapping
        # Note: Cardmarket returns product data which may have
        # different structure

        # Extract basic card information
        name = card_data.get("name", "")

        # Cardmarket uses idProduct as the unique identifier
        product_id = card_data.get("idProduct", card_data.get("id", ""))
        card_id = str(product_id)

        # Extract set information
        # Cardmarket may have expansion or category for set info
        set_name = card_data.get("expansion", card_data.get("category", ""))
        set_code = card_data.get("expansionCode", card_data.get("abbreviation", ""))

        # Extract card number
        card_number = card_data.get("number", "")

        # Extract rarity - Cardmarket uses rarity or rarityName
        rarity_str = card_data.get("rarity", card_data.get("rarityName", ""))
        # Map Cardmarket rarity names to our enum
        # Cardmarket may use different formats: "Common", "Uncommon",
        # "Rare", "Mythic Rare"
        rarity_map = {
            "Common": Rarity.COMMON,
            "Uncommon": Rarity.UNCOMMON,
            "Rare": Rarity.RARE,
            "Mythic Rare": Rarity.MYTHIC,
            "Mythic": Rarity.MYTHIC,
            "Special": Rarity.SPECIAL,
            "Bonus": Rarity.BONUS,
            "common": Rarity.COMMON,
            "uncommon": Rarity.UNCOMMON,
            "rare": Rarity.RARE,
            "mythic": Rarity.MYTHIC,
            "mythic rare": Rarity.MYTHIC,
            "special": Rarity.SPECIAL,
            "bonus": Rarity.BONUS,
        }
        rarity = rarity_map.get(rarity_str, Rarity.COMMON)

        # Extract card type
        type_line = card_data.get("type", "")

        # Extract mana cost - Cardmarket may use convertedManaCost
        mana_cost = card_data.get("manaCost", "")
        cmc = card_data.get("convertedManaCost")
        if cmc is not None:
            try:
                cmc = float(cmc)
            except (ValueError, TypeError):
                cmc = None

        # Extract colors - Cardmarket provides color data
        color_data = card_data.get("color", "")
        color_identity_str = card_data.get("colorIdentity", "")

        # Parse color string
        colors = self._parse_cardmarket_color_string(color_data)
        color_identity = (
            self._parse_cardmarket_color_string(color_identity_str) or colors
        )

        # Extract power and toughness
        power = card_data.get("power")
        toughness = card_data.get("toughness")
        if power is not None:
            power = str(power)
        if toughness is not None:
            toughness = str(toughness)

        # Extract loyalty
        loyalty = card_data.get("loyalty")
        if loyalty is not None:
            loyalty = str(loyalty)

        # Extract flavor text
        flavor_text = card_data.get("flavorText", "")
        flavors = [flavor_text] if flavor_text else None

        # Extract artist
        artist = card_data.get("artist", "")

        # Extract multiverse IDs if available
        multiverse_ids = card_data.get("multiverseIds", [])
        if multiverse_ids and isinstance(multiverse_ids, list):
            multiverse_ids = list(str(mid) for mid in multiverse_ids)
        else:
            multiverse_ids = []

        # Extract legalities - Cardmarket may have legalities data
        legalities_data = card_data.get("legalities", {})
        legalities = {}
        for fmt, status in legalities_data.items():
            try:
                format_enum = Format(fmt)
                legalities[format_enum] = status
            except ValueError:
                legalities[fmt] = status

        # Extract image URL
        image_url = card_data.get("imageUrl", "")
        image_uris = {"cardmarket": image_url} if image_url else None

        # Parse card faces (for split/flip/transform cards)
        # Cardmarket may have cardFaces or similar
        card_faces_data = card_data.get("cardFaces", [])
        faces = []
        for face_data in card_faces_data:
            if isinstance(face_data, dict):
                face = CardFace(
                    name=face_data.get("name", ""),
                    mana_cost=face_data.get("manaCost", ""),
                    type_line=face_data.get("type", ""),
                    oracle_text=face_data.get("text", ""),
                    flavor_text=face_data.get("flavorText", ""),
                    power=face_data.get("power"),
                    toughness=face_data.get("toughness"),
                    loyalty=face_data.get("loyalty"),
                    colors=self._parse_cardmarket_color_string(
                        face_data.get("colors", "")
                    ),
                )
                faces.append(face)

        # Create the normalized Card object
        try:
            card = Card(
                id=card_id,
                name=name,
                set_code=set_code if set_code else None,
                set_name=set_name if set_name else None,
                set_type=None,  # Not directly available from Cardmarket
                collector_number=card_number if card_number else None,
                rarity=rarity,
                type_line=type_line if type_line else None,
                mana_cost=mana_cost if mana_cost else None,
                cmc=cmc,
                colors=colors if colors else None,
                color_identity=color_identity if color_identity else None,
                power=power,
                toughness=toughness,
                loyalty=loyalty,
                scryfall_id=None,  # Cardmarket doesn't use Scryfall IDs
                oracle_id=None,
                oracle_text=None,
                flavors=flavors,
                artist=artist if artist else None,
                image_uris=image_uris,
                cardmarket_id=int(product_id) if product_id else None,
                source="cardmarket",
            )
            return card

        except Exception as e:
            logger.error(f"Failed to create Card object: {e}")
            # Return a minimal card with required fields
            return Card(
                id=card_id,
                name=name,
                source="cardmarket",
            )

    def _parse_cardmarket_color_string(self, color_str: str) -> list[Color]:
        """Parse a Cardmarket color string into Color enum values.

        Args:
            color_str: Color string from Cardmarket.

        Returns:
            List of Color enum values.
        """
        if not color_str:
            return []

        # Handle comma-separated color names
        if "," in color_str:
            color_names = [c.strip().lower() for c in color_str.split(",")]
            color_map: dict[str, Color] = {
                "white": Color("W"),
                "blue": Color("U"),
                "black": Color("B"),
                "red": Color("R"),
                "green": Color("G"),
                "colorless": Color("C"),
            }
            return [color_map.get(c, Color.COLORLESS) for c in color_names]

        # Handle single character codes
        color_map: dict[str, Color] = {
            "W": Color("W"),
            "U": Color("U"),
            "B": Color("B"),
            "R": Color("R"),
            "G": Color("G"),
            "C": Color.COLORLESS,
        }

        colors = []
        for char in color_str.upper():
            if char in color_map:
                colors.append(color_map[char])

        return colors

    def _parse_pricing(self, pricing_data: dict[str, Any]) -> Pricing:
        """Parse Cardmarket pricing data into a normalized Pricing model.

        Args:
            pricing_data: Raw pricing data from Cardmarket API.

        Returns:
            A normalized Pricing object with Cardmarket-specific data.
        """
        # Cardmarket pricing data structure may vary
        # The /marketplace/prices endpoint returns price data for
        # various sellers

        # Initialize with None values for all valid fields
        cardmarket_pricing_data: dict[str, float | None] = {
            "avg1": None,
            "avg7": None,
            "avg30": None,
            "low": None,
            "low_ex": None,
            "trend": None,
        }

        # Try to extract from results or direct structure
        results = pricing_data.get("results", [])
        if results:
            # Aggregate prices by condition
            for result in results:
                condition = result.get("condition", "").lower().replace(" ", "_")
                condition_name = (
                    result.get("conditionName", "").lower().replace(" ", "_")
                )
                price = result.get("price", 0)
                if isinstance(price, (int, float)):
                    # Map condition names to our fields
                    if condition in [
                        "near_mint",
                        "mint",
                    ] or condition_name in [
                        "near_mint",
                        "mint",
                    ]:
                        cardmarket_pricing_data["avg1"] = float(price)
                    elif condition in [
                        "excellent",
                        "ex",
                    ] or condition_name in [
                        "excellent",
                        "ex",
                    ]:
                        cardmarket_pricing_data["low_ex"] = float(price)
                    elif condition == "low" or condition_name == "low":
                        cardmarket_pricing_data["low"] = float(price)
        else:
            # Try direct fields
            for field in ["avg1", "avg7", "avg30", "low", "low_ex", "trend"]:
                if field in pricing_data:
                    price = pricing_data[field]
                    if isinstance(price, (int, float)):
                        cardmarket_pricing_data[field] = float(price)

        # Also check for price trends
        trends = pricing_data.get("trends", {})
        if "avg1" in trends and isinstance(trends["avg1"], (int, float)):
            cardmarket_pricing_data["avg1"] = float(trends["avg1"])
        if "avg7" in trends and isinstance(trends["avg7"], (int, float)):
            cardmarket_pricing_data["avg7"] = float(trends["avg7"])
        if "avg30" in trends and isinstance(trends["avg30"], (int, float)):
            cardmarket_pricing_data["avg30"] = float(trends["avg30"])

        cardmarket_pricing = CardmarketPricing(**cardmarket_pricing_data)

        pricing = Pricing(
            cardmarket=cardmarket_pricing,
        )

        return pricing

    def _check_rate_limit(self) -> None:
        """Check if the rate limit has been exceeded.

        Cardmarket has a rate limit of 30,000-100,000 requests per day.

        Raises:
            RateLimitError: If rate limit is exceeded.
        """
        # For now, we'll rely on the HTTP client's rate limiting
        # and the API's own rate limit responses
        pass

    def _handle_response(
        self, response: requests.Response, resource_type: str | None = None
    ) -> Any:
        """Handle an HTTP response and raise appropriate exceptions.

        This method overrides the base class to handle Cardmarket-specific
        response formats and error codes.

        Args:
            response: The requests.Response object.
            resource_type: The type of resource being retrieved.

        Returns:
            The parsed response data.

        Raises:
            NotFoundError: If the response status is 404.
            RateLimitError: If the response status is 429.
            AuthenticationError: If the response status is 401 or 403.
            APIError: If the response status is 4xx or 5xx.
        """
        # First, handle HTTP errors
        if response.status_code >= 400:
            self._handle_http_error(response, resource_type or "unknown")

        # Try to parse JSON response
        try:
            return response.json()
        except ValueError:
            return response.text

    def _handle_http_error(
        self, response: requests.Response, resource_type: str
    ) -> None:
        """Handle HTTP errors from the Cardmarket API.

        Args:
            response: The error response.
            resource_type: The type of resource that caused the error.

        Raises:
            RateLimitError: If rate limit is exceeded.
            NotFoundError: If the resource is not found.
            AuthenticationError: If authentication fails.
            APIError: For other API errors.
        """
        status_code = response.status_code

        if status_code == 404:
            raise NotFoundError(
                f"Resource not found: {resource_type}",
                provider=self.name,
                status_code=status_code,
                resource_type=resource_type,
            )

        if status_code == 401:
            raise AuthenticationError(
                "OAuth1 authentication failed",
                auth_type="oauth1",
                provider=self.name,
                status_code=status_code,
            )

        if status_code == 403:
            raise AuthenticationError(
                "Access denied (OAuth1 authorization failed)",
                auth_type="oauth1",
                provider=self.name,
                status_code=status_code,
            )

        if status_code == 429:
            # Parse retry-after header if available
            retry_after = response.headers.get("Retry-After", "0")
            try:
                retry_seconds = int(retry_after)
            except ValueError:
                retry_seconds = 3600  # 1 hour default

            raise RateLimitError(
                f"Rate limit exceeded for Cardmarket API. "
                f"Retry after {retry_seconds} seconds.",
                provider=self.name,
                retry_after=retry_seconds,
                status_code=status_code,
            )

        if status_code == 400:
            raise InvalidQueryError(
                "Invalid query for Cardmarket API",
                provider=self.name,
                status_code=status_code,
            )

        # For other errors, try to extract error message from response
        try:
            error_data = response.json()
            error_message = error_data.get("message", "") or error_data.get("error", "")
        except Exception:
            error_message = response.text or "Unknown error"

        raise APIError(
            f"Cardmarket API error: {error_message}",
            provider=self.name,
            status_code=status_code,
        )

    def get_rate_limit_status(self) -> dict[str, Any]:
        """Get the current rate limit status for Cardmarket.

        Returns:
            A dictionary containing rate limit information specific
            to Cardmarket.

        Note:
            Cardmarket rate limit is 30,000-100,000 requests per day.
        """
        status = super().get_rate_limit_status()
        status.update(
            {
                "provider": self.name,
                "provider_specific": {
                    "requests_per_day_min": 30000,
                    "requests_per_day_max": 100000,
                    "requests_per_day": "30000-100000",
                },
                "authenticated": self.is_authenticated(),
                "api_version": "2.0 (release1)",
            }
        )
        return status

    def close(self) -> None:
        """Close the provider's resources."""
        self.auth_handler.clear_auth()
        super().close()

    def __repr__(self) -> str:
        """Return a string representation of the Cardmarket provider.

        Returns:
            String representation.
        """
        auth_status = (
            "authenticated" if self.is_authenticated() else "not authenticated"
        )
        return (
            f"Cardmarket(provider={self.name}, base_url={self.base_url}, "
            f"{auth_status})"
        )
