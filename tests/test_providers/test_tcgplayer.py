"""Tests for the TCGPlayer provider.

This module contains unit tests for the TCGPlayer provider implementation,
covering all major functionality including authentication, card retrieval,
search, and error handling.
"""

import unittest
from unittest.mock import MagicMock, patch

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
        """Test authenticating after provider initialization.

        Mocks the underlying HTTP token request so the real authenticate()
        flow runs end-to-end, naturally setting the authenticated state via
        the public API rather than directly manipulating private flags.
        """
        tcgplayer = TCGPlayer()
        self.assertFalse(tcgplayer.is_authenticated())

        # Mock the HTTP token request so the real authenticate() flow runs
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        with patch("pymtg.auth.oauth2.requests.post", return_value=mock_response):
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

    def test_get_card_returns_card(self):
        """Tests that get_card returns a card by product ID."""
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
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            card = self.tcgplayer.get_card(card_id="12345")

            self.assertIsInstance(card, Card)
            self.assertEqual(card.name, "Black Lotus")

    def test_get_card_with_pricing(self):
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
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            card = self.tcgplayer.get_card(card_id="12345", include="pricing")

            self.assertIsInstance(card, Card)
            self.assertEqual(card.name, "Black Lotus")

    def test_get_card_product_id_required(self):
        """Test that InvalidQueryError is raised when product_id is not provided."""
        with self.assertRaises(InvalidQueryError):
            self.tcgplayer.get_card(card_id=None)  # type: ignore  # Intentional None argument

    def test_get_card_not_found(self):
        """Test that NotFoundError is raised when card doesn't exist."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Product not found"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Not Found", response=mock_response
        )
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
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

    def test_search_returns_results(self):
        """Tests that search returns results for a query."""
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
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            cards = self.tcgplayer.search(name="Black Lotus", limit=2)

            self.assertIsInstance(cards, list)
            self.assertEqual(len(cards), 2)
            self.assertEqual(cards[0].name, "Black Lotus")

    def test_search_with_color_filter(self):
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
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            cards = self.tcgplayer.search(colors=[Color.BLUE], limit=1)

            self.assertEqual(len(cards), 1)

    def test_search_with_pagination(self):
        """Test search with pagination parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ) as mock_get:
            # Test page 2 with limit 20
            self.tcgplayer.search(name="test", limit=20, page=2)

            # Verify offset was calculated correctly
            call_args = mock_get.call_args
            self.assertEqual(call_args[1]["params"]["offset"], 20)

    def test_search_with_order(self):
        """Test search with sorting order."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ) as mock_get:
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

    def test_search_syntax_returns_results(self):
        """Tests that search_syntax returns results for a query."""
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
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            cards = self.tcgplayer.search_syntax("name:Black Lotus")

            self.assertEqual(len(cards), 1)
            self.assertEqual(cards[0].name, "Black Lotus")

    def test_search_syntax_with_parameters(self):
        """Test syntax search with additional parameters."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ) as mock_get:
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

    def test_get_pricing_returns_pricing(self):
        """Tests that get_pricing returns pricing for a product ID."""
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
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            pricing = self.tcgplayer.get_pricing(product_id=12345)

            self.assertIsInstance(pricing, Pricing)
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

    def test_autocomplete_returns_results(self):
        """Tests that autocomplete returns results for a query."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"name": "Black Lotus"},
                {"name": "Blacker Lotus"},
                {"name": "Lotus Bloom"},
            ]
        }
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            suggestions = self.tcgplayer.autocomplete("Lotus")

            self.assertIsInstance(suggestions, list)
            self.assertEqual(len(suggestions), 3)
            self.assertIn("Black Lotus", suggestions)

    def test_autocomplete_uses_default_limit(self):
        """Test that autocomplete uses default limit of 10 when not specified."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ) as mock_get:
            self.tcgplayer.autocomplete("Lotus")

            _, kwargs = mock_get.call_args
            self.assertEqual(kwargs["params"]["limit"], 10)

    def test_autocomplete_uses_explicit_limit(self):
        """Test that autocomplete uses the limit parameter from the signature."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ) as mock_get:
            self.tcgplayer.autocomplete("Lotus", limit=5)

            _, kwargs = mock_get.call_args
            self.assertEqual(kwargs["params"]["limit"], 5)

    def test_autocomplete_ignores_limit_in_kwargs(self):
        """Test that limit passed via kwargs splat binds to the signature param.

        This verifies the fix for issue #198: previously `kwargs.get('limit', 10)`
        ignored the signature `limit` parameter. Now the signature parameter is
        used directly. When `limit=99` is passed (even via kwargs splat), Python
        binds it to the explicit `limit` parameter, not to `**kwargs`.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ) as mock_get:
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

    def test_rate_limit_error(self):
        """Test that RateLimitError is raised on rate limit exceeded."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_response.json.return_value = {"message": "Rate limit exceeded"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Rate Limit Exceeded", response=mock_response
        )

        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            with self.assertRaises(RateLimitError):
                self.tcgplayer.search(name="test")

    def test_authentication_error(self):
        """Test that AuthenticationError is raised on authentication failure."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Invalid token"}

        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            with patch.object(
                self.tcgplayer,
                "refresh_auth",
                side_effect=AuthenticationError("Refresh failed", provider="tcgplayer"),
            ):
                with self.assertRaises(AuthenticationError) as cm:
                    self.tcgplayer.search(name="test")

        self.assertEqual(cm.exception.provider, "tcgplayer")

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

        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            with patch.object(
                self.tcgplayer, "refresh_auth", side_effect=refresh_error
            ):
                with self.assertRaises(AuthenticationError) as cm:
                    self.tcgplayer._make_request("GET", "/v2/catalog/products")

        error = cm.exception
        self.assertEqual(error.status_code, 401)
        self.assertEqual(error.provider, "tcgplayer")
        self.assertEqual(error.auth_type, "oauth2")
        self.assertIn("Token refresh failed", error.message)
        self.assertEqual(error.details["refresh_error"], "Refresh token request failed")
        self.assertIs(error.__cause__, refresh_error)

    def test_make_request_401_refresh_success_retries_request(self):
        """Test that _make_request retries after successful token refresh.

        When a 401 is received and refresh_auth() succeeds, the request
        should be retried with the new auth applied to the session. The
        retry must use the same HTTP method, endpoint, and parameters as
        the original request.
        """
        first_response = MagicMock()
        first_response.status_code = 401

        second_response = MagicMock()
        second_response.status_code = 200
        second_response.raise_for_status.return_value = None

        with patch.object(
            self.tcgplayer.http_client,
            "get",
            side_effect=[first_response, second_response],
        ) as mock_get:
            with patch.object(self.tcgplayer, "refresh_auth") as mock_refresh:
                with patch.object(
                    self.tcgplayer.auth_handler, "apply_auth"
                ) as mock_apply:
                    result = self.tcgplayer._make_request("GET", "/v2/catalog/products")

        mock_refresh.assert_called_once()
        mock_apply.assert_called_once_with(self.tcgplayer.http_client.session)
        self.assertIs(result, second_response)
        # Verify retry used same endpoint as original request
        self.assertEqual(mock_get.call_count, 2)
        first_call = mock_get.call_args_list[0]
        second_call = mock_get.call_args_list[1]
        self.assertIn("/v2/catalog/products", first_call.args[0])
        self.assertIn("/v2/catalog/products", second_call.args[0])

    def test_make_request_401_refresh_failure_logs_info(self):
        """Test that 401 detection is logged before attempting refresh.

        The _make_request method should log an info message when a 401
        is received, before attempting the token refresh.
        """
        mock_response = MagicMock()
        mock_response.status_code = 401

        refresh_error = AuthenticationError("Refresh failed", provider="tcgplayer")

        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            with patch.object(
                self.tcgplayer, "refresh_auth", side_effect=refresh_error
            ):
                with self.assertLogs("pymtg.providers.tcgplayer", level="INFO") as cm:
                    with self.assertRaises(AuthenticationError) as error_cm:
                        self.tcgplayer._make_request("GET", "/v2/catalog/products")

        self.assertTrue(
            any("Received 401" in msg for msg in cm.output),
            f"Expected 401 log message, got: {cm.output}",
        )
        self.assertEqual(error_cm.exception.provider, "tcgplayer")

    def test_api_error(self):
        """Test that APIError is raised on generic API errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal server error"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "Internal Server Error", response=mock_response
        )

        with patch.object(
            self.tcgplayer.http_client, "get", return_value=mock_response
        ):
            with self.assertRaises(APIError) as cm:
                self.tcgplayer.search(name="test")

        self.assertEqual(cm.exception.status_code, 500)
        self.assertEqual(cm.exception.provider, "tcgplayer")

    def test_network_error(self):
        """Test that NetworkError is raised on network errors."""
        with patch.object(
            self.tcgplayer.http_client,
            "get",
            side_effect=NetworkError("Connection failed"),
        ):
            with self.assertRaises(NetworkError) as cm:
                self.tcgplayer.search(name="test")

        self.assertIn("Connection failed", cm.exception.message)


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
        self.assertIsNotNone(colors)
        self.assertEqual(len(colors), 1)
        self.assertEqual(
            colors[0], Color.WHITE
        )  # Use enum instance, not class attribute

    def test_parse_card_data_negative_cmc_logs_warning(self):
        """Test that negative CMC values log a warning and set to None."""
        data = {
            "productId": 12345,
            "name": "Test Card",
            "convertedManaCost": "-2",
        }
        with self.assertLogs(level="WARNING") as log:
            card = self.tcgplayer._parse_card_data(data)
        self.assertIsNone(card.cmc)
        self.assertTrue(any("Negative CMC" in m for m in log.output))

    def test_parse_card_data_invalid_cmc_logs_warning(self):
        """Test that invalid CMC values log a warning and set to None."""
        data = {
            "productId": 12345,
            "name": "Test Card",
            "convertedManaCost": "not_a_number",
        }
        with self.assertLogs(level="WARNING") as log:
            card = self.tcgplayer._parse_card_data(data)
        self.assertIsNone(card.cmc)
        self.assertTrue(any("Invalid CMC" in m for m in log.output))

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

    def test_parse_card_data_set_name_uses_group_name(self):
        """Test set_name uses groupName, not categoryName.

        Verifies that set_code comes from categoryName and set_name
        comes from groupName (a different field), fixing the bug where
        both were set to categoryName.
        """
        data = {
            "productId": 12345,
            "name": "Serra Angel",
            "categoryName": "LEA",
            "groupName": "Limited Edition Alpha",
        }

        card = self.tcgplayer._parse_card_data(data)

        self.assertIsInstance(card, Card)
        self.assertEqual(card.set_code, "LEA")
        self.assertEqual(card.set_name, "Limited Edition Alpha")

    def test_parse_card_data_set_name_none_without_group_name(self):
        """Test set_name is None when groupName is not provided.

        Verifies that set_name falls back to None when groupName is
        absent, rather than duplicating the set_code value.
        """
        data = {
            "productId": 12345,
            "name": "Plains",
            "categoryName": "LEA",
        }

        card = self.tcgplayer._parse_card_data(data)

        self.assertIsInstance(card, Card)
        self.assertEqual(card.set_code, "LEA")
        self.assertIsNone(card.set_name)

    def test_parse_card_data_pricing_uses_condition_name(self):
        """Test pricing extraction uses conditionName, not condition.

        Verifies that _parse_card_data extracts pricing from extendedData
        using the conditionName field (not condition) and normalizes
        values by lowercasing and replacing spaces with underscores.
        """
        data = {
            "productId": 12345,
            "name": "Serra Angel",
            "categoryName": "LEA",
            "extendedData": [
                {
                    "price": 5000.00,
                    "conditionName": "Near Mint",
                },
                {
                    "price": 3000.00,
                    "conditionName": "Very Good",
                },
            ],
        }

        card = self.tcgplayer._parse_card_data(data)

        self.assertIsInstance(card, Card)
        self.assertIsNotNone(card.pricing)
        self.assertIsNotNone(card.pricing.tcgplayer)
        tcg_pricing = card.pricing.tcgplayer
        self.assertEqual(tcg_pricing.near_mint, 5000.00)
        self.assertEqual(tcg_pricing.very_good, 3000.00)

    def test_parse_card_data_pricing_ignores_condition_field(self):
        """Test pricing extraction ignores the incorrect condition field.

        Verifies that extendedData entries with only a condition field
        (the wrong field name) are not extracted into pricing data.
        """
        data = {
            "productId": 12345,
            "name": "Serra Angel",
            "categoryName": "LEA",
            "extendedData": [
                {
                    "price": 5000.00,
                    "condition": "Near Mint",
                },
            ],
        }

        card = self.tcgplayer._parse_card_data(data)

        self.assertIsInstance(card, Card)
        self.assertIsNone(card.pricing)

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

    def test_parse_color_string_mixed_format(self):
        """Test parsing mixed format color string (single char + names)."""
        colors = self.tcgplayer._parse_tcgplayer_color_string("W, Blue")
        self.assertEqual(len(colors), 2)
        self.assertIn(Color.WHITE, colors)
        self.assertIn(Color.BLUE, colors)

    def test_parse_color_string_unknown_logs_warning(self):
        """Test that unknown color values log a warning."""
        with self.assertLogs(level="WARNING") as log:
            colors = self.tcgplayer._parse_tcgplayer_color_string("W, Xyz")
        self.assertEqual(len(colors), 1)
        self.assertIn(Color.WHITE, colors)
        # Xyz has no valid chars, so 1 part-level warning
        self.assertEqual(len(log.output), 1)
        self.assertIn("Xyz", log.output[0])

    def test_parse_color_string_all_invalid(self):
        """Test that fully invalid input returns empty list with warnings."""
        with self.assertLogs(level="WARNING") as log:
            colors = self.tcgplayer._parse_tcgplayer_color_string("XYZ")
        self.assertEqual(len(colors), 0)
        # 1 part-level warning (no valid chars found)
        self.assertEqual(len(log.output), 1)

    def test_parse_color_string_single_char_no_comma(self):
        """Test parsing single character codes without comma."""
        colors = self.tcgplayer._parse_tcgplayer_color_string("WUBRG")
        self.assertEqual(len(colors), 5)
        self.assertIn(Color.WHITE, colors)
        self.assertIn(Color.BLUE, colors)
        self.assertIn(Color.BLACK, colors)
        self.assertIn(Color.RED, colors)
        self.assertIn(Color.GREEN, colors)

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

    def test_parse_card_data_type_field_preferred_over_productType(self):
        """Test that 'type' field is preferred over 'productType'.

        Verifies that when both 'type' and 'productType' are present,
        the 'type' field value is used for type_line.
        """
        data = {
            "productId": 12345,
            "name": "Serra Angel",
            "categoryName": "LEA",
            "type": "Creature - Angel",
            "productType": "Magic: The Gathering - Single Card",
        }
        card = self.tcgplayer._parse_card_data(data)
        self.assertEqual(card.type_line, "Creature - Angel")

    def test_parse_card_data_type_field_used_directly(self):
        """Test that 'type' field is used without productType validation.

        Verifies that the 'type' field is used directly even if it
        would not pass _extract_type_line validation (e.g., a value
        not starting with a known MTG type prefix).
        """
        data = {
            "productId": 12345,
            "name": "Custom Card",
            "categoryName": "LEA",
            "type": "Legendary Artifact - Equipment",
        }
        card = self.tcgplayer._parse_card_data(data)
        self.assertEqual(card.type_line, "Legendary Artifact - Equipment")

    def test_parse_card_data_empty_type_falls_back_to_productType(self):
        """Test that empty 'type' field falls back to 'productType'.

        Verifies that when 'type' is an empty string, _parse_card_data
        falls back to validating 'productType'.
        """
        data = {
            "productId": 12345,
            "name": "Serra Angel",
            "categoryName": "LEA",
            "type": "",
            "productType": "Creature - Angel",
        }
        card = self.tcgplayer._parse_card_data(data)
        self.assertEqual(card.type_line, "Creature - Angel")


if __name__ == "__main__":
    unittest.main()
