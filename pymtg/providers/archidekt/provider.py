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
    endpoints from HAR file analysis.

Archidekt uses JWT token-based authentication via the /api/rest-auth/login/
endpoint. The JWT token is then included in the Authorization header as
"JWT <token>" for authenticated requests.

Key API Endpoints:
    - POST /api/rest-auth/login/ - JWT authentication
    - GET /api/cards/v2/ - Card search
    - GET /api/cards/v2/{id}/ - Get specific card
    - GET /api/cards/editions/ - List all MTG sets/editions
    - GET /api/cards/subtypes/ - List all card subtypes
    - GET /api/decks/v2/ - List user decks
    - POST /api/decks/v2/ - Create deck
    - GET /api/decks/v2/{id}/ - Get deck details
    - PATCH /api/decks/{id}/modifyCards/v2/ - Modify deck cards
    - GET /api/decks/folders/{folder_id}/ - Get folder contents
    - GET /api/decks/tags/v2/ - Get available deck tags
    - POST /api/decks/folders/deleteItems/ - Delete items from folder
    - GET /api/users/{user_id}/decks/ - Get user's decks
    - GET /api/comments/{comment_id}/ - Get deck comments
    - GET /api/users/{user_id}/notificationCount/ - Get notification count
    - GET /api/ws/collaborative/{id}/ - WebSocket for collaborative editing (not implemented)
"""

import json
import logging
import re
import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterator

import requests

from pymtg.auth.jwt import JWTAuthHandler
from pymtg.exceptions import APIError, NetworkError
from pymtg.models.card import Card, CardFace, Pricing
from pymtg.models.pricing import ScryfallPricing
from pymtg.models.deck import Deck
from pymtg.models.enums import Color, Format, Rarity, SetType
from pymtg.providers.archidekt.exceptions import (
    ArchidektAPIError,
    ArchidektAuthenticationError,
    ArchidektNotFoundError,
    ArchidektRateLimitError,
    ArchidektValidationError,
)
from pymtg.providers.base import BaseProvider
from pymtg.utils.har_logger import HARLogger
from pymtg.utils.rate_limiting import RateLimiter, RateLimitConfig

logger = logging.getLogger(__name__)


class Archidekt(BaseProvider):
    """Archidekt API provider implementation.

    This class provides access to the Archidekt API, which is an
    unofficial API for the Archidekt deck building website.
    Archidekt provides deck management, card search, and collection
    tracking features.

    Authentication is required for most endpoints and uses JWT tokens via
    the /api/rest-auth/login/ endpoint. JWT tokens are then included in the
    Authorization header as "JWT <token>".

    Attributes:
        name: Provider name ("archidekt").
        base_url: Base URL for the Archidekt API ("https://archidekt.com/api/").
        config: Provider configuration.
        http_client: HTTP client for making requests.
        rate_limit: Rate limit information.
        auth_handler: JWT authentication handler.
        har_logger: HAR logger for debugging.
        rate_limiter: Rate limiter for API calls.
        deck_relation_map: Mapping of (deck_id, card_id) to deck_relation_id for
            card management operations.

    Example:
        # Authenticate and create provider
        archidekt = Archidekt(
            username="your_username", password="your_password"
        )

        # Get a specific deck
        deck = archidekt.get_deck("24299438")
        print(deck.name)

        # Get user decks
        decks = archidekt.get_user_decks()
        for deck in decks:
            print(deck.name)

        # Search for cards
        cards = archidekt.search(name="Black Lotus", limit=5)
        for card in cards:
            print(card.name, card.set_name)

        # Create a deck
        new_deck = archidekt.create_deck(
            name="My Commander Deck",
            format=Format.COMMANDER
        )
        print(f"Created deck with ID: {new_deck.id}")

        # Add cards to deck
        archidekt.add_card_to_deck(
            deck_id=new_deck.id,
            card_name="Sol Ring",
            quantity=1
        )
    """

    # Map Archidekt format IDs to pymtg Format enum
    # Based on HAR file analysis and existing Format enum values
    FORMAT_MAP: dict[Format, int] = {
        Format.STANDARD: 1,
        Format.MODERN: 2,
        Format.LEGACY: 3,
        Format.VINTAGE: 4,
        Format.COMMANDER: 5,
        Format.PAUPER: 6,
        Format.PIONEER: 7,
        Format.BRAWL: 8,
        Format.TWO_HEADED_GIANT: 9,
        Format.CONSPIRACY: 15,
        Format.OATHBREAKER: 20,
        Format.EXPLORER: 21,
        Format.HISTORIC: 23,
        Format.OLD_SCHOOL: 10,
    }

    # Map Archidekt game IDs to pymtg game representation
    GAME_ID_PAPER = 1
    GAME_ID_MTGO = 2
    GAME_ID_ARENA = 3

    # Maximum number of deck-relation entries retained in memory. Once
    # exceeded, the least-recently-inserted entry is evicted.
    MAX_RELATION_MAP_SIZE = 1000

    # Reverse map for parsing
    FORMAT_ID_MAP: dict[int, Format] = {v: k for k, v in FORMAT_MAP.items()}

    # Valid Archidekt search parameters (from HAR analysis)
    VALID_SEARCH_PARAMS: set[str] = {
        "nameSearch",  # Partial name search
        "name",  # Exact name search
        "exact",  # Exact match flag
        "oracleCardIds",  # Search by oracle card IDs
        "game",  # Game filter (1=paper, 2=MTGO, 3=Arena)
        "formatLegality",  # Format legality filter
        "colorIdentity",  # Color identity filter
        "colors",  # Colors filter
        "color",  # Color filter
        "rarity",  # Rarity filter
        "set",  # Set code filter
        "type",  # Type line filter
        "subtype",  # Subtype filter
        "cmc",  # Converted mana cost filter
        "power",  # Power filter
        "toughness",  # Toughness filter
        "loyalty",  # Loyalty filter
        "textSearch",  # Text search
        "keyword",  # Keyword filter
        "artist",  # Artist filter
        "release",  # Release date filter
        "setType",  # Set type filter
        "includeTokens",  # Include tokens
        "includeDigital",  # Include digital-only cards
        "includeEmblems",  # Include emblem cards
        "includeArtCards",  # Include art cards
        "unique",  # Unique results only
        "orderBy",  # Sort order
        "page",  # Page number
        "pageSize",  # Page size
    }

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the Archidekt provider.

        Args:
            username: Username for authentication. If not provided,
                authenticated operations will not work.
            password: Password for authentication. If not provided,
                authenticated operations will not work.

        Raises:
            ArchidektAuthenticationError: If authentication fails during initialization.
        """
        # Set username and password before calling super().__init__
        # so they're available in _initialize
        self._username = username
        self._password = password

        # Initialize HAR logger
        self.har_logger = HARLogger(enabled=False)

        # Initialize rate limiter with Archidekt's ~60 requests/minute limit
        self.rate_limiter = RateLimiter(
            {
                "archidekt": RateLimitConfig(
                    requests_per_minute=60,
                    burst_size=10,
                ),
            }
        )

        # Map to store deck relation IDs for card management.
        # Format: {(deck_id, card_id): deck_relation_id}
        # Bounded to avoid unbounded memory growth in long-running sessions
        # that load many decks. The least-recently-inserted entries are
        # evicted once the cap is reached.
        self._deck_relation_map: OrderedDict[tuple[str, str], str] = OrderedDict()

        # Lock for thread safety
        self._lock = threading.Lock()

        # Call parent constructor which will call _initialize
        super().__init__()

        # Initialize JWT auth handler after base class sets up base_url
        self.auth_handler = JWTAuthHandler(
            base_url=self.base_url or "https://archidekt.com",
            login_endpoint="/rest-auth/login/",
            provider="archidekt",
        )

        # Apply authentication if credentials were provided
        if username and password:
            try:
                self.auth_handler.authenticate(username=username, password=password)
                self._apply_auth_to_http_client()
                logger.info("Archidekt JWT authentication successful")
            except Exception as e:
                # Clear credentials from memory after authentication attempt
                self._username = None
                self._password = None
                # Re-raise as Archidekt-specific authentication error
                if isinstance(e, (NetworkError, APIError)):
                    raise ArchidektAuthenticationError(
                        f"Authentication failed: {e}",
                        status_code=getattr(e, "status_code", None),
                    ) from e
                else:
                    raise ArchidektAuthenticationError(
                        f"Authentication failed: {e}",
                    ) from e
            finally:
                # Ensure credentials are cleared from memory
                self._username = None
                self._password = None

    def _initialize(self) -> None:
        """Archidekt-specific initialization."""
        # Override the base_url from config to use /api/ endpoint
        # This is called by BaseProvider.__init__ before auth_handler is set
        self.base_url = "https://archidekt.com/api/"

        # Update HTTP client with the correct base URL
        if hasattr(self, "http_client") and self.http_client:
            self.http_client.base_url = self.base_url

    def _apply_auth_to_http_client(self) -> None:
        """Apply JWT authentication to the HTTP client."""
        # Apply JWT token to the existing HTTP client session
        self.auth_handler.apply_auth(self.http_client.session)

    def _check_authentication(self) -> None:
        """Check if authentication is required and valid.

        Raises:
            ArchidektAuthenticationError: If authentication is required but not valid.
        """
        if not self.is_authenticated():
            raise ArchidektAuthenticationError(
                "Authentication is required for this operation. "
                "Please provide username and password when creating the provider.",
                status_code=401,
            )

    def is_authenticated(self) -> bool:
        """Check if the provider is currently authenticated.

        Returns:
            True if JWT token is present and valid, False otherwise.
        """
        return self.auth_handler.is_authenticated()

    def authenticate(self, username: str, password: str) -> None:
        """Authenticate with Archidekt using username and password.

        Args:
            username: The username for authentication.
            password: The password for authentication.

        Raises:
            ArchidektAuthenticationError: If authentication fails.
            NetworkError: If there is a network error.
            APIError: If the API returns an error during authentication.
        """
        try:
            self.auth_handler.authenticate(username=username, password=password)
            self._apply_auth_to_http_client()
            logger.info("Archidekt JWT authentication successful")
        except (NetworkError, APIError):
            # Preserve transient network/API errors so callers can
            # distinguish them from genuine authentication failures.
            raise
        except Exception as e:
            raise ArchidektAuthenticationError(
                f"Authentication failed: {e}",
            ) from e

    def clear_auth(self) -> None:
        """Clear authentication credentials."""
        self.auth_handler.clear_auth()
        # Clear the HTTP client's authorization header
        if hasattr(self, "http_client") and self.http_client:
            # Remove Authorization header if present
            if "Authorization" in self.http_client.session.headers:
                del self.http_client.session.headers["Authorization"]
        logger.info("Archidekt authentication cleared")

    def refresh_auth(
        self,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Refresh the provider's authentication.

        Uses the stored JWT refresh token to obtain a new access token
        without requiring username/password. If no refresh token is
        available, falls back to full re-authentication using the provided
        credentials.

        Args:
            username: Username for re-authentication fallback. Required
                if no refresh token is stored.
            password: Password for re-authentication fallback. Required
                if no refresh token is stored.

        Raises:
            ArchidektAuthenticationError: If token refresh fails and no
                fallback credentials are provided.
            NetworkError: If there is a network error during refresh.
            APIError: If the API returns an error during refresh.
        """
        try:
            self.auth_handler.refresh(username=username, password=password)
            self._apply_auth_to_http_client()
            logger.info("Archidekt authentication refreshed successfully")
        except (NetworkError, APIError):
            # Preserve transient network/API errors so callers can
            # distinguish them from genuine authentication failures.
            raise
        except Exception as e:
            raise ArchidektAuthenticationError(
                f"Authentication refresh failed: {e}",
            ) from e

    def enable_har_logging(self) -> None:
        """Enable HAR logging for debugging."""
        self.har_logger.enable()

    def disable_har_logging(self) -> None:
        """Disable HAR logging."""
        self.har_logger.disable()

    def export_har(self, filepath: str | None = None) -> str:
        """Export captured HAR data to a file or string.

        Args:
            filepath: Path to write the HAR file. If None, returns the HAR JSON.

        Returns:
            The HAR JSON string.

        Raises:
            ValueError: If no HAR entries have been captured.
        """
        return self.har_logger.export(filepath)

    def _log_response(self, response: requests.Response) -> None:
        """Log a response to HAR logger if enabled.

        Args:
            response: The requests.Response object.
        """
        if self.har_logger.enabled:
            # Extract response data
            headers = dict(response.headers) if hasattr(response, "headers") else {}
            # Convert RequestsCookieJar to dict[str, str]
            cookies: dict[str, str] = {}
            if hasattr(response, "cookies"):
                for name, value in response.cookies.items():
                    cookies[name] = str(value)

            # Try to get the raw body content
            body = None
            if hasattr(response, "_content"):
                body = response._content

            # Log the response
            self.har_logger.log_response(
                status=response.status_code,
                status_text=response.reason if hasattr(response, "reason") else "",
                headers=headers,
                body=body,
                cookies=cookies,
            )

    def _evict_relation_map(self) -> None:
        """Evict oldest entries when the relation map exceeds its cap.

        Must be called while holding ``self._lock``. Removes
        least-recently-inserted entries until the map is within the
        configured ``MAX_RELATION_MAP_SIZE``.
        """
        while len(self._deck_relation_map) > self.MAX_RELATION_MAP_SIZE:
            self._deck_relation_map.popitem(last=False)

    def _sanitize_response_text(self, text: str) -> str:
        """Sanitize response text to remove sensitive data before logging.

        Callers should pass the FULL response text (not pre-truncated) so the
        regex patterns can match complete fields; truncate the returned value
        afterwards if a shorter representation is needed.

        Args:
            text: The full response text to sanitize.

        Returns:
            Sanitized text with sensitive fields redacted.
        """
        # Use a pattern that handles escaped quotes in JSON strings.
        # A named capture group ``key`` extracts the field name (including
        # the surrounding quotes and trailing colon) so the redacted value
        # can be reconstructed without splitting on ":" which is unsafe
        # when the sensitive value itself contains a colon.
        # (?:[^"\\]|\\.)* matches either non-quote/non-backslash chars OR escaped chars
        sensitive_patterns = [
            r'(?P<key>"token"\s*:)\s*"(?:[^"\\]|\\.)*"',
            r'(?P<key>"access_token"\s*:)\s*"(?:[^"\\]|\\.)*"',
            r'(?P<key>"refresh_token"\s*:)\s*"(?:[^"\\]|\\.)*"',
            r'(?P<key>"password"\s*:)\s*"(?:[^"\\]|\\.)*"',
            r'(?P<key>"username"\s*:)\s*"(?:[^"\\]|\\.)*"',
            r'(?P<key>"email"\s*:)\s*"(?:[^"\\]|\\.)*"',
            r'(?P<key>"api_key"\s*:)\s*"(?:[^"\\]|\\.)*"',
            r'(?P<key>"secret"\s*:)\s*"(?:[^"\\]|\\.)*"',
        ]

        sanitized = text
        for pattern in sensitive_patterns:
            sanitized = re.sub(
                pattern,
                lambda m: m.group("key") + ' "[REDACTED]"',
                sanitized,
            )

        return sanitized

    def _handle_response(self, response: requests.Response, resource_type: str) -> Any:
        """Handle HTTP response and raise appropriate exceptions.

        Args:
            response: The requests.Response object.
            resource_type: The type of resource being requested (for error messages).

        Returns:
            The parsed JSON data from the response.

        Raises:
            ArchidektAuthenticationError: If authentication fails (401, 403).
            ArchidektNotFoundError: If resource is not found (404).
            ArchidektRateLimitError: If rate limit is exceeded (429).
            ArchidektAPIError: If there is a server error (5xx).
            NetworkError: If there is a network error.
            APIError: If there is another API error.
        """
        # Log the response if HAR logging is enabled
        self._log_response(response)

        try:
            # Check for network errors
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            status_code = response.status_code

            if status_code == 401:
                # Avoid logging sensitive data in authentication errors.
                # Sanitize the full response text first so the regex can match
                # complete fields, then truncate for the error details.
                response_text = response.text or ""
                sanitized_text = self._sanitize_response_text(response_text)[:200]
                raise ArchidektAuthenticationError(
                    f"Authentication failed for {resource_type}",
                    status_code=status_code,
                    details={
                        "response_text": sanitized_text,
                    },
                ) from e
            elif status_code == 403:
                # Avoid logging sensitive data in authentication errors.
                response_text = response.text or ""
                sanitized_text = self._sanitize_response_text(response_text)[:200]
                raise ArchidektAuthenticationError(
                    f"Access denied for {resource_type}",
                    status_code=status_code,
                    details={
                        "response_text": sanitized_text,
                    },
                ) from e
            elif status_code == 404:
                raise ArchidektNotFoundError(
                    f"{resource_type.replace('_', ' ').title()} not found",
                    status_code=status_code,
                    resource_type=resource_type,
                ) from e
            elif status_code == 429:
                # Honor the Retry-After header if present. It may be a
                # delta-seconds integer or an HTTP-date; fall back to 60s.
                retry_after = 60
                retry_header = response.headers.get("Retry-After")
                if retry_header:
                    try:
                        retry_after = int(retry_header)
                    except (ValueError, TypeError):
                        # Could be an HTTP-date (RFC 7231) or malformed.
                        # Parse the date and compute the remaining seconds.
                        try:
                            retry_date = parsedate_to_datetime(retry_header)
                            if retry_date is not None:
                                if retry_date.tzinfo is None:
                                    retry_date = retry_date.replace(tzinfo=timezone.utc)
                                now = datetime.now(timezone.utc)
                                delta = (retry_date - now).total_seconds()
                                retry_after = max(0, int(delta))
                        except (TypeError, ValueError, OverflowError):
                            logger.warning(
                                "Could not parse Retry-After " "header: %s",
                                retry_header,
                            )
                raise ArchidektRateLimitError(
                    "Rate limit exceeded",
                    status_code=status_code,
                    retry_after=retry_after,
                ) from e
            elif 500 <= status_code < 600:
                response_text = response.text or ""
                raise ArchidektAPIError(
                    f"Server error: {status_code}",
                    status_code=status_code,
                    details={
                        "response_text": self._sanitize_response_text(response_text)[
                            :200
                        ],
                    },
                ) from e
            else:
                response_text = response.text or ""
                raise APIError(
                    f"API error: {status_code} - "
                    f"{self._sanitize_response_text(response_text)[:200]}",
                    provider=self.name,
                    status_code=status_code,
                ) from e
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                f"Network error during {resource_type} request",
                original_exception=e,
            ) from e

        # Try to parse JSON response
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError):
            # If response is not JSON, return text
            return response.text

    def search(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
        game: int | None = None,
        format: str | None = None,
        rarity: str | None = None,
        set_code: str | None = None,
        subtype: str | None = None,
        cmc: int | None = None,
        power: str | None = None,
        toughness: str | None = None,
        loyalty: str | None = None,
        text_search: str | None = None,
        keyword: str | None = None,
        artist: str | None = None,
        release: str | None = None,
        set_type: str | None = None,
        include_tokens: bool | None = None,
        include_digital: bool | None = None,
        include_emblems: bool | None = None,
        include_art_cards: bool | None = None,
        unique: str | None = None,
    ) -> list[Card]:
        """Search for cards with generic parameters.

        This method searches for cards using common MTG parameters that are
        mapped to Archidekt's API. It provides a consistent interface across
        all providers.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include in its color identity.
            identity: List of colors the card's color identity must exactly match.
            type_line: Type line the card must include.
            limit: Maximum number of results to return (default 20).
            page: Page number for pagination (1-based, default 1).
            order: Sort order for results.
            game: Game filter (1=paper, 2=MTGO, 3=Arena).
            format: Format legality filter.
            rarity: Rarity filter.
            set_code: Set code filter.
            subtype: Card subtype filter.
            cmc: Converted mana cost filter.
            power: Power filter.
            toughness: Toughness filter.
            loyalty: Loyalty filter.
            text_search: Oracle text search filter.
            keyword: Keyword filter.
            artist: Artist filter.
            release: Release date filter.
            set_type: Set type filter.
            include_tokens: Whether to include tokens.
            include_digital: Whether to include digital-only cards.
            include_emblems: Whether to include emblem cards.
            include_art_cards: Whether to include art cards.
            unique: Unique results filter.

        Returns:
            A list of Card objects matching the search criteria.

        Raises:
            ArchidektValidationError: If the search parameters are invalid.
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
        """
        try:
            # Apply rate limiting. Using the guard context manager ensures the
            # request is recorded against the sliding window on success (the
            # manual check()/wait() pair never recorded requests, making the
            # configured limit a no-op).
            with self.rate_limiter.guard("archidekt"):
                # Validate and process search parameters
                search_params = self._build_search_query(
                    name=name,
                    colors=colors,
                    identity=identity,
                    type_line=type_line,
                    limit=limit,
                    page=page,
                    order=order,
                    game=game,
                    format=format,
                    rarity=rarity,
                    set_code=set_code,
                    subtype=subtype,
                    cmc=cmc,
                    power=power,
                    toughness=toughness,
                    loyalty=loyalty,
                    text_search=text_search,
                    keyword=keyword,
                    artist=artist,
                    release=release,
                    set_type=set_type,
                    include_tokens=include_tokens,
                    include_digital=include_digital,
                    include_emblems=include_emblems,
                    include_art_cards=include_art_cards,
                    unique=unique,
                )

                # Build the request URL and parameters
                endpoint = "cards/v2/"

                logger.debug(f"Searching Archidekt with params: {search_params}")

                response = self.http_client.get(endpoint, params=search_params)
                data = self._handle_response(response, "card_search")

            # Parse results
            if not data or not isinstance(data, dict):
                return []

            # Extract card results
            results = data.get("results", [])
            if not results:
                return []

            # Parse each card result
            cards = []
            for card_data in results:
                try:
                    card = self._parse_card(card_data)
                    cards.append(card)
                except Exception as e:
                    logger.warning(f"Failed to parse card data: {e}")
                    continue

            return cards

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt search: {e}")
            raise NetworkError(
                "Network error during search",
                original_exception=e,
                provider=self.name,
            ) from e

    def _build_search_query(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
        game: int | None = None,
        format: str | None = None,
        rarity: str | None = None,
        set_code: str | None = None,
        subtype: str | None = None,
        cmc: int | None = None,
        power: str | None = None,
        toughness: str | None = None,
        loyalty: str | None = None,
        text_search: str | None = None,
        keyword: str | None = None,
        artist: str | None = None,
        release: str | None = None,
        set_type: str | None = None,
        include_tokens: bool | None = None,
        include_digital: bool | None = None,
        include_emblems: bool | None = None,
        include_art_cards: bool | None = None,
        unique: str | None = None,
    ) -> dict[str, Any]:
        """Build Archidekt-specific search parameters from generic ones.

        Args:
            name: Card name or name fragment.
            colors: List of colors for color filter.
            identity: List of colors for color identity filter.
            type_line: Type line filter.
            limit: Maximum results.
            page: Page number.
            order: Sort order.
            game: Game filter (1=paper, 2=MTGO, 3=Arena).
            format: Format legality filter.
            rarity: Rarity filter.
            set_code: Set code filter.
            subtype: Card subtype filter.
            cmc: Converted mana cost filter.
            power: Power filter.
            toughness: Toughness filter.
            loyalty: Loyalty filter.
            text_search: Oracle text search filter.
            keyword: Keyword filter.
            artist: Artist filter.
            release: Release date filter.
            set_type: Set type filter.
            include_tokens: Whether to include tokens.
            include_digital: Whether to include digital-only cards.
            include_emblems: Whether to include emblem cards.
            include_art_cards: Whether to include art cards.
            unique: Unique results filter.

        Returns:
            Dictionary of Archidekt-specific search parameters.
        """
        params: dict[str, Any] = {}

        # Include standard flags from HAR file
        params["includeTokens"] = ""
        params["includeDigital"] = ""
        params["includeEmblems"] = ""
        params["includeArtCards"] = ""
        params["unique"] = ""

        # Set game to paper (1) by default
        params["game"] = self.GAME_ID_PAPER

        # Handle name search
        if name:
            params["nameSearch"] = name

        # Handle color identity
        if identity:
            # Map Color enum to Archidekt color strings
            color_map = {
                Color.WHITE: "White",
                Color.BLUE: "Blue",
                Color.BLACK: "Black",
                Color.RED: "Red",
                Color.GREEN: "Green",
            }
            color_strings = [
                color_map.get(c, str(c)) for c in identity if c in color_map
            ]
            if color_strings:
                params["colorIdentity"] = ",".join(color_strings)

        # Handle colors
        if colors:
            color_map = {
                Color.WHITE: "White",
                Color.BLUE: "Blue",
                Color.BLACK: "Black",
                Color.RED: "Red",
                Color.GREEN: "Green",
            }
            color_strings = [color_map.get(c, str(c)) for c in colors if c in color_map]
            if color_strings:
                params["colors"] = ",".join(color_strings)

        # Handle type line
        if type_line:
            params["type"] = type_line

        # Handle limit and pagination
        if limit:
            params["pageSize"] = limit
        if page > 1:
            params["page"] = page

        # Handle ordering
        if order:
            params["orderBy"] = order

        # Add additional filter parameters
        extra_params: dict[str, Any] = {
            "game": game,
            "formatLegality": format,
            "rarity": rarity,
            "set": set_code,
            "subtype": subtype,
            "cmc": cmc,
            "power": power,
            "toughness": toughness,
            "loyalty": loyalty,
            "textSearch": text_search,
            "keyword": keyword,
            "artist": artist,
            "release": release,
            "setType": set_type,
            "includeTokens": include_tokens,
            "includeDigital": include_digital,
            "includeEmblems": include_emblems,
            "includeArtCards": include_art_cards,
            "unique": unique,
        }

        for key, value in extra_params.items():
            if value is not None:
                params[key] = value

        return params

    def search_syntax(
        self,
        query: str,
        limit: int = 20,
        page: int = 1,
        order: str | None = None,
        game: int | None = None,
        format: str | None = None,
        rarity: str | None = None,
        set_code: str | None = None,
        subtype: str | None = None,
        cmc: int | None = None,
        power: str | None = None,
        toughness: str | None = None,
        loyalty: str | None = None,
        text_search: str | None = None,
        keyword: str | None = None,
        artist: str | None = None,
        release: str | None = None,
        set_type: str | None = None,
        include_tokens: bool | None = None,
        include_digital: bool | None = None,
        include_emblems: bool | None = None,
        include_art_cards: bool | None = None,
        unique: str | None = None,
    ) -> list[Card]:
        """Search for cards using Archidekt-specific query syntax.

        This method provides an escape hatch for power users who need to use
        Archidekt-specific query syntax that is not available through the
        generic search() method.

        Args:
            query: The Archidekt-specific query string.
            limit: Maximum number of results to return (default 20).
            page: Page number for pagination (1-based, default 1).
            order: Sort order for results.
            game: Game filter (1=paper, 2=MTGO, 3=Arena).
            format: Format legality filter.
            rarity: Rarity filter.
            set_code: Set code filter.
            subtype: Card subtype filter.
            cmc: Converted mana cost filter.
            power: Power filter.
            toughness: Toughness filter.
            loyalty: Loyalty filter.
            text_search: Oracle text search filter.
            keyword: Keyword filter.
            artist: Artist filter.
            release: Release date filter.
            set_type: Set type filter.
            include_tokens: Whether to include tokens.
            include_digital: Whether to include digital-only cards.
            include_emblems: Whether to include emblem cards.
            include_art_cards: Whether to include art cards.
            unique: Unique results filter.

        Returns:
            A list of Card objects matching the query.

        Raises:
            ArchidektValidationError: If the query is invalid.
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
        """
        if not query or not isinstance(query, str):
            raise ArchidektValidationError(
                "Query must be a non-empty string",
                provider=self.name,
            )

        if limit is not None and (not isinstance(limit, int) or limit < 1):
            raise ArchidektValidationError(
                "limit must be a positive integer (>= 1)",
                provider=self.name,
            )

        try:
            with self.rate_limiter.guard("archidekt"):
                params: dict[str, Any] = {
                    "nameSearch": query,
                    "game": self.GAME_ID_PAPER,
                    "includeTokens": "",
                    "includeDigital": "",
                    "includeEmblems": "",
                    "includeArtCards": "",
                    "unique": "",
                }

                if limit:
                    params["pageSize"] = limit
                if page > 1:
                    params["page"] = page
                if order:
                    params["orderBy"] = order

                # Add additional filter parameters
                extra_params: dict[str, Any] = {
                    "game": game,
                    "formatLegality": format,
                    "rarity": rarity,
                    "set": set_code,
                    "subtype": subtype,
                    "cmc": cmc,
                    "power": power,
                    "toughness": toughness,
                    "loyalty": loyalty,
                    "textSearch": text_search,
                    "keyword": keyword,
                    "artist": artist,
                    "release": release,
                    "setType": set_type,
                    "includeTokens": include_tokens,
                    "includeDigital": include_digital,
                    "includeEmblems": include_emblems,
                    "includeArtCards": include_art_cards,
                    "unique": unique,
                }

                for key, value in extra_params.items():
                    if value is not None:
                        params[key] = value

                response = self.http_client.get("cards/v2/", params=params)
                data = self._handle_response(response, "card_search_syntax")

                if not data or not isinstance(data, dict):
                    return []

                results = data.get("results", [])
                if not results:
                    return []

                cards = []
                for card_data in results:
                    try:
                        card = self._parse_card(card_data)
                        cards.append(card)
                    except Exception as e:
                        logger.warning(f"Failed to parse card data: {e}")
                        continue

                return cards

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt search_syntax: {e}")
            raise NetworkError(
                "Network error during search_syntax",
                original_exception=e,
                provider=self.name,
            ) from e

    def get_card(self, card_id: str) -> Card:
        """Get a specific card by its Archidekt ID.

        Note:
            Archidekt uses its own card IDs. These can be obtained
            from search results or deck data.

        Args:
            card_id: The Archidekt card ID.

        Returns:
            A Card object for the specified card.

        Raises:
            ArchidektValidationError: If card_id is not provided.
            ArchidektNotFoundError: If the card is not found.
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
        """
        if not card_id:
            raise ArchidektValidationError(
                "card_id is required for get_card()",
                provider=self.name,
            )

        try:
            with self.rate_limiter.guard("archidekt"):
                # Archidekt doesn't have a direct GET /cards/v2/{id}/ endpoint
                # We need to use search. Try multiple approaches:
                # 1. Try as oracleCardIds (works for numeric IDs and some string IDs)
                # 2. Try as regular id with exact match
                # 3. Try name search

                # First, try using oracleCardIds for all card IDs
                # This works for numeric IDs and can also work for non-numeric IDs
                params = {
                    "oracleCardIds": card_id,
                    "game": 1,
                    "unique": True,
                    "pageSize": 1,
                }
                response = self.http_client.get("cards/v2/", params=params)
                data = self._handle_response(response, "card")

                if data and data.get("results"):
                    return self._parse_card(data["results"][0])

                # If oracleCardIds didn't work, try as a name or other identifier
                params = {
                    "nameSearch": card_id,
                    "exact": True,
                    "game": 1,
                    "unique": True,
                    "pageSize": 1,
                }
                response = self.http_client.get("cards/v2/", params=params)
                data = self._handle_response(response, "card")

                if not data or not data.get("results"):
                    raise ArchidektNotFoundError(
                        "Card not found",
                        status_code=404,
                        resource_type="card",
                        resource_id=card_id,
                    )

                # Return the first result
                return self._parse_card(data["results"][0])

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_card: {e}")
            raise NetworkError(
                "Network error during get_card",
                original_exception=e,
                provider=self.name,
            ) from e

    def get_deck(self, deck_id: str) -> Deck:
        """Get a specific deck by its Archidekt ID.

        Note:
            Archidekt deck IDs are numeric strings. Decks can be public or private.
            Private decks require authentication.

        Args:
            deck_id: The Archidekt deck ID.

        Returns:
            A Deck object for the specified deck.

        Raises:
            ArchidektValidationError: If deck_id is not provided.
            ArchidektNotFoundError: If the deck is not found.
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
        """
        if not deck_id:
            raise ArchidektValidationError(
                "deck_id is required for get_deck()",
                provider=self.name,
            )

        try:
            with self.rate_limiter.guard("archidekt"):
                response = self.http_client.get(f"decks/v2/{deck_id}/")
                data = self._handle_response(response, "deck")

                if not data:
                    raise ArchidektNotFoundError(
                        "Deck not found",
                        status_code=404,
                        resource_type="deck",
                        resource_id=deck_id,
                    )

                return self._parse_deck(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_deck: {e}")
            raise NetworkError(
                "Network error during get_deck",
                original_exception=e,
                provider=self.name,
            ) from e

    def get_user_decks(self, user_id: str | None = None) -> list[Deck]:
        """Get all decks for a specific user or the authenticated user.

        Args:
            user_id: The user ID. If None, uses the authenticated user.

        Returns:
            A list of Deck objects for the user's decks.

        Raises:
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
        """
        try:
            with self.rate_limiter.guard("archidekt"):
                # Archidekt API uses /api/users/{user_id}/decks/ endpoint
                # If no user_id provided, use the authenticated user's ID
                target_user_id = user_id
                if not target_user_id:
                    if not hasattr(self, "auth_handler") or self.auth_handler is None:
                        raise ArchidektValidationError(
                            "user_id is required or authentication must be provided",
                            provider=self.name,
                        )
                    target_user_id = self.auth_handler.user_id

                if not target_user_id:
                    raise ArchidektValidationError(
                        "user_id is required or authentication must be provided",
                        provider=self.name,
                    )

                response = self.http_client.get(f"users/{target_user_id}/decks/")
                data = self._handle_response(response, "user_decks")

                if not data:
                    return []

                # Handle both single deck and list of decks
                if isinstance(data, dict):
                    if "results" in data:
                        results = data["results"]
                    elif "decks" in data:
                        results = data["decks"]
                    else:
                        results = [data]
                elif isinstance(data, list):
                    results = data
                else:
                    results = [data]

                decks = []
                for deck_data in results:
                    try:
                        deck = self._parse_deck(deck_data)
                        decks.append(deck)
                    except Exception as e:
                        logger.warning(f"Failed to parse deck data: {e}")
                        continue

                return decks

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_user_decks: {e}")
            raise NetworkError(
                "Network error during get_user_decks",
                original_exception=e,
                provider=self.name,
            ) from e

    def create_deck(
        self,
        name: str,
        format: Format | None = None,
        description: str = "",
        private: bool = True,
        unlisted: bool = False,
        folder_id: str | None = None,
    ) -> Deck:
        """Create a new deck.

        Args:
            name: The name of the deck.
            format: The format of the deck. Defaults to Commander.
            description: The description of the deck.
            private: Whether the deck is private. Defaults to True.
            unlisted: Whether the deck is unlisted. Defaults to False.
            folder_id: The parent folder ID for the deck. If None, uses
                the default folder.

        Returns:
            The created Deck object.

        Raises:
            ArchidektAuthenticationError: If authentication is required but not provided.
            ArchidektValidationError: If required parameters are missing.
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
        """
        self._check_authentication()

        if not name:
            raise ArchidektValidationError(
                "name is required for create_deck()",
                provider=self.name,
            )

        try:
            with self.rate_limiter.guard("archidekt"):
                # Map format to Archidekt format ID
                deck_format = (
                    self.FORMAT_MAP.get(format, self.FORMAT_MAP[Format.COMMANDER])
                    if format
                    else self.FORMAT_MAP[Format.COMMANDER]
                )

                # Build deck creation payload based on HAR file analysis
                payload = {
                    "name": name,
                    "deckFormat": deck_format,
                    "game": self.GAME_ID_PAPER,  # Paper magic
                    "parent_folder": folder_id,
                }

                # Add optional fields
                if description:
                    payload["description"] = description

                payload["private"] = private
                payload["unlisted"] = unlisted

                response = self.http_client.post("decks/v2/", json=payload)
                data = self._handle_response(response, "deck_creation")

                if not data:
                    raise ArchidektAPIError(
                        "Deck creation failed - no response data",
                        provider=self.name,
                    )

                return self._parse_deck(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt create_deck: {e}")
            raise NetworkError(
                "Network error during create_deck",
                original_exception=e,
                provider=self.name,
            ) from e

    def _resolve_card_id_by_name(self, card_name: str) -> str:
        """Resolve a card name to its Archidekt card ID without rate limiting.

        Performs an internal card search to look up the card ID for a given
        name. Used by methods such as :meth:`add_card_to_deck` when only a
        card name is supplied. This bypasses the rate limiter because the
        calling method already governs the overall operation with the
        ``guard()`` context manager, avoiding double-counting a single
        logical operation against the rate limit.

        Args:
            card_name: The card name to resolve.

        Returns:
            The resolved card ID as a string.

        Raises:
            ArchidektValidationError: If the card cannot be found or has
                no valid ID.
            NetworkError: If there is a network error during the lookup.
            ArchidektAPIError: If the API returns an error.
        """
        search_params = self._build_search_query(name=card_name, limit=1)
        endpoint = "cards/v2/"
        try:
            response = self.http_client.get(endpoint, params=search_params)
            data = self._handle_response(response, "card_search")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt card lookup: {e}")
            raise NetworkError(
                "Network error during card lookup",
                original_exception=e,
                provider=self.name,
            ) from e

        if not data or not isinstance(data, dict):
            raise ArchidektValidationError(
                f"Card not found: {card_name}",
                provider=self.name,
            )
        results = data.get("results", [])
        if not results:
            raise ArchidektValidationError(
                f"Card not found: {card_name}",
                provider=self.name,
            )
        try:
            card = self._parse_card(results[0])
        except Exception as e:
            raise ArchidektValidationError(
                f"Card found but could not be parsed: {card_name}",
            ) from e
        resolved_id = getattr(card, "id", None) or getattr(card, "oracle_id", None)
        if not resolved_id:
            raise ArchidektValidationError(
                f"Card found but has no valid ID: {card_name}",
                provider=self.name,
            )
        return str(resolved_id)

    def add_card_to_deck(
        self,
        deck_id: str,
        card_id: str | None = None,
        card_name: str | None = None,
        quantity: int = 1,
        foil: bool = False,
        categories: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a card to a deck.

        Either card_id or card_name must be provided.

        Args:
            deck_id: The Archidekt deck ID.
            card_id: The Archidekt card ID to add.
            card_name: The card name to add (will be resolved to card ID).
            quantity: The quantity to add. Defaults to 1.
            foil: Whether to add as foil. Defaults to False.
            categories: List of categories for the card in the deck.

        Returns:
            The API response containing updated deck information.

        Raises:
            ArchidektAuthenticationError: If authentication is required but not provided.
            ArchidektValidationError: If required parameters are missing.
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
        """
        self._check_authentication()

        if not deck_id:
            raise ArchidektValidationError(
                "deck_id is required for add_card_to_deck()",
                provider=self.name,
            )

        if not card_id and not card_name:
            raise ArchidektValidationError(
                "Either card_id or card_name is required for add_card_to_deck()",
                provider=self.name,
            )

        # If only card_name is provided, resolve to card_id. Use the
        # internal resolver (which bypasses rate limiting) so the overall
        # operation is counted once by the guard() block below.
        if card_id is None and card_name:
            card_id = self._resolve_card_id_by_name(card_name)

        if not card_id:
            raise ArchidektValidationError(
                "Could not resolve card to valid card_id",
                provider=self.name,
            )

        # Archidekt uses integer card/deck IDs. A non-numeric ID (e.g. a
        # UUID-style oracle id) would raise ValueError; validate explicitly
        # here BEFORE the try/except block so that ArchidektValidationError is
        # not accidentally caught by the RequestException handler.
        try:
            card_id_int = int(card_id)
            deck_id_int = int(deck_id)
        except (TypeError, ValueError) as conv_err:
            raise ArchidektValidationError(
                f"card_id and deck_id must be numeric, got "
                f"card_id={card_id!r}, deck_id={deck_id!r}",
                provider=self.name,
            ) from conv_err

        try:
            with self.rate_limiter.guard("archidekt"):
                # Generate unique patch ID
                patch_id = str(uuid.uuid4())

                # Build the operation payload based on HAR file analysis
                # PATCH /api/decks/{deck_id}/modifyCards/v2/ with operations
                operations = [
                    {
                        "cardId": card_id_int,  # Archidekt uses integer card IDs
                        "deckId": deck_id_int,  # Archidekt uses integer deck IDs
                        "patchId": patch_id,
                        "operation": "Add",
                        "quantity": quantity,
                        "modifier": "Foil" if foil else "Normal",
                    }
                ]

                # Add categories if provided
                if categories:
                    for op in operations:
                        op["categories"] = categories

                payload = {
                    "operations": operations,
                    "deckId": deck_id_int,
                }

                response = self.http_client.patch(
                    f"decks/{deck_id}/modifyCards/v2/", json=payload
                )
                data = self._handle_response(response, "deck_modify_cards")

                # Extract the actual deck_relation_id from the API response
                # The response likely contains a list of results with deckRelationId fields
                actual_relation_id = None
                if data and isinstance(data, dict):
                    # Try to extract from the first result if available
                    results = data.get("results", [])
                    if results and isinstance(results, list) and len(results) > 0:
                        actual_relation_id = results[0].get(
                            "deckRelationId"
                        ) or results[0].get("id")

                # Fall back to patch_id if no relation ID found (should not happen)
                if actual_relation_id is None:
                    actual_relation_id = patch_id
                    logger.warning(
                        f"Could not extract deck_relation_id from response, using patch_id: {patch_id}"
                    )

                # Store the actual deck_relation_id
                with self._lock:
                    self._deck_relation_map[(deck_id, card_id)] = str(
                        actual_relation_id
                    )
                    self._evict_relation_map()

                return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt add_card_to_deck: {e}")
            raise NetworkError(
                "Network error during add_card_to_deck",
                original_exception=e,
                provider=self.name,
            ) from e

    def remove_card_from_deck(
        self,
        deck_id: str,
        card_id: str,
        deck_relation_id: str | None = None,
        quantity: int = 1,
    ) -> dict[str, Any]:
        """Remove a card from a deck.

        Args:
            deck_id: The Archidekt deck ID.
            card_id: The Archidekt card ID to remove.
            deck_relation_id: The deck relation ID from previous add operation.
                If not provided, will try to look up from internal mapping.
            quantity: The quantity to remove. Defaults to 1.

        Returns:
            The API response containing updated deck information.

        Raises:
            ArchidektAuthenticationError: If authentication is required but not provided.
            ArchidektValidationError: If required parameters are missing.
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
        """
        self._check_authentication()

        if not deck_id:
            raise ArchidektValidationError(
                "deck_id is required for remove_card_from_deck()",
                provider=self.name,
            )

        if not card_id:
            raise ArchidektValidationError(
                "card_id is required for remove_card_from_deck()",
                provider=self.name,
            )

        # Try to get deck_relation_id from internal mapping
        if deck_relation_id is None:
            with self._lock:
                deck_relation_id = self._deck_relation_map.get((deck_id, card_id))

        if not deck_relation_id:
            raise ArchidektValidationError(
                f"No deck_relation_id found for deck {deck_id}, card {card_id}. "
                "Please provide the deck_relation_id from the add_card_to_deck response.",
                provider=self.name,
            )

        # Archidekt uses integer card/deck IDs. A non-numeric ID would
        # raise ValueError; validate explicitly here BEFORE the try/except
        # block so that ArchidektValidationError is not accidentally caught by
        # the RequestException handler.
        try:
            card_id_int = int(card_id)
            deck_id_int = int(deck_id)
        except (TypeError, ValueError) as conv_err:
            raise ArchidektValidationError(
                f"card_id and deck_id must be numeric, got "
                f"card_id={card_id!r}, deck_id={deck_id!r}",
                provider=self.name,
            ) from conv_err

        try:
            with self.rate_limiter.guard("archidekt"):
                # Generate unique patch ID
                patch_id = str(uuid.uuid4())

                # Build the operation payload
                operations = [
                    {
                        "cardId": card_id_int,
                        "deckId": deck_id_int,
                        "deckRelationId": deck_relation_id,
                        "patchId": patch_id,
                        "operation": "Remove",
                        "quantity": quantity,
                    }
                ]

                payload = {
                    "operations": operations,
                    "deckId": deck_id_int,
                }

                response = self.http_client.patch(
                    f"decks/{deck_id}/modifyCards/v2/", json=payload
                )
                data = self._handle_response(response, "deck_modify_cards")

                # Remove the now-stale relation entry so a subsequent
                # remove with the same (deck_id, card_id) cannot reuse an
                # invalid relation ID.
                with self._lock:
                    self._deck_relation_map.pop((deck_id, card_id), None)

                return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt remove_card_from_deck: {e}")
            raise NetworkError(
                "Network error during remove_card_from_deck",
                original_exception=e,
                provider=self.name,
            ) from e

    def _get_field(self, data: dict[str, Any], *field_names: str) -> Any:
        """Helper to get a field from a dict, trying multiple possible field names.

        Args:
            data: The dictionary to search.
            *field_names: Field names to try, in order of preference.

        Returns:
            The first matching value, or None if none found.
        """
        for field in field_names:
            value = data.get(field)
            if value is not None:
                return value
        return None

    def _parse_card(self, card_data: dict[str, Any]) -> Card:
        """Parse Archidekt card data into a pymtg Card object.

        Args:
            card_data: The raw card data from Archidekt API.

        Returns:
            A Card object.

        Raises:
            ValueError: If required card data is missing.
        """
        if not card_data:
            raise ValueError("No card data provided")

        # Handle nested oracleCard object (from HAR file analysis)
        oracle_card = card_data.get("oracleCard") or card_data

        # Extract basic card information
        card_id = str(
            self._get_field(card_data, "id") or self._get_field(oracle_card, "id") or ""
        )
        name = str(self._get_field(oracle_card, "name") or "")
        mana_cost = str(self._get_field(oracle_card, "manaCost", "mana_cost") or "")

        # Extract Scryfall ID (can be at top level or in oracleCard)
        # Normalize empty strings to None for ID fields
        scryfall_id_raw = (
            self._get_field(oracle_card, "scryfall_id")
            or self._get_field(card_data, "scryfall_id")
            or ""
        )
        scryfall_id = str(scryfall_id_raw) if scryfall_id_raw else None

        # Extract card text (try oracle_text first, then text)
        text = str(self._get_field(oracle_card, "oracle_text", "text") or "")

        # Extract type information
        # Try both 'type' and 'type_line' fields
        card_type = str(self._get_field(oracle_card, "type", "type_line") or "")
        supertypes = self._get_field(oracle_card, "superTypes", "super_types") or []
        types = self._get_field(oracle_card, "types") or []
        subtypes = self._get_field(oracle_card, "subTypes", "sub_types") or []

        # Combine for type_line
        type_line_parts = []
        if supertypes:
            type_line_parts.extend(supertypes)
        if types:
            type_line_parts.extend(types)
        if subtypes:
            type_line_parts.append("-")
            type_line_parts.extend(subtypes)

        # If we didn't get anything from the structured fields, use the simple type or type_line
        if not type_line_parts and card_type:
            type_line_parts = [card_type]

        type_line = " ".join(type_line_parts) if type_line_parts else card_type

        # Extract power and toughness (return None if missing/empty)
        power = str(self._get_field(oracle_card, "power") or "") or None
        toughness = str(self._get_field(oracle_card, "toughness") or "") or None
        loyalty = str(self._get_field(oracle_card, "loyalty") or "") or None

        # Extract colors
        colors_data = self._get_field(oracle_card, "colors") or []
        color_identity_data = (
            self._get_field(oracle_card, "colorIdentity", "color_identity") or []
        )
        color_indicator_data = (
            self._get_field(oracle_card, "colorIndicator", "color_indicator") or []
        )

        # Map Archidekt color strings to Color enum
        # Supports both single-letter codes (W, U, B, R, G) and full names (White, Blue, Black, Red, Green)
        color_map = {
            "W": Color.WHITE,
            "White": Color.WHITE,
            "U": Color.BLUE,
            "Blue": Color.BLUE,
            "B": Color.BLACK,
            "Black": Color.BLACK,
            "R": Color.RED,
            "Red": Color.RED,
            "G": Color.GREEN,
            "Green": Color.GREEN,
        }

        colors = []
        for c in colors_data:
            if c in color_map:
                colors.append(color_map[c])
            else:
                logger.debug(f"Unknown color: {c}")

        color_identity = []
        for c in color_identity_data:
            if c in color_map:
                color_identity.append(color_map[c])
            else:
                logger.debug(f"Unknown color in identity: {c}")

        color_indicator = []
        for c in color_indicator_data:
            if c in color_map:
                color_indicator.append(color_map[c])
            else:
                logger.debug(f"Unknown color in indicator: {c}")

        # Extract rarity
        rarity_str = str(self._get_field(oracle_card, "rarity") or "").lower()
        rarity_map = {
            "common": Rarity.COMMON,
            "uncommon": Rarity.UNCOMMON,
            "rare": Rarity.RARE,
            "mythic": Rarity.MYTHIC,
            "special": Rarity.SPECIAL,
            "bonus": Rarity.BONUS,
        }
        rarity = rarity_map.get(rarity_str)

        # Extract set information from nested edition object or set field or top-level
        edition = card_data.get("edition") or {}
        set_data = card_data.get("set") or {}

        set_name = str(
            edition.get("editionname", "")
            or set_data.get("name", "")
            or card_data.get("set_name", "")
            or ""
        )
        set_code = str(
            edition.get("editioncode", "")
            or set_data.get("code", "")
            or card_data.get("set_code", "")
            or ""
        )
        set_type_str = str(
            edition.get("editiontype", "")
            or set_data.get("set_type", "")
            or card_data.get("set_type", "")
            or ""
        ).lower()
        set_type_map = {
            "expansion": SetType.EXPANSION,
            "core": SetType.CORE,
            "commander": SetType.COMMANDER,
            "funny": SetType.MEME,
            "masterpiece": SetType.MASTERPIECE,
            "promo": SetType.PROMO,
            "starter": SetType.STARTER,
            "box": SetType.BOX,
        }
        set_type = set_type_map.get(set_type_str)

        # Extract edition release date
        released_at = str(edition.get("editiondate", "") or "")

        # Extract prices
        prices_data = card_data.get("prices") or {}
        prices = {
            "usd": float(prices_data.get("tcg", 0) or 0),
            "usd_foil": float(
                prices_data.get("tcgFoil", prices_data.get("tcgfoil", 0)) or 0
            ),
            "eur": float(prices_data.get("ck", 0) or 0),
            "eur_foil": float(
                prices_data.get("ckFoil", prices_data.get("ckfoil", 0)) or 0
            ),
            "tix": float(prices_data.get("mtgo", 0) or 0),
        }

        # Extract collector information
        collector_number = str(card_data.get("collectorNumber", "") or "")
        multiverse_id = int(card_data.get("multiverseid", 0) or 0)

        # Extract artist (can be in card_data or oracle_card)
        artist = str(
            self._get_field(card_data, "artist")
            or self._get_field(oracle_card, "artist")
            or ""
        )

        # Extract oracle ID for grouping cards with the same text
        oracle_id = str(self._get_field(oracle_card, "id") or card_id)

        # Create Card object
        # Note: Convert multiverse_id to list for Card model
        multiverse_ids = [multiverse_id] if multiverse_id else None

        # Convert flavor text to list format
        flavor_text_str = self._get_field(oracle_card, "flavor", "flavor_text")
        if flavor_text_str is None or flavor_text_str == "":
            flavors = None
        else:
            flavors = [str(flavor_text_str)]

        # Build pricing object
        # Archidekt provides pricing data that maps to ScryfallPricing
        scryfall_pricing = None
        if any(prices.values()):
            scryfall_pricing = ScryfallPricing(
                usd=prices.get("usd"),
                usd_foil=prices.get("usd_foil"),
                eur=prices.get("eur"),
                eur_foil=prices.get("eur_foil"),
                tix=prices.get("tix"),
            )

        # Parse card faces if present
        card_faces = None
        card_faces_data = card_data.get("card_faces")
        if card_faces_data and isinstance(card_faces_data, list):
            parsed_faces = []
            for face_data in card_faces_data:
                # Skip non-dict entries
                if not isinstance(face_data, dict):
                    continue

                # Extract flavor text and normalize it
                face_flavor = face_data.get("flavor_text")
                normalized_flavor = (
                    self._normalize_flavor_text(face_flavor) if face_flavor else None
                )

                parsed_face = CardFace(
                    name=str(face_data.get("name", "")),
                    mana_cost=str(face_data.get("manaCost", "") or ""),
                    type_line=str(face_data.get("type", "") or ""),
                    oracle_text=str(face_data.get("text", "") or ""),
                    flavor_text=normalized_flavor,
                )
                parsed_faces.append(parsed_face)
            card_faces = parsed_faces if parsed_faces else None

            # If we have card faces, use the first face's name as the card name
            # (for transform, modal dual-faced, etc.)
            if card_faces and name != card_faces[0].name:
                name = card_faces[0].name

        return Card(
            id=card_id,
            scryfall_id=scryfall_id if scryfall_id else None,
            name=name,
            oracle_id=oracle_id,
            mana_cost=mana_cost,
            cmc=float(self._get_field(oracle_card, "cmc") or 0),
            type_line=type_line,
            oracle_text=text,
            power=power,
            toughness=toughness,
            loyalty=loyalty,
            colors=colors,
            color_identity=color_identity,
            color_indicator=color_indicator if color_indicator else None,
            rarity=rarity,
            set_name=set_name,
            set_code=set_code,
            set_type=set_type,
            collector_number=collector_number,
            multiverse_ids=multiverse_ids,
            artist=artist,
            released_at=released_at,
            pricing=Pricing(scryfall=scryfall_pricing) if scryfall_pricing else None,
            flavors=flavors,
            card_faces=card_faces,
            source="archidekt",
        )

    def _parse_deck(self, deck_data: dict[str, Any]) -> Deck:
        """Parse Archidekt deck data into a pymtg Deck object.

        Args:
            deck_data: The raw deck data from Archidekt API.

        Returns:
            A Deck object.

        Raises:
            ValueError: If required deck data is missing.
        """
        if not deck_data:
            raise ValueError("No deck data provided")

        # Extract basic deck information
        deck_id = str(deck_data.get("id", ""))
        name = str(deck_data.get("name", ""))

        # Extract deck format (can be numeric ID or string name)
        deck_format = None
        deck_format_id = int(deck_data.get("deckFormat", 0) or 0)
        if deck_format_id:
            deck_format = self.FORMAT_ID_MAP.get(deck_format_id)

        # Also check for string format field (for backward compatibility with tests)
        format_str = str(deck_data.get("format", "")).lower()
        if format_str and not deck_format:
            # Try to match by string name
            for fmt, fmt_id in self.FORMAT_MAP.items():
                if fmt.value.lower() == format_str:
                    deck_format = fmt
                    break

            # If still no match, log a warning and default to COMMANDER
            if not deck_format:
                logger.warning(
                    f"Unknown deck format '{format_str}', defaulting to COMMANDER"
                )
                deck_format = Format.COMMANDER

        # Extract owner information
        owner_data = deck_data.get("owner", {})
        owner_id = str(owner_data.get("id", ""))
        # Try both username and name fields
        owner_username = str(
            owner_data.get("username", "") or owner_data.get("name", "")
        )

        # Extract parent folder ID if present
        parent_folder_id = None
        if "parentFolderId" in deck_data:
            parent_folder_id = str(deck_data["parentFolderId"])
        elif "parent_folder" in deck_data:
            parent_folder_id = str(deck_data["parent_folder"])

        # Extract timestamps
        created_at = str(deck_data.get("createdAt", "") or "")
        updated_at = str(deck_data.get("updatedAt", "") or "")

        # Extract color information. Archidekt may return colors as a dict
        # (e.g. {"W": true, "U": false}) or as a list (e.g. ["W", "U"]);
        # handle both formats for robustness.
        colors_data = deck_data.get("colors", {})
        color_identity = []
        color_map = {
            "W": Color.WHITE,
            "U": Color.BLUE,
            "B": Color.BLACK,
            "R": Color.RED,
            "G": Color.GREEN,
        }

        if isinstance(colors_data, dict):
            for color_code, is_present in colors_data.items():
                if is_present and color_code in color_map:
                    color_identity.append(color_map[color_code])
        elif isinstance(colors_data, list):
            for color_code in colors_data:
                if color_code in color_map:
                    color_identity.append(color_map[color_code])

        # Extract description
        description = str(deck_data.get("description", "") or "")

        # Extract privacy settings
        is_private = bool(deck_data.get("private", False))
        is_unlisted = bool(deck_data.get("unlisted", False))

        # Convert to privacy string
        privacy = None
        if is_unlisted:
            privacy = "unlisted"
        elif is_private:
            privacy = "private"
        else:
            privacy = "public"

        # Parse deck cards if present
        cards = []
        from pymtg.models.card import DeckCard

        def parse_card_entry(card_entry, board=None, default_quantity=1):
            """Helper to parse a card entry and add it to cards list."""
            if not isinstance(card_entry, dict):
                return

            card_data = card_entry.get("card", {})

            # Skip if card_data is not a dict or is empty
            if not isinstance(card_data, dict) or not card_data:
                return

            quantity = int(
                card_entry.get("quantity", default_quantity) or default_quantity
            )

            # Try to get board from entry first, then from card entry
            # categories. In Archidekt's deck API, categories live on the
            # card entry (the deck card wrapper), not on the inner card
            # definition, so read from card_entry.
            entry_board = board
            if not entry_board:
                card_categories = card_entry.get("categories", [])
                if isinstance(card_categories, list):
                    for category in card_categories:
                        category_lower = str(category).lower()
                        if category_lower == "main":
                            entry_board = "main"
                            break
                        elif category_lower == "sideboard":
                            entry_board = "sideboard"
                            break
                        elif category_lower == "commander":
                            entry_board = "commander"
                            break
                        elif category_lower == "maybeboard":
                            entry_board = "maybe"
                            break

            # Parse the card
            parsed_card = self._parse_card(card_data)

            # Create DeckCard
            deck_card = DeckCard(
                card=parsed_card,
                count=quantity,
                board=entry_board,
            )
            cards.append(deck_card)

            # Populate the deck relation map so remove_card_from_deck can
            # look up the relation ID for cards loaded from the API without
            # requiring the caller to pass deck_relation_id explicitly.
            # Archidekt exposes the relation ID on the card entry as either
            # "deckRelationId" or "id" (the entry's own ID), and the card's
            # oracle/numeric ID lives under card_data["id"].
            card_id_str = str(card_data.get("id", ""))
            relation_id = card_entry.get("deckRelationId") or card_entry.get("id")
            if card_id_str and relation_id is not None:
                with self._lock:
                    self._deck_relation_map[(deck_id, card_id_str)] = str(relation_id)
                    self._evict_relation_map()

        # Parse main cards
        for card_entry in deck_data.get("cards", []):
            parse_card_entry(card_entry, board="main")

        # Parse sideboard
        for card_entry in deck_data.get("sideboard", []):
            parse_card_entry(card_entry, board="sideboard")

        # Parse commanders
        for card_entry in deck_data.get("commanders", []):
            parse_card_entry(card_entry, board="commander", default_quantity=1)

        # Create Deck object
        return Deck(
            id=deck_id,
            name=name,
            format=deck_format,
            owner_id=owner_id,
            owner=owner_username,
            description=description,
            created_at=created_at,
            updated_at=updated_at,
            privacy=privacy,
            source="archidekt",
            cards=cards,
            parent_folder_id=parent_folder_id,
        )

    def autocomplete(self, query: str, limit: int = 10) -> list[str]:
        """Autocomplete card names for Archidekt.

        This method provides autocomplete suggestions for card names.
        Currently returns an empty list as autocomplete is not yet implemented
        for Archidekt.

        Args:
            query: The partial card name to autocomplete.
            limit: Maximum number of suggestions to return (default 10).

        Returns:
            An empty list (not yet implemented).
        """
        # TODO: Implement autocomplete when Archidekt API endpoint is known
        logger.warning("Archidekt autocomplete not yet implemented")
        return []

    def iter_search(
        self,
        name: str | None = None,
        colors: list[Color] | None = None,
        identity: list[Color] | None = None,
        type_line: str | None = None,
        limit: int = 100,
        order: str | None = None,
    ) -> Iterator[Card]:
        """Iterate through all search results, yielding cards lazily.

        This method is a generator that pages through all search results and
        yields each :class:`Card` one at a time, so callers can stream large
        result sets without materializing the entire list in memory.

        Args:
            name: Card name or name fragment to search for.
            colors: List of colors the card must include in its color identity.
            identity: List of colors the card's color identity must exactly match.
            type_line: Type line the card must include.
            limit: Maximum number of results to return per page.
            order: Sort order for results.

        Yields:
            Card objects matching the search criteria, one at a time.

        Raises:
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
        """
        page = 1

        while True:
            # Search for one page of results
            cards = self.search(
                name=name,
                colors=colors,
                identity=identity,
                type_line=type_line,
                limit=limit,
                page=page,
                order=order,
            )

            if not cards:
                break

            yield from cards

            # Stop if this was the last (partial) page.
            if len(cards) < limit:
                break

            page += 1

    # =========================================================================
    # Card Metadata Methods
    # =========================================================================

    def get_editions(self) -> list[dict[str, Any]]:
        """Get list of all Magic: The Gathering editions/sets.

        This endpoint returns metadata about all available sets that can be used
        for filtering card searches.

        Returns:
            A list of edition objects, each containing:
                - editioncode (str): Short code for the set (e.g., "trc", "fra")
                - editionname (str): Full name of the set
                - editiondate (str): Release date in YYYY-MM-DD format
                - editiontype (str): Type of set (expansion, commander, promo, etc.)
                - mtgoCode (str or None): MTG Online code

        Raises:
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.

        Evidence from HAR file `/tmp/archidekt2.har`:
            - GET /api/cards/editions/
            - Status: 200
            - Response: JSON array of 1000+ edition objects
        """
        try:
            with self.rate_limiter.guard("archidekt"):
                # Public endpoint - no authentication required
                response = self.http_client.get("cards/editions/")
                data = self._handle_response(response, "editions")

                if not data:
                    return []

                # Ensure we have a list
                if isinstance(data, dict):
                    return [data]
                return list(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_editions: {e}")
            raise NetworkError(
                "Network error during get_editions",
                original_exception=e,
                provider=self.name,
            ) from e

    def get_subtypes(self) -> list[dict[str, Any]]:
        """Get list of all Magic: The Gathering card subtypes.

        This endpoint returns metadata about all available subtypes that can be used
        for filtering card searches.

        Returns:
            A list of subtype objects, each containing:
                - subtypename (str): The name of the subtype (e.g., "Angel", "Zombie")

        Raises:
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.

        Evidence from HAR file `/tmp/archidekt2.har`:
            - GET /api/cards/subtypes/
            - Status: 200
            - Response: JSON array of subtype objects
        """
        try:
            with self.rate_limiter.guard("archidekt"):
                # Public endpoint - no authentication required
                response = self.http_client.get("cards/subtypes/")
                data = self._handle_response(response, "subtypes")

                if not data:
                    return []

                # Ensure we have a list
                if isinstance(data, dict):
                    return [data]
                return list(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_subtypes: {e}")
            raise NetworkError(
                "Network error during get_subtypes",
                original_exception=e,
                provider=self.name,
            ) from e

    # =========================================================================
    # Deck Organization Methods
    # =========================================================================

    def get_folder(self, folder_id: str) -> dict[str, Any]:
        """Get contents of a deck folder.

        Retrieves metadata about a folder including its subfolders and decks.

        Args:
            folder_id: The ID of the folder to retrieve.

        Returns:
            A folder object containing:
                - id (int): Folder ID
                - name (str): Folder name
                - parentFolder (dict or None): Reference to parent folder
                - private (bool): Whether folder is private
                - owner (dict): Owner user information
                - subfolders (list): Nested folder objects
                - decks (list): Deck objects in this folder

        Raises:
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.

        Evidence from HAR file `/tmp/archidekt2.har`:
            - GET /api/decks/folders/1735877/
            - Status: 200
            - Response: JSON object with folder metadata and decks array
        """
        self._check_authentication()

        try:
            with self.rate_limiter.guard("archidekt"):
                response = self.http_client.get(f"decks/folders/{folder_id}/")
                data = self._handle_response(response, "folder")

                if not data:
                    return {}

                return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_folder: {e}")
            raise NetworkError(
                "Network error during get_folder",
                original_exception=e,
                provider=self.name,
            ) from e

    def get_tags(self, q: str | None = None) -> list[dict[str, Any]]:
        """Get list of all available deck tags.

        Retrieves metadata about all available tags that users can apply to their decks.

        Args:
            q: Optional search query to filter tags.

        Returns:
            A list of tag objects, each containing:
                - id (int): Tag ID
                - name (str): Tag name (e.g., "+1/+1 Counters", "Aggro")
                - aliases (str): Comma-separated alternative names
                - description (str): Tag description
                - created_at (str): Creation timestamp

        Raises:
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.

        Evidence from HAR file `/tmp/archidekt2.har`:
            - GET /api/decks/tags/v2/?q=
            - Status: 200
            - Response: JSON array of tag objects
        """
        self._check_authentication()

        try:
            with self.rate_limiter.guard("archidekt"):
                params = {}
                if q is not None:
                    params["q"] = q

                response = self.http_client.get("decks/tags/v2/", params=params)
                data = self._handle_response(response, "tags")

                if not data:
                    return []

                # Ensure we have a list
                if isinstance(data, dict):
                    return [data]
                return list(data)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_tags: {e}")
            raise NetworkError(
                "Network error during get_tags",
                original_exception=e,
                provider=self.name,
            ) from e

    def delete_folder_items(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Delete items from a deck folder.

        Removes decks or other items from a folder.

        Args:
            items: List of items to delete, each containing:
                - id (int): The item ID (typically a deck ID)
                - type (str): The type of item (e.g., "deck")

        Returns:
            A response object with status information.

        Raises:
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
            ArchidektValidationError: If items parameter is invalid.

        Evidence from HAR file `/tmp/archidekt2.har`:
            - POST /api/decks/folders/deleteItems/
            - Request: {"items": [{"id": 24299438, "type": "deck"}]}
            - Status: 200
            - Response: {"status": "success"}
        """
        self._check_authentication()

        if not items:
            raise ArchidektValidationError(
                "items parameter is required and must not be empty",
                provider=self.name,
            )

        try:
            with self.rate_limiter.guard("archidekt"):
                response = self.http_client.post(
                    "decks/folders/deleteItems/",
                    json={"items": items},
                )
                data = self._handle_response(response, "delete_folder_items")

                return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt delete_folder_items: {e}")
            raise NetworkError(
                "Network error during delete_folder_items",
                original_exception=e,
                provider=self.name,
            ) from e

    # =========================================================================
    # Social Features Methods
    # =========================================================================

    def get_comment(
        self, comment_id: str, page: int = 1, order_by: str | None = None
    ) -> dict[str, Any]:
        """Get a comment by its ID.

        Retrieves comment thread information including the comment, owner, and child comments.

        Args:
            comment_id: The ID of the comment to retrieve.
            page: Page number for pagination (default: 1).
            order_by: Sort order for results (e.g., "-points").

        Returns:
            A comment object containing:
                - id (int): Comment ID
                - title (str or None): Comment title
                - text (str or None): Comment text
                - owner (dict): User who owns the comment
                - deck (dict): Reference to the deck being commented on
                - parent (dict or None): Parent comment for threads
                - childrenCount (int): Number of child comments
                - children (dict): Paginated child comments with links, count, results
                - createdAt (str): Creation timestamp
                - editedAt (str or None): Last edit timestamp
                - points (int): Upvote count
                - userInput (int): User input indicator
                - archived (bool): Whether comment is archived
                - locked (bool): Whether comment is locked
                - featured (str or None): Featured status
                - type (int): Comment type

        Raises:
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.

        Evidence from HAR file `/tmp/archidekt2.har`:
            - GET /api/comments/23446857/?page=1&orderBy=-points
            - GET /api/comments/24354478/?page=1&orderBy=-points
            - Status: 200
            - Response: JSON object with comment details
        """
        self._check_authentication()

        try:
            with self.rate_limiter.guard("archidekt"):
                params: dict[str, Any] = {"page": page}
                if order_by:
                    params["orderBy"] = order_by

                response = self.http_client.get(
                    f"comments/{comment_id}/", params=params
                )
                data = self._handle_response(response, "comment")

                if not data:
                    return {}

                return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_comment: {e}")
            raise NetworkError(
                "Network error during get_comment",
                original_exception=e,
                provider=self.name,
            ) from e

    def get_notification_count(self, user_id: str | None = None) -> dict[str, Any]:
        """Get the unread notification count for a user.

        Args:
            user_id: The user ID. If None, uses the authenticated user.

        Returns:
            A notification count object containing:
                - notificationCount (int): Number of unread notifications
                - patreonAccount (dict or None): Patreon account information if applicable

        Raises:
            NetworkError: If there is a network error.
            ArchidektAPIError: If the API returns an error.
            ArchidektValidationError: If user_id is not provided and not authenticated.

        Evidence from HAR file `/tmp/archidekt2.har`:
            - GET /api/users/1071357/notificationCount/
            - Status: 200
            - Response: {"notificationCount": 0, "patreonAccount": null}
        """
        try:
            with self.rate_limiter.guard("archidekt"):
                # If no user_id provided, use the authenticated user's ID
                target_user_id = user_id
                if not target_user_id:
                    if not hasattr(self, "auth_handler") or self.auth_handler is None:
                        raise ArchidektValidationError(
                            "user_id is required or authentication must be provided",
                            provider=self.name,
                        )
                    target_user_id = self.auth_handler.user_id

                if not target_user_id:
                    raise ArchidektValidationError(
                        "user_id is required or authentication must be provided",
                        provider=self.name,
                    )

                response = self.http_client.get(
                    f"users/{target_user_id}/notificationCount/"
                )
                data = self._handle_response(response, "notification_count")

                if not data:
                    return {}

                return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Archidekt get_notification_count: {e}")
            raise NetworkError(
                "Network error during get_notification_count",
                original_exception=e,
                provider=self.name,
            ) from e

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickle serialization to exclude sensitive data.

        Returns:
            Dictionary of attributes to pickle, excluding sensitive data.
        """
        state = self.__dict__.copy()

        # Exclude sensitive data
        state["_username"] = None
        state["_password"] = None
        state["_deck_relation_map"] = {}  # Clear relation mapping
        state["har_logger"] = HARLogger(enabled=False)  # Reset HAR logger

        # Handle auth_handler pickle - store None as it contains sensitive tokens
        state["auth_handler"] = None  # Will need re-authentication

        # Exclude non-picklable objects (threading.Lock / RateLimiter)
        state.pop("_lock", None)
        state.pop("rate_limiter", None)

        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Custom unpickle deserialization.

        The ``auth_handler`` is reinitialized WITHOUT credentials or tokens
        for security (it was excluded from the pickle state by
        ``__getstate__``). The unpickled provider is therefore NOT
        authenticated; callers must call ``authenticate()`` before any
        authenticated operation. Any stale ``Authorization`` header on the
        HTTP client session is also cleared to avoid sending outdated
        credentials.

        Args:
            state: Dictionary of attributes from pickle.
        """
        self.__dict__.update(state)  # type: ignore[attr-defined]
        # Recreate non-picklable objects excluded by __getstate__
        self._lock = threading.Lock()
        self.rate_limiter = RateLimiter(
            {
                "archidekt": RateLimitConfig(
                    requests_per_minute=60,
                    burst_size=10,
                ),
            }
        )
        # Reinitialize auth_handler since it was excluded from pickle state
        self.auth_handler = JWTAuthHandler(
            base_url=self.base_url or "https://archidekt.com",
            login_endpoint="/rest-auth/login/",
            provider="archidekt",
        )
        # The HTTP client session headers are stale after unpickle; clear any
        # leftover Authorization header so requests do not send outdated tokens.
        if hasattr(self, "http_client") and self.http_client:
            self.http_client.session.headers.pop("Authorization", None)

    @staticmethod
    def _normalize_flavor_text(flavor_text: Any) -> str | None:
        """Normalize flavor text for Archidekt cards.

        Args:
            flavor_text: The flavor text to normalize. Can be a string, list of strings,
                list of other types (will be converted), or None. Other types return None.

        Returns:
            The normalized flavor text as a string, or None if empty or unsupported type.
        """
        if flavor_text is None:
            return None
        if isinstance(flavor_text, str):
            return flavor_text if flavor_text else None
        if isinstance(flavor_text, list):
            filtered = [str(f) for f in flavor_text if f]
            return " ".join(filtered) if filtered else None
        # For unsupported types (int, etc.), return None
        return None

    def __repr__(self) -> str:
        """Return a string representation of the Archidekt provider.

        Returns:
            String representation including provider name and authentication status.
        """
        return f"Archidekt(authenticated={self.is_authenticated()}, base_url={self.base_url})"


# Export the class for backward compatibility
ArchidektProvider = Archidekt
