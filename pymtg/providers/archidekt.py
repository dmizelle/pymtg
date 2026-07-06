"""Archidekt provider implementation for the pymtg library.

This module provides the Archidekt class which implements the
BaseProvider interface for interacting with the Archidekt API
(https://archidekt.com).

Archidekt is a deck building and collection management website for
Magic: The Gathering. It provides an unofficial API for accessing deck
and card data.

Note:
    The Archidekt API is unofficial and undocumented. This
    implementation is based on reverse-engineering of the website's API
    endpoints. Users may need to provide HAR files for testing and
    verification of API behavior.

Archidekt uses session-based authentication with CSRF protection.
"""

import logging
from typing import Any

import requests

from pymtg.auth.session import SessionAuthHandler
from pymtg.exceptions import InvalidQueryError, NetworkError, NotFoundError
from pymtg.models.card import Card, CardFace
from pymtg.models.deck import Deck
from pymtg.models.enums import Board, Color, Format, Rarity, SetType
from pymtg.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class Archidekt(BaseProvider):
    """Archidekt API provider implementation.

    This class provides access to the Archidekt API, which is an
    unofficial API for the Archidekt deck building website.
    Archidekt provides deck management,
    card search, and collection tracking features.

    Authentication is required for most endpoints and uses session cookies with
    CSRF token protection.

    Attributes:
        name: Provider name ("archidekt").
        base_url: Base URL for the Archidekt API ("https://archidekt.com").
        config: Provider configuration.
        http_client: HTTP client for making requests.
        rate_limit: Rate limit information.
        auth_handler: Session authentication handler.

    Example:
        # Authenticate and create provider
        archidekt = Archidekt(
            username="your_username", password="your_password"
        )

        # Get a specific deck
        deck = archidekt.get_deck("deck-uuid-here")
        print(deck.name)

        # Get user decks
        decks = archidekt.get_user_decks()
        for deck in decks:
            print(deck.name)

        # Search for cards
        cards = archidekt.search(name="Black Lotus", limit=5)
        for card in cards:
            print(card.name, card.set_name)
    """

    # Valid Archidekt search parameters
    VALID_SEARCH_PARAMS: set[str] = {
        "format",
        "rarity",
        "set",
        "cmc",
        "color",
        "type",
        "subtype",
        "power",
        "toughness",
        "loyalty",
        "textsearch",
        "keyword",
        "artist",
        "release",
        "set_type",
    }

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Archidekt provider.

        Args:
            username: Username for authentication. If not provided,
                some endpoints may not work.
            password: Password for authentication. If not provided,
                some endpoints may not work.
            **kwargs: Additional initialization parameters.

        Raises:
            AuthenticationError: If authentication fails during initialization.
        """
        # Set username and password before calling super().__init__
        # so they're available in _initialize
        self._username = username
        self._password = password

        # Call parent constructor which will call _initialize
        super().__init__(**kwargs)

        # Initialize session auth handler after base class sets up base_url
        self.auth_handler = SessionAuthHandler(
            base_url=self.base_url or "",
            login_endpoint="/accounts/login/",
            csrf_header="X-CSRFToken",
            csrf_cookie="csrftoken",
        )

        # Apply authentication if credentials were provided
        if username and password:
            self.auth_handler.authenticate(username=username, password=password)
            self._apply_auth_to_http_client()
            logger.info("Archidekt authentication successful")

    def _initialize(self, **kwargs: Any) -> None:
        """Archidekt-specific initialization.

        Args:
            **kwargs: Additional initialization parameters.
        """
        # This is called by BaseProvider.__init__ before auth_handler is set
        # So we just need to make sure the base class initialization is complete
        pass

    def _apply_auth_to_http_client(self) -> None:
        """Apply session authentication to the HTTP client."""
        # Apply auth cookies to the existing HTTP client session
        self.auth_handler.apply_auth(self.http_client.session)

    def is_authenticated(self) -> bool:
        """Check if the provider is currently authenticated.

        Returns:
            True if session cookies are present and valid, False otherwise.
        """
        return self.auth_handler.is_authenticated()

    def refresh_auth(self) -> None:
        """Refresh the provider's authentication.

        Re-authenticates using the stored credentials.

        Raises:
            AuthenticationError: If refresh fails or no credentials stored.
        """
        self.auth_handler.refresh()
        self._apply_auth_to_http_client()
        logger.info("Archidekt authentication refreshed successfully")

    def authenticate(self, username: str, password: str) -> None:
        """Authenticate with Archidekt using username and password.

        Args:
            username: The username for authentication.
            password: The password for authentication.

        Raises:
            AuthenticationError: If authentication fails.
            NetworkError: If there is a network error.
        """
        self.auth_handler.authenticate(username=username, password=password)
        self._apply_auth_to_http_client()
        logger.info("Archidekt authentication successful")

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
        mapped to Archidekt's API. It provides a consistent interface across
        all providers.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include in its color identity.
            identity: List of colors the card's color identity must exactly
                match.
            type_line: Type line the card must include.
            limit: Maximum number of results to return (default 20).
            page: Page number for pagination (1-based, default 1).
            order: Sort order for results.
            **kwargs: Additional Archidekt-specific parameters.

        Returns:
            A list of Card objects matching the search criteria.

        Raises:
            InvalidQueryError: If the search parameters are invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If authentication is required but not provided.
        """
        try:
            # Validate kwargs against allowed parameters
            for key in kwargs:
                if (
                    not isinstance(key, str)
                    or key.lower() not in self.VALID_SEARCH_PARAMS
                ):
                    raise InvalidQueryError(
                        f"Invalid search parameter: {key}. "
                        f"Valid parameters: {', '.join(sorted(self.VALID_SEARCH_PARAMS))}"
                    )

            # Build query parameters
            params: dict[str, Any] = {
                "q": self._build_search_query(
                    name=name,
                    colors=colors,
                    identity=identity,
                    type_line=type_line,
                    **kwargs,
                )
            }

            if limit:
                params["limit"] = limit
            if page > 1:
                params["page"] = page
            if order:
                params["order"] = order

            # Add additional kwargs as query parameters
            for key, value in kwargs.items():
                if key not in ["name", "colors", "identity", "type_line"]:
                    params[key] = value

            response = self.http_client.get("/api/cards/", params=params)
            data = self._handle_response(response, "cards")

            if not data:
                return []

            # Parse card results
            cards = []
            for card_data in data:
                cards.append(self._parse_card(card_data))

            return cards

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt search: {e}")
            raise NetworkError(
                "Network error during search", original_exception=e
            ) from e

    def search_syntax(self, query: str, limit: int = 20, **kwargs: Any) -> list[Card]:
        """Search for cards using Archidekt-specific query syntax.

        This method provides an escape hatch for power users who need to use
        Archidekt-specific query syntax that is not available through the
        generic search() method.

        Args:
            query: The Archidekt-specific query string.
            limit: Maximum number of results to return (default 20).
            **kwargs: Additional Archidekt-specific parameters.

        Returns:
            A list of Card objects matching the query.

        Raises:
            InvalidQueryError: If the query is invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If authentication is required but not provided.
        """
        if not query or not isinstance(query, str):
            raise InvalidQueryError("Query must be a non-empty string")

        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise InvalidQueryError("limit must be a positive integer (>= 1)")

        try:
            params: dict[str, Any] = {"q": query}
            if limit:
                params["limit"] = limit

            for key, value in kwargs.items():
                params[key] = value

            response = self.http_client.get("/api/cards/", params=params)
            data = self._handle_response(response, "cards")

            if not data:
                return []

            # Parse card results
            cards = []
            for card_data in data:
                cards.append(self._parse_card(card_data))

            return cards

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt search_syntax: {e}")
            raise NetworkError(
                "Network error during search_syntax", original_exception=e
            ) from e

    def get_card(self, card_id: str, **kwargs: Any) -> Card:
        """Get a specific card by its Archidekt ID.

        Note:
            Archidekt uses its own card IDs. These can be obtained
            from search results or deck data.

        Args:
            card_id: The Archidekt card ID.
            **kwargs: Additional parameters.

        Returns:
            A Card object for the specified card.

        Raises:
            NotFoundError: If the card is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            InvalidQueryError: If card_id is not provided.
        """
        if not card_id:
            raise InvalidQueryError(
                "card_id is required for Archidekt.get_card()",
                provider=self.name,
            )

        try:
            response = self.http_client.get(f"/api/cards/{card_id}/")
            data = self._handle_response(response, "card")

            if not data:
                raise NotFoundError(
                    "Card not found",
                    provider=self.name,
                    resource_type="card",
                    resource_id=card_id,
                )

            return self._parse_card(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_card: {e}")
            raise NetworkError(
                "Network error during get_card", original_exception=e
            ) from e

    def get_deck(self, deck_id: str, **kwargs: Any) -> Deck:
        """Get a specific deck by its Archidekt ID.

        Note:
            Archidekt deck IDs are UUID strings. Decks can be public or private.
            Private decks require authentication.

        Args:
            deck_id: The Archidekt deck UUID.
            **kwargs: Additional parameters.

        Returns:
            A Deck object for the specified deck.

        Raises:
            NotFoundError: If the deck is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            AuthenticationError: If the deck is private and authentication fails.
        """
        try:
            response = self.http_client.get(f"/api/decks/{deck_id}/")
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
            logger.error(f"Network error during Archidekt get_deck: {e}")
            raise NetworkError(
                "Network error during get_deck", original_exception=e
            ) from e

    def get_user_decks(self, user_id: str | None = None, **kwargs: Any) -> list[Deck]:
        """Get all decks for a specific user.

        Args:
            user_id: The user ID or username. If None, uses the authenticated user.
            **kwargs: Additional parameters.

        Returns:
            A list of Deck objects for the user's decks.

        Raises:
            AuthenticationError: If authentication is required but not provided.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
        """
        try:
            # If no user_id provided, use the authenticated user's endpoint
            if user_id is None:
                endpoint = "/api/decks/"
            else:
                endpoint = f"/api/users/{user_id}/decks/"

            response = self.http_client.get(endpoint)
            data = self._handle_response(response, "decks")

            if not data:
                return []

            decks = []
            for deck_data in data:
                decks.append(self._parse_deck(deck_data))

            return decks

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_user_decks: {e}")
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
            NotImplementedError: If autocomplete is not supported.
        """
        # Archidekt may not have a dedicated autocomplete endpoint
        # For now, we'll return an empty list
        # This can be implemented if the endpoint is discovered
        logger.warning("Archidekt autocomplete not yet implemented")
        return []

    def _build_search_query(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Build an Archidekt query string from search parameters.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include.
            identity: List of colors the card's color identity must exactly match.
            type_line: Type line the card must include.
            **kwargs: Additional search parameters.

        Returns:
            A query string suitable for Archidekt's API.
        """
        query_parts = []

        # WUBRG color order for sorting
        color_order = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}

        # Add name filter
        if name:
            # Sanitize name to prevent query injection
            sanitized_name = name.replace("\\", "\\\\").replace('"', '\\"')
            query_parts.append(f'"{sanitized_name}"')

        # Add color filters
        if colors:
            # Sort colors in WUBRG order
            color_str = "".join(
                c.value
                for c in sorted(colors, key=lambda c: color_order.get(c.value, 99))
            )
            query_parts.append(f"c:{color_str}")

        # Add color identity filter
        if identity:
            # Sort colors in WUBRG order
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

    @staticmethod
    def _normalize_flavor_text(value: Any) -> str | None:
        """Normalize flavor_text to a string or None.

        The Archidekt API may return flavor_text as a string, a list of
        strings, or None. This helper ensures a consistent str | None
        return type, preventing type safety violations when the value
        is assigned to CardFace.flavor_text (typed as str | None).

        Args:
            value: Raw flavor_text value from the API (str, list, or None).

        Returns:
            The flavor text as a single string, or None if the input is
            empty, None, or an unsupported type.
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value if value else None
        if isinstance(value, list):
            joined = " ".join(str(item) for item in value if item)
            return joined if joined else None
        return None

    def _parse_card(self, data: dict[str, Any]) -> Card:
        """Parse Archidekt card data into a normalized Card model.

        Args:
            data: Raw card data from Archidekt API.

        Returns:
            A normalized Card object.
        """
        # Handle card faces (for flip/transform cards)
        card_faces_data = data.get("card_faces", [])
        if not isinstance(card_faces_data, list):
            logger.warning(
                "Skipping invalid card_faces: expected list, got %s",
                type(card_faces_data).__name__,
            )
            card_faces_data = []
        card_faces = None

        if card_faces_data:
            # Multi-faced card
            parsed_faces = []
            for face_data in card_faces_data:
                if not isinstance(face_data, dict):
                    logger.warning(
                        "Skipping invalid face_data: expected dict, got %s",
                        type(face_data).__name__,
                    )
                    continue
                card_face = CardFace(
                    name=face_data.get("name", ""),
                    mana_cost=face_data.get("mana_cost"),
                    type_line=face_data.get("type_line"),
                    oracle_text=face_data.get("oracle_text") or face_data.get("text"),
                    power=face_data.get("power"),
                    toughness=face_data.get("toughness"),
                    loyalty=face_data.get("loyalty"),
                    flavor_text=self._normalize_flavor_text(
                        face_data.get("flavor_text")
                    ),
                    artist=face_data.get("artist"),
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
        colors_data = data.get("colors", [])
        colors = []
        if colors_data:
            for color_str in colors_data:
                try:
                    colors.append(Color(color_str.upper()))
                except ValueError:
                    # Handle invalid color strings
                    logger.debug(f"Unknown color: {color_str}")

        # Parse color identity
        color_identity_data = data.get("color_identity", [])
        color_identity = []
        if color_identity_data:
            for color_str in color_identity_data:
                try:
                    color_identity.append(Color(color_str.upper()))
                except ValueError:
                    logger.debug(f"Unknown color in identity: {color_str}")

        # Parse color indicator
        color_indicator_data = data.get("color_indicator", [])
        color_indicator = []
        if color_indicator_data:
            for color_str in color_indicator_data:
                try:
                    color_indicator.append(Color(color_str.upper()))
                except ValueError:
                    logger.debug(f"Unknown color in indicator: {color_str}")

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

        # Get card ID - use Scryfall ID if available, otherwise Archidekt ID
        card_id = data.get("id", "") or data.get("scryfall_id", "")

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

        return Card(
            id=card_id,
            scryfall_id=data.get("scryfall_id"),
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
            rarity=rarity,
            collector_number=data.get("number"),
            power=power,
            toughness=toughness,
            loyalty=loyalty,
            layout=data.get("layout", "normal"),
            image_uris=image_uris if image_uris else None,
            card_faces=card_faces,
            set_code=set_code if set_code else None,
            set_name=set_name if set_name else None,
            set_type=set_type.value if set_type else None,
            multiverse_ids=data.get("multiverse_ids"),
            scryfall_uri=data.get("scryfall_uri"),
            uri=data.get("uri"),
            artist=data.get("artist"),
            source="archidekt",
        )

    def _parse_deck(self, data: dict[str, Any]) -> Deck:
        """Parse Archidekt deck data into a normalized Deck model.

        Args:
            data: Raw deck data from Archidekt API.

        Returns:
            A normalized Deck object.
        """
        deck_cards = []

        # Parse main deck cards
        main_cards = data.get("cards", [])
        for card_data in main_cards:
            if not isinstance(card_data, dict):
                logger.warning(
                    "Skipping invalid card_data in main deck: " "expected dict, got %s",
                    type(card_data).__name__,
                )
                continue
            quantity = card_data.get("quantity", 1)
            card_info = card_data.get("card", {})
            if not isinstance(card_info, dict):
                logger.warning(
                    "Skipping invalid card_info in main deck: " "expected dict, got %s",
                    type(card_info).__name__,
                )
                continue

            # Parse card
            card = self._parse_card(card_info)

            # Determine board - default to MAIN
            board = Board.MAIN
            if card_data.get("board"):
                board_str = card_data.get("board", "").upper()
                try:
                    board = Board[board_str]
                except (KeyError, TypeError):
                    pass

            from pymtg.models.card import DeckCard

            deck_card = DeckCard(
                card=card,
                count=quantity,
                board=board,
            )
            deck_cards.append(deck_card)

        # Parse sideboard cards if present
        sideboard_cards = data.get("sideboard", [])
        for card_data in sideboard_cards:
            if not isinstance(card_data, dict):
                logger.warning(
                    "Skipping invalid card_data in sideboard: " "expected dict, got %s",
                    type(card_data).__name__,
                )
                continue
            quantity = card_data.get("quantity", 1)
            card_info = card_data.get("card", {})
            if not isinstance(card_info, dict):
                logger.warning(
                    "Skipping invalid card_info in sideboard: " "expected dict, got %s",
                    type(card_info).__name__,
                )
                continue

            card = self._parse_card(card_info)

            from pymtg.models.card import DeckCard

            deck_card = DeckCard(
                card=card,
                count=quantity,
                board=Board.SIDEBOARD,
            )
            deck_cards.append(deck_card)

        # Parse commander cards if present
        commander_cards = data.get("commanders", [])
        for card_data in commander_cards:
            if not isinstance(card_data, dict):
                logger.warning(
                    "Skipping invalid card_data in commanders: "
                    "expected dict, got %s",
                    type(card_data).__name__,
                )
                continue
            card_info = card_data.get("card", {})
            if not isinstance(card_info, dict):
                logger.warning(
                    "Skipping invalid card_info in commanders: "
                    "expected dict, got %s",
                    type(card_info).__name__,
                )
                continue

            card = self._parse_card(card_info)

            from pymtg.models.card import DeckCard

            deck_card = DeckCard(
                card=card,
                count=1,
                board=Board.COMMANDER,
            )
            deck_cards.append(deck_card)

        # Parse format
        format_str = data.get("format", "").upper()
        try:
            deck_format = Format[format_str]
        except (KeyError, TypeError):
            deck_format = Format.COMMANDER  # Default if unknown

        # Get deck description
        description = data.get("description", "")

        # Get deck ID
        deck_id = data.get("id") or data.get("uuid", "")

        # Get owner information
        owner_data = data.get("owner", {})
        owner = owner_data.get("name", "") if owner_data else ""
        owner_id = owner_data.get("id", "") if owner_data else ""

        # Convert is_public to privacy
        privacy = "private" if data.get("is_public", True) is False else "public"

        # Convert single category to list
        categories = [data.get("category", "")] if data.get("category") else []

        return Deck(
            id=deck_id,
            name=data.get("name", "Unnamed Deck"),
            description=description,
            format=deck_format,
            cards=deck_cards,
            commander=data.get("commander", []),
            source="archidekt",
            url=data.get("url"),
            owner=owner,
            owner_id=owner_id,
            privacy=privacy,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            tags=data.get("tags", []),
            categories=categories,
        )

    def __repr__(self) -> str:
        """Return a string representation of the Archidekt provider.

        Returns:
            A string representation suitable for debugging.
        """
        auth_status = (
            "authenticated" if self.is_authenticated() else "not authenticated"
        )
        return (
            f"Archidekt(name={self.name!r}, base_url={self.base_url!r}, {auth_status})"
        )
