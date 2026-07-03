"""Tests for the Cardmarket provider.

This module contains unit tests for the Cardmarket provider implementation,
including authentication, card retrieval, search, and error handling.

Note:
    These tests use mocked responses since Cardmarket API access requires
    pre-approved developer credentials.
"""

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
        """Test authenticate method with missing consumer key."""
        cardmarket = Cardmarket()

        with pytest.raises(AuthenticationError) as exc_info:
            cardmarket.authenticate(
                consumer_secret="test_consumer_secret",
                access_token="test_access_token",
                access_token_secret="test_access_token_secret",
            )

        assert "Consumer key and consumer secret are required" in str(exc_info.value)

    def test_authenticate_method_missing_consumer_secret(self):
        """Test authenticate method with missing consumer secret."""
        cardmarket = Cardmarket()

        with pytest.raises(AuthenticationError) as exc_info:
            cardmarket.authenticate(
                consumer_key="test_consumer_key",
                access_token="test_access_token",
                access_token_secret="test_access_token_secret",
            )

        assert "Consumer key and consumer secret are required" in str(exc_info.value)

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

    def test_search_success(self):
        """Test successful card search."""
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
        ):
            results = cardmarket.search(name="Black Lotus", limit=5)

            assert len(results) == 1
            assert results[0].name == "Black Lotus"
            assert results[0].set_name == "Limited Edition Alpha"
            assert results[0].set_code == "LEA"

    def test_search_empty_results(self):
        """Test search with empty results."""
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
            results = cardmarket.search(name="Non-existent Card")

            assert results == []

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


class TestCardmarketGetCard:
    """Tests for Cardmarket get_card functionality."""

    def test_get_card_success(self):
        """Test successful card retrieval by ID."""
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

    def test_search_syntax_success(self):
        """Test successful syntax search."""
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
        ):
            results = cardmarket.search_syntax(query="name:Black Lotus", limit=5)

            assert len(results) == 1

    def test_search_syntax_without_authentication(self):
        """Test search_syntax without authentication raises AuthenticationError."""
        cardmarket = Cardmarket()

        with pytest.raises(AuthenticationError):
            cardmarket.search_syntax(query="name:Black Lotus")


class TestCardmarketPricing:
    """Tests for Cardmarket pricing functionality."""

    def test_get_pricing_success(self):
        """Test successful pricing retrieval."""
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
                    "conditionName": "Good",
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

        # After close, authentication should still be valid
        # (credentials are cleared from auth_handler, but the provider still has them)
        assert cardmarket.auth_handler.consumer_key is None


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
        """Test OAuth1Handler authenticate with missing credentials."""
        handler = OAuth1Handler()

        with pytest.raises(AuthenticationError):
            handler.authenticate(
                access_token="test_access_token",
                access_token_secret="test_access_token_secret",
            )

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
