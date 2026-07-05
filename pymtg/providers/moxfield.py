"""Moxfield provider implementation for the pymtg library.

This module provides the Moxfield class which implements the BaseProvider interface
for interacting with the Moxfield API via the Parse.bot wrapper service.

Moxfield is a deck building and collection management website for Magic: The
Gathering. Since Moxfield does not have an official public API, this implementation
uses the Parse.bot wrapper service (https://parse.bot) to access Moxfield data.

Note:
    This provider requires a Parse.bot API key passed via the X-API-Key header.
    Users must obtain an API key from Parse.bot to use this provider.

Parse.bot provides a scraping API that wraps Moxfield's internal API endpoints.
"""

import logging
from typing import Any

import requests

from pymtg.auth.api_key import APIKeyAuthHandler
from pymtg.config import PROVIDER_CONFIGS, ProviderConfig
from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    InvalidQueryError,
    NetworkError,
    NotFoundError,
)
from pymtg.models.card import Card, CardFace, DeckCard
from pymtg.models.deck import Deck
from pymtg.models.enums import Board, Color, Format, Rarity, SetType
from pymtg.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class Moxfield(BaseProvider):
    """Moxfield API provider implementation via Parse.bot wrapper.

    This class provides access to Moxfield deck and card data through the
    Parse.bot wrapper service. Moxfield itself does not have a public API,
    so Parse.bot acts as an intermediary that scrapes and provides structured
    access to Moxfield data.

    Authentication is required and uses a Parse.bot API key passed via the
    X-API-Key header.

    Attributes:
        name: Provider name ("moxfield").
        base_url: Base URL for the Parse.bot Moxfield scraper endpoint.
        config: Provider configuration.
        http_client: HTTP client for making requests.
        rate_limit: Rate limit information.
        auth_handler: API key authentication handler.

    Example:
        # Create provider with API key
        moxfield = Moxfield(api_key="your-parse-bot-api-key")

        # Get a specific deck
        deck = moxfield.get_deck("deck-uuid-here")
        print(deck.name)

        # Get user decks
        decks = moxfield.get_user_decks()
        for deck in decks:
            print(deck.name)

        # Search for cards
        cards = moxfield.search(name="Black Lotus", limit=5)
        for card in cards:
            print(card.name, card.set_name)
    """

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        """Initialize the Moxfield provider.

        Args:
            api_key: Parse.bot API key for authentication. Required for all
                endpoints.
            **kwargs: Additional initialization parameters.

        Raises:
            AuthenticationError: If api_key is not provided.
        """
        # Call parent constructor first to ensure base attributes are set
        # before storing provider-specific state. This avoids leaving the
        # object in an inconsistent state if super().__init__() raises.
        super().__init__(**kwargs)

        # Store API key after parent initialization succeeds
        self._api_key = api_key

        # Initialize API key auth handler for Parse.bot
        self.auth_handler = APIKeyAuthHandler(
            header_name="X-API-Key",
            header_prefix=None,
        )

        # Apply authentication if API key was provided
        if api_key:
            self.auth_handler.authenticate(api_key=api_key)
            self._apply_auth_to_http_client()
        else:
            logger.warning(
                "Moxfield provider initialized without API key. "
                "Most endpoints will not work."
            )

    def _initialize(self, **kwargs: Any) -> None:
        """Moxfield-specific initialization.

        Args:
            **kwargs: Additional initialization parameters.
        """
        # Ensure the name is set correctly
        self.name = "moxfield"
        self.config = PROVIDER_CONFIGS.get(
            "moxfield",
            ProviderConfig(
                name="moxfield",
                base_url="",
            ),
        )
        self.base_url = self.config.base_url
        self.rate_limit = self.config.rate_limit or {}

    def _apply_auth_to_http_client(self) -> None:
        """Apply API key authentication to the HTTP client."""
        if self._api_key:
            # Apply auth headers to the existing HTTP client session
            self.auth_handler.apply_auth(self.http_client.session)

    def is_authenticated(self) -> bool:
        """Check if the provider is currently authenticated.

        Returns:
            True if API key is present and valid, False otherwise.
        """
        return self.auth_handler.is_authenticated()

    def refresh_auth(self) -> None:
        """Refresh the provider's authentication.

        For API key authentication, this just verifies the key is still present.

        Raises:
            AuthenticationError: If no API key is present.
        """
        if not self._api_key:
            raise AuthenticationError(
                "Cannot refresh authentication: no API key provided",
                provider=self.name,
                auth_type="api_key",
            )
        self.auth_handler.refresh()
        self._apply_auth_to_http_client()

    def authenticate(self, api_key: str) -> None:
        """Authenticate with Parse.bot using an API key.

        Args:
            api_key: The Parse.bot API key for authentication.

        Raises:
            AuthenticationError: If authentication fails.
        """
        self._api_key = api_key
        self.auth_handler.authenticate(api_key=api_key)
        self._apply_auth_to_http_client()

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

        This method searches for cards using common MTG parameters that are
        mapped to Parse.bot's Moxfield query syntax. It provides a consistent
        interface across all providers.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include in its color identity.
            identity: List of colors the card's color identity must exactly match.
            type_line: Type line the card must include.
            limit: Maximum number of results to return (default 20).
            page: Page number for pagination (1-based, default 1).
            order: Sort order for results.
            **kwargs: Additional Parse.bot/Moxfield-specific parameters:
                - format: Format filter (standard, modern, commander, etc.).
                - rarity: Rarity filter.
                - set: Set code filter.
                - cmc: Converted mana cost filter.

        Returns:
            A list of Card objects matching the search criteria.

        Raises:
            InvalidQueryError: If the search parameters are invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If API key is not provided.
        """
        if not self.is_authenticated():
            raise AuthenticationError(
                "Moxfield requires a Parse.bot API key",
                provider=self.name,
                auth_type="api_key",
            )

        try:
            # Build query parameters
            params: dict[str, Any] = {}

            # Build the query string using Parse.bot's search syntax
            query = self._build_search_query(
                name=name,
                colors=colors,
                identity=identity,
                type_line=type_line,
                **kwargs,
            )

            if query:
                params["query"] = query

            # Parse.bot uses 'limit' and 'offset' for pagination
            # offset = (page - 1) * limit
            if limit:
                params["limit"] = limit
            if page > 1:
                params["offset"] = (page - 1) * limit

            # Add additional kwargs as query parameters
            for key, value in kwargs.items():
                if key not in ["name", "colors", "identity", "type_line"]:
                    params[key] = value

            # Use Parse.bot's /cards/search endpoint
            response = self.http_client.get("/cards/search", params=params)
            data = self._handle_response(response, "cards")

            if not data:
                return []

            # Parse card results
            cards = []
            for card_data in data:
                card = self._parse_card(card_data)
                if card is not None:
                    cards.append(card)

            return cards

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Moxfield search: {e}")
            raise NetworkError(
                "Network error during search", original_exception=e
            ) from e

    def search_syntax(self, query: str, limit: int = 20, **kwargs: Any) -> list[Card]:
        """Search for cards using Parse.bot-specific query syntax.

        This method provides an escape hatch for power users who need to use
        Parse.bot's specific query syntax that is not available through the
        generic search() method.

        Args:
            query: The Parse.bot/Moxfield query string.
            limit: Maximum number of results to return (default 20).
            **kwargs: Additional Parse.bot-specific parameters.

        Returns:
            A list of Card objects matching the query.

        Raises:
            InvalidQueryError: If the query is invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If API key is not provided.
        """
        if not self.is_authenticated():
            raise AuthenticationError(
                "Moxfield requires a Parse.bot API key",
                provider=self.name,
                auth_type="api_key",
            )

        try:
            params: dict[str, Any] = {"query": query}

            if limit:
                params["limit"] = limit

            for key, value in kwargs.items():
                params[key] = value

            # Use Parse.bot's /cards/search endpoint with raw query
            response = self.http_client.get("/cards/search", params=params)
            data = self._handle_response(response, "cards")

            if not data:
                return []

            # Parse card results
            cards = []
            for card_data in data:
                card = self._parse_card(card_data)
                if card is not None:
                    cards.append(card)

            return cards

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Moxfield search_syntax: {e}")
            raise NetworkError(
                "Network error during search_syntax", original_exception=e
            ) from e

    def get_card(self, card_id: str, **kwargs: Any) -> Card:
        """Get a specific card by its Moxfield/Parse.bot ID.

        Note:
            Moxfield uses its own card IDs internally. Parse.bot may use
            different identifiers. Check the API response for the actual ID format.

        Args:
            card_id: The Moxfield/Parse.bot card ID.
            **kwargs: Additional parameters.

        Returns:
            A Card object for the specified card.

        Raises:
            NotFoundError: If the card is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If API key is not provided.
            InvalidQueryError: If card_id is not provided.
        """
        if not card_id:
            raise InvalidQueryError(
                "card_id is required for Moxfield.get_card()",
                provider=self.name,
            )

        if not self.is_authenticated():
            raise AuthenticationError(
                "Moxfield requires a Parse.bot API key",
                provider=self.name,
                auth_type="api_key",
            )

        try:
            # Try using /cards/{id} endpoint
            response = self.http_client.get(f"/cards/{card_id}")
            data = self._handle_response(response, "card")

            if not data:
                raise NotFoundError(
                    "Card not found",
                    provider=self.name,
                    resource_type="card",
                    resource_id=card_id,
                )

            card = self._parse_card(data)
            if card is None:
                raise NotFoundError(
                    "Card has missing required fields",
                    provider=self.name,
                    resource_type="card",
                    resource_id=card_id,
                )
            return card

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Moxfield get_card: {e}")
            raise NetworkError(
                "Network error during get_card", original_exception=e
            ) from e

    def get_deck(self, deck_id: str, **kwargs: Any) -> Deck:
        """Get a specific deck by its Moxfield ID.

        Note:
            Moxfield deck IDs are typically numeric or UUID strings.
            Parse.bot wraps the Moxfield API, so the ID format may vary.

        Args:
            deck_id: The Moxfield deck ID.
            **kwargs: Additional parameters.

        Returns:
            A Deck object for the specified deck.

        Raises:
            NotFoundError: If the deck is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If API key is not provided.
        """
        if not self.is_authenticated():
            raise AuthenticationError(
                "Moxfield requires a Parse.bot API key",
                provider=self.name,
                auth_type="api_key",
            )

        try:
            # Use Parse.bot's /decks/{id} endpoint
            response = self.http_client.get(f"/decks/{deck_id}")
            data = self._handle_response(response, "deck")

            if not data:
                raise NotFoundError(
                    "Deck not found",
                    provider=self.name,
                    resource_type="deck",
                    resource_id=deck_id,
                )

            return self._parse_deck(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Moxfield get_deck: {e}")
            raise NetworkError(
                "Network error during get_deck", original_exception=e
            ) from e

    def get_deck_full(self, deck_id: str, **kwargs: Any) -> Deck:
        """Get a specific deck with full details by its Moxfield ID.

        This method retrieves a deck with all available details, including
        full card information for each card in the deck.

        Note:
            This may make additional API calls to resolve card details
            if not included in the initial response.

        Args:
            deck_id: The Moxfield deck ID.
            **kwargs: Additional parameters.

        Returns:
            A Deck object with full details for the specified deck.

        Raises:
            NotFoundError: If the deck is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If API key is not provided.
        """
        if not self.is_authenticated():
            raise AuthenticationError(
                "Moxfield requires a Parse.bot API key",
                provider=self.name,
                auth_type="api_key",
            )

        try:
            # Use Parse.bot's /decks/{id}/full endpoint if available
            # Otherwise fall back to /decks/{id}
            try:
                response = self.http_client.get(f"/decks/{deck_id}/full")
                data = self._handle_response(response, "deck")
            except APIError:
                # Fall back to regular endpoint
                response = self.http_client.get(f"/decks/{deck_id}")
                data = self._handle_response(response, "deck")

            if not data:
                raise NotFoundError(
                    "Deck not found",
                    provider=self.name,
                    resource_type="deck",
                    resource_id=deck_id,
                )

            return self._parse_deck(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Moxfield get_deck_full: {e}")
            raise NetworkError(
                "Network error during get_deck_full", original_exception=e
            ) from e

    def get_user_decks(self, user_id: str | None = None, **kwargs: Any) -> list[Deck]:
        """Get all decks for a specific user.

        Args:
            user_id: The Moxfield user ID or username. If None, may attempt
                to get decks for the authenticated user (if supported by Parse.bot).
            **kwargs: Additional parameters.

        Returns:
            A list of Deck objects for the user's decks.

        Raises:
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If API key is not provided.
            NotImplementedError: If Parse.bot doesn't support this endpoint.
        """
        if not self.is_authenticated():
            raise AuthenticationError(
                "Moxfield requires a Parse.bot API key",
                provider=self.name,
                auth_type="api_key",
            )

        try:
            # Use Parse.bot's /users/{user_id}/decks endpoint
            if user_id:
                endpoint = f"/users/{user_id}/decks"
            else:
                # Try to get current user's decks
                endpoint = "/users/me/decks"

            response = self.http_client.get(endpoint)
            data = self._handle_response(response, "decks")

            if not data:
                return []

            decks = []
            for deck_data in data:
                decks.append(self._parse_deck(deck_data))

            return decks

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Moxfield get_user_decks: {e}")
            raise NetworkError(
                "Network error during get_user_decks", original_exception=e
            ) from e

    def autocomplete(self, query: str, limit: int = 10, **kwargs: Any) -> list[str]:
        """Get autocomplete suggestions for a query.

        Args:
            query: The partial query string.
            limit: Maximum number of suggestions to return (default 10).
            **kwargs: Additional parameters.

        Returns:
            A list of autocomplete suggestions.

        Raises:
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If API key is not provided.
            NotImplementedError: If autocomplete is not supported.
        """
        if not self.is_authenticated():
            raise AuthenticationError(
                "Moxfield requires a Parse.bot API key",
                provider=self.name,
                auth_type="api_key",
            )

        try:
            params: dict[str, Any] = {"query": query}
            if limit:
                params["limit"] = limit

            for key, value in kwargs.items():
                params[key] = value

            # Use Parse.bot's /cards/autocomplete endpoint
            response = self.http_client.get("/cards/autocomplete", params=params)
            data = self._handle_response(response, "autocomplete")

            if not data:
                return []

            # Data could be a list of strings or a dict with 'suggestions' key
            if isinstance(data, list):
                return [str(item) for item in data]
            elif isinstance(data, dict):
                suggestions = data.get("suggestions", [])
                return [str(item) for item in suggestions]
            else:
                return []

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Moxfield autocomplete: {e}")
            raise NetworkError(
                "Network error during autocomplete", original_exception=e
            ) from e

    def _build_search_query(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Build a Parse.bot/Moxfield query string from search parameters.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include in its color identity.
            identity: List of colors the card's color identity must exactly match.
            type_line: Type line the card must include.
            **kwargs: Additional search parameters.

        Returns:
            A query string suitable for Parse.bot's Moxfield API.
        """
        query_parts = []

        # WUBRG color order for sorting
        color_order = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}

        # Add name filter
        if name:
            # Exact match if it looks like a specific card name
            query_parts.append(f'"{name}"')

        # Add color filters (color inclusion).
        # Moxfield uses Scryfall syntax: c: for single-color include,
        # ci: for multi-color identity inclusion.
        if colors:
            color_str = "".join(
                c.value
                for c in sorted(colors, key=lambda c: color_order.get(c.value, 99))
            )
            if len(colors) == 1:
                query_parts.append(f"c:{color_str}")
            else:
                query_parts.append(f"ci:{color_str}")

        # Add exact color identity filter.
        # id: matches cards whose color identity is within the given set
        # (Scryfall coverage semantics).
        if identity:
            id_str = "".join(
                c.value
                for c in sorted(identity, key=lambda c: color_order.get(c.value, 99))
            )
            query_parts.append(f"id:{id_str}")

        # Add type line filter
        if type_line:
            query_parts.append(f"t:{type_line}")

        # Add additional kwargs
        for key, value in kwargs.items():
            if isinstance(value, str):
                query_parts.append(f"{key}:{value}")
            elif isinstance(value, (list, tuple)):
                for v in value:
                    query_parts.append(f"{key}:{v}")
            else:
                query_parts.append(f"{key}:{value}")

        return " ".join(query_parts)

    def _parse_card(self, data: dict[str, Any]) -> Card | None:
        """Parse Moxfield/Parse.bot card data into a normalized Card model.

        Args:
            data: Raw card data from Parse.bot's Moxfield API.

        Returns:
            A normalized Card object, or None if required fields are missing.
        """
        # Validate required fields
        card_id = data.get("scryfall_id") or data.get("id", "")
        name = data.get("name", "")
        missing_fields = []
        if not card_id:
            missing_fields.append("scryfall_id or id")
        if not name:
            missing_fields.append("name")
        if missing_fields:
            logger.warning(
                f"Skipping card due to missing required fields: "
                f"{', '.join(missing_fields)}"
            )
            return None
        # Handle card faces (for flip/transform cards)
        card_faces_data = data.get("card_faces", [])
        card_faces = None

        if card_faces_data:
            # Multi-faced card
            parsed_faces = []
            for face_data in card_faces_data:
                card_face = CardFace(
                    name=face_data.get("name", ""),
                    mana_cost=face_data.get("mana_cost"),
                    type_line=face_data.get("type_line"),
                    oracle_text=face_data.get("oracle_text") or face_data.get("text"),
                    power=face_data.get("power"),
                    toughness=face_data.get("toughness"),
                    loyalty=face_data.get("loyalty"),
                    flavor_text=face_data.get("flavor_text"),
                    artist=face_data.get("artist"),
                    artist_id=face_data.get("artist_id"),
                    illustration_id=face_data.get("illustration_id"),
                    colors=self._parse_colors(face_data.get("colors", [])),
                    color_indicator=self._parse_colors(
                        face_data.get("color_indicator", [])
                    ),
                )
                parsed_faces.append(card_face)

            if parsed_faces:
                card_faces = parsed_faces

            # Use first face for main card attributes if card_faces exist
            if card_faces:
                first_face = card_faces[0]
                name = first_face.name or data.get("name", "")
                mana_cost = first_face.mana_cost
                type_line = first_face.type_line
                oracle_text = first_face.oracle_text
                power = first_face.power
                toughness = first_face.toughness
                loyalty = first_face.loyalty
            else:
                name = data.get("name", "")
                mana_cost = data.get("mana_cost", "")
                type_line = data.get("type_line", "")
                oracle_text = data.get("oracle_text", "") or data.get("text", "")
                power = data.get("power")
                toughness = data.get("toughness")
                loyalty = data.get("loyalty")
        else:
            # Single-faced card
            name = data.get("name", "")
            mana_cost = data.get("mana_cost", "")
            type_line = data.get("type_line", "")
            oracle_text = data.get("oracle_text", "") or data.get("text", "")
            power = data.get("power")
            toughness = data.get("toughness")
            loyalty = data.get("loyalty")

        # Parse colors from color identity or colors field
        colors = self._parse_colors(data.get("colors", []))

        # Parse color identity
        color_identity = self._parse_colors(data.get("color_identity", []))

        # Parse color indicator
        color_indicator = self._parse_colors(data.get("color_indicator", []))

        # Parse rarity
        rarity_str = data.get("rarity", "").upper()
        try:
            rarity = Rarity[rarity_str]
        except (KeyError, TypeError):
            rarity = Rarity.COMMON  # Default if unknown

        # Parse set information
        set_data = data.get("set", {})
        set_name = set_data.get("name", "") if set_data else data.get("set_name", "")
        set_code = set_data.get("code", "") if set_data else data.get("set_code", "")
        set_type_str = data.get("set_type", "").upper()

        # Parse set type
        try:
            set_type = SetType[set_type_str]
        except (KeyError, TypeError):
            set_type = SetType.CORE  # Default if unknown

        # Build pricing - Parse.bot may not provide full pricing info
        pricing = None

        # Get card ID - use Scryfall ID if available, otherwise Moxfield ID
        card_id = data.get("scryfall_id") or data.get("id", "")

        # Handle flavor text - can be string or list
        flavor_text = data.get("flavor_text")
        if flavor_text and isinstance(flavor_text, str):
            flavors = [flavor_text]
        elif isinstance(flavor_text, list):
            flavors = flavor_text
        else:
            flavors = None

        # Handle image URIs - ensure all values are strings or None
        raw_image_uris = data.get("image_uris", {})
        image_uris: dict[str, str] | None = {}
        if raw_image_uris:
            # Convert all values to strings, filtering out None values
            image_uris = {
                key: str(value)
                for key, value in raw_image_uris.items()
                if value is not None
            }
            image_uris = image_uris if image_uris else None
        elif data.get("image_url"):
            image_url = data.get("image_url")
            image_uris = {"normal": str(image_url)} if image_url is not None else None

        # Parse keywords
        keywords = data.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [keywords]

        return Card(
            id=card_id,
            scryfall_id=data.get("scryfall_id"),
            oracle_id=data.get("oracle_id"),
            name=name,
            printed_name=data.get("printed_name"),
            mana_cost=mana_cost,
            cmc=data.get("cmc"),
            type_line=type_line,
            printed_type_line=data.get("printed_type_line"),
            oracle_text=oracle_text,
            printed_text=data.get("printed_text"),
            flavors=flavors,
            colors=colors if colors else None,
            color_identity=color_identity if color_identity else None,
            color_indicator=color_indicator if color_indicator else None,
            keywords=keywords if keywords else None,
            all_parts=data.get("all_parts"),
            card_faces=card_faces,
            set_code=set_code if set_code else None,
            set_name=set_name if set_name else None,
            set_type=set_type.value if set_type else None,
            rarity=rarity,
            collector_number=data.get("collector_number"),
            power=power,
            toughness=toughness,
            loyalty=loyalty,
            defense=data.get("defense"),
            layout=data.get("layout", "normal"),
            image_uris=image_uris if image_uris else None,
            image_status=data.get("image_status"),
            pricing=pricing,
            legalities=data.get("legalities"),
            released_at=data.get("released_at"),
            reserved=data.get("reserved"),
            foil=data.get("foil"),
            nonfoil=data.get("nonfoil"),
            oversized=data.get("oversized"),
            promo=data.get("promo"),
            reprint=data.get("reprint"),
            variation=data.get("variation"),
            multiverse_ids=data.get("multiverse_ids"),
            tcgplayer_id=data.get("tcgplayer_id"),
            cardmarket_id=data.get("cardmarket_id"),
            prints_search_uri=data.get("prints_search_uri"),
            rulings_uri=data.get("rulings_uri"),
            scryfall_uri=data.get("scryfall_uri"),
            uri=data.get("uri"),
            source="moxfield",
        )

    def _parse_colors(self, colors_data: list[str] | None) -> list[Color] | None:
        """Parse a list of color strings into Color enum values.

        Args:
            colors_data: List of color strings (e.g., ["W", "U", "B"]).

        Returns:
            List of Color enum values, or None if input is None.
        """
        if not colors_data:
            return None

        colors = []
        for color_str in colors_data:
            try:
                colors.append(Color(color_str.upper()))
            except ValueError:
                logger.warning(f"Invalid color: {color_str}")

        return colors if colors else None

    def _parse_deck(self, data: dict[str, Any]) -> Deck:
        """Parse Moxfield/Parse.bot deck data into a normalized Deck model.

        Args:
            data: Raw deck data from Parse.bot's Moxfield API.

        Returns:
            A normalized Deck object.
        """
        deck_cards = []

        # Parse main deck cards - Parse.bot may use different field names
        # Try common field names: cards, main_deck, mainDeck
        main_cards = (
            data.get("cards", [])
            or data.get("main_deck", [])
            or data.get("mainDeck", [])
        )

        for card_data in main_cards:
            # Parse.bot may return card data in different formats
            # Format 1: {"card": {...}, "quantity": N, "board": "main"}
            # Format 2: {"name": "...", "quantity": N, "board": "main", "card": {...}}
            # Format 3: Direct card object with count

            quantity = (
                card_data.get("quantity")
                or card_data.get("count")
                or card_data.get("qty")
                or 1
            )

            # Get card info - could be nested or at top level
            card_info = card_data.get("card", card_data)

            # Parse card
            card = self._parse_card(card_info)
            if card is None:
                continue

            # Determine board - default to MAIN
            board = Board.MAIN
            board_str = card_data.get("board", "") or card_data.get("type", "") or ""
            if board_str:
                try:
                    board = Board[board_str.upper()]
                except (KeyError, TypeError):
                    # Try with lowercase
                    try:
                        board = Board[board_str.lower()]
                    except (KeyError, TypeError):
                        pass

            deck_card = DeckCard(
                card=card,
                count=quantity,
                board=board,
            )
            deck_cards.append(deck_card)

        # Parse sideboard cards if present
        sideboard_cards = data.get("sideboard", []) or data.get("side_board", []) or []
        for card_data in sideboard_cards:
            quantity = (
                card_data.get("quantity")
                or card_data.get("count")
                or card_data.get("qty")
                or 1
            )
            card_info = card_data.get("card", card_data)

            card = self._parse_card(card_info)
            if card is None:
                continue

            deck_card = DeckCard(
                card=card,
                count=quantity,
                board=Board.SIDEBOARD,
            )
            deck_cards.append(deck_card)

        # Parse commander cards if present
        commander_cards = data.get("commanders", []) or data.get("commander", []) or []
        for card_data in commander_cards:
            card_info = card_data.get("card", card_data)

            card = self._parse_card(card_info)
            if card is None:
                continue

            deck_card = DeckCard(
                card=card,
                count=1,
                board=Board.COMMANDER,
            )
            deck_cards.append(deck_card)

        # Parse maybe board cards if present
        maybe_cards = data.get("maybe", []) or data.get("maybe_board", []) or []
        for card_data in maybe_cards:
            quantity = (
                card_data.get("quantity")
                or card_data.get("count")
                or card_data.get("qty")
                or 1
            )
            card_info = card_data.get("card", card_data)

            card = self._parse_card(card_info)
            if card is None:
                continue

            deck_card = DeckCard(
                card=card,
                count=quantity,
                board=Board.MAYBEBOARD,
            )
            deck_cards.append(deck_card)

        # Parse format
        format_str = (data.get("format", "") or "").upper()
        try:
            deck_format = Format[format_str]
        except (KeyError, TypeError):
            deck_format = Format.COMMANDER  # Default if unknown

        # Get deck description
        description = data.get("description", "") or data.get("desc", "")

        # Get deck ID
        deck_id = data.get("id") or data.get("uuid", "") or data.get("deck_id", "")

        # Get owner information
        owner = (
            data.get("owner", "") or data.get("username", "") or data.get("user", "")
        )
        owner_id = data.get("owner_id", "") or data.get("user_id", "")

        # Determine privacy
        is_public = data.get("is_public", True)
        privacy = "private" if is_public is False else "public"

        # Parse tags
        tags = data.get("tags", []) or []

        # Parse categories
        categories = data.get("categories", []) or []

        # Parse view count
        views = data.get("views") or data.get("view_count")

        # Parse upvotes/downvotes
        upvotes = data.get("upvotes") or data.get("likes")
        downvotes = data.get("downvotes") or data.get("dislikes")

        return Deck(
            id=deck_id,
            name=data.get("name", "Unnamed Deck"),
            description=description,
            format=deck_format,
            commander=data.get("commander", []),
            cards=deck_cards,
            source="moxfield",
            source_id=data.get("source_id"),
            url=data.get("url"),
            owner=owner,
            owner_id=owner_id,
            privacy=privacy,
            created_at=data.get("created_at") or data.get("createdAt"),
            updated_at=data.get("updated_at") or data.get("updatedAt"),
            views=views,
            upvotes=upvotes,
            downvotes=downvotes,
            tags=tags,
            categories=categories,
            collapsed=data.get("collapsed"),
        )

    def __repr__(self) -> str:
        """Return a string representation of the Moxfield provider.

        Returns:
            A string representation suitable for debugging.
        """
        auth_status = (
            "authenticated" if self.is_authenticated() else "not authenticated"
        )
        return (
            f"Moxfield(name={self.name!r}, "
            f"base_url={self.base_url!r}, {auth_status})"
        )
