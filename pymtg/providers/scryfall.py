"""Scryfall provider implementation for the pymtg library.

This module provides the Scryfall class which implements the BaseProvider
interface for interacting with the Scryfall API
(https://scryfall.com/docs/api).

Scryfall is a comprehensive Magic: The Gathering database with a free,
public API that doesn't require authentication for most endpoints.
"""

import logging
from typing import Any

import requests

from pymtg.auth.no_auth import NoAuthHandler
from pymtg.config import PROVIDER_CONFIGS
from pymtg.exceptions import (
    InvalidQueryError,
    NetworkError,
    NotFoundError,
)
from pymtg.models.card import Card, CardFace
from pymtg.models.deck import Deck
from pymtg.models.enums import Color, Format, Rarity, SetType
from pymtg.models.pricing import Pricing, ScryfallPricing
from pymtg.providers.base import BaseProvider

logger = logging.getLogger(__name__)


class Scryfall(BaseProvider):
    """Scryfall API provider implementation.

    This class provides access to the Scryfall API, which is a comprehensive
    Magic: The Gathering database with a free, public API. Scryfall provides
    detailed card information, search capabilities, and various other endpoints
    for MTG data.

    Scryfall uses the Scryfall UUID as the canonical card identifier.

    Attributes:
        name: Provider name ("scryfall").
        base_url: Base URL for the Scryfall API ("https://api.scryfall.com").
        config: Provider configuration.
        http_client: HTTP client for making requests.
        rate_limit: Rate limit information.

    Example:
        scryfall = Scryfall()
        card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")
        print(card.name)

        # Search for cards
        cards = scryfall.search(name="Black Lotus", limit=5)
        for card in cards:
            print(card.name, card.set_name)

        # Use query syntax
        blue_creatures = scryfall.search_syntax("c:U type:creature", limit=10)
    """

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the Scryfall provider.

        Args:
            **kwargs: Additional initialization parameters
                (ignored for Scryfall).
        """
        super().__init__(**kwargs)
        self.name = "scryfall"
        self.config = PROVIDER_CONFIGS.get("scryfall", self.config)
        self.base_url = self.config.base_url
        self.auth_handler = NoAuthHandler()

    def _initialize(self, **kwargs: Any) -> None:
        """Scryfall-specific initialization.

        Args:
            **kwargs: Additional initialization parameters.
        """
        # Scryfall uses no authentication
        pass

    def is_authenticated(self) -> bool:
        """Check if the provider is currently authenticated.

        Scryfall doesn't require authentication for public endpoints.

        Returns:
            Always True for Scryfall since no authentication is required.
        """
        return True

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
        mapped to Scryfall's query syntax. It provides a consistent interface
        across all providers.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include in its color identity.
            identity: List of colors the card's color identity must exactly
                match.
            type_line: Type line the card must include.
            limit: Maximum number of results to return (max 175 per page).
            page: Page number for pagination (1-based).
            order: Sort order for results. Common values: "name",
                "released", "power", "toughness"
            **kwargs: Additional Scryfall-specific parameters:
                - set_code: Set code to filter by (e.g., "LEA", "M20").
                - rarity: Card rarity to filter by.
                - cmc: Converted mana cost to filter by
                  (int or dict with "gte", "lte").
                - power: Power to filter by (str or dict).
                - toughness: Toughness to filter by (str or dict).
                - loyalty: Loyalty to filter by.
                - format: Format legality to filter by.
                - is_reserved: Whether the card is on the Reserved List.
                - is_foil: Whether the card is foil.
                - is_nonfoil: Whether the card is non-foil.
                - include_extras: Whether to include extra cards
                  (tokens, etc.).
                - include_multilingual: Whether to include non-English
                  printings.
                - include_variations: Whether to include variations.

        Returns:
            A list of Card objects matching the search criteria.

        Raises:
            InvalidQueryError: If the search parameters are invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            RateLimitError: If rate limits are exceeded.

        Example:
            # Find all blue cards named "Lotus"
            cards = scryfall.search(name="Lotus", colors=[Color.BLUE])

            # Find creatures with CMC >= 3 and <= 5
            creatures = scryfall.search(
                type_line="Creature", cmc={"gte": 3, "lte": 5}
            )
        """
        try:
            # Build query parameters
            params: dict[str, Any] = {
                "q": self._build_search_query(
                    name=name,
                    colors=colors,
                    identity=identity,
                    type_line=type_line,
                    **kwargs,
                ),
                "page": page,
                "limit": min(limit, 175),
            }

            # Add sorting if specified
            if order:
                params["order"] = order

            # Add additional kwargs as query parameters
            for key, value in kwargs.items():
                if key not in ["name", "colors", "identity", "type_line"]:
                    if isinstance(value, dict):
                        # Handle dict parameters like {"gte": 3, "lte": 5}
                        for subkey, subvalue in value.items():
                            params[f"{key}_{subkey}"] = subvalue
                    else:
                        params[key] = value

            response = self.http_client.get("/cards/search", params=params)
            data = self._handle_response(response, "cards")

            if not data or "data" not in data:
                return []

            return [self._parse_card(scryfall_data) for scryfall_data in data["data"]]

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Scryfall search: {e}")
            raise NetworkError(
                "Network error during search", original_exception=e
            ) from e

    def _build_search_query(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Build a Scryfall query string from search parameters.

        Args:
            name: Card name or name fragment.
            colors: List of colors the card must include.
            identity: List of colors the card's color identity must exactly
                match.
            type_line: Type line the card must include.
            **kwargs: Additional search parameters.

        Returns:
            A Scryfall query string.
        """
        query_parts = []

        if name:
            # Use fuzzy matching for name searches
            query_parts.append(f'"{name}"')

        if colors:
            color_letters = "".join(c.value for c in colors)
            if len(colors) == 1:
                query_parts.append(f"c:{color_letters}")
            else:
                query_parts.append(f"ci:{color_letters}")

        if identity:
            id_letters = "".join(c.value for c in identity)
            query_parts.append(f"id:{id_letters}")

        if type_line:
            query_parts.append(f'"{type_line}"')

        # Handle additional kwargs
        for key, value in kwargs.items():
            if key == "set_code" and value:
                query_parts.append(f"set:{value}")
            elif key == "rarity" and value:
                if isinstance(value, Rarity):
                    query_parts.append(f"r:{value.value}")
                else:
                    query_parts.append(f"r:{value}")
            elif key == "cmc" and value:
                if isinstance(value, dict):
                    if "gte" in value:
                        query_parts.append(f"cmc>={value['gte']}")
                    if "lte" in value:
                        query_parts.append(f"cmc<={value['lte']}")
                else:
                    query_parts.append(f"cmc:{value}")
            elif key == "power" and value:
                if isinstance(value, dict):
                    if "gte" in value:
                        query_parts.append(f"pow>={value['gte']}")
                    if "lte" in value:
                        query_parts.append(f"pow<={value['lte']}")
                else:
                    query_parts.append(f"pow:{value}")
            elif key == "toughness" and value:
                if isinstance(value, dict):
                    if "gte" in value:
                        query_parts.append(f"tou>={value['gte']}")
                    if "lte" in value:
                        query_parts.append(f"tou<={value['lte']}")
                else:
                    query_parts.append(f"tou:{value}")
            elif key == "format" and value:
                if isinstance(value, Format):
                    query_parts.append(f"f:{value.value}")
                else:
                    query_parts.append(f"f:{value}")

        return " ".join(query_parts)

    def search_syntax(self, query: str, limit: int = 20, **kwargs: Any) -> list[Card]:
        """Search for cards using Scryfall query syntax.

        This method provides an escape hatch for power users who need to use
        Scryfall's full query syntax directly.

        Args:
            query: The Scryfall query string (see https://scryfall.com/docs/syntax).
            limit: Maximum number of results to return (max 175 per page).
            **kwargs: Additional parameters:
                - page: Page number for pagination (1-based).
                - order: Sort order for results.
                - unique: Whether to return only unique card names
                  ("cards", "prints", "art", "versions").
                - dir: Sort direction ("auto", "asc", "desc").
                - include_extras: Whether to include extra cards.
                - include_multilingual: Whether to include non-English
                  printings.
                - include_variations: Whether to include variations.

        Returns:
            A list of Card objects matching the query.

        Raises:
            InvalidQueryError: If the query is invalid.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            RateLimitError: If rate limits are exceeded.

        Example:
            # Find all blue creatures
            blue_creatures = scryfall.search_syntax(
                "c:U type:creature", limit=10
            )

            # Find cards with oracle text containing "draw a card"
            draw_cards = scryfall.search_syntax('o:"draw a card"', limit=5)

            # Find cards printed in 2020
            recent_cards = scryfall.search_syntax("year:2020", limit=20)
        """
        try:
            if not query or not isinstance(query, str):
                raise InvalidQueryError("Query must be a non-empty string")

            params: dict[str, Any] = {
                "q": query,
                "limit": min(limit, 175),
            }

            # Add optional parameters
            if "page" in kwargs:
                params["page"] = kwargs["page"]
            if "order" in kwargs:
                params["order"] = kwargs["order"]
            if "unique" in kwargs:
                params["unique"] = kwargs["unique"]
            if "dir" in kwargs:
                params["dir"] = kwargs["dir"]
            if "include_extras" in kwargs:
                params["include_extras"] = kwargs["include_extras"]
            if "include_multilingual" in kwargs:
                params["include_multilingual"] = kwargs["include_multilingual"]
            if "include_variations" in kwargs:
                params["include_variations"] = kwargs["include_variations"]

            response = self.http_client.get("/cards/search", params=params)
            data = self._handle_response(response, "cards")

            if not data or "data" not in data:
                return []

            return [self._parse_card(scryfall_data) for scryfall_data in data["data"]]

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Scryfall syntax search: {e}")
            raise NetworkError(
                "Network error during syntax search", original_exception=e
            ) from e

    def get_card(self, card_id: str, **kwargs: Any) -> Card:
        """Get a specific card by its Scryfall ID.

        Args:
            card_id: The Scryfall UUID for the card.
            **kwargs: Additional parameters (currently ignored).

        Returns:
            A Card object for the specified card.

        Raises:
            NotFoundError: If the card is not found.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            RateLimitError: If rate limits are exceeded.

        Example:
            # Get Black Lotus
            black_lotus = scryfall.get_card(
                "38625902-0567-4f24-85b0-a00843553997"
            )
            print(black_lotus.name, black_lotus.mana_cost)
        """
        try:
            response = self.http_client.get(f"/cards/{card_id}")
            data = self._handle_response(response, "card")

            if not data:
                raise NotFoundError(
                    f"Card with ID {card_id} not found",
                    provider=self.name,
                    resource_type="card",
                )

            return self._parse_card(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error getting card {card_id}: {e}")
            raise NetworkError(
                f"Network error getting card {card_id}", original_exception=e
            ) from e

    def get_cards_by_name(
        self, name: str, fuzzy: bool = True, **kwargs: Any
    ) -> list[Card]:
        """Get cards by name using the /cards/named endpoint.

        This is a Scryfall-specific method that allows looking up cards
        by their exact name or using fuzzy matching.

        Args:
            name: The card name to search for.
            fuzzy: Whether to use fuzzy matching (True) or exact
                matching (False).
            **kwargs: Additional parameters:
                - set_code: Set code to filter by (e.g., "LEA", "M20").
                - language: Language code to filter by (e.g., "en", "fr").

        Returns:
            A list of Card objects matching the name.

        Raises:
            InvalidQueryError: If the name is empty.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            RateLimitError: If rate limits are exceeded.

        Example:
            # Get all printings of "Black Lotus"
            printings = scryfall.get_cards_by_name("Black Lotus")

            # Get exact match only
            exact = scryfall.get_cards_by_name("Black Lotus", fuzzy=False)
        """
        try:
            if not name or not isinstance(name, str):
                raise InvalidQueryError("Name must be a non-empty string")

            params: dict[str, Any] = {"fuzzy": str(fuzzy).lower()}

            if "set_code" in kwargs:
                params["set"] = kwargs["set_code"]
            if "language" in kwargs:
                params["lang"] = kwargs["language"]

            # URL encode the name for the path
            import urllib.parse

            response = self.http_client.get(
                f"/cards/named?{urllib.parse.urlencode(params)}",
                allow_redirects=True,
            )
            data = self._handle_response(response, "card")

            if not data:
                return []

            # Handle both single card and list responses
            if isinstance(data, list):
                return [self._parse_card(card_data) for card_data in data]
            else:
                return [self._parse_card(data)]

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error getting cards by name '{name}': {e}")
            raise NetworkError(
                "Network error getting cards by name", original_exception=e
            ) from e

    def autocomplete(self, query: str, limit: int = 10, **kwargs: Any) -> list[str]:
        """Get autocomplete suggestions for a card name query.

        Args:
            query: The partial card name to autocomplete.
            limit: Maximum number of suggestions to return (max 20).
            **kwargs: Additional parameters (currently ignored).

        Returns:
            A list of autocomplete suggestions (card names).

        Raises:
            InvalidQueryError: If the query is empty.
            NetworkError: If there is a network error.
            APIError: If the API returns an error.
            RateLimitError: If rate limits are exceeded.

        Example:
            # Get suggestions for "Ligh"
            suggestions = scryfall.autocomplete("Ligh")
            # Returns: ["Lightning Bolt", "Lightning Greaves", ...]
        """
        try:
            if not query or not isinstance(query, str):
                raise InvalidQueryError("Query must be a non-empty string")

            params = {"q": query, "limit": min(limit, 20)}

            response = self.http_client.get("/cards/autocomplete", params=params)
            data = self._handle_response(response, "autocomplete")

            if not data or "data" not in data:
                return []

            return data["data"]

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during autocomplete: {e}")
            raise NetworkError(
                "Network error during autocomplete", original_exception=e
            ) from e

    def _parse_card(self, scryfall_data: dict[str, Any]) -> Card:
        """Parse Scryfall JSON data into a normalized Card object.

        Args:
            scryfall_data: The raw JSON data from Scryfall.

        Returns:
            A normalized Card object.
        """
        # Extract the Scryfall card ID. For Scryfall, the provider-specific
        # card ID and the canonical Scryfall UUID are the same value, so both
        # the Card.id and Card.scryfall_id fields are populated from it.
        card_id = scryfall_data.get("id", "")

        # Extract basic information
        card_faces = scryfall_data.get("card_faces")

        # Handle multi-faced cards
        if card_faces:
            # For multi-faced cards, use the first face for main attributes
            main_face = card_faces[0]
            name = main_face.get("name", "")
            mana_cost = main_face.get("mana_cost")
            type_line = main_face.get("type_line")
            oracle_text = main_face.get("oracle_text")
            power = main_face.get("power")
            toughness = main_face.get("toughness")
            colors = self._parse_colors(main_face.get("colors"))
            color_identity = self._parse_colors(scryfall_data.get("color_identity"))
            color_indicator = self._parse_colors(main_face.get("color_indicator"))

            # Parse all card faces
            parsed_faces = [self._parse_card_face(face) for face in card_faces]
        else:
            name = scryfall_data.get("name", "")
            mana_cost = scryfall_data.get("mana_cost")
            type_line = scryfall_data.get("type_line")
            oracle_text = scryfall_data.get("oracle_text")
            power = scryfall_data.get("power")
            toughness = scryfall_data.get("toughness")
            colors = self._parse_colors(scryfall_data.get("colors"))
            color_identity = self._parse_colors(scryfall_data.get("color_identity"))
            color_indicator = self._parse_colors(scryfall_data.get("color_indicator"))
            parsed_faces = None

        # Parse pricing
        pricing_data = scryfall_data.get("prices")
        pricing = self._parse_pricing(pricing_data) if pricing_data else None

        # Parse legalities
        legalities_data = scryfall_data.get("legalities")
        legalities = (
            self._parse_legalities(legalities_data) if legalities_data else None
        )

        # Parse set information
        set_info = scryfall_data.get("set")
        if isinstance(set_info, str):
            # Simple set code string
            set_code = set_info
            set_name = None
            set_type_str = None
        elif isinstance(set_info, dict):
            # Full set object
            set_code = set_info.get("code")
            set_name = set_info.get("name")
            set_type_str = set_info.get("set_type")
        else:
            # Fallback
            set_code = None
            set_name = None
            set_type_str = None

        # Map set type to our enum
        set_type = None
        if set_type_str:
            try:
                set_type = SetType(set_type_str.lower())
            except ValueError:
                logger.debug(f"Unknown set type: {set_type_str}")

        # Map rarity
        rarity_str = scryfall_data.get("rarity")
        rarity = None
        if rarity_str:
            try:
                rarity = Rarity[rarity_str.upper()]
            except KeyError:
                logger.debug(f"Unknown rarity: {rarity_str}")

        return Card(
            id=card_id,
            scryfall_id=card_id,
            oracle_id=scryfall_data.get("oracle_id"),
            name=name,
            printed_name=scryfall_data.get("printed_name"),
            mana_cost=mana_cost,
            cmc=scryfall_data.get("cmc"),
            type_line=type_line,
            printed_type_line=scryfall_data.get("printed_type_line"),
            oracle_text=oracle_text,
            printed_text=scryfall_data.get("printed_text"),
            flavors=(
                [scryfall_data.get("flavor_text", "")]
                if scryfall_data.get("flavor_text")
                else None
            ),
            colors=colors,
            color_identity=color_identity,
            color_indicator=color_indicator,
            keywords=scryfall_data.get("keywords"),
            all_parts=(
                [
                    str(part.get("id", ""))
                    for part in scryfall_data.get("all_parts", [])
                    if part and isinstance(part, dict)
                ]
                if scryfall_data.get("all_parts")
                else None
            ),
            card_faces=parsed_faces,
            set_code=set_code,
            set_name=set_name,
            set_type=set_type.value if set_type else None,
            rarity=rarity,
            collector_number=scryfall_data.get("collector_number"),
            power=power,
            toughness=toughness,
            loyalty=scryfall_data.get("loyalty"),
            defense=scryfall_data.get("defense"),
            layout=scryfall_data.get("layout"),
            image_uris=(
                scryfall_data.get("image_uris")
                if scryfall_data.get("image_uris")
                else None
            ),
            image_status=scryfall_data.get("image_status"),
            pricing=pricing,
            legalities=legalities,
            released_at=scryfall_data.get("released_at"),
            reserved=scryfall_data.get("reserved"),
            foil=scryfall_data.get("foil"),
            nonfoil=scryfall_data.get("nonfoil"),
            oversized=scryfall_data.get("oversized"),
            promo=scryfall_data.get("promo"),
            reprint=scryfall_data.get("reprint"),
            variation=scryfall_data.get("variation"),
            multiverse_ids=scryfall_data.get("multiverse_ids"),
            tcgplayer_id=scryfall_data.get("tcgplayer_id"),
            cardmarket_id=scryfall_data.get("cardmarket_id"),
            prints_search_uri=scryfall_data.get("prints_search_uri"),
            rulings_uri=scryfall_data.get("rulings_uri"),
            scryfall_uri=scryfall_data.get("scryfall_uri"),
            uri=scryfall_data.get("uri"),
            source=self.name,
        )

    def _parse_card_face(self, face_data: dict[str, Any]) -> CardFace:
        """Parse a single card face from Scryfall data.

        Args:
            face_data: The raw JSON data for a single card face.

        Returns:
            A CardFace object.
        """
        return CardFace(
            name=face_data.get("name", ""),
            mana_cost=face_data.get("mana_cost"),
            type_line=face_data.get("type_line"),
            oracle_text=face_data.get("oracle_text"),
            power=face_data.get("power"),
            toughness=face_data.get("toughness"),
            colors=self._parse_colors(face_data.get("colors")),
            color_indicator=self._parse_colors(face_data.get("color_indicator")),
            loyalty=face_data.get("loyalty"),
            defense=face_data.get("defense"),
            flavor_text=face_data.get("flavor_text"),
            artist=face_data.get("artist"),
            artist_id=face_data.get("artist_id"),
            illustration_id=face_data.get("illustration_id"),
            image_uris=(
                face_data.get("image_uris") if face_data.get("image_uris") else None
            ),
        )

    def _parse_colors(self, colors: list[str] | None) -> list[Color] | None:
        """Parse color strings into Color enum values.

        Args:
            colors: List of color strings (e.g., ["W", "U", "B", "R", "G"]).

        Returns:
            List of Color enum values or None.
        """
        if not colors:
            return None

        try:
            return [Color(color.upper()) for color in colors]
        except ValueError:
            # Handle unknown colors (shouldn't happen with Scryfall)
            valid_colors = []
            for color in colors:
                try:
                    valid_colors.append(Color(color.upper()))
                except ValueError:
                    logger.debug(f"Unknown color: {color}")
            return valid_colors if valid_colors else None

    def _parse_pricing(self, pricing_data: dict[str, Any]) -> Pricing:
        """Parse Scryfall pricing data into a Pricing object.

        Scryfall can return pricing data in different formats:
        - New format: {"usd": "0.42", "usd_foil": "1.23", ...} (strings or None)
        - Old format: {"usd": {"normal": "0.42", "foil": "1.23"}, ...} (nested dicts)
        - Missing: None or missing keys

        Args:
            pricing_data: The raw pricing data from Scryfall.

        Returns:
            A Pricing object with Scryfall pricing populated.
        """

        def parse_currency_value(value: Any) -> float | None:
            """Parse a currency value from Scryfall API.

            Args:
                value: The value to parse (string, float, None, or dict).

            Returns:
                The parsed float value or None.
            """
            if value is None:
                return None
            if isinstance(value, (float, int)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
            if isinstance(value, dict):
                # Handle old nested format: {"normal": "0.42", "foil": "1.23"}
                normal = value.get("normal")
                return parse_currency_value(normal)
            return None

        def get_price_from_currency_dict(
            currency_key: str, price_type: str = "normal"
        ) -> float | None:
            """Extract a specific price from currency data.

            Args:
                currency_key: The currency key (e.g., "usd", "eur", "tix").
                price_type: The price type ("normal", "foil", "etched").

            Returns:
                The parsed price value or None.
            """
            currency_data = pricing_data.get(currency_key)
            if currency_data is None:
                return None

            if isinstance(currency_data, dict):
                # Handle nested format: {"normal": "0.42", "foil": "1.23"}
                price_value = currency_data.get(price_type)
                return parse_currency_value(price_value)
            else:
                # Handle flat format: currency_data is the price directly
                return parse_currency_value(currency_data)

        return Pricing(
            scryfall=ScryfallPricing(
                usd=get_price_from_currency_dict("usd", "normal"),
                usd_foil=get_price_from_currency_dict("usd", "foil"),
                usd_etched=get_price_from_currency_dict("usd", "etched"),
                eur=get_price_from_currency_dict("eur", "normal"),
                eur_foil=get_price_from_currency_dict("eur", "foil"),
                tix=get_price_from_currency_dict("tix", "normal"),
            ),
            tcgplayer=None,
            cardmarket=None,
        )

    def _parse_legalities(self, legalities_data: dict[str, str]) -> dict[str, str]:
        """Parse Scryfall legalities data into a format legality dictionary.

        Args:
            legalities_data: The raw legalities data from Scryfall.

        Returns:
            A dictionary mapping format names to legality statuses.
        """
        return {
            format_name: status
            for format_name, status in legalities_data.items()
            if status != "not_legal"
        }

    def get_deck(self, deck_id: str, **kwargs: Any) -> Deck:
        """Get a deck by its ID.

        Scryfall does not support deck retrieval.

        Args:
            deck_id: The deck ID.
            **kwargs: Additional parameters (currently ignored).

        Returns:
            Never returns - always raises NotImplementedError.

        Raises:
            NotImplementedError: Scryfall does not support deck retrieval.
        """
        raise NotImplementedError("Scryfall does not support deck retrieval")

    def get_user_decks(self, user_id: str | None = None, **kwargs: Any) -> list[Deck]:
        """Get all user decks.

        Scryfall does not support user deck retrieval.

        Args:
            user_id: The user ID (ignored for Scryfall).
            **kwargs: Additional parameters (currently ignored).

        Returns:
            Never returns - always raises NotImplementedError.

        Raises:
            NotImplementedError: Scryfall does not support user deck retrieval.
        """
        raise NotImplementedError("Scryfall does not support user deck retrieval")

    def get_rate_limit_status(self) -> dict[str, Any]:
        """Get the current rate limit status for Scryfall.

        Scryfall has the following rate limits:
        - 2 requests per second for /cards/search
        - 10 requests per second for other endpoints

        Returns:
            A dictionary containing rate limit information.
        """
        return {
            "rate_limit": self.rate_limit,
            "search_limit": {"requests_per_second": 2},
            "other_limit": {"requests_per_second": 10},
        }

    def __repr__(self) -> str:
        """Return a string representation of the Scryfall provider.

        Returns:
            A string representation suitable for debugging.
        """
        return f"Scryfall(name={self.name!r}, base_url={self.base_url!r})"
