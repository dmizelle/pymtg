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
        """Test that empty strings pass pair validation but keep existing.

        Pair validation uses `is not None` checks, so empty strings count
        as 'provided' and pass the pair check. However, the credential
        update uses truthiness (`or`), so empty strings are treated as
        falsy and the existing stored value is retained. This documents
        the pre-existing `or`-based update behavior.
        """
        handler = OAuth1Handler(
            consumer_key="ck",
            consumer_secret="cs",
            access_token="at",
            access_token_secret="ats",
        )

        handler.authenticate(
            consumer_key="",
            consumer_secret="",
            access_token="",
            access_token_secret="",
        )

        # Empty strings are falsy, so `or` keeps existing values
        assert handler.consumer_key == "ck"
        assert handler.consumer_secret == "cs"
        assert handler.access_token == "at"
        assert handler.access_token_secret == "ats"
        assert handler.is_authenticated()

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

    def test_record_request_increments_counter(self):
        """Test that _record_request increments the request counter."""
        cardmarket = Cardmarket()

        cardmarket._record_request()
        assert cardmarket._request_count == 1

        cardmarket._record_request()
        assert cardmarket._request_count == 2

    def test_check_rate_limit_raises_when_exceeded(self):
        """Test that _check_rate_limit raises RateLimitError when limit is reached."""
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 2
        cardmarket._request_count = 2

        with pytest.raises(RateLimitError):
            cardmarket._check_rate_limit()

    def test_check_rate_limit_passes_when_below_limit(self):
        """Test that _check_rate_limit does not raise when below limit."""
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 100
        cardmarket._request_count = 50

        # Should not raise
        cardmarket._check_rate_limit()

    def test_check_rate_limit_passes_one_below_limit(self):
        """Test that _check_rate_limit does not raise when one below limit."""
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 100
        cardmarket._request_count = 99

        # Should not raise (only raises when >= limit)
        cardmarket._check_rate_limit()

    def test_check_rate_limit_raises_at_limit(self):
        """Test that _check_rate_limit raises when count >= limit."""
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 100
        cardmarket._request_count = 100

        with pytest.raises(RateLimitError) as exc_info:
            cardmarket._check_rate_limit()

        assert "rate limit exceeded" in str(exc_info.value).lower()

    def test_record_and_check_rate_limit_interaction(self):
        """Test that _record_request and _check_rate_limit work together."""
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 3

        # Record requests up to limit
        for _ in range(3):
            cardmarket._record_request()

        # Should raise now
        with pytest.raises(RateLimitError):
            cardmarket._check_rate_limit()

    def test_check_rate_limit_zero_limit(self):
        """Test that _check_rate_limit raises immediately when limit is 0."""
        cardmarket = Cardmarket()
        cardmarket._rate_limit = 0

        with pytest.raises(RateLimitError):
            cardmarket._check_rate_limit()
