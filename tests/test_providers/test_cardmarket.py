"""Tests for the Cardmarket provider.

This module contains unit tests for the Cardmarket provider implementation,
including authentication, card retrieval, search, and error handling.

Note:
    These tests use mocked responses since Cardmarket API access requires
    pre-approved developer credentials.
"""

from datetime import date

import pytest
from unittest.mock import MagicMock, patch

import requests

from pymtg.auth.oauth1 import OAuth1Handler
from pymtg.exceptions import (
    AuthenticationError,
    InvalidQueryError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from pymtg.models.enums import Color, Rarity
from pymtg.models.pricing import Pricing
from pymtg.providers.cardmarket import Cardmarket


def _make_mock_search_response(product_name: str = "Test") -> dict:
    """Build a Cardmarket-style search response payload for tests.

    The payload mirrors the shape returned by the Cardmarket search
    endpoint. Centralizing it avoids copy-paste drift across the several
    search-game tests that exercise the same response structure.

    Args:
        product_name: The product/card name to embed in the response.

    Returns:
        A dict mimicking a Cardmarket search API response.
    """
    return {
        "results": [
            {
                "idProduct": 12345,
                "productName": product_name,
                "cardName": product_name,
                "idLanguage": 1,
                "idSet": 1,
                "idGame": 1,
                "idRarity": 1,
                "idCardType": 1,
                "idSubType": 1,
                "idColor": 1,
                "idFormat": 1,
                "idSetType": 1,
                "idSetFormat": 1,
                "idCardFace": 1,
                "idLayout": 1,
                "idCardLayout": 1,
                "idCardFaceType": 1,
                "idCardFaceLayout": 1,
                "idCardFaceLayoutType": 1,
                "idCardFaceLayoutSubType": 1,
                "idCardFaceLayoutSubTypeType": 1,
                "idCardFaceLayoutSubTypeSubType": 1,
            }
        ],
        "numberOfResults": 1,
        "currentPage": 1,
        "currentPageResult": 1,
        "nPages": 1,
        "actionsWarning": [],
    }


class TestCardmarketInitialization:
    """Tests for Cardmarket provider initialization."""

    def test_initialization_with_all_credentials(self):
        """Test Cardmarket initialization with all OAuth1 credentials."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        assert cardmarket.name == "cardmarket"
        assert cardmarket.is_authenticated()
        assert cardmarket.base_url == "https://apiv2.cardmarket.com"

    def test_initialization_without_credentials(self):
        """Test Cardmarket initialization without credentials."""
        cardmarket = Cardmarket()

        assert cardmarket.name == "cardmarket"
        assert not cardmarket.is_authenticated()

    def test_initialization_with_partial_credentials(self):
        """Test Cardmarket initialization with partial credentials."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
        )

        assert cardmarket.name == "cardmarket"
        # Without access token/secret, not authenticated
        assert not cardmarket.is_authenticated()


class TestCardmarketAuthentication:
    """Tests for Cardmarket authentication."""

    def test_authenticate_method(self):
        """Test the authenticate method with valid credentials."""
        cardmarket = Cardmarket()

        cardmarket.authenticate(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        assert cardmarket.is_authenticated()

    def test_authenticate_method_missing_consumer_key(self):
        """Test authenticate method with missing consumer key.

        Providing consumer_secret without consumer_key is a partial pair
        update, which is rejected before any credentials are modified.
        """
        cardmarket = Cardmarket()

        with pytest.raises(AuthenticationError) as exc_info:
            cardmarket.authenticate(
                consumer_secret="test_consumer_secret",
                access_token="test_access_token",
                access_token_secret="test_access_token_secret",
            )

        assert "must be provided together" in str(exc_info.value)

    def test_authenticate_method_missing_consumer_secret(self):
        """Test authenticate method with missing consumer secret.

        Providing consumer_key without consumer_secret is a partial pair
        update, which is rejected before any credentials are modified.
        """
        cardmarket = Cardmarket()

        with pytest.raises(AuthenticationError) as exc_info:
            cardmarket.authenticate(
                consumer_key="test_consumer_key",
                access_token="test_access_token",
                access_token_secret="test_access_token_secret",
            )

        assert "must be provided together" in str(exc_info.value)

    def test_refresh_auth_raises_error(self):
        """Test that refresh_auth raises AuthenticationError for OAuth1."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            cardmarket.refresh_auth()

        assert "OAuth1 does not support automatic token refresh" in str(exc_info.value)

    def test_authenticate_method_missing_consumer_credentials(self):
        """Test authenticate with only access tokens, no consumer credentials.

        When authenticate() is called with the access token pair but no
        consumer pair on a fresh Cardmarket (no stored consumer credentials),
        pair validation passes (both consumer args are None) but the
        'required' check raises. Verifies the full error message matches
        the implementation.
        """
        cardmarket = Cardmarket()

        with pytest.raises(AuthenticationError) as exc_info:
            cardmarket.authenticate(
                access_token="test_access_token",
                access_token_secret="test_access_token_secret",
            )

        assert "Consumer key and consumer secret are required" in str(exc_info.value)
        assert "OAuth1 authentication" in str(exc_info.value)

    def test_is_authenticated_with_valid_credentials(self):
        """Test is_authenticated returns True with valid credentials."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        assert cardmarket.is_authenticated()

    def test_is_authenticated_without_access_token(self):
        """Test is_authenticated returns False without access token."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
        )

        assert not cardmarket.is_authenticated()


class TestCardmarketSearch:
    """Tests for Cardmarket search functionality."""

    def test_search_returns_results(self):
        """Tests that search returns results for a query.

        This test verifies that the correct endpoint and query parameters are
        passed to the HTTP client, including the search term, game filter,
        and limit.
        """
        # Mock response data
        mock_response_data = {
            "results": [
                {
                    "idProduct": 12345,
                    "name": "Black Lotus",
                    "expansion": "Limited Edition Alpha",
                    "expansionCode": "LEA",
                    "rarity": "Mythic Rare",
                    "type": "Instant",
                    "manaCost": "{0}",
                    "color": "",
                    "colorIdentity": "",
                    "text": "Add {B}{B}{B}{B}.",
                    "artist": "Christopher Rush",
                    "number": "232",
                    "releaseDate": "1993-08-05",
                }
            ]
        }

        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: mock_response_data),
        ) as mock_get:
            results = cardmarket.search(name="Black Lotus", limit=5)

        assert len(results) == 1
        assert results[0].name == "Black Lotus"
        assert results[0].set_name == "Limited Edition Alpha"
        assert results[0].set_code == "LEA"
        # Verify HTTP client was called with correct URL and params
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "/ws/v2.0/products/output.json/"
        assert call_args[1]["params"] == {
            "search": "Black Lotus",
            "game": "Magic",
            "limit": 5,
        }

    def test_search_empty_results(self):
        """Tests search with empty results.

        This test verifies that the correct endpoint and query parameters are
        passed to the HTTP client even when no results are returned.
        """
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: {"results": []}),
        ) as mock_get:
            results = cardmarket.search(name="Non-existent Card")

        assert results == []
        # Verify HTTP client was called with correct URL and params
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "/ws/v2.0/products/output.json/"
        assert call_args[1]["params"] == {
            "search": "Non-existent Card",
            "game": "Magic",
            "limit": 20,
        }

    def test_search_without_authentication(self):
        """Test search without authentication raises AuthenticationError."""
        cardmarket = Cardmarket()

        with pytest.raises(AuthenticationError) as exc_info:
            cardmarket.search(name="Black Lotus")

        assert "Authentication required" in str(exc_info.value)

    def test_search_network_error(self):
        """Test search with network error."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with patch.object(
            cardmarket.http_client,
            "get",
            side_effect=requests.exceptions.RequestException("Connection error"),
        ):
            with pytest.raises(NetworkError) as exc_info:
                cardmarket.search(name="Black Lotus")

            assert "Network error" in str(exc_info.value)
            # The original RequestException should be chained as __cause__
            # so the underlying traceback is preserved.
            assert exc_info.value.__cause__ is not None

    def test_search_negative_limit_raises(self):
        """Test search with limit <= 0 raises InvalidQueryError.

        Verifies that limit values of 0 and -1 are rejected before any
        API request is made.
        """
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        for invalid_limit in (0, -1):
            with pytest.raises(InvalidQueryError) as exc_info:
                cardmarket.search(name="Black Lotus", limit=invalid_limit)

            assert "limit must be a positive integer (>= 1)" in str(exc_info.value)

    def test_search_negative_page_raises(self):
        """Test search with page <= 0 raises InvalidQueryError.

        Verifies that page values of 0 and -1 are rejected before any
        API request is made.
        """
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        for invalid_page in (0, -1):
            with pytest.raises(InvalidQueryError) as exc_info:
                cardmarket.search(name="Black Lotus", page=invalid_page)

            assert "page must be a positive integer (>= 1)" in str(exc_info.value)

    def test_search_game_defaults_to_magic(self):
        """Test search defaults game to Magic when not provided."""
        mock_response_data = _make_mock_search_response("Black Lotus")
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )
        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: mock_response_data),
        ) as mock_get:
            cardmarket.search(name="Black Lotus")
            call_args = mock_get.call_args
            assert call_args[1]["params"]["game"] == "Magic"

    def test_search_game_uses_provided_value(self):
        """Test search uses provided game value."""
        mock_response_data = _make_mock_search_response("Test")
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )
        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: mock_response_data),
        ) as mock_get:
            cardmarket.search(name="Test", game="StarCityGames")
            call_args = mock_get.call_args
            assert call_args[1]["params"]["game"] == "StarCityGames"

    def test_search_game_invalid_defaults_to_magic_with_warning(self, caplog):
        """Test search defaults game to Magic when invalid with warning."""
        mock_response_data = _make_mock_search_response("Test")
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )
        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: mock_response_data),
        ) as mock_get:
            cardmarket.search(name="Test", game="")
            call_args = mock_get.call_args
            assert call_args[1]["params"]["game"] == "Magic"
            assert any(
                "Invalid or missing game parameter" in record.message
                for record in caplog.records
            )

    def test_search_game_empty_string_defaults_to_magic(self):
        """Test search defaults game to Magic when empty string."""
        mock_response_data = _make_mock_search_response("Test")
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )
        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: mock_response_data),
        ) as mock_get:
            cardmarket.search(name="Test", game="")
            call_args = mock_get.call_args
            assert call_args[1]["params"]["game"] == "Magic"


class TestCardmarketGetCard:
    """Tests for Cardmarket get_card functionality."""

    def test_get_card_returns_card(self):
        """Tests that get_card returns a card by ID."""
        mock_response_data = {
            "results": [
                {
                    "idProduct": 12345,
                    "name": "Black Lotus",
                    "expansion": "Limited Edition Alpha",
                    "expansionCode": "LEA",
                    "rarity": "Mythic Rare",
                    "type": "Instant",
                    "manaCost": "{0}",
                    "text": "Add {B}{B}{B}{B}.",
                    "artist": "Christopher Rush",
                    "number": "232",
                }
            ]
        }

        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: mock_response_data),
        ):
            card = cardmarket.get_card(card_id="12345")

            assert card.id == "12345"
            assert card.name == "Black Lotus"

    def test_get_card_not_found(self):
        """Test get_card with card not found."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: {"results": []}),
        ):
            with pytest.raises(NotFoundError) as exc_info:
                cardmarket.get_card(card_id="99999")

            assert "Card with ID 99999 not found" in str(exc_info.value)

    def test_get_card_without_authentication(self):
        """Test get_card without authentication raises AuthenticationError."""
        cardmarket = Cardmarket()

        with pytest.raises(AuthenticationError):
            cardmarket.get_card(card_id="12345")


class TestCardmarketSearchSyntax:
    """Tests for Cardmarket search_syntax functionality."""

    def test_search_syntax_returns_results(self):
        """Tests that search_syntax returns results for a query.

        This test verifies that the correct endpoint and query parameters are
        passed to the HTTP client, including the raw query string and limit.
        """
        mock_response_data = {
            "results": [
                {
                    "idProduct": 12345,
                    "name": "Black Lotus",
                    "expansion": "Limited Edition Alpha",
                }
            ]
        }

        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: mock_response_data),
        ) as mock_get:
            results = cardmarket.search_syntax(query="name:Black Lotus", limit=5)

        assert len(results) == 1
        # Verify HTTP client was called with correct URL and params
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[0][0] == "/ws/v2.0/products/output.json/"
        assert call_args[1]["params"] == {
            "search": "name:Black Lotus",
            "limit": 5,
        }

    def test_search_syntax_without_authentication(self):
        """Test search_syntax without authentication raises AuthenticationError."""
        cardmarket = Cardmarket()

        with pytest.raises(AuthenticationError):
            cardmarket.search_syntax(query="name:Black Lotus")


class TestCardmarketPricing:
    """Tests for Cardmarket pricing functionality."""

    def test_get_pricing_returns_pricing(self):
        """Tests that get_pricing returns pricing for a product ID."""
        mock_response_data = {
            "results": [
                {
                    "skuId": 67890,
                    "price": 123.45,
                    "conditionId": 1,
                    "conditionName": "Near Mint",
                },
                {
                    "skuId": 67891,
                    "price": 99.99,
                    "conditionId": 2,
                    "conditionName": "Excellent",
                },
            ]
        }

        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: mock_response_data),
        ):
            pricing = cardmarket.get_pricing(product_id=12345)

            assert isinstance(pricing, Pricing)
            assert pricing.cardmarket is not None
            # Verify the mock prices were actually parsed into the correct
            # condition-mapped fields (Near Mint -> avg1, Excellent -> low_ex).
            assert pricing.cardmarket.avg1 == 123.45
            assert pricing.cardmarket.low_ex == 99.99

    def test_get_pricing_invalid_product_id(self):
        """Test get_pricing with invalid product ID."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with pytest.raises(InvalidQueryError) as exc_info:
            cardmarket.get_pricing(product_id="invalid-id")

        assert "Invalid product_id" in str(exc_info.value)

    def test_get_pricing_not_found(self):
        """Test get_pricing with product not found."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=MagicMock(status_code=200, json=lambda: {}),
        ):
            with pytest.raises(NotFoundError) as exc_info:
                cardmarket.get_pricing(product_id=99999)

            assert "Pricing for product ID 99999 not found" in str(exc_info.value)


class TestCardmarketErrorHandling:
    """Tests for Cardmarket error handling."""

    def test_handle_http_error_404(self):
        """Test handling of 404 Not Found error."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {}

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=mock_response,
        ):
            with pytest.raises(NotFoundError) as exc_info:
                cardmarket.get_card(card_id="99999")

            assert exc_info.value.status_code == 404

    def test_handle_http_error_401(self):
        """Test handling of 401 Unauthorized error."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {}

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=mock_response,
        ):
            with pytest.raises(AuthenticationError) as exc_info:
                cardmarket.get_card(card_id="12345")

            assert exc_info.value.auth_type == "oauth1"

    def test_handle_http_error_403(self):
        """Test handling of 403 Forbidden error."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {}

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=mock_response,
        ):
            with pytest.raises(AuthenticationError) as exc_info:
                cardmarket.get_card(card_id="12345")

            assert exc_info.value.auth_type == "oauth1"

    def test_handle_http_error_429(self):
        """Test handling of 429 Rate Limit Exceeded error."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {}

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=mock_response,
        ):
            with pytest.raises(RateLimitError) as exc_info:
                cardmarket.get_card(card_id="12345")

            assert exc_info.value.retry_after == 60

    def test_handle_http_error_400(self):
        """Test handling of 400 Bad Request error."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {}

        with patch.object(
            cardmarket.http_client,
            "get",
            return_value=mock_response,
        ):
            with pytest.raises(InvalidQueryError) as exc_info:
                cardmarket.get_card(card_id="invalid")

            assert exc_info.value.status_code == 400


class TestCardmarketRateLimit:
    """Tests for Cardmarket rate limiting."""

    def test_get_rate_limit_status(self):
        """Test rate limit status retrieval."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        status = cardmarket.get_rate_limit_status()

        assert status["provider"] == "cardmarket"
        assert status["authenticated"] is True
        assert "provider_specific" in status


class TestCardmarketClose:
    """Tests for Cardmarket close functionality."""

    def test_close_method(self):
        """Test the close method."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        # Close should not raise any errors
        cardmarket.close()

        # After close, all credentials are cleared from auth_handler
        assert cardmarket.auth_handler.consumer_key is None
        assert cardmarket.auth_handler.consumer_secret is None
        assert cardmarket.auth_handler.access_token is None
        assert cardmarket.auth_handler.access_token_secret is None


class TestCardmarketRepr:
    """Tests for Cardmarket string representation."""

    def test_repr_authenticated(self):
        """Test repr with authenticated provider."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        repr_str = repr(cardmarket)

        assert "Cardmarket" in repr_str
        assert "authenticated" in repr_str

    def test_repr_not_authenticated(self):
        """Test repr with non-authenticated provider."""
        cardmarket = Cardmarket()

        repr_str = repr(cardmarket)

        assert "Cardmarket" in repr_str
        assert "not authenticated" in repr_str


class TestCardmarketParseCard:
    """Tests for Cardmarket card parsing."""

    def test_parse_card_basic(self):
        """Test basic card parsing."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        card_data = {
            "idProduct": 12345,
            "name": "Test Card",
            "expansion": "Test Set",
            "expansionCode": "TST",
            "rarity": "Common",
            "type": "Creature",
            "manaCost": "{1}{W}",
            "color": "W",
            "power": "1",
            "toughness": "1",
        }

        card = cardmarket._parse_card(card_data)

        assert card.id == "12345"
        assert card.name == "Test Card"
        assert card.set_name == "Test Set"
        assert card.set_code == "TST"
        assert card.rarity == Rarity.COMMON
        assert card.type_line == "Creature"
        assert card.mana_cost == "{1}{W}"
        assert card.colors is not None and Color("W") in card.colors
        assert card.power == "1"
        assert card.toughness == "1"

    def test_parse_card_with_color_identity(self):
        """Test card parsing with color identity."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        card_data = {
            "idProduct": 12345,
            "name": "Test Card",
            "color": "WU",
            "colorIdentity": "WU",
        }

        card = cardmarket._parse_card(card_data)

        assert card.colors is not None and Color("W") in card.colors
        assert card.colors is not None and Color("U") in card.colors
        assert card.color_identity is not None and Color("W") in card.color_identity
        assert card.color_identity is not None and Color("U") in card.color_identity

    def test_parse_card_minimal(self):
        """Test minimal card parsing with required fields only."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        card_data = {"idProduct": 12345, "name": "Minimal Card"}

        card = cardmarket._parse_card(card_data)

        assert card.id == "12345"
        assert card.name == "Minimal Card"
        assert card.source == "cardmarket"

    def test_parse_pricing_basic(self):
        """Test basic pricing parsing."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        pricing_data = {
            "results": [
                {
                    "price": 10.50,
                    "conditionName": "Near Mint",
                },
                {
                    "price": 8.50,
                    "conditionName": "Good",
                },
            ]
        }

        pricing = cardmarket._parse_pricing(pricing_data)

        assert isinstance(pricing, Pricing)
        assert pricing.cardmarket is not None

    def test_parse_pricing_negative_price_skipped(self):
        """Test that negative prices are skipped in pricing parsing."""
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        pricing_data = {
            "results": [
                {
                    "price": -5.0,
                    "conditionName": "Near Mint",
                },
                {
                    "price": 10.50,
                    "conditionName": "Near Mint",
                },
            ]
        }

        pricing = cardmarket._parse_pricing(pricing_data)

        assert isinstance(pricing, Pricing)
        assert pricing.cardmarket is not None
        # Negative price should be skipped, only valid price used
        assert pricing.cardmarket.avg1 == 10.50

    def test_parse_pricing_unmapped_condition_warning(self, caplog):
        """Test that unmapped conditions log a warning."""
        import logging

        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        pricing_data = {
            "results": [
                {
                    "price": 10.50,
                    "condition": "damaged",
                    "conditionName": "Damaged",
                },
            ]
        }

        with caplog.at_level(logging.WARNING, logger="pymtg.providers.cardmarket"):
            pricing = cardmarket._parse_pricing(pricing_data)

        assert isinstance(pricing, Pricing)
        assert "Unmapped condition 'damaged'" in caplog.text

    @pytest.mark.parametrize(
        ("rarity_str", "expected_rarity"),
        [
            ("Common", Rarity.COMMON),
            ("Uncommon", Rarity.UNCOMMON),
            ("Rare", Rarity.RARE),
            ("Mythic Rare", Rarity.MYTHIC),
            ("Mythic", Rarity.MYTHIC),
            ("Special", Rarity.SPECIAL),
            ("Bonus", Rarity.BONUS),
            ("common", Rarity.COMMON),
            ("uncommon", Rarity.UNCOMMON),
            ("rare", Rarity.RARE),
            ("mythic", Rarity.MYTHIC),
            ("mythic rare", Rarity.MYTHIC),
            ("special", Rarity.SPECIAL),
            ("bonus", Rarity.BONUS),
        ],
    )
    def test_parse_card_rarity_mapping(self, rarity_str, expected_rarity):
        """Test that all Cardmarket rarity strings map to the correct enum.

        Cardmarket's rarity_map covers 14 entries: 7 rarity names in both
        Title Case and lowercase. This parametrized test exercises every
        entry to ensure parsing edge cases are covered.
        """
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        card_data = {
            "idProduct": 12345,
            "name": "Test Card",
            "rarity": rarity_str,
        }

        card = cardmarket._parse_card(card_data)

        assert card.rarity == expected_rarity

    def test_parse_card_unknown_rarity_defaults_to_common(self):
        """Test that an unrecognized rarity string defaults to COMMON.

        The rarity_map uses .get() with Rarity.COMMON as the default, so
        any value not in the map (e.g. a newly introduced rarity) should
        fall back to COMMON rather than raising.
        """
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        card_data = {
            "idProduct": 12345,
            "name": "Test Card",
            "rarity": "Totally Unknown Rarity",
        }

        card = cardmarket._parse_card(card_data)

        assert card.rarity == Rarity.COMMON

    def test_parse_card_missing_rarity_defaults_to_common(self):
        """Test that a missing rarity field defaults to COMMON.

        The rarity lookup uses card_data.get("rarity", ...) which returns
        an empty string when the key is absent; the empty string is not in
        rarity_map, so the default COMMON is used.
        """
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        card_data = {
            "idProduct": 12345,
            "name": "Test Card",
        }

        card = cardmarket._parse_card(card_data)

        assert card.rarity == Rarity.COMMON

    def test_parse_card_empty_rarity_defaults_to_common(self):
        """Test that an empty rarity string defaults to COMMON.

        An empty string is not a key in rarity_map, so the .get() default
        of Rarity.COMMON applies.
        """
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        card_data = {
            "idProduct": 12345,
            "name": "Test Card",
            "rarity": "",
        }

        card = cardmarket._parse_card(card_data)

        assert card.rarity == Rarity.COMMON

    def test_parse_card_rarity_name_fallback(self):
        """Test that rarityName is used when rarity is absent.

        Cardmarket responses may use either 'rarity' or 'rarityName' for
        the rarity field. The parser falls back to rarityName when rarity
        is missing.
        """
        cardmarket = Cardmarket(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        card_data = {
            "idProduct": 12345,
            "name": "Test Card",
            "rarityName": "Rare",
        }

        card = cardmarket._parse_card(card_data)

        assert card.rarity == Rarity.RARE


class TestOAuth1Handler:
    """Tests for the OAuth1Handler used by Cardmarket."""

    def test_oauth1_handler_initialization(self):
        """Test OAuth1Handler initialization."""
        handler = OAuth1Handler(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        assert handler.consumer_key == "test_consumer_key"
        assert handler.consumer_secret == "test_consumer_secret"
        assert handler.access_token == "test_access_token"
        assert handler.access_token_secret == "test_access_token_secret"

    def test_oauth1_handler_init_all_credentials_authenticated(self):
        """Test that init with all 4 credentials sets _authenticated True."""
        handler = OAuth1Handler(
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_token_secret="ats",
        )
        assert handler.is_authenticated()

    def test_oauth1_handler_init_access_tokens_only_not_authenticated(self):
        """Test that init with only access tokens does not authenticate.

        Previously __init__ set _authenticated=True based only on access_token
        and access_token_secret, but is_authenticated() checks all 4 credentials.
        This verifies the inconsistency is fixed.
        """
        handler = OAuth1Handler(
            access_token="at",
            access_token_secret="ats",
        )
        assert not handler.is_authenticated()

    def test_oauth1_handler_init_consumer_credentials_only_not_authenticated(self):
        """Test that init with only consumer credentials does not authenticate."""
        handler = OAuth1Handler(
            consumer_key="ck",
            consumer_secret="cs",
        )
        assert not handler.is_authenticated()

    def test_oauth1_handler_init_no_credentials_not_authenticated(self):
        """Test that init with no credentials does not authenticate."""
        handler = OAuth1Handler()
        assert not handler.is_authenticated()

    def test_oauth1_handler_init_partial_credentials_not_authenticated(self):
        """Test that init with partial credentials does not authenticate."""
        handler = OAuth1Handler(
            consumer_key="ck",
            access_token="at",
        )
        assert not handler.is_authenticated()

    def test_oauth1_handler_authenticate(self):
        """Test OAuth1Handler authenticate method."""
        handler = OAuth1Handler(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
        )

        handler.authenticate(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        assert handler.is_authenticated()

    def test_oauth1_handler_authenticate_missing_credentials(self):
        """Test OAuth1Handler authenticate with missing credentials.

        Providing the access token pair without the consumer pair passes
        pair validation (both consumer args are None), but the subsequent
        'required' check raises because no consumer credentials are stored.
        Verifies the full error message matches the implementation.
        """
        handler = OAuth1Handler()

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(
                access_token="test_access_token",
                access_token_secret="test_access_token_secret",
            )

        assert "Consumer key and consumer secret are required" in str(exc_info.value)
        assert "OAuth1 authentication" in str(exc_info.value)

    def test_oauth1_handler_authenticate_partial_consumer_pair_rejected(self):
        """Test that providing consumer_key without consumer_secret fails.

        Partial credential pair updates create inconsistent state where a
        new consumer_key is paired with an old consumer_secret. This is
        rejected before any credentials are modified.
        """
        handler = OAuth1Handler(
            consumer_key="old_key",
            consumer_secret="old_secret",
            access_token="at",
            access_token_secret="ats",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(consumer_key="new_key")

        assert "must be provided together" in str(exc_info.value)
        # Verify no credentials were modified
        assert handler.consumer_key == "old_key"
        assert handler.consumer_secret == "old_secret"

    def test_oauth1_handler_authenticate_partial_consumer_secret_rejected(self):
        """Test that providing consumer_secret without consumer_key fails."""
        handler = OAuth1Handler(
            consumer_key="old_key",
            consumer_secret="old_secret",
            access_token="at",
            access_token_secret="ats",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(consumer_secret="new_secret")

        assert "must be provided together" in str(exc_info.value)
        assert handler.consumer_key == "old_key"
        assert handler.consumer_secret == "old_secret"

    def test_oauth1_handler_authenticate_partial_access_token_rejected(self):
        """Test that providing access_token without secret fails.

        Partial credential pair updates create inconsistent state where a
        new access_token is paired with an old access_token_secret.
        """
        handler = OAuth1Handler(
            consumer_key="ck",
            consumer_secret="cs",
            access_token="old_token",
            access_token_secret="old_secret",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(access_token="new_token")

        assert "must be provided together" in str(exc_info.value)
        assert handler.access_token == "old_token"
        assert handler.access_token_secret == "old_secret"

    def test_oauth1_handler_authenticate_partial_access_secret_rejected(self):
        """Test that providing access_token_secret without token fails."""
        handler = OAuth1Handler(
            consumer_key="ck",
            consumer_secret="cs",
            access_token="old_token",
            access_token_secret="old_secret",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(access_token_secret="new_secret")

        assert "must be provided together" in str(exc_info.value)
        assert handler.access_token == "old_token"
        assert handler.access_token_secret == "old_secret"

    def test_oauth1_handler_authenticate_no_pairs_keeps_existing(self):
        """Test that providing no new credentials keeps existing values.

        When neither consumer nor access credential pairs are provided
        (both None), the existing stored credentials are retained. This
        is the valid 'neither' case for pair validation.
        """
        handler = OAuth1Handler(
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_token_secret="ats",
        )

        handler.authenticate()

        assert handler.consumer_key == "ck"
        assert handler.consumer_secret == "cs"
        assert handler.access_token == "at"
        assert handler.access_token_secret == "ats"
        assert handler.is_authenticated()

    def test_oauth1_handler_authenticate_empty_string_pair_passes_validation(self):
        """Test that empty strings pass pair validation and overwrite stored.

        Pair validation uses `is not None` checks, so empty strings count
        as 'provided' and pass the pair check. With explicit None-based
        updates (rather than truthiness via `or`), an empty string is
        treated as a deliberate value and overwrites the previously stored
        credential. Passing all-empty strings therefore clears every
        credential, and the subsequent required-credential check raises
        AuthenticationError because empty consumer_key/secret are falsy.
        """
        handler = OAuth1Handler(
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_token_secret="ats",
        )

        with pytest.raises(AuthenticationError) as exc_info:
            handler.authenticate(
                consumer_key="",
                consumer_secret="",
                access_token="",
                access_token_secret="",
            )

        assert "Consumer key and consumer secret are required" in str(exc_info.value)
        # Empty strings are stored verbatim (not retained from before).
        assert handler.consumer_key == ""
        assert handler.consumer_secret == ""
        assert handler.access_token == ""
        assert handler.access_token_secret == ""
        assert not handler.is_authenticated()

    def test_oauth1_handler_is_authenticated(self):
        """Test OAuth1Handler is_authenticated method."""
        handler = OAuth1Handler(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        assert handler.is_authenticated()

    def test_oauth1_handler_clear_auth(self):
        """Test OAuth1Handler clear_auth method."""
        handler = OAuth1Handler(
            consumer_key="test_consumer_key",
            consumer_secret="test_consumer_secret",
            access_token="test_access_token",
            access_token_secret="test_access_token_secret",
        )

        handler.clear_auth()

        assert handler.consumer_key is None
        assert handler.consumer_secret is None
        assert handler.access_token is None
        assert handler.access_token_secret is None
        assert not handler.is_authenticated()


class TestCardmarketRateLimiting:
    """Tests for Cardmarket rate limit tracking."""

    def test_rate_limit_initialization(self):
        """Test that rate limit attributes are initialized correctly."""
        cardmarket = Cardmarket()

        assert cardmarket._request_count == 0
        assert cardmarket._rate_limit == 30000

    def test_check_and_record_increments_counter(self):
        """Test that _check_and_record_request increments the counter.

        Verifies that calling _check_and_record_request increments the
        request count by one when below the rate limit.
        """
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 100
        cardmarket._rate_limit_reset_day = date.today()
        cardmarket._request_count = 0

        cardmarket._check_and_record_request()
        assert cardmarket._request_count == 1

        cardmarket._check_and_record_request()
        assert cardmarket._request_count == 2

    def test_check_and_record_raises_when_exceeded(self):
        """Test that _check_and_record_request raises at the limit.

        Verifies that calling _check_and_record_request raises
        RateLimitError when the request count equals the rate limit.
        """
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 2
        cardmarket._rate_limit_reset_day = date.today()
        cardmarket._request_count = 2

        with pytest.raises(RateLimitError):
            cardmarket._check_and_record_request()

    def test_check_and_record_passes_when_below_limit(self):
        """Test that _check_and_record_request passes when below limit.

        Verifies that no exception is raised and the counter is
        incremented when the request count is well below the limit.
        """
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 100
        cardmarket._rate_limit_reset_day = date.today()
        cardmarket._request_count = 50

        cardmarket._check_and_record_request()
        assert cardmarket._request_count == 51

    def test_check_and_record_passes_one_below_limit(self):
        """Test that _check_and_record_request passes one below limit.

        Verifies that the method succeeds (and increments) when the
        count is exactly one below the rate limit.
        """
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 100
        cardmarket._rate_limit_reset_day = date.today()
        cardmarket._request_count = 99

        cardmarket._check_and_record_request()
        assert cardmarket._request_count == 100

    def test_check_and_record_raises_at_limit(self):
        """Test that _check_and_record_request raises when count >= limit.

        Verifies that the method raises RateLimitError with a
        descriptive message when the request count equals the limit.
        """
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 100
        cardmarket._rate_limit_reset_day = date.today()
        cardmarket._request_count = 100

        with pytest.raises(RateLimitError) as exc_info:
            cardmarket._check_and_record_request()

        assert "rate limit exceeded" in str(exc_info.value).lower()

    def test_check_and_record_raises_on_fourth_request(self):
        """Test that _check_and_record_request raises after N requests.

        Verifies that repeatedly calling the method eventually raises
        when the rate limit is reached.
        """
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 3

        # First 3 requests should succeed (daily reset sets count to 0,
        # then increments to 1, 2, 3).
        cardmarket._check_and_record_request()
        cardmarket._check_and_record_request()
        cardmarket._check_and_record_request()

        # Fourth request should raise (count == 3 >= limit == 3)
        with pytest.raises(RateLimitError):
            cardmarket._check_and_record_request()

    def test_check_and_record_zero_limit(self):
        """Test that _check_and_record_request raises when limit is 0.

        Verifies that the method raises immediately when the rate
        limit is set to 0 (no requests allowed).
        """
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 0
        cardmarket._rate_limit_reset_day = date.today()

        with pytest.raises(RateLimitError):
            cardmarket._check_and_record_request()

    def test_check_and_record_resets_on_new_day(self):
        """Test that _check_and_record_request resets counter on new day.

        Verifies that when the calendar day changes, the request
        counter is reset to 0 before checking and incrementing.
        """
        from datetime import timedelta

        cardmarket = Cardmarket()
        cardmarket._rate_limit = 2
        # Simulate a previous day's counting window
        yesterday = date.today() - timedelta(days=1)
        cardmarket._rate_limit_reset_day = yesterday
        cardmarket._request_count = 2  # Hit limit yesterday

        # Today is a new day — should reset and succeed
        cardmarket._check_and_record_request()
        assert cardmarket._request_count == 1
        assert cardmarket._rate_limit_reset_day == date.today()
