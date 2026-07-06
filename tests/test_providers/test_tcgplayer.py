"""Tests for the TCGPlayer provider.

This module contains unit tests for the TCGPlayer provider implementation,
covering all major functionality including authentication, card retrieval,
search, and error handling.
"""

import unittest
from unittest.mock import MagicMock, patch

import pytest
import requests

from pymtg.auth.oauth2 import OAuth2ClientCredentialsHandler
from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    InvalidQueryError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from pymtg.models.card import Card
from pymtg.models.enums import Color, Rarity
from pymtg.models.pricing import Pricing
from pymtg.providers.tcgplayer import TCGPlayer


class TestTCGPlayerInitialization(unittest.TestCase):
    """Test TCGPlayer provider initialization."""

    def test_default_initialization_no_auth(self):
        """Test that TCGPlayer provider initializes without credentials."""
        tcgplayer = TCGPlayer()
        self.assertEqual(tcgplayer.name, "tcgplayer")
        self.assertEqual(tcgplayer.base_url, "https://api.tcgplayer.com")
        self.assertIsNotNone(tcgplayer.http_client)
        self.assertIsNotNone(tcgplayer.config)
        self.assertIsNotNone(tcgplayer.auth_handler)

    def test_initialization_with_credentials(self):
        """Test that TCGPlayer provider initializes with credentials."""
        with patch.object(OAuth2ClientCredentialsHandler, "authenticate"):
            with patch.object(OAuth2ClientCredentialsHandler, "apply_auth"):
                tcgplayer = TCGPlayer(
                    client_id="test_client_id", client_secret="test_client_secret"
                )
                self.assertEqual(tcgplayer.name, "tcgplayer")
                self.assertEqual(tcgplayer.client_id, "test_client_id")
                self.assertEqual(tcgplayer.client_secret, "test_client_secret")
                # Authentication is lazy - not authenticated until first use or explicit call
                self.assertFalse(tcgplayer.is_authenticated())

    def test_is_authenticated_with_credentials(self):
        """Test that is_authenticated returns True when authenticated."""
        tcgplayer = TCGPlayer()
        # Set authenticated flag directly
        tcgplayer.auth_handler._authenticated = True
        tcgplayer.auth_handler.access_token = "test_token"
        self.assertTrue(tcgplayer.is_authenticated())

    def test_is_authenticated_without_credentials(self):
        """Test that is_authenticated returns False without credentials."""
        tcgplayer = TCGPlayer()
        self.assertFalse(tcgplayer.is_authenticated())

    def test_rate_limit_status(self):
        """Test that rate limit status returns correct information."""
        tcgplayer = TCGPlayer()
        status = tcgplayer.get_rate_limit_status()

        self.assertIn("provider", status)
        self.assertIn("rate_limit", status)
        self.assertIn("authenticated", status)
        self.assertEqual(status["provider"], "tcgplayer")
        self.assertEqual(status["rate_limit"], {"requests_per_second": 10})

    def test_authenticate_after_initialization(self):
        """Test authenticating after provider initialization."""
        tcgplayer = TCGPlayer()
        self.assertFalse(tcgplayer.is_authenticated())

        # Mock the authenticate method to set authenticated flag
        tcgplayer.auth_handler._authenticated = False
        with patch.object(tcgplayer.auth_handler, "authenticate"):
            with patch.object(tcgplayer.auth_handler, "apply_auth"):
                # Set the flag manually since we're mocking
                tcgplayer.auth_handler._authenticated = True
                tcgplayer.auth_handler.access_token = "test_token"
                tcgplayer.authenticate(
                    client_id="new_client_id", client_secret="new_client_secret"
                )
                self.assertEqual(tcgplayer.client_id, "new_client_id")
                self.assertEqual(tcgplayer.client_secret, "new_client_secret")
                self.assertTrue(tcgplayer.is_authenticated())

    def test_repr(self):
        """Test string representation of TCGPlayer provider."""
        tcgplayer = TCGPlayer()
        repr_str = repr(tcgplayer)
        self.assertIn("TCGPlayer", repr_str)
        self.assertIn("not authenticated", repr_str)


class TestTCGPlayerAuthenticationRequired(unittest.TestCase):
    """Test that TCGPlayer requires authentication for most operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer()

    def test_search_requires_auth(self):
        """Test that search raises AuthenticationError without auth."""
        with self.assertRaises(AuthenticationError):
            self.tcgplayer.search(name="Black Lotus")

    def test_search_syntax_requires_auth(self):
        """Test that search_syntax raises AuthenticationError without auth."""
        with self.assertRaises(AuthenticationError):
            self.tcgplayer.search_syntax("name:Black Lotus")

    def test_get_card_requires_auth(self):
        """Test that get_card raises AuthenticationError without auth."""
        with self.assertRaises(AuthenticationError):
            self.tcgplayer.get_card(card_id="12345")

    def test_get_pricing_requires_auth(self):
        """Test that get_pricing raises AuthenticationError without auth."""
        with self.assertRaises(AuthenticationError):
            self.tcgplayer.get_pricing(product_id=12345)

    def test_autocomplete_requires_auth(self):
        """Test that autocomplete raises AuthenticationError without auth."""
        with self.assertRaises(AuthenticationError):
            self.tcgplayer.autocomplete("Black")

    def test_iter_search_requires_auth(self):
        """Test that iter_search raises AuthenticationError without auth."""
        with self.assertRaises(AuthenticationError):
            list(self.tcgplayer.iter_search(name="Black Lotus"))


class TestTCGPlayerGetCard(unittest.TestCase):
    """Test TCGPlayer.get_card() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        # Mock the auth_handler to be authenticated
        self.tcgplayer.auth_handler._authenticated = True
        self.tcgplayer.auth_handler.access_token = "test_token"

    @patch("requests.Session.get")
    def test_get_card_success(self, mock_get):
        """Test successful card retrieval by product ID."""
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "productId": 12345,
            "name": "Black Lotus",
            "categoryName": "LEA",
            "categoryGroupName": "Core Sets",
            "rarity": "Mythic Rare",
            "productType": "Magic: The Gathering - Single Card",
            "color": "",
            "colorIdentity": "",
            "convertedManaCost": "0",
            "number": "1",
            "imageUrl": "https://example.com/image.jpg",
            "artist": "Christopher Rush",
            "flavorText": "",
        }
        mock_get.return_value = mock_response

        card = self.tcgplayer.get_card(card_id="12345")

        self.assertIsInstance(card, Card)
        self.assertEqual(card.name, "Black Lotus")

    @patch("requests.Session.get")
    def test_get_card_with_pricing(self, mock_get):
        """Test card retrieval with pricing data included."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "productId": 12345,
            "name": "Black Lotus",
            "categoryName": "LEA",
            "extendedData": [
                {
                    "price": 5000.00,
                    "conditionName": "Near Mint",
                },
                {
                    "price": 3000.00,
                    "conditionName": "Good",
                },
            ],
        }
        mock_get.return_value = mock_response

        card = self.tcgplayer.get_card(card_id="12345", include="pricing")

        self.assertIsInstance(card, Card)
        self.assertEqual(card.name, "Black Lotus")

    @patch("requests.Session.request")
    def test_get_card_product_id_required(self, mock_request):
        """Test that InvalidQueryError is raised when product_id is not provided."""
        with self.assertRaises(InvalidQueryError):
            self.tcgplayer.get_card(card_id=None)  # type: ignore  # Intentional None argument

    @patch("requests.Session.get")
    def test_get_card_not_found(self, mock_get):
        """Test that NotFoundError is raised when card doesn't exist."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Product not found"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Not Found", response=mock_response
        )
        mock_get.return_value = mock_response

        with self.assertRaises(NotFoundError):
            self.tcgplayer.get_card(card_id="99999")


class TestTCGPlayerSearch(unittest.TestCase):
    """Test TCGPlayer.search() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        # Mock the auth_handler to be authenticated
        self.tcgplayer.auth_handler._authenticated = True
        self.tcgplayer.auth_handler.access_token = "test_token"

    @patch("requests.Session.get")
    def test_search_success(self, mock_get):
        """Test successful card search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "productId": 12345,
                    "name": "Black Lotus",
                    "categoryName": "LEA",
                    "rarity": "Mythic Rare",
                    "productType": "Magic: The Gathering - Single Card",
                },
                {
                    "productId": 12346,
                    "name": "Ancestral Recall",
                    "categoryName": "LEA",
                    "rarity": "Rare",
                    "productType": "Magic: The Gathering - Single Card",
                },
            ]
        }
        mock_get.return_value = mock_response

        cards = self.tcgplayer.search(name="Black Lotus", limit=2)

        self.assertIsInstance(cards, list)
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0].name, "Black Lotus")

    @patch("requests.Session.get")
    def test_search_with_color_filter(self, mock_get):
        """Test search with color filters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "productId": 12345,
                    "name": "Island",
                    "color": "U",
                }
            ]
        }
        mock_get.return_value = mock_response

        cards = self.tcgplayer.search(colors=[Color.BLUE], limit=1)

        self.assertEqual(len(cards), 1)

    @patch("requests.Session.get")
    def test_search_with_pagination(self, mock_get):
        """Test search with pagination parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        # Test page 2 with limit 20
        self.tcgplayer.search(name="test", limit=20, page=2)

        # Verify offset was calculated correctly
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["offset"], 20)

    @patch("requests.Session.get")
    def test_search_with_order(self, mock_get):
        """Test search with sorting order."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        self.tcgplayer.search(name="test", order="name_asc")

        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["sort"], "ProductName Ascending")


class TestTCGPlayerSearchSyntax(unittest.TestCase):
    """Test TCGPlayer.search_syntax() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        # Mock the auth_handler to be authenticated
        self.tcgplayer.auth_handler._authenticated = True
        self.tcgplayer.auth_handler.access_token = "test_token"

    @patch("requests.Session.get")
    def test_search_syntax_success(self, mock_get):
        """Test successful syntax search."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "productId": 12345,
                    "name": "Black Lotus",
                }
            ]
        }
        mock_get.return_value = mock_response

        cards = self.tcgplayer.search_syntax("name:Black Lotus")

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].name, "Black Lotus")

    @patch("requests.Session.get")
    def test_search_syntax_with_parameters(self, mock_get):
        """Test syntax search with additional parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        self.tcgplayer.search_syntax("name:Island", limit=10, order="price_asc")

        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["params"]["search"], "name:Island")
        self.assertEqual(call_args[1]["params"]["limit"], 10)


class TestTCGPlayerPricing(unittest.TestCase):
    """Test TCGPlayer.get_pricing() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        # Mock the auth_handler to be authenticated
        self.tcgplayer.auth_handler._authenticated = True
        self.tcgplayer.auth_handler.access_token = "test_token"

    @patch("requests.Session.get")
    def test_get_pricing_success(self, mock_get):
        """Test successful pricing retrieval."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "skuId": 67890,
                    "price": 100.00,
                    "conditionId": 1,
                    "conditionName": "Near Mint",
                },
                {
                    "skuId": 67891,
                    "price": 75.00,
                    "conditionId": 2,
                    "conditionName": "Good",
                },
            ]
        }
        mock_get.return_value = mock_response

        pricing = self.tcgplayer.get_pricing(product_id=12345)

        self.assertIsInstance(pricing, Pricing)
        self.assertIsNotNone(pricing.tcgplayer)
        self.assertIsNotNone(pricing.tcgplayer)

    def test_get_pricing_product_id_required(self):
        """Test that InvalidQueryError is raised when product_id is not provided."""
        with self.assertRaises(InvalidQueryError):
            self.tcgplayer.get_pricing(product_id=None)  # type: ignore  # Intentional None argument


class TestTCGPlayerAutocomplete(unittest.TestCase):
    """Test TCGPlayer.autocomplete() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        # Mock the auth_handler to be authenticated
        self.tcgplayer.auth_handler._authenticated = True
        self.tcgplayer.auth_handler.access_token = "test_token"

    @patch("requests.Session.get")
    def test_autocomplete_success(self, mock_get):
        """Test successful autocomplete."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"name": "Black Lotus"},
                {"name": "Blacker Lotus"},
                {"name": "Lotus Bloom"},
            ]
        }
        mock_get.return_value = mock_response

        suggestions = self.tcgplayer.autocomplete("Lotus")

        self.assertIsInstance(suggestions, list)
        self.assertEqual(len(suggestions), 3)
        self.assertIn("Black Lotus", suggestions)

    @patch("requests.Session.get")
    def test_autocomplete_uses_default_limit(self, mock_get):
        """Test that autocomplete uses default limit of 10 when not specified."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        self.tcgplayer.autocomplete("Lotus")

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["limit"], 10)

    @patch("requests.Session.get")
    def test_autocomplete_uses_explicit_limit(self, mock_get):
        """Test that autocomplete uses the limit parameter from the signature."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        self.tcgplayer.autocomplete("Lotus", limit=5)

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["limit"], 5)

    @patch("requests.Session.get")
    def test_autocomplete_ignores_limit_in_kwargs(self, mock_get):
        """Test that limit passed via kwargs splat binds to the signature param.

        This verifies the fix for issue #198: previously `kwargs.get('limit', 10)`
        ignored the signature `limit` parameter. Now the signature parameter is
        used directly. When `limit=99` is passed (even via kwargs splat), Python
        binds it to the explicit `limit` parameter, not to `**kwargs`.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        # limit=99 binds to the signature parameter, not to **kwargs
        self.tcgplayer.autocomplete("Lotus", **{"limit": 99})

        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["limit"], 99)


class TestTCGPlayerDeckMethods(unittest.TestCase):
    """Test TCGPlayer deck-related methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        # Mock the auth_handler to be authenticated
        self.tcgplayer.auth_handler._authenticated = True
        self.tcgplayer.auth_handler.access_token = "test_token"

    def test_get_deck_not_implemented(self):
        """Test that get_deck raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.tcgplayer.get_deck(deck_id=12345)

    def test_get_user_decks_not_implemented(self):
        """Test that get_user_decks raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.tcgplayer.get_user_decks()


class TestTCGPlayerIterSearch(unittest.TestCase):
    """Test TCGPlayer.iter_search() method."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        # Mock the auth_handler to be authenticated
        self.tcgplayer.auth_handler._authenticated = True
        self.tcgplayer.auth_handler.access_token = "test_token"

    @patch.object(TCGPlayer, "search")
    def test_iter_search_yields_pages(self, mock_search):
        """Test that iter_search yields pages of results."""
        # Mock search to return results for first page, then empty
        mock_search.side_effect = [
            [
                Card(
                    id="1",
                    name="Card 1",
                    set_code="SET",
                    collector_number="1",
                    mana_cost="",
                    cmc=None,
                    type_line="",
                    rarity=None,
                    colors=None,
                    color_identity=None,
                    oracle_text=None,
                ),
                Card(
                    id="2",
                    name="Card 2",
                    set_code="SET",
                    collector_number="2",
                    mana_cost="",
                    cmc=None,
                    type_line="",
                    rarity=None,
                    colors=None,
                    color_identity=None,
                    oracle_text=None,
                ),
            ],
            [],  # Empty list ends iteration
        ]

        pages = list(self.tcgplayer.iter_search(name="test"))

        self.assertEqual(len(pages), 2)  # Should get 2 individual cards

    def _make_card(self, card_id: str) -> Card:
        """Create a minimal Card object for testing.

        Args:
            card_id: The unique identifier for the test card.

        Returns:
            A minimal Card object with only required fields populated.
        """
        return Card(
            id=card_id,
            name=f"Card {card_id}",
            set_code="SET",
            collector_number=card_id,
            mana_cost="",
            cmc=None,
            type_line="",
            rarity=None,
            colors=None,
            color_identity=None,
            oracle_text=None,
        )

    @patch.object(TCGPlayer, "search")
    def test_iter_search_limit_caps_total_results(self, mock_search):
        """Test that limit caps the total number of yielded results.

        Verifies the fix for issue #197: the signature limit parameter is
        used as the total cap, not overridden by kwargs.get('limit', 100).
        """
        # search returns 5 cards per page
        mock_search.side_effect = [
            [self._make_card(str(i)) for i in range(5)],
            [self._make_card(str(i)) for i in range(5, 10)],
            [self._make_card(str(i)) for i in range(10, 15)],
        ]

        results = list(self.tcgplayer.iter_search(name="test", limit=7))

        self.assertEqual(len(results), 7)

    @patch.object(TCGPlayer, "search")
    def test_iter_search_page_size_passed_to_search(self, mock_search):
        """Test that page_size is used as the per-page limit passed to search."""
        mock_search.side_effect = [
            [self._make_card("1")],
            [],  # Empty ends iteration
        ]

        list(self.tcgplayer.iter_search(name="test", page_size=25))

        # search should be called with limit=25 (the page_size)
        _, kwargs = mock_search.call_args
        self.assertEqual(kwargs["limit"], 25)

    @patch.object(TCGPlayer, "search")
    def test_iter_search_default_page_size(self, mock_search):
        """Test that default page_size of 50 is passed to search."""
        mock_search.side_effect = [
            [self._make_card("1")],
            [],
        ]

        list(self.tcgplayer.iter_search(name="test"))

        _, kwargs = mock_search.call_args
        self.assertEqual(kwargs["limit"], 50)

    @patch.object(TCGPlayer, "search")
    def test_iter_search_forwards_signature_params_to_search(self, mock_search):
        """Test that colors, identity, and type_line are forwarded to search.

        Previously iter_search only forwarded name to search(), ignoring
        the colors, identity, and type_line signature parameters.
        """
        mock_search.side_effect = [
            [self._make_card("1")],
            [],
        ]

        test_colors = [Color.WHITE]
        test_identity = [Color.WHITE]
        list(
            self.tcgplayer.iter_search(
                name="test",
                colors=test_colors,
                identity=test_identity,
                type_line="Creature",
            )
        )

        args, kwargs = mock_search.call_args
        self.assertEqual(args[0] if args else kwargs.get("name"), "test")
        self.assertEqual(kwargs["colors"], test_colors)
        self.assertEqual(kwargs["identity"], test_identity)
        self.assertEqual(kwargs["type_line"], "Creature")

    @patch.object(TCGPlayer, "search")
    def test_iter_search_limit_not_overridden_by_kwargs(self, mock_search):
        """Test that limit in kwargs does not override the signature parameter.

        Verifies the fix for issue #197: previously kwargs.get('limit', 100)
        ignored the signature limit parameter. Now the signature parameter
        is used as the total cap. Also verifies kwargs['limit'] passed to
        search() is page_size, not the limit from **kwargs.
        """
        # Each page returns 3 cards
        page = [self._make_card(str(i)) for i in range(3)]
        mock_search.side_effect = [page, page, page, []]

        # limit=5 via kwargs splat binds to signature param (total cap = 5)
        results = list(self.tcgplayer.iter_search(name="test", **{"limit": 5}))

        self.assertEqual(len(results), 5)
        # search() should receive page_size (default 50) as its limit, not 5
        _, kwargs = mock_search.call_args
        self.assertEqual(kwargs["limit"], 50)

    @patch.object(TCGPlayer, "search")
    def test_iter_search_limit_zero_yields_nothing(self, mock_search):
        """Test that limit=0 yields no results.

        An edge case where the total cap is zero, so no cards should be
        yielded and search() should never be called.
        """
        results = list(self.tcgplayer.iter_search(name="test", limit=0))

        self.assertEqual(len(results), 0)
        mock_search.assert_not_called()

    @patch.object(TCGPlayer, "search")
    def test_iter_search_limit_one_yields_single_result(self, mock_search):
        """Test that limit=1 yields exactly one result.

        An edge case where the total cap is one, so only the first card
        from the first page should be yielded.
        """
        mock_search.side_effect = [
            [self._make_card("1"), self._make_card("2"), self._make_card("3")],
            [],
        ]

        results = list(self.tcgplayer.iter_search(name="test", limit=1))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "1")


class TestTCGPlayerErrorHandling(unittest.TestCase):
    """Test TCGPlayer error handling."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        # Mock the auth_handler to be authenticated
        self.tcgplayer.auth_handler._authenticated = True
        self.tcgplayer.auth_handler.access_token = "test_token"

    @patch("requests.Session.get")
    def test_rate_limit_error(self, mock_get):
        """Test that RateLimitError is raised on rate limit exceeded."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {"message": "Rate limit exceeded"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Rate Limit Exceeded", response=mock_response
        )
        mock_get.return_value = mock_response

        with self.assertRaises(RateLimitError):
            self.tcgplayer.search(name="test")

    @patch("requests.Session.get")
    def test_authentication_error(self, mock_get):
        """Test that AuthenticationError is raised on authentication failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Invalid token"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Unauthorized", response=mock_response
        )
        mock_get.return_value = mock_response

        with patch.object(self.tcgplayer.http_client, "session", MagicMock()):
            with patch.object(
                self.tcgplayer.http_client.session,
                "get",
                return_value=mock_response,
            ):
                with self.assertRaises(AuthenticationError):
                    self.tcgplayer.search(name="test")

    def test_make_request_401_refresh_failure_preserves_context(self):
        """Test that 401 context is preserved when token refresh fails.

        When _make_request receives a 401 and refresh_auth() raises
        AuthenticationError, the re-raised error should include the
        original 401 context (status_code=401, provider, auth_type)
        and chain the original refresh failure via __cause__.
        """
        mock_response = MagicMock()
        mock_response.status_code = 401

        refresh_error = AuthenticationError(
            "Refresh token request failed",
            provider="tcgplayer",
            auth_type="oauth2",
        )

        session_mock = MagicMock()
        with patch.object(self.tcgplayer.http_client, "session", session_mock):
            with patch.object(
                session_mock,
                "get",
                return_value=mock_response,
            ):
                with patch.object(
                    self.tcgplayer, "refresh_auth", side_effect=refresh_error
                ):
                    with pytest.raises(AuthenticationError) as exc_info:
                        self.tcgplayer._make_request("GET", "/v2/catalog/products")

        error = exc_info.value
        assert error.status_code == 401
        assert error.provider == "tcgplayer"
        assert error.auth_type == "oauth2"
        assert "Token refresh failed" in error.message
        assert error.details["refresh_error"] == "Refresh token request failed"
        assert error.__cause__ is refresh_error

    def test_make_request_401_refresh_success_retries_request(self):
        """Test that _make_request retries after successful token refresh.

        When a 401 is received and refresh_auth() succeeds, the request
        should be retried with the new auth applied to the session.
        """
        first_response = MagicMock()
        first_response.status_code = 401

        second_response = MagicMock()
        second_response.status_code = 200
        second_response.raise_for_status.return_value = None

        session_mock = MagicMock()
        with patch.object(self.tcgplayer.http_client, "session", session_mock):
            with patch.object(
                session_mock,
                "get",
                side_effect=[first_response, second_response],
            ):
                with patch.object(self.tcgplayer, "refresh_auth") as mock_refresh:
                    with patch.object(
                        self.tcgplayer.auth_handler, "apply_auth"
                    ) as mock_apply:
                        result = self.tcgplayer._make_request(
                            "GET", "/v2/catalog/products"
                        )

        mock_refresh.assert_called_once()
        mock_apply.assert_called_once_with(session_mock)
        assert result is second_response

    def test_make_request_401_refresh_failure_logs_info(self):
        """Test that 401 detection is logged before attempting refresh.

        The _make_request method should log an info message when a 401
        is received, before attempting the token refresh.
        """
        mock_response = MagicMock()
        mock_response.status_code = 401

        refresh_error = AuthenticationError("Refresh failed", provider="tcgplayer")

        with patch.object(self.tcgplayer.http_client, "session", MagicMock()):
            with patch.object(
                self.tcgplayer.http_client.session,
                "get",
                return_value=mock_response,
            ):
                with patch.object(
                    self.tcgplayer, "refresh_auth", side_effect=refresh_error
                ):
                    with self.assertLogs(
                        "pymtg.providers.tcgplayer", level="INFO"
                    ) as cm:
                        with self.assertRaises(AuthenticationError):
                            self.tcgplayer._make_request("GET", "/v2/catalog/products")

        assert any(
            "Received 401" in msg for msg in cm.output
        ), f"Expected 401 log message, got: {cm.output}"

    @patch("requests.Session.get")
    def test_api_error(self, mock_get):
        """Test that APIError is raised on generic API errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal server error"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Internal Server Error", response=mock_response
        )
        mock_get.return_value = mock_response

        with patch.object(self.tcgplayer.http_client, "session", MagicMock()):
            with patch.object(
                self.tcgplayer.http_client.session,
                "get",
                return_value=mock_response,
            ):
                with self.assertRaises(APIError):
                    self.tcgplayer.search(name="test")

    @patch("requests.Session.get")
    def test_network_error(self, mock_get):
        """Test that NetworkError is raised on network errors."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with patch.object(self.tcgplayer.http_client, "session", MagicMock()):
            with patch.object(
                self.tcgplayer.http_client.session,
                "get",
                side_effect=mock_get.side_effect,
            ):
                with self.assertRaises(NetworkError):
                    self.tcgplayer.search(name="test")


class TestTCGPlayerResponseParsing(unittest.TestCase):
    """Test TCGPlayer response parsing methods."""

    def setUp(self):
        """Set up test fixtures."""
        self.tcgplayer = TCGPlayer(
            client_id="test_client_id", client_secret="test_client_secret"
        )
        # Mock the auth_handler to be authenticated
        self.tcgplayer.auth_handler._authenticated = True
        self.tcgplayer.auth_handler.access_token = "test_token"

    def test_parse_card_data_with_all_fields(self):
        """Test parsing card data with all fields present."""
        data = {
            "productId": 12345,
            "name": "Serra Angel",
            "categoryName": "LEA",
            "categoryGroupName": "Core Sets",
            "rarity": "Rare",
            "productType": "Creature - Angel",
            "color": "W",
            "colorIdentity": "W",
            "convertedManaCost": "5",
            "number": "1",
            "power": "4",
            "toughness": "4",
            "imageUrl": "https://example.com/serra_angel.jpg",
            "artist": "Doug Chaffee",
            "flavorText": "Vigilance, Flying",
        }

        card = self.tcgplayer._parse_card_data(data)

        self.assertIsInstance(card, Card)
        self.assertEqual(card.name, "Serra Angel")
        self.assertEqual(card.set_code, "LEA")
        self.assertEqual(card.rarity, Rarity.RARE)
        self.assertEqual(card.type_line, "Creature - Angel")
        self.assertEqual(card.mana_cost, "5")
        self.assertEqual(card.cmc, 5.0)
        self.assertEqual(card.power, "4")
        self.assertEqual(card.toughness, "4")
        self.assertIsNotNone(card.colors)
        colors = card.colors
        assert colors is not None
        self.assertEqual(len(colors), 1)
        self.assertEqual(
            colors[0], Color.WHITE
        )  # Use enum instance, not class attribute

    def test_parse_card_data_minimal(self):
        """Test parsing card data with minimal fields."""
        data = {
            "productId": 12345,
            "name": "Plains",
            "categoryName": "LEA",
        }

        card = self.tcgplayer._parse_card_data(data)

        self.assertIsInstance(card, Card)
        self.assertEqual(card.name, "Plains")
        self.assertEqual(card.set_code, "LEA")

    def test_parse_color_string_single_char(self):
        """Test parsing color string with single character codes."""
        colors = self.tcgplayer._parse_tcgplayer_color_string("WU")
        self.assertEqual(len(colors), 2)
        self.assertIn(Color.WHITE, colors)
        self.assertIn(Color.BLUE, colors)

    def test_parse_color_string_names(self):
        """Test parsing color string with color names."""
        colors = self.tcgplayer._parse_tcgplayer_color_string("White,Blue,Black")
        self.assertEqual(len(colors), 3)
        self.assertIn(Color.WHITE, colors)
        self.assertIn(Color.BLUE, colors)
        self.assertIn(Color.BLACK, colors)

    def test_parse_color_string_empty(self):
        """Test parsing empty color string."""
        colors = self.tcgplayer._parse_tcgplayer_color_string("")
        self.assertEqual(len(colors), 0)

    def test_extract_type_line_valid_creature(self):
        """Test _extract_type_line with a valid creature type.

        Verifies that a productType value like "Creature - Angel"
        (from detailed card data) is returned as-is.
        """
        result = self.tcgplayer._extract_type_line("Creature - Angel")
        self.assertEqual(result, "Creature - Angel")

    def test_extract_type_line_valid_instant(self):
        """Test _extract_type_line with a valid instant type.

        Verifies that a simple card type like "Instant" is returned
        as-is.
        """
        result = self.tcgplayer._extract_type_line("Instant")
        self.assertEqual(result, "Instant")

    def test_extract_type_line_valid_land(self):
        """Test _extract_type_line with a valid land type.

        Verifies that "Land" is returned as-is.
        """
        result = self.tcgplayer._extract_type_line("Land")
        self.assertEqual(result, "Land")

    def test_extract_type_line_valid_planeswalker(self):
        """Test _extract_type_line with a valid planeswalker type.

        Verifies that "Planeswalker - Jace" is returned as-is.
        """
        result = self.tcgplayer._extract_type_line("Planeswalker - Jace")
        self.assertEqual(result, "Planeswalker - Jace")

    def test_extract_type_line_product_category_search(self):
        """Test _extract_type_line with a search-result product category.

        Verifies that "Magic: The Gathering - Single Card" (the
        productType returned by search results) is rejected and
        returns None instead of being used as type_line.
        """
        result = self.tcgplayer._extract_type_line("Magic: The Gathering - Single Card")
        self.assertIsNone(result)

    def test_extract_type_line_sealed_product(self):
        """Test _extract_type_line with a sealed product category.

        Verifies that sealed product markers are rejected.
        """
        result = self.tcgplayer._extract_type_line("Sealed Product")
        self.assertIsNone(result)

    def test_extract_type_line_empty(self):
        """Test _extract_type_line with an empty string.

        Verifies that an empty productType returns None.
        """
        result = self.tcgplayer._extract_type_line("")
        self.assertIsNone(result)

    def test_extract_type_line_unknown_value(self):
        """Test _extract_type_line with an unknown value.

        Verifies that a value that is neither a known MTG card type
        nor a recognized product category returns None (conservative
        behavior to avoid storing wrong data as type_line).
        """
        result = self.tcgplayer._extract_type_line("Some Unknown Type")
        self.assertIsNone(result)

    def test_extract_type_line_case_insensitive_creature(self):
        """Test _extract_type_line is case-insensitive.

        Verifies that "CREATURE - ANGEL" is recognized as a valid
        creature type and returned as-is (preserving original case).
        """
        result = self.tcgplayer._extract_type_line("CREATURE - ANGEL")
        self.assertEqual(result, "CREATURE - ANGEL")

    def test_extract_type_line_mixed_case(self):
        """Test _extract_type_line handles mixed-case input.

        Verifies that "cReAtUrE - aNgEl" is recognized as a valid
        creature type and returned as-is (preserving original case).
        """
        result = self.tcgplayer._extract_type_line("cReAtUrE - aNgEl")
        self.assertEqual(result, "cReAtUrE - aNgEl")

    def test_extract_type_line_non_string_none(self):
        """Test _extract_type_line with None input.

        Verifies that passing None (which can happen if the API
        returns null for productType) returns None gracefully.
        """
        result = self.tcgplayer._extract_type_line(None)  # type: ignore[arg-type]
        self.assertIsNone(result)

    def test_extract_type_line_non_string_int(self):
        """Test _extract_type_line with integer input.

        Verifies that passing a non-string (e.g., an integer) returns
        None gracefully rather than raising a TypeError.
        """
        result = self.tcgplayer._extract_type_line(12345)  # type: ignore[arg-type]
        self.assertIsNone(result)

    def test_extract_type_line_whitespace_padding(self):
        """Test _extract_type_line with whitespace-padded input.

        Verifies that leading/trailing whitespace is stripped before
        validation, so "  Creature - Angel  " is recognized as a
        valid creature type and returned without the padding.
        """
        result = self.tcgplayer._extract_type_line("  Creature - Angel  ")
        self.assertEqual(result, "Creature - Angel")

    def test_extract_type_line_only_whitespace(self):
        """Test _extract_type_line with only whitespace.

        Verifies that a string containing only whitespace returns
        None (treated as empty after stripping).
        """
        result = self.tcgplayer._extract_type_line("   ")
        self.assertIsNone(result)

    def test_parse_card_data_product_category_type_line(self):
        """Test that product category productType does not set type_line.

        Verifies that when _parse_card_data receives a productType
        containing a product category (as search results do), the
        resulting Card has type_line=None rather than the product
        category string.
        """
        data = {
            "productId": 12345,
            "name": "Serra Angel",
            "categoryName": "LEA",
            "productType": "Magic: The Gathering - Single Card",
        }
        card = self.tcgplayer._parse_card_data(data)
        self.assertIsNone(card.type_line)


if __name__ == "__main__":
    unittest.main()
