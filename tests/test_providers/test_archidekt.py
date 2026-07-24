"""Tests for the Archidekt provider.

This module contains unit tests for the Archidekt provider implementation,
covering all major functionality including authentication, deck retrieval,
card search, and error handling.

Note:
    The Archidekt API is unofficial and undocumented. These tests use mocked
    responses to verify the provider's behavior without requiring actual API
    credentials or network access.
"""

import functools
import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from pymtg.auth.jwt import JWTAuthHandler
from pymtg.exceptions import (
    AuthenticationError,
    NetworkError,
    NotFoundError,
)
from pymtg.models.card import Card
from pymtg.models.deck import Deck
from pymtg.providers.archidekt.exceptions import (
    ArchidektAuthenticationError,
    ArchidektValidationError,
)
from pymtg.models.enums import Board, Color, Format, Rarity, SetType
from pymtg.providers.archidekt import Archidekt


def mock_authenticated_and_http_client(func):
    """Decorator to mock JWTAuthHandler.is_authenticated and Archidekt.http_client.

    This reduces duplication in tests that need both mocks.

    Returns:
        Decorated function with both mocks applied.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        patcher1 = patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
        patcher2 = patch.object(Archidekt, "http_client")

        with patcher1, patcher2 as mock_http_client:
            return func(*args, mock_http_client=mock_http_client, **kwargs)

    return wrapper


class TestArchidektInitialization(unittest.TestCase):
    """Test Archidekt provider initialization."""

    def test_default_initialization(self):
        """Test that Archidekt provider initializes correctly with default parameters."""
        archidekt = Archidekt()
        self.assertEqual(archidekt.name, "archidekt")
        self.assertEqual(archidekt.base_url, "https://archidekt.com/api/")
        self.assertIsNotNone(archidekt.http_client)
        self.assertIsNotNone(archidekt.config)
        self.assertIsNotNone(archidekt.auth_handler)
        self.assertIsInstance(archidekt.auth_handler, JWTAuthHandler)

    def test_initialization_with_credentials(self):
        """Test that Archidekt provider initializes with credentials."""
        with patch.object(JWTAuthHandler, "authenticate") as mock_auth:
            archidekt = Archidekt(username="test_user", password="test_pass")

            self.assertEqual(archidekt.name, "archidekt")
            mock_auth.assert_called_once_with(
                username="test_user", password="test_pass"
            )

    def test_initialization_with_credentials_logs_auth_info(self):
        """Tests that init with credentials logs authentication info."""
        with patch.object(JWTAuthHandler, "authenticate"):
            with self.assertLogs("pymtg.providers.archidekt", level="INFO") as cm:
                Archidekt(username="test_user", password="test_pass")

        self.assertTrue(
            any("Archidekt JWT authentication successful" in msg for msg in cm.output),
            f"Expected auth success log, got: {cm.output}",
        )

    def test_is_authenticated_without_creds(self):
        """Test that is_authenticated returns False without credentials."""
        archidekt = Archidekt()
        self.assertFalse(archidekt.is_authenticated())

    def test_is_authenticated_with_creds(self):
        """Test that is_authenticated returns True with valid credentials."""
        with patch.object(JWTAuthHandler, "authenticate"):
            with patch.object(JWTAuthHandler, "is_authenticated", return_value=True):
                archidekt = Archidekt(username="test_user", password="test_pass")
                self.assertTrue(archidekt.is_authenticated())

    def test_rate_limit_status(self):
        """Test that rate limit status returns correct information."""
        archidekt = Archidekt()
        status = archidekt.get_rate_limit_status()

        self.assertIn("requests_per_minute", status)
        self.assertEqual(status["requests_per_minute"], 60)

    def test_repr(self):
        """Test string representation of Archidekt provider."""
        archidekt = Archidekt()
        repr_str = repr(archidekt)

        self.assertIn("Archidekt", repr_str)
        self.assertIn("archidekt", repr_str)
        self.assertIn("authenticated=False", repr_str)


class TestArchidektAuthentication(unittest.TestCase):
    """Test Archidekt authentication methods."""

    @patch.object(JWTAuthHandler, "authenticate")
    def test_authenticate_with_valid_credentials(self, mock_auth):
        """Tests that authenticate works with valid credentials."""
        archidekt = Archidekt()
        archidekt.authenticate("test_user", "test_pass")

        mock_auth.assert_called_once_with(username="test_user", password="test_pass")

    @patch.object(JWTAuthHandler, "authenticate")
    def test_authenticate_logs_info_on_success(self, mock_auth):
        """Tests that authenticate logs an info message on success."""
        archidekt = Archidekt()
        with self.assertLogs("pymtg.providers.archidekt", level="INFO") as cm:
            archidekt.authenticate("test_user", "test_pass")

        self.assertTrue(
            any("Archidekt JWT authentication successful" in msg for msg in cm.output),
            f"Expected auth success log, got: {cm.output}",
        )

    @patch.object(JWTAuthHandler, "authenticate")
    def test_authenticate_failure(self, mock_auth):
        """Test authentication failure raises AuthenticationError."""
        mock_auth.side_effect = AuthenticationError("Login failed")

        archidekt = Archidekt()

        with self.assertRaises(AuthenticationError):
            archidekt.authenticate("test_user", "test_pass")

    @patch.object(JWTAuthHandler, "refresh")
    def test_refresh_auth_with_valid_credentials(self, mock_refresh):
        """Tests that refresh_auth works with valid credentials."""
        archidekt = Archidekt()
        archidekt.refresh_auth()

        mock_refresh.assert_called_once()

    @patch.object(JWTAuthHandler, "refresh")
    def test_refresh_auth_logs_info_on_success(self, mock_refresh):
        """Tests that refresh_auth logs an info message on success."""
        archidekt = Archidekt()
        with self.assertLogs("pymtg.providers.archidekt", level="INFO") as cm:
            archidekt.refresh_auth()

        self.assertTrue(
            any(
                "Archidekt authentication refreshed successfully" in msg
                for msg in cm.output
            ),
            f"Expected auth refresh log, got: {cm.output}",
        )

    @patch.object(JWTAuthHandler, "refresh")
    def test_refresh_auth_failure(self, mock_refresh):
        """Test authentication refresh failure raises AuthenticationError."""
        mock_refresh.side_effect = AuthenticationError("Refresh failed")

        archidekt = Archidekt()

        with self.assertRaises(AuthenticationError):
            archidekt.refresh_auth()


class TestArchidektGetCard(unittest.TestCase):
    """Test Archidekt.get_card() method."""

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    @patch.object(Archidekt, "_parse_card")
    def test_get_card_returns_card(
        self, mock_parse_card, mock_http_client, mock_handle_response
    ):
        """Tests that get_card returns a card by ID."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock the response data (now uses search endpoint which returns results list)
        mock_data = {
            "count": 1,
            "results": [
                {
                    "id": "archidekt-card-123",
                    "name": "Black Lotus",
                    "scryfall_id": "38625902-0567-4f24-85b0-a00843553997",
                    "mana_cost": "{0}",
                    "type_line": "Artifact",
                    "oracle_text": "{T}, Sacrifice this artifact: Add {B}{B}{B}{B}{B}{B}{B}.",
                    "rarity": "mythic",
                    "color_identity": [],
                    "colors": [],
                    "cmc": 0.0,
                    "oracleCard": {"id": "archidekt-card-123"},
                }
            ],
        }
        mock_handle_response.return_value = mock_data

        # Mock the parse method
        mock_parse_card.return_value = Card(
            id="archidekt-card-123",
            scryfall_id="38625902-0567-4f24-85b0-a00843553997",
            name="Black Lotus",
            mana_cost="{0}",
            source="archidekt",
        )

        archidekt = Archidekt()
        card = archidekt.get_card("123")

        self.assertIsInstance(card, Card)
        self.assertEqual(card.name, "Black Lotus")
        self.assertEqual(card.scryfall_id, "38625902-0567-4f24-85b0-a00843553997")
        self.assertEqual(card.source, "archidekt")

        # Verify HTTP client was called correctly (now uses search endpoint with numeric ID)
        mock_http_client.get.assert_called_once_with(
            "cards/v2/",
            params={"oracleCardIds": "123", "game": 1, "unique": True, "pageSize": 1},
        )

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    def test_get_card_not_found(self, mock_http_client, mock_handle_response):
        """Test that NotFoundError is raised when card doesn't exist."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock empty response data
        mock_handle_response.return_value = None

        archidekt = Archidekt()

        with self.assertRaises(NotFoundError) as context:
            archidekt.get_card("non-existent-id")

        self.assertEqual(context.exception.provider, "archidekt")
        self.assertEqual(context.exception.resource_type, "card")
        self.assertEqual(context.exception.resource_id, "non-existent-id")

    @patch.object(Archidekt, "http_client")
    def test_get_card_network_error(self, mock_http_client):
        """Test that NetworkError is raised on network failure."""
        # Mock the HTTP client to raise a request exception
        mock_http_client.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )

        archidekt = Archidekt()

        with self.assertRaises(NetworkError) as context:
            archidekt.get_card("test-id")

        self.assertIn("Network error during get_card", str(context.exception))


class TestArchidektGetDeck(unittest.TestCase):
    """Test Archidekt.get_deck() method."""

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    @patch.object(Archidekt, "_parse_deck")
    def test_get_deck_returns_deck(
        self, mock_parse_deck, mock_http_client, mock_handle_response
    ):
        """Tests that get_deck returns a deck by ID."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock the response data
        mock_data = {
            "id": "deck-uuid-123",
            "name": "Test Deck",
            "description": "A test deck",
            "format": "commander",
            "cards": [],
        }
        mock_handle_response.return_value = mock_data

        # Mock the parse method
        mock_parse_deck.return_value = Deck(
            id="deck-uuid-123", name="Test Deck", source="archidekt"
        )

        archidekt = Archidekt()
        deck = archidekt.get_deck("deck-uuid-123")

        self.assertIsInstance(deck, Deck)
        self.assertEqual(deck.id, "deck-uuid-123")
        self.assertEqual(deck.name, "Test Deck")
        self.assertEqual(deck.source, "archidekt")

        # Verify HTTP client was called correctly
        mock_http_client.get.assert_called_once_with("decks/v2/deck-uuid-123/")

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    def test_get_deck_not_found(self, mock_http_client, mock_handle_response):
        """Test that NotFoundError is raised when deck doesn't exist."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock empty response data
        mock_handle_response.return_value = None

        archidekt = Archidekt()

        with self.assertRaises(NotFoundError) as context:
            archidekt.get_deck("non-existent-deck-id")

        self.assertEqual(context.exception.provider, "archidekt")
        self.assertEqual(context.exception.resource_type, "deck")
        self.assertEqual(context.exception.resource_id, "non-existent-deck-id")

    @patch.object(Archidekt, "http_client")
    def test_get_deck_network_error(self, mock_http_client):
        """Test that NetworkError is raised on network failure."""
        # Mock the HTTP client to raise a request exception
        mock_http_client.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )

        archidekt = Archidekt()

        with self.assertRaises(NetworkError) as context:
            archidekt.get_deck("test-deck-id")

        self.assertIn("Network error during get_deck", str(context.exception))


class TestArchidektGetUserDecks(unittest.TestCase):
    """Test Archidekt.get_user_decks() method."""

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    @patch.object(Archidekt, "_parse_deck")
    def test_get_user_decks_with_user_id(
        self, mock_parse_deck, mock_http_client, mock_handle_response
    ):
        """Test successful retrieval of user decks with user ID."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock the response data
        mock_data = [
            {"id": "deck1", "name": "Deck 1"},
            {"id": "deck2", "name": "Deck 2"},
        ]
        mock_handle_response.return_value = mock_data

        # Mock the parse method
        mock_parse_deck.side_effect = [
            Deck(id="deck1", name="Deck 1", source="archidekt"),
            Deck(id="deck2", name="Deck 2", source="archidekt"),
        ]

        archidekt = Archidekt()
        decks = archidekt.get_user_decks(user_id="test-user")

        self.assertIsInstance(decks, list)
        self.assertEqual(len(decks), 2)
        self.assertEqual(decks[0].id, "deck1")
        self.assertEqual(decks[1].id, "deck2")

        # Verify HTTP client was called correctly
        mock_http_client.get.assert_called_once_with("users/test-user/decks/")

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    @patch.object(Archidekt, "_parse_deck")
    def test_get_user_decks_without_user_id(
        self, mock_parse_deck, mock_http_client, mock_handle_response
    ):
        """Test retrieval of decks for authenticated user (no user_id)."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock the response data
        mock_data = [{"id": "deck1", "name": "My Deck"}]
        mock_handle_response.return_value = mock_data

        # Mock the parse method
        mock_parse_deck.return_value = Deck(
            id="deck1", name="My Deck", source="archidekt"
        )

        # Create archidekt with mocked auth handler that has a user_id
        archidekt = Archidekt()
        # Set the private _user_id attribute directly (property is read-only)
        archidekt.auth_handler._user_id = "auth-user-123"

        decks = archidekt.get_user_decks()

        self.assertIsInstance(decks, list)
        self.assertEqual(len(decks), 1)

        # Verify HTTP client was called with correct endpoint
        mock_http_client.get.assert_called_once_with("users/auth-user-123/decks/")

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    def test_get_user_decks_empty(self, mock_http_client, mock_handle_response):
        """Test that empty list is returned when user has no decks."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock empty response data
        mock_handle_response.return_value = []

        archidekt = Archidekt()
        decks = archidekt.get_user_decks(user_id="test-user")

        self.assertIsInstance(decks, list)
        self.assertEqual(len(decks), 0)

    @patch.object(Archidekt, "http_client")
    def test_get_user_decks_network_error(self, mock_http_client):
        """Test that NetworkError is raised on network failure."""
        # Mock the HTTP client to raise a request exception
        mock_http_client.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )

        archidekt = Archidekt()
        # Set the private _user_id attribute directly (property is read-only)
        archidekt.auth_handler._user_id = "auth-user-123"

        with self.assertRaises(NetworkError) as context:
            archidekt.get_user_decks()

        self.assertIn("Network error during get_user_decks", str(context.exception))


class TestArchidektSearch(unittest.TestCase):
    """Test Archidekt.search() method."""

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    @patch.object(Archidekt, "_parse_card")
    def test_search_returns_results(
        self, mock_parse_card, mock_http_client, mock_handle_response
    ):
        """Tests that search returns results for a query."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response data
        mock_data = {"results": [{"id": "card1"}, {"id": "card2"}]}
        mock_handle_response.return_value = mock_data

        # Mock parse method
        mock_parse_card.side_effect = [
            Card(id="card1", name="Card 1", source="archidekt"),
            Card(id="card2", name="Card 2", source="archidekt"),
        ]

        archidekt = Archidekt()
        cards = archidekt.search(name="Black Lotus", limit=20)

        self.assertIsInstance(cards, list)
        self.assertEqual(len(cards), 2)

        # Verify HTTP client was called correctly with dict parameters
        call_args = mock_http_client.get.call_args
        self.assertEqual(call_args[0][0], "cards/v2/")
        self.assertIn("nameSearch", call_args[1]["params"])
        self.assertEqual(call_args[1]["params"]["nameSearch"], "Black Lotus")

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    @patch.object(Archidekt, "_parse_card")
    def test_search_with_colors(
        self, mock_parse_card, mock_http_client, mock_handle_response
    ):
        """Test search with color filters."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response data
        mock_data = {"results": [{"id": "card1"}]}
        mock_handle_response.return_value = mock_data

        # Mock parse method
        mock_parse_card.return_value = Card(
            id="card1", name="Card 1", source="archidekt"
        )

        archidekt = Archidekt()
        cards = archidekt.search(colors=[Color.BLUE, Color.WHITE])

        self.assertEqual(len(cards), 1)

        # Verify query building was called with colors
        call_args = mock_http_client.get.call_args
        self.assertIn("colors", call_args[1]["params"])
        self.assertEqual(call_args[1]["params"]["colors"], "Blue,White")

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    def test_search_empty_results(self, mock_http_client, mock_handle_response):
        """Test that empty list is returned when no results found."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock empty response data (API returns a dict with empty results)
        mock_handle_response.return_value = {"results": []}

        archidekt = Archidekt()
        cards = archidekt.search(name="Non-existent Card")

        self.assertIsInstance(cards, list)
        self.assertEqual(len(cards), 0)

    @patch.object(Archidekt, "http_client")
    def test_search_network_error(self, mock_http_client):
        """Test that NetworkError is raised on network failure."""
        # Mock the HTTP client to raise a request exception
        mock_http_client.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )

        archidekt = Archidekt()

        with self.assertRaises(NetworkError) as context:
            archidekt.search(name="test")

        self.assertIn("Network error during search", str(context.exception))


class TestArchidektSearchSyntax(unittest.TestCase):
    """Test Archidekt.search_syntax() method."""

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    @patch.object(Archidekt, "_parse_card")
    def test_search_syntax_returns_results(
        self, mock_parse_card, mock_http_client, mock_handle_response
    ):
        """Tests that search_syntax returns results for a query."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response data
        mock_data = {"results": [{"id": "card1", "name": "Test Card"}]}
        mock_handle_response.return_value = mock_data

        # Mock parse method
        mock_parse_card.return_value = Card(
            id="card1", name="Test Card", source="archidekt"
        )

        archidekt = Archidekt()
        cards = archidekt.search_syntax("c:U type:creature", limit=10)

        self.assertIsInstance(cards, list)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].name, "Test Card")

        # Verify HTTP client was called with query
        call_args = mock_http_client.get.call_args
        self.assertIn("nameSearch", call_args[1]["params"])
        self.assertEqual(call_args[1]["params"]["nameSearch"], "c:U type:creature")
        self.assertEqual(call_args[1]["params"]["pageSize"], 10)

    @patch.object(Archidekt, "http_client")
    def test_search_syntax_network_error(self, mock_http_client):
        """Test that NetworkError is raised on network failure."""
        # Mock the HTTP client to raise a request exception
        mock_http_client.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )

        archidekt = Archidekt()

        with self.assertRaises(NetworkError) as context:
            archidekt.search_syntax("c:U")

        self.assertIn("Network error during search_syntax", str(context.exception))


class TestArchidektAutocomplete(unittest.TestCase):
    """Test Archidekt.autocomplete() method."""

    def test_autocomplete_not_implemented(self):
        """Test that autocomplete returns empty list (not yet implemented)."""
        archidekt = Archidekt()
        suggestions = archidekt.autocomplete("black")

        self.assertIsInstance(suggestions, list)
        self.assertEqual(len(suggestions), 0)

    def test_autocomplete_logs_warning(self):
        """Test that autocomplete logs a warning about not being implemented."""
        archidekt = Archidekt()
        with self.assertLogs("pymtg.providers.archidekt", level="WARNING") as cm:
            archidekt.autocomplete("black")

        self.assertTrue(
            any(
                "Archidekt autocomplete not yet implemented" in msg for msg in cm.output
            ),
            f"Expected 'Archidekt autocomplete not yet implemented' warning, "
            f"got: {cm.output}",
        )


class TestArchidektParseCard(unittest.TestCase):
    """Test Archidekt._parse_card() method."""

    def test_parse_simple_card(self):
        """Test parsing a simple card with no special features."""
        archidekt = Archidekt()

        data = {
            "id": "card-123",
            "scryfall_id": "scryfall-123",
            "name": "Test Card",
            "printed_name": "Test Card",
            "mana_cost": "{1}{U}",
            "type_line": "Creature — Human Wizard",
            "printed_type_line": "Creature — Human Wizard",
            "oracle_text": "Draw a card.",
            "printed_text": "Draw a card.",
            "flavor_text": "A test card",
            "artist": "Test Artist",
            "number": "123",
            "power": "1",
            "toughness": "2",
            "loyalty": None,
            "color_identity": ["U"],
            "colors": ["U"],
            "color_indicator": [],
            "rarity": "common",
            "set": {"name": "Test Set", "code": "TST"},
            "set_type": "core",
            "cmc": 2.0,
            "prices": {
                "usd": 0.50,
                "usd_foil": 1.00,
                "eur": 0.40,
                "tix": 0.10,
            },
            "image_url": "https://example.com/image.jpg",
        }

        card = archidekt._parse_card(data)

        self.assertIsInstance(card, Card)
        self.assertEqual(card.id, "card-123")
        self.assertEqual(card.scryfall_id, "scryfall-123")
        self.assertEqual(card.name, "Test Card")
        self.assertEqual(card.mana_cost, "{1}{U}")
        self.assertEqual(card.type_line, "Creature — Human Wizard")
        self.assertEqual(card.oracle_text, "Draw a card.")
        self.assertEqual(card.flavors, ["A test card"])
        self.assertEqual(card.artist, "Test Artist")
        self.assertEqual(card.power, "1")
        self.assertEqual(card.toughness, "2")
        self.assertEqual(card.rarity, Rarity.COMMON)
        self.assertEqual(card.set_name, "Test Set")
        self.assertEqual(card.set_code, "TST")
        self.assertEqual(card.set_type, SetType.CORE)
        self.assertEqual(card.cmc, 2.0)
        self.assertEqual(card.source, "archidekt")

    def test_parse_card_with_card_faces(self):
        """Test parsing a card with multiple faces (transform card)."""
        archidekt = Archidekt()

        data = {
            "id": "card-456",
            "name": "Test Transform Card",
            "card_faces": [
                {
                    "name": "Front Side",
                    "mana_cost": "{1}",
                    "type_line": "Creature — Human",
                    "oracle_text": "Front text",
                    "power": "1",
                    "toughness": "1",
                },
                {
                    "name": "Back Side",
                    "mana_cost": "",
                    "type_line": "Creature — Demon",
                    "oracle_text": "Back text",
                    "power": "5",
                    "toughness": "5",
                },
            ],
            "color_identity": ["B"],
            "rarity": "mythic",
            "set": {"name": "Test Set", "code": "TST"},
        }

        card = archidekt._parse_card(data)

        self.assertIsInstance(card, Card)
        self.assertEqual(card.name, "Front Side")
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        self.assertEqual(len(card_faces), 2)
        self.assertEqual(card_faces[0].name, "Front Side")
        self.assertEqual(card_faces[1].name, "Back Side")
        self.assertEqual(card.color_identity, [Color.BLACK])

    def test_parse_card_card_faces_not_list(self):
        """Test _parse_card handles card_faces that is not a list.

        Verifies that when card_faces is a non-list value (e.g., dict,
        string, int), it is treated as empty and the card parses without
        card_faces instead of raising a TypeError during iteration.
        """
        archidekt = Archidekt()

        for invalid in ({"name": "x"}, "not a list", 42, None):
            data = {
                "id": "card-999",
                "name": "Simple Card",
                "card_faces": invalid,
            }
            card = archidekt._parse_card(data)
            self.assertIsInstance(card, Card)
            self.assertIsNone(card.card_faces)
            self.assertEqual(card.name, "Simple Card")

    def test_parse_card_card_faces_skips_non_dict_entries(self):
        """Test _parse_card skips non-dict entries in card_faces.

        Verifies that non-dict entries in the card_faces list are skipped
        and only valid dict faces are parsed into CardFace objects.
        """
        archidekt = Archidekt()

        data = {
            "id": "card-1000",
            "name": "Transform Card",
            "card_faces": [
                "not a dict",
                42,
                None,
                {
                    "name": "Valid Face",
                    "mana_cost": "{1}",
                    "type_line": "Creature",
                    "oracle_text": "text",
                },
            ],
        }

        card = archidekt._parse_card(data)
        self.assertIsInstance(card, Card)
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        self.assertEqual(len(card_faces), 1)
        self.assertEqual(card_faces[0].name, "Valid Face")

    def test_parse_card_with_missing_fields(self):
        """Test parsing a card with missing optional fields."""
        archidekt = Archidekt()

        data = {
            "id": "card-789",
            "name": "Simple Card",
            "mana_cost": "",
            "type_line": "Artifact",
        }

        card = archidekt._parse_card(data)

        self.assertIsInstance(card, Card)
        self.assertEqual(card.id, "card-789")
        self.assertEqual(card.name, "Simple Card")
        self.assertEqual(card.mana_cost, "")
        self.assertEqual(card.type_line, "Artifact")
        self.assertEqual(card.oracle_text, "")
        self.assertIsNone(card.power)
        self.assertIsNone(card.toughness)

    def test_parse_card_invalid_color_logs_debug(self):
        """Test that invalid color strings are logged at debug, not warning."""
        archidekt = Archidekt()

        data = {
            "id": "card-invalid-color",
            "name": "Invalid Color Card",
            "colors": ["X"],
            "color_identity": ["Y"],
            "color_indicator": ["Z"],
        }

        with self.assertLogs("pymtg.providers.archidekt", level="DEBUG") as cm:
            card = archidekt._parse_card(data)

        self.assertIsInstance(card, Card)
        debug_msgs = [msg for msg in cm.output if "DEBUG" in msg]
        self.assertTrue(
            any("Unknown color: X" in msg for msg in debug_msgs),
            f"Expected debug log 'Unknown color: X', got: {cm.output}",
        )
        self.assertTrue(
            any("Unknown color in identity: Y" in msg for msg in debug_msgs),
            f"Expected debug log 'Unknown color in identity: Y', got: {cm.output}",
        )
        self.assertTrue(
            any("Unknown color in indicator: Z" in msg for msg in debug_msgs),
            f"Expected debug log 'Unknown color in indicator: Z', got: {cm.output}",
        )

    def test_parse_card_invalid_color_no_warning(self):
        """Test that invalid colors do not produce warning-level logs."""
        archidekt = Archidekt()

        data = {
            "id": "card-invalid-color",
            "name": "Invalid Color Card",
            "colors": ["X"],
        }

        # assertNoLogs verifies no records at WARNING or above are emitted.
        with self.assertNoLogs("pymtg.providers.archidekt", level="WARNING"):
            archidekt._parse_card(data)


class TestArchidektParseDeck(unittest.TestCase):
    """Test Archidekt._parse_deck() method."""

    def test_parse_simple_deck(self):
        """Test parsing a simple deck with main cards only."""
        archidekt = Archidekt()

        # Mock the _parse_card method to return simple Card objects
        with patch.object(archidekt, "_parse_card") as mock_parse_card:
            mock_parse_card.side_effect = [
                Card(id="card1", name="Card 1", source="archidekt"),
                Card(id="card2", name="Card 2", source="archidekt"),
            ]

            data = {
                "id": "deck-123",
                "uuid": "deck-123",
                "name": "Test Deck",
                "description": "A test deck",
                "format": "commander",
                "cards": [
                    {"quantity": 4, "card": {"id": "card1"}},
                    {"quantity": 2, "card": {"id": "card2"}},
                ],
                "owner": {"name": "test_user", "id": "user-123"},
                "is_public": True,
                "created_at": "2024-01-01",
                "updated_at": "2024-01-02",
                "tags": ["test"],
                "category": "casual",
            }

            deck = archidekt._parse_deck(data)

            self.assertIsInstance(deck, Deck)
            self.assertEqual(deck.id, "deck-123")
            self.assertEqual(deck.name, "Test Deck")
            self.assertEqual(deck.description, "A test deck")
            self.assertEqual(deck.format, Format.COMMANDER)
            self.assertEqual(deck.owner, "test_user")
            self.assertEqual(deck.owner_id, "user-123")
            self.assertEqual(deck.privacy, "public")
            cards = deck.cards or []
            self.assertEqual(len(cards), 2)
            self.assertEqual(cards[0].count, 4)
            self.assertEqual(cards[1].count, 2)

    def test_parse_deck_with_sideboard_and_commander(self):
        """Test parsing a deck with sideboard and commander sections."""
        archidekt = Archidekt()

        # Mock the _parse_card method
        with patch.object(archidekt, "_parse_card") as mock_parse_card:
            mock_parse_card.side_effect = [
                Card(id="main1", name="Main 1", source="archidekt"),
                Card(id="main2", name="Main 2", source="archidekt"),
                Card(id="side1", name="Side 1", source="archidekt"),
                Card(id="cmd1", name="Commander", source="archidekt"),
            ]

            data = {
                "id": "deck-456",
                "name": "EDH Deck",
                "format": "commander",
                "cards": [
                    {"quantity": 4, "card": {"id": "main1"}, "board": "main"},
                    {"quantity": 2, "card": {"id": "main2"}, "board": "main"},
                ],
                "sideboard": [
                    {"quantity": 3, "card": {"id": "side1"}},
                ],
                "commanders": [
                    {"card": {"id": "cmd1"}},
                ],
            }

            deck = archidekt._parse_deck(data)

            self.assertIsInstance(deck, Deck)
            self.assertEqual(deck.id, "deck-456")
            self.assertEqual(deck.name, "EDH Deck")
            cards = deck.cards or []
            self.assertEqual(len(cards), 4)

            # Check that cards have correct boards
            main_cards = [c for c in cards if c.board == Board.MAIN]
            side_cards = [c for c in cards if c.board == Board.SIDEBOARD]
            cmd_cards = [c for c in cards if c.board == Board.COMMANDER]

            self.assertEqual(len(main_cards), 2)
            self.assertEqual(len(side_cards), 1)
            self.assertEqual(len(cmd_cards), 1)

    def test_parse_empty_deck(self):
        """Test parsing a deck with no cards."""
        archidekt = Archidekt()

        data = {
            "id": "deck-789",
            "name": "Empty Deck",
            "format": "standard",
            "cards": [],
        }

        deck = archidekt._parse_deck(data)

        self.assertIsInstance(deck, Deck)
        self.assertEqual(deck.id, "deck-789")
        self.assertEqual(deck.name, "Empty Deck")
        cards = deck.cards or []
        self.assertEqual(len(cards), 0)

    def test_parse_deck_skips_invalid_card_data_in_main(self):
        """Test that non-dict entries in main cards are skipped with warning."""
        archidekt = Archidekt()

        with patch.object(archidekt, "_parse_card") as mock_parse_card:
            mock_parse_card.side_effect = [
                Card(id="card1", name="Card 1", source="archidekt"),
            ]

            data = {
                "id": "deck-1",
                "name": "Test",
                "cards": [
                    "not-a-dict",
                    42,
                    {"quantity": 4, "card": {"id": "card1"}},
                ],
            }

            deck = archidekt._parse_deck(data)

            cards = deck.cards or []
            self.assertEqual(len(cards), 1)
            self.assertEqual(mock_parse_card.call_count, 1)

    def test_parse_deck_skips_invalid_card_info_in_main(self):
        """Test that entries with non-dict card_info in main are skipped."""
        archidekt = Archidekt()

        with patch.object(archidekt, "_parse_card") as mock_parse_card:
            mock_parse_card.side_effect = [
                Card(id="card1", name="Card 1", source="archidekt"),
            ]

            data = {
                "id": "deck-1",
                "name": "Test",
                "cards": [
                    {"quantity": 4, "card": "not-a-dict"},
                    {"quantity": 2, "card": 123},
                    {"quantity": 1, "card": {"id": "card1"}},
                ],
            }

            deck = archidekt._parse_deck(data)

            cards = deck.cards or []
            self.assertEqual(len(cards), 1)
            self.assertEqual(mock_parse_card.call_count, 1)

    def test_parse_deck_skips_invalid_card_data_in_sideboard(self):
        """Test that non-dict entries in sideboard are skipped."""
        archidekt = Archidekt()

        with patch.object(archidekt, "_parse_card") as mock_parse_card:
            mock_parse_card.side_effect = [
                Card(id="side1", name="Side 1", source="archidekt"),
            ]

            data = {
                "id": "deck-1",
                "name": "Test",
                "cards": [],
                "sideboard": [
                    None,
                    {"quantity": 3, "card": {"id": "side1"}},
                ],
            }

            deck = archidekt._parse_deck(data)

            cards = deck.cards or []
            self.assertEqual(len(cards), 1)
            self.assertEqual(mock_parse_card.call_count, 1)

    def test_parse_deck_skips_invalid_card_info_in_sideboard(self):
        """Test that entries with non-dict card_info in sideboard are skipped."""
        archidekt = Archidekt()

        with patch.object(archidekt, "_parse_card") as mock_parse_card:
            mock_parse_card.side_effect = [
                Card(id="side1", name="Side 1", source="archidekt"),
            ]

            data = {
                "id": "deck-1",
                "name": "Test",
                "cards": [],
                "sideboard": [
                    {"quantity": 3, "card": ["not", "a", "dict"]},
                    {"quantity": 1, "card": {"id": "side1"}},
                ],
            }

            deck = archidekt._parse_deck(data)

            cards = deck.cards or []
            self.assertEqual(len(cards), 1)
            self.assertEqual(mock_parse_card.call_count, 1)

    def test_parse_deck_skips_invalid_card_data_in_commanders(self):
        """Test that non-dict entries in commanders are skipped."""
        archidekt = Archidekt()

        with patch.object(archidekt, "_parse_card") as mock_parse_card:
            mock_parse_card.side_effect = [
                Card(id="cmd1", name="Commander", source="archidekt"),
            ]

            data = {
                "id": "deck-1",
                "name": "Test",
                "cards": [],
                "commanders": [
                    "invalid",
                    {"card": {"id": "cmd1"}},
                ],
            }

            deck = archidekt._parse_deck(data)

            cards = deck.cards or []
            self.assertEqual(len(cards), 1)
            self.assertEqual(mock_parse_card.call_count, 1)

    def test_parse_deck_skips_invalid_card_info_in_commanders(self):
        """Test that entries with non-dict card_info in commanders are skipped."""
        archidekt = Archidekt()

        with patch.object(archidekt, "_parse_card") as mock_parse_card:
            mock_parse_card.side_effect = [
                Card(id="cmd1", name="Commander", source="archidekt"),
            ]

            data = {
                "id": "deck-1",
                "name": "Test",
                "cards": [],
                "commanders": [
                    {"card": 42},
                    {"card": {"id": "cmd1"}},
                ],
            }

            deck = archidekt._parse_deck(data)

            cards = deck.cards or []
            self.assertEqual(len(cards), 1)
            self.assertEqual(mock_parse_card.call_count, 1)

    def test_parse_deck_unknown_format_logs_warning(self):
        """Test that unknown deck format logs a warning and defaults to COMMANDER.

        This test verifies that when an unknown deck format is encountered,
        a warning is logged and the deck defaults to COMMANDER format.
        """
        archidekt = Archidekt()

        with patch.object(archidekt, "_parse_card") as mock_parse_card:
            mock_parse_card.return_value = Card(
                id="card1", name="Card 1", source="archidekt"
            )

            data = {
                "id": "deck-789",
                "name": "Test Deck",
                "format": "unknown_format",
                "cards": [{"quantity": 1, "card": {"id": "card1"}, "board": "main"}],
            }

            with self.assertLogs("pymtg.providers.archidekt", level="WARNING") as log:
                deck = archidekt._parse_deck(data)

            # Verify the deck was created with COMMANDER format
            self.assertEqual(deck.format, Format.COMMANDER)
            # Verify the warning was logged
            self.assertTrue(
                any("Unknown deck format" in record.message for record in log.records)
            )


class TestArchidektBuildSearchQuery(unittest.TestCase):
    """Test Archidekt._build_search_query() method."""

    def test_build_query_with_name(self):
        """Test building query with name parameter."""
        archidekt = Archidekt()
        query = archidekt._build_search_query(name="Black Lotus")

        self.assertIsInstance(query, dict)
        self.assertEqual(query.get("nameSearch"), "Black Lotus")

    def test_build_query_with_colors(self):
        """Test building query with color parameters."""
        archidekt = Archidekt()
        query = archidekt._build_search_query(colors=[Color.BLUE, Color.BLACK])

        self.assertIsInstance(query, dict)
        self.assertEqual(query.get("colors"), "Blue,Black")

    def test_build_query_with_identity(self):
        """Test building query with color identity parameter."""
        archidekt = Archidekt()
        query = archidekt._build_search_query(identity=[Color.WHITE, Color.BLUE])

        self.assertIsInstance(query, dict)
        self.assertEqual(query.get("colorIdentity"), "White,Blue")

    def test_build_query_with_type_line(self):
        """Test building query with type line parameter."""
        archidekt = Archidekt()
        query = archidekt._build_search_query(type_line="Creature")

        self.assertIsInstance(query, dict)
        self.assertEqual(query.get("type"), "Creature")

    def test_build_query_combined(self):
        """Test building query with multiple parameters."""
        archidekt = Archidekt()
        query = archidekt._build_search_query(
            name="Lotus",
            colors=[Color.BLACK],
            type_line="Artifact",
        )

        self.assertIsInstance(query, dict)
        self.assertEqual(query.get("nameSearch"), "Lotus")
        self.assertEqual(query.get("colors"), "Black")
        self.assertEqual(query.get("type"), "Artifact")

    def test_build_query_name_parameter(self):
        """Test that name parameter is correctly set."""
        archidekt = Archidekt()
        query = archidekt._build_search_query(name="Card Name")
        self.assertEqual(query.get("nameSearch"), "Card Name")

    def test_build_query_name_passthrough(self):
        """Test that the name parameter is passed through verbatim to nameSearch.

        The provider intentionally does not sanitize the ``name`` parameter;
        query-injection prevention relies on the HTTP client's parameter
        encoding rather than on escaping performed here. This test documents
        that passthrough behavior so the contract is explicit.
        """
        archidekt = Archidekt()

        # Backslash is passed through unchanged.
        query = archidekt._build_search_query(name="Card\\Name")
        self.assertEqual(query.get("nameSearch"), "Card\\Name")

        # Double quote is passed through unchanged.
        query = archidekt._build_search_query(name='Card"Name')
        self.assertEqual(query.get("nameSearch"), 'Card"Name')


class TestArchidektNormalizeFlavorText(unittest.TestCase):
    """Tests for the _normalize_flavor_text helper method."""

    def test_normalize_flavor_text_string(self):
        """Tests that a string flavor_text is returned as-is."""
        result = Archidekt._normalize_flavor_text("A flavorful card")
        self.assertEqual(result, "A flavorful card")

    def test_normalize_flavor_text_empty_string(self):
        """Tests that an empty string flavor_text returns None."""
        result = Archidekt._normalize_flavor_text("")
        self.assertIsNone(result)

    def test_normalize_flavor_text_none(self):
        """Tests that None flavor_text returns None."""
        result = Archidekt._normalize_flavor_text(None)
        self.assertIsNone(result)

    def test_normalize_flavor_text_list(self):
        """Tests that a list flavor_text is joined into a single string."""
        result = Archidekt._normalize_flavor_text(["Flavor one", "Flavor two"])
        self.assertEqual(result, "Flavor one Flavor two")

    def test_normalize_flavor_text_empty_list(self):
        """Tests that an empty list flavor_text returns None."""
        result = Archidekt._normalize_flavor_text([])
        self.assertIsNone(result)

    def test_normalize_flavor_text_list_with_empty_items(self):
        """Tests that a list with empty items filters them out."""
        result = Archidekt._normalize_flavor_text(["Flavor one", "", "Flavor two"])
        self.assertEqual(result, "Flavor one Flavor two")

    def test_normalize_flavor_text_list_all_empty(self):
        """Tests that a list with all empty items returns None."""
        result = Archidekt._normalize_flavor_text(["", ""])
        self.assertIsNone(result)

    def test_normalize_flavor_text_unsupported_type(self):
        """Tests that unsupported types (e.g. int) return None."""
        result = Archidekt._normalize_flavor_text(42)
        self.assertIsNone(result)

    def test_normalize_flavor_text_list_of_non_strings(self):
        """Tests that a list of non-string items converts them to strings."""
        result = Archidekt._normalize_flavor_text([1, 2, 3])
        self.assertEqual(result, "1 2 3")


class TestArchidektCardFaceFlavorText(unittest.TestCase):
    """Tests for CardFace flavor_text normalization in _parse_card."""

    def test_parse_card_face_flavor_text_string(self):
        """Tests that string flavor_text in card_faces is passed through."""
        archidekt = Archidekt()
        data = {
            "id": "card-1",
            "name": "Test Card",
            "card_faces": [
                {
                    "name": "Face One",
                    "flavor_text": "A string flavor",
                },
            ],
        }
        card = archidekt._parse_card(data)
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        self.assertEqual(card_faces[0].flavor_text, "A string flavor")

    def test_parse_card_face_flavor_text_list(self):
        """Tests that list flavor_text in card_faces is joined to a string.

        This is the core issue #170 scenario: the API may return a list
        for flavor_text, but CardFace.flavor_text is typed as str | None.
        """
        archidekt = Archidekt()
        data = {
            "id": "card-2",
            "name": "Test Card",
            "card_faces": [
                {
                    "name": "Face One",
                    "flavor_text": ["Flavor part one", "Flavor part two"],
                },
            ],
        }
        card = archidekt._parse_card(data)
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        self.assertEqual(
            card_faces[0].flavor_text,
            "Flavor part one Flavor part two",
        )

    def test_parse_card_face_flavor_text_none(self):
        """Tests that None flavor_text in card_faces returns None."""
        archidekt = Archidekt()
        data = {
            "id": "card-3",
            "name": "Test Card",
            "card_faces": [
                {
                    "name": "Face One",
                    "flavor_text": None,
                },
            ],
        }
        card = archidekt._parse_card(data)
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        self.assertIsNone(card_faces[0].flavor_text)

    def test_parse_card_face_flavor_text_missing(self):
        """Tests that missing flavor_text in card_faces returns None."""
        archidekt = Archidekt()
        data = {
            "id": "card-4",
            "name": "Test Card",
            "card_faces": [
                {
                    "name": "Face One",
                },
            ],
        }
        card = archidekt._parse_card(data)
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        self.assertIsNone(card_faces[0].flavor_text)

    def test_parse_card_face_flavor_text_empty_string(self):
        """Tests that empty string flavor_text in card_faces returns None."""
        archidekt = Archidekt()
        data = {
            "id": "card-5",
            "name": "Test Card",
            "card_faces": [
                {
                    "name": "Face One",
                    "flavor_text": "",
                },
            ],
        }
        card = archidekt._parse_card(data)
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        self.assertIsNone(card_faces[0].flavor_text)

    def test_parse_card_face_flavor_text_type_safety(self):
        """Tests that CardFace.flavor_text is always str or None, never list.

        This directly verifies the type safety fix from issue #170: even
        when the API returns a list, the normalized value must be a str
        or None to match the CardFace.flavor_text type annotation.
        """
        archidekt = Archidekt()
        data = {
            "id": "card-6",
            "name": "Test Card",
            "card_faces": [
                {
                    "name": "Face One",
                    "flavor_text": ["A", "B", "C"],
                },
            ],
        }
        card = archidekt._parse_card(data)
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        flavor = card_faces[0].flavor_text
        self.assertIsInstance(flavor, (str, type(None)))


class TestArchidektCardMetadata(unittest.TestCase):
    """Tests for card metadata endpoints (editions, subtypes)."""

    @mock_authenticated_and_http_client
    def test_get_editions_success(self, mock_http_client):
        """Test that get_editions returns list of editions."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "editioncode": "trc",
                "editionname": "Star Trek Commander",
                "editiondate": "2026-11-20",
                "editiontype": "commander",
                "mtgoCode": "trc",
            },
            {
                "editioncode": "fra",
                "editionname": "Reality Fracture",
                "editiondate": "2026-10-02",
                "editiontype": "expansion",
                "mtgoCode": "fra",
            },
        ]
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        editions = archidekt.get_editions()

        self.assertIsInstance(editions, list)
        self.assertEqual(len(editions), 2)
        self.assertEqual(editions[0]["editioncode"], "trc")
        mock_http_client.get.assert_called_once_with("cards/editions/")

    @mock_authenticated_and_http_client
    def test_get_editions_empty(self, mock_http_client):
        """Test that get_editions returns empty list on empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        editions = archidekt.get_editions()

        self.assertIsInstance(editions, list)
        self.assertEqual(len(editions), 0)

    @mock_authenticated_and_http_client
    def test_get_editions_network_error(self, mock_http_client):
        """Test that get_editions raises NetworkError on network failure."""
        mock_http_client.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )

        archidekt = Archidekt()

        with self.assertRaises(NetworkError):
            archidekt.get_editions()

    @mock_authenticated_and_http_client
    def test_get_subtypes_success(self, mock_http_client):
        """Test that get_subtypes returns list of subtypes."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"subtypename": "Angel"},
            {"subtypename": "Zombie"},
            {"subtypename": "Advisor"},
        ]
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        subtypes = archidekt.get_subtypes()

        self.assertIsInstance(subtypes, list)
        self.assertEqual(len(subtypes), 3)
        self.assertEqual(subtypes[0]["subtypename"], "Angel")
        mock_http_client.get.assert_called_once_with("cards/subtypes/")

    @mock_authenticated_and_http_client
    def test_get_subtypes_empty(self, mock_http_client):
        """Test that get_subtypes returns empty list on empty response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        subtypes = archidekt.get_subtypes()

        self.assertIsInstance(subtypes, list)
        self.assertEqual(len(subtypes), 0)


class TestArchidektDeckOrganization(unittest.TestCase):
    """Tests for deck organization endpoints (folders, tags)."""

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_get_folder_success(self, mock_http_client, mock_is_auth):
        """Test that get_folder returns folder data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 1735877,
            "name": "Home",
            "parentFolder": None,
            "private": False,
            "owner": {"id": 1071357, "username": "test_user"},
            "subfolders": [],
            "decks": [],
        }
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        folder = archidekt.get_folder("1735877")

        self.assertIsInstance(folder, dict)
        self.assertEqual(folder["id"], 1735877)
        self.assertEqual(folder["name"], "Home")
        mock_http_client.get.assert_called_once_with(
            "decks/folders/1735877/",
            params={
                "folderId": "1735877",
                "name": "",
                "orderBy": "-updatedAt",
            },
        )

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_get_tags_success(self, mock_http_client, mock_is_auth):
        """Test that get_tags returns list of tags."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": 72,
                "name": "+1/+1 Counters",
                "aliases": "",
                "description": "",
                "created_at": "2023-03-30T12:12:15.761335Z",
            },
            {
                "id": 28,
                "name": "Aggro",
                "aliases": "aggressive sligh creatures",
                "description": "",
                "created_at": "2023-03-30T12:12:15.494531Z",
            },
        ]
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        tags = archidekt.get_tags()

        self.assertIsInstance(tags, list)
        self.assertEqual(len(tags), 2)
        self.assertEqual(tags[0]["name"], "+1/+1 Counters")
        mock_http_client.get.assert_called_once_with("decks/tags/v2/", params={})

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_get_tags_with_query(self, mock_http_client, mock_is_auth):
        """Test that get_tags passes query parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        archidekt.get_tags(q="counters")

        mock_http_client.get.assert_called_once_with(
            "decks/tags/v2/", params={"q": "counters"}
        )

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_delete_folder_items_success(self, mock_http_client, mock_is_auth):
        """Test that delete_folder_items successfully deletes items."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_http_client.post.return_value = mock_response

        archidekt = Archidekt()

        result = archidekt.delete_folder_items([{"id": 24299438, "type": "deck"}])

        self.assertEqual(result["status"], "success")
        mock_http_client.post.assert_called_once_with(
            "decks/folders/deleteItems/",
            json={"items": [{"id": 24299438, "type": "deck"}]},
        )

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_delete_folder_items_empty_list(self, mock_http_client, mock_is_auth):
        """Test that delete_folder_items raises error for empty list."""
        archidekt = Archidekt()

        with self.assertRaises(ArchidektValidationError):
            archidekt.delete_folder_items([])


class TestArchidektSocialFeatures(unittest.TestCase):
    """Tests for social features endpoints (comments, notifications)."""

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_get_comment_success(self, mock_http_client, mock_is_auth):
        """Test that get_comment returns comment data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 24354478,
            "title": None,
            "text": None,
            "owner": {"id": 1071357, "username": "test_user"},
            "deck": {"id": 24299438},
            "childrenCount": 0,
            "children": {"links": {}, "count": 0, "results": []},
            "createdAt": "2026-07-12T18:27:09.242647Z",
            "points": 0,
            "type": 4,
        }
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        comment = archidekt.get_comment("24354478")

        self.assertIsInstance(comment, dict)
        self.assertEqual(comment["id"], 24354478)
        mock_http_client.get.assert_called_once_with(
            "comments/24354478/", params={"page": 1}
        )

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_get_comment_with_page(self, mock_http_client, mock_is_auth):
        """Test that get_comment respects page parameter."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        archidekt.get_comment("24354478", page=2)

        mock_http_client.get.assert_called_once_with(
            "comments/24354478/", params={"page": 2}
        )

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_get_notification_count_success(self, mock_http_client, mock_is_auth):
        """Test that get_notification_count returns notification data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "notificationCount": 0,
            "patreonAccount": None,
        }
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()
        # Set the private _user_id attribute directly (property is read-only)
        archidekt.auth_handler._user_id = "1071357"

        result = archidekt.get_notification_count()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["notificationCount"], 0)
        mock_http_client.get.assert_called_once_with("users/1071357/notificationCount/")

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_get_notification_count_with_user_id(self, mock_http_client, mock_is_auth):
        """Test that get_notification_count uses provided user_id."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "notificationCount": 5,
            "patreonAccount": None,
        }
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()

        result = archidekt.get_notification_count(user_id="123456")

        self.assertEqual(result["notificationCount"], 5)
        mock_http_client.get.assert_called_once_with("users/123456/notificationCount/")

    @patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
    @patch.object(Archidekt, "http_client")
    def test_get_notification_count_no_user(self, mock_http_client, mock_is_auth):
        """Test that get_notification_count raises error without user_id."""
        archidekt = Archidekt()
        # No auth handler user_id set

        with self.assertRaises(ArchidektValidationError):
            archidekt.get_notification_count()


if __name__ == "__main__":
    unittest.main()


def _get_call_json(mock_method):
    """Extract the ``json`` kwarg from a mocked HTTP call.

    Args:
        mock_method: A mocked call object (e.g. ``mock_http_client.post``).

    Returns:
        The payload dict passed as the ``json`` keyword argument.
    """
    _, kwargs = mock_method.call_args
    return kwargs["json"]


# =========================================================================
# PART 1: Fixes for existing endpoints
# =========================================================================


class TestCreateDeckFixes(unittest.TestCase):
    """Tests for the fixed create_deck payload fields."""

    @patch.object(Archidekt, "_parse_deck")
    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_create_deck_with_edh_bracket(
        self, mock_handle_response, mock_parse_deck, mock_http_client
    ):
        """Tests that edh_bracket appears in the create_deck payload."""
        mock_handle_response.return_value = {"id": 1, "name": "D"}
        mock_parse_deck.return_value = Deck(id="1", name="D", source="archidekt")

        archidekt = Archidekt()
        archidekt.create_deck(name="D", edh_bracket=3)

        payload = _get_call_json(mock_http_client.post)
        self.assertEqual(payload["edhBracket"], 3)
        mock_http_client.post.assert_called_once_with("decks/v2/", json=payload)

    @patch.object(Archidekt, "_parse_deck")
    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_create_deck_with_theorycrafted(
        self, mock_handle_response, mock_parse_deck, mock_http_client
    ):
        """Tests that theorycrafted flag appears in the payload."""
        mock_handle_response.return_value = {"id": 1, "name": "D"}
        mock_parse_deck.return_value = Deck(id="1", name="D", source="archidekt")

        archidekt = Archidekt()
        archidekt.create_deck(name="D", theorycrafted=True)

        payload = _get_call_json(mock_http_client.post)
        self.assertTrue(payload["theorycrafted"])

    @patch.object(Archidekt, "_parse_deck")
    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_create_deck_with_commanders(
        self, mock_handle_response, mock_parse_deck, mock_http_client
    ):
        """Tests that commanders_to_add populates extras.commandersToAdd."""
        mock_handle_response.return_value = {"id": 1, "name": "D"}
        mock_parse_deck.return_value = Deck(id="1", name="D", source="archidekt")

        archidekt = Archidekt()
        archidekt.create_deck(name="D", commanders_to_add=["100", "200"])

        payload = _get_call_json(mock_http_client.post)
        self.assertEqual(payload["extras"]["commandersToAdd"], [100, 200])

    @patch.object(Archidekt, "_parse_deck")
    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_create_deck_with_folder_id(
        self, mock_handle_response, mock_parse_deck, mock_http_client
    ):
        """Tests that folder_id is converted to parent_folder int."""
        mock_handle_response.return_value = {"id": 1, "name": "D"}
        mock_parse_deck.return_value = Deck(id="1", name="D", source="archidekt")

        archidekt = Archidekt()
        archidekt.create_deck(name="D", folder_id="1735877")

        payload = _get_call_json(mock_http_client.post)
        self.assertEqual(payload["parent_folder"], 1735877)

    @patch.object(Archidekt, "_parse_deck")
    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_create_deck_minimal(
        self, mock_handle_response, mock_parse_deck, mock_http_client
    ):
        """Tests that minimal create_deck uses sensible defaults."""
        mock_handle_response.return_value = {"id": 1, "name": "D"}
        mock_parse_deck.return_value = Deck(id="1", name="D", source="archidekt")

        archidekt = Archidekt()
        archidekt.create_deck(name="D")

        payload = _get_call_json(mock_http_client.post)
        self.assertEqual(payload["name"], "D")
        self.assertIsNone(payload["edhBracket"])
        self.assertFalse(payload["theorycrafted"])
        self.assertTrue(payload["private"])
        self.assertEqual(payload["extras"]["commandersToAdd"], [])
        self.assertEqual(payload["game"], Archidekt.GAME_ID_PAPER)


class TestAddCardToDeckFixes(unittest.TestCase):
    """Tests for the fixed add_card_to_deck payload and relation tracking."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_add_card_correct_payload(self, mock_handle_response, mock_http_client):
        """Tests that the add payload uses cards array with action add."""
        mock_handle_response.return_value = {"add": [{"deckRelationId": 3286753088}]}

        archidekt = Archidekt()
        archidekt.add_card_to_deck(deck_id="d1", card_id="c1", quantity=2)

        mock_http_client.patch.assert_called_once()
        call_args, call_kwargs = mock_http_client.patch.call_args
        self.assertEqual(call_args[0], "decks/d1/modifyCards/v2/")
        payload = call_kwargs["json"]
        self.assertIn("cards", payload)
        card = payload["cards"][0]
        self.assertEqual(card["action"], "add")
        self.assertEqual(card["cardid"], "c1")
        self.assertEqual(card["modifications"]["quantity"], 2)
        self.assertEqual(card["modifications"]["modifier"], "Normal")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_add_card_with_categories(self, mock_handle_response, mock_http_client):
        """Tests that categories are passed in the card payload."""
        mock_handle_response.return_value = {"add": [{"deckRelationId": 1}]}

        archidekt = Archidekt()
        archidekt.add_card_to_deck(
            deck_id="d1", card_id="c1", categories=["Ramp", "Draw"]
        )

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload["cards"][0]["categories"], ["Ramp", "Draw"])

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_add_card_foil(self, mock_handle_response, mock_http_client):
        """Tests that foil flag sets modifier to Foil."""
        mock_handle_response.return_value = {"add": [{"deckRelationId": 1}]}

        archidekt = Archidekt()
        archidekt.add_card_to_deck(deck_id="d1", card_id="c1", foil=True)

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload["cards"][0]["modifications"]["modifier"], "Foil")

    @patch.object(Archidekt, "_resolve_card_id_by_name")
    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_add_card_by_name(
        self, mock_handle_response, mock_resolve, mock_http_client
    ):
        """Tests that card_name is resolved to a card_id."""
        mock_resolve.return_value = "resolved-123"
        mock_handle_response.return_value = {"add": [{"deckRelationId": 1}]}

        archidekt = Archidekt()
        archidekt.add_card_to_deck(deck_id="d1", card_name="Sol Ring")

        mock_resolve.assert_called_once_with("Sol Ring")
        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload["cards"][0]["cardid"], "resolved-123")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_add_card_extracts_relation_id(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that the deck_relation_id is extracted and stored."""
        mock_handle_response.return_value = {"add": [{"deckRelationId": 3286753088}]}

        archidekt = Archidekt()
        archidekt.add_card_to_deck(deck_id="d1", card_id="c1")

        self.assertEqual(archidekt._deck_relation_map[("d1", "c1")], "3286753088")

    @mock_authenticated_and_http_client
    def test_add_card_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.patch.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.add_card_to_deck(deck_id="d1", card_id="c1")

    @patch.object(Archidekt, "http_client")
    def test_add_card_no_auth(self, mock_http_client):
        """Tests that add_card_to_deck raises when not authenticated."""
        archidekt = Archidekt()
        with self.assertRaises(ArchidektAuthenticationError):
            archidekt.add_card_to_deck(deck_id="d1", card_id="c1")

    @mock_authenticated_and_http_client
    def test_add_card_missing_deck_id(self, mock_http_client):
        """Tests that missing deck_id raises ArchidektValidationError."""
        archidekt = Archidekt()
        with self.assertRaises(ArchidektValidationError):
            archidekt.add_card_to_deck(deck_id="", card_id="c1")

    @mock_authenticated_and_http_client
    def test_add_card_missing_card_id_and_name(self, mock_http_client):
        """Tests that missing card_id and card_name raises validation error."""
        archidekt = Archidekt()
        with self.assertRaises(ArchidektValidationError):
            archidekt.add_card_to_deck(deck_id="d1")


class TestRemoveCardFromDeckFixes(unittest.TestCase):
    """Tests for the fixed remove_card_from_deck payload and relation map."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_remove_card_correct_payload(self, mock_handle_response, mock_http_client):
        """Tests remove payload uses action remove and deckRelationId."""
        mock_handle_response.return_value = {}

        archidekt = Archidekt()
        archidekt.remove_card_from_deck(
            deck_id="d1", card_id="c1", deck_relation_id="rel-1"
        )

        call_args, call_kwargs = mock_http_client.patch.call_args
        self.assertEqual(call_args[0], "decks/d1/modifyCards/v2/")
        payload = call_kwargs["json"]
        card = payload["cards"][0]
        self.assertEqual(card["action"], "remove")
        self.assertEqual(card["cardid"], "c1")
        self.assertEqual(card["deckRelationId"], "rel-1")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_remove_card_with_explicit_relation_id(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that an explicitly provided deck_relation_id is used."""
        mock_handle_response.return_value = {}

        archidekt = Archidekt()
        archidekt.remove_card_from_deck(
            deck_id="d1", card_id="c1", deck_relation_id="explicit-rel"
        )

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload["cards"][0]["deckRelationId"], "explicit-rel")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_remove_card_with_lookup_relation_id(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that deck_relation_id is looked up from the internal map."""
        mock_handle_response.return_value = {}

        archidekt = Archidekt()
        archidekt._deck_relation_map[("d1", "c1")] = "looked-up-rel"

        archidekt.remove_card_from_deck(deck_id="d1", card_id="c1")

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload["cards"][0]["deckRelationId"], "looked-up-rel")

    @mock_authenticated_and_http_client
    def test_remove_card_no_relation_id(self, mock_http_client):
        """Tests that missing relation_id raises ArchidektValidationError."""
        archidekt = Archidekt()
        with self.assertRaises(ArchidektValidationError):
            archidekt.remove_card_from_deck(deck_id="d1", card_id="c1")

    @mock_authenticated_and_http_client
    def test_remove_card_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.patch.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        archidekt._deck_relation_map[("d1", "c1")] = "rel-1"
        with self.assertRaises(NetworkError):
            archidekt.remove_card_from_deck(deck_id="d1", card_id="c1")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_remove_card_clears_relation_map(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that the relation map entry is cleared after removal."""
        mock_handle_response.return_value = {}

        archidekt = Archidekt()
        archidekt._deck_relation_map[("d1", "c1")] = "rel-1"

        archidekt.remove_card_from_deck(
            deck_id="d1", card_id="c1", deck_relation_id="rel-1"
        )

        self.assertNotIn(("d1", "c1"), archidekt._deck_relation_map)


class TestGetFolderFixes(unittest.TestCase):
    """Tests for the fixed get_folder query parameters."""

    @mock_authenticated_and_http_client
    def test_get_folder_with_query_params(self, mock_http_client):
        """Tests that folderId, name, and orderBy params are sent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1735877, "name": "Home"}
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()
        result = archidekt.get_folder("1735877")

        self.assertEqual(result["id"], 1735877)
        mock_http_client.get.assert_called_once_with(
            "decks/folders/1735877/",
            params={
                "folderId": "1735877",
                "name": "",
                "orderBy": "-updatedAt",
            },
        )

    @mock_authenticated_and_http_client
    def test_get_folder_custom_order_by(self, mock_http_client):
        """Tests that a custom order_by value is forwarded."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1}
        mock_http_client.get.return_value = mock_response

        archidekt = Archidekt()
        archidekt.get_folder("1735877", order_by="-name")

        mock_http_client.get.assert_called_once_with(
            "decks/folders/1735877/",
            params={"folderId": "1735877", "name": "", "orderBy": "-name"},
        )

    @mock_authenticated_and_http_client
    def test_get_folder_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.get.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.get_folder("1735877")


# =========================================================================
# PART 2: New deck management methods
# =========================================================================


class TestUpdateDeck(unittest.TestCase):
    """Tests for the update_deck method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_update_deck_name_only(self, mock_handle_response, mock_http_client):
        """Tests that updating only the name sends just the name field."""
        mock_handle_response.return_value = {"name": "New Name"}

        archidekt = Archidekt()
        archidekt.update_deck(deck_id="d1", name="New Name")

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload, {"name": "New Name"})
        mock_http_client.patch.assert_called_once_with("decks/d1/update/", json=payload)

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_update_deck_format(self, mock_handle_response, mock_http_client):
        """Tests that format is mapped to deckFormat in the payload."""
        mock_handle_response.return_value = {"deckFormat": 2}

        archidekt = Archidekt()
        archidekt.update_deck(deck_id="d1", format=Format.MODERN)

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload, {"deckFormat": 2})

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_update_deck_private(self, mock_handle_response, mock_http_client):
        """Tests that the private flag is sent in the payload."""
        mock_handle_response.return_value = {"private": False}

        archidekt = Archidekt()
        archidekt.update_deck(deck_id="d1", private=False)

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload, {"private": False})

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_update_deck_multiple_fields(self, mock_handle_response, mock_http_client):
        """Tests that multiple fields are included in the payload."""
        mock_handle_response.return_value = {"name": "N", "private": True}

        archidekt = Archidekt()
        archidekt.update_deck(deck_id="d1", name="N", private=True, edh_bracket=3)

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload, {"name": "N", "private": True, "edhBracket": 3})

    @mock_authenticated_and_http_client
    def test_update_deck_no_fields(self, mock_http_client):
        """Tests that providing no fields raises ArchidektValidationError."""
        archidekt = Archidekt()
        with self.assertRaises(ArchidektValidationError):
            archidekt.update_deck(deck_id="d1")

    @mock_authenticated_and_http_client
    def test_update_deck_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.patch.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.update_deck(deck_id="d1", name="N")

    @patch.object(Archidekt, "http_client")
    def test_update_deck_no_auth(self, mock_http_client):
        """Tests that update_deck raises when not authenticated."""
        archidekt = Archidekt()
        with self.assertRaises(ArchidektAuthenticationError):
            archidekt.update_deck(deck_id="d1", name="N")


class TestDeleteDeck(unittest.TestCase):
    """Tests for the delete_deck method."""

    @mock_authenticated_and_http_client
    def test_delete_deck_success(self, mock_http_client):
        """Tests that a 204 response returns True."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_http_client.delete.return_value = mock_response

        archidekt = Archidekt()
        result = archidekt.delete_deck("d1")

        self.assertTrue(result)
        mock_http_client.delete.assert_called_once_with("decks/d1/")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_delete_deck_not_found(self, mock_handle_response, mock_http_client):
        """Tests that a non-204 response is delegated to _handle_response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http_client.delete.return_value = mock_response
        mock_handle_response.side_effect = NotFoundError(
            "not found", provider="archidekt", resource_type="deck"
        )

        archidekt = Archidekt()
        with self.assertRaises(NotFoundError):
            archidekt.delete_deck("d1")

    @mock_authenticated_and_http_client
    def test_delete_deck_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.delete.side_effect = requests.exceptions.RequestException(
            "err"
        )

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.delete_deck("d1")

    @patch.object(Archidekt, "http_client")
    def test_delete_deck_no_auth(self, mock_http_client):
        """Tests that delete_deck raises when not authenticated."""
        archidekt = Archidekt()
        with self.assertRaises(ArchidektAuthenticationError):
            archidekt.delete_deck("d1")


class TestCloneDeck(unittest.TestCase):
    """Tests for the clone_deck method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_clone_deck_default_name(self, mock_handle_response, mock_http_client):
        """Tests that a default name is generated when name is None."""
        mock_handle_response.return_value = {"id": 24588192}

        archidekt = Archidekt()
        archidekt.clone_deck(source_deck_id="24588160")

        payload = _get_call_json(mock_http_client.post)
        self.assertEqual(payload["name"], "Copy of deck 24588160")
        self.assertEqual(payload["copyId"], 24588160)
        mock_http_client.post.assert_called_once_with("decks/copy/", json=payload)

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_clone_deck_custom_name(self, mock_handle_response, mock_http_client):
        """Tests that a custom name is used in the payload."""
        mock_handle_response.return_value = {"id": 24588192}

        archidekt = Archidekt()
        archidekt.clone_deck(source_deck_id="24588160", name="My Clone")

        payload = _get_call_json(mock_http_client.post)
        self.assertEqual(payload["name"], "My Clone")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_clone_deck_private(self, mock_handle_response, mock_http_client):
        """Tests that the private flag is forwarded in the payload."""
        mock_handle_response.return_value = {"id": 24588192}

        archidekt = Archidekt()
        archidekt.clone_deck(source_deck_id="24588160", private=False)

        payload = _get_call_json(mock_http_client.post)
        self.assertFalse(payload["private"])

    @mock_authenticated_and_http_client
    def test_clone_deck_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.post.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.clone_deck(source_deck_id="24588160")

    @patch.object(Archidekt, "http_client")
    def test_clone_deck_no_auth(self, mock_http_client):
        """Tests that clone_deck raises when not authenticated."""
        archidekt = Archidekt()
        with self.assertRaises(ArchidektAuthenticationError):
            archidekt.clone_deck(source_deck_id="24588160")


class TestExportDeckPdf(unittest.TestCase):
    """Tests for the export_deck_pdf method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_export_deck_pdf_success(self, mock_handle_response, mock_http_client):
        """Tests that a successful export returns the file URL dict."""
        mock_handle_response.return_value = {
            "fileUrl": "https://storage.googleapis.com/x.pdf"
        }

        archidekt = Archidekt()
        result = archidekt.export_deck_pdf(
            deck_name="My Deck",
            cards=[{"name": "Sol Ring", "quantity": 1}],
        )

        self.assertEqual(result["fileUrl"], "https://storage.googleapis.com/x.pdf")
        mock_http_client.post.assert_called_once_with(
            "decks/exportPdf/",
            json=_get_call_json(mock_http_client.post),
        )

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_export_deck_pdf_with_cards(self, mock_handle_response, mock_http_client):
        """Tests that card entries expand into card_N / card_N_qty keys."""
        mock_handle_response.return_value = {"fileUrl": "url"}

        archidekt = Archidekt()
        archidekt.export_deck_pdf(
            deck_name="D",
            cards=[
                {"name": "Sol Ring", "quantity": 1},
                {"name": "Arcane Signet", "quantity": 2},
            ],
        )

        payload = _get_call_json(mock_http_client.post)
        self.assertEqual(payload["deckName"], "D")
        self.assertEqual(payload["card_0"], "Sol Ring")
        self.assertEqual(payload["card_0_qty"], 1)
        self.assertEqual(payload["card_1"], "Arcane Signet")
        self.assertEqual(payload["card_1_qty"], 2)

    @mock_authenticated_and_http_client
    def test_export_deck_pdf_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.post.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.export_deck_pdf(
                deck_name="D", cards=[{"name": "Sol Ring", "quantity": 1}]
            )


class TestVoteDeck(unittest.TestCase):
    """Tests for the vote_deck method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_vote_deck_upvote(self, mock_handle_response, mock_http_client):
        """Tests that an upvote sends remove=False and returns points."""
        mock_handle_response.return_value = {"points": 1}

        archidekt = Archidekt()
        result = archidekt.vote_deck(deck_id="d1")

        payload = _get_call_json(mock_http_client.put)
        self.assertEqual(payload, {"up": True, "remove": False})
        mock_http_client.put.assert_called_once_with("decks/d1/vote/", json=payload)
        self.assertEqual(result["points"], 1)

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_vote_deck_remove_vote(self, mock_handle_response, mock_http_client):
        """Tests that removing a vote sends remove=True."""
        mock_handle_response.return_value = {"points": 0}

        archidekt = Archidekt()
        archidekt.vote_deck(deck_id="d1", remove=True)

        payload = _get_call_json(mock_http_client.put)
        self.assertTrue(payload["remove"])

    @mock_authenticated_and_http_client
    def test_vote_deck_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.put.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.vote_deck(deck_id="d1")


class TestModifyCards(unittest.TestCase):
    """Tests for the batch modify_cards method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_modify_cards_add_operation(self, mock_handle_response, mock_http_client):
        """Tests that an add operation is constructed correctly."""
        mock_handle_response.return_value = {"add": [{"deckRelationId": 111}]}

        archidekt = Archidekt()
        archidekt.modify_cards(
            deck_id="d1",
            operations=[{"action": "add", "card_id": "c1"}],
        )

        payload = _get_call_json(mock_http_client.patch)
        card = payload["cards"][0]
        self.assertEqual(card["action"], "add")
        self.assertEqual(card["cardid"], "c1")
        self.assertNotIn("deckRelationId", card)

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_modify_cards_remove_operation(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that a remove operation includes deckRelationId."""
        mock_handle_response.return_value = {}

        archidekt = Archidekt()
        archidekt.modify_cards(
            deck_id="d1",
            operations=[
                {
                    "action": "remove",
                    "card_id": "c1",
                    "deck_relation_id": "rel-1",
                }
            ],
        )

        payload = _get_call_json(mock_http_client.patch)
        card = payload["cards"][0]
        self.assertEqual(card["action"], "remove")
        self.assertEqual(card["deckRelationId"], "rel-1")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_modify_cards_modify_operation(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that a modify operation includes deckRelationId."""
        mock_handle_response.return_value = {}

        archidekt = Archidekt()
        archidekt.modify_cards(
            deck_id="d1",
            operations=[
                {
                    "action": "modify",
                    "card_id": "c1",
                    "deck_relation_id": "rel-1",
                    "quantity": 3,
                }
            ],
        )

        payload = _get_call_json(mock_http_client.patch)
        card = payload["cards"][0]
        self.assertEqual(card["action"], "modify")
        self.assertEqual(card["modifications"]["quantity"], 3)
        self.assertEqual(card["deckRelationId"], "rel-1")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_modify_cards_batch_operations(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that multiple operations are sent in a single request."""
        mock_handle_response.return_value = {"add": [{"deckRelationId": 222}]}

        archidekt = Archidekt()
        archidekt.modify_cards(
            deck_id="d1",
            operations=[
                {"action": "add", "card_id": "c1"},
                {
                    "action": "remove",
                    "card_id": "c2",
                    "deck_relation_id": "rel-2",
                },
            ],
        )

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(len(payload["cards"]), 2)
        self.assertEqual(payload["cards"][0]["action"], "add")
        self.assertEqual(payload["cards"][1]["action"], "remove")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_modify_cards_stores_relation_ids(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that relation IDs from add results are stored in the map."""
        mock_handle_response.return_value = {"add": [{"deckRelationId": 3286753088}]}

        archidekt = Archidekt()
        archidekt.modify_cards(
            deck_id="d1",
            operations=[{"action": "add", "card_id": "c1"}],
        )

        self.assertEqual(archidekt._deck_relation_map[("d1", "c1")], "3286753088")

    @mock_authenticated_and_http_client
    def test_modify_cards_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.patch.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.modify_cards(
                deck_id="d1",
                operations=[{"action": "add", "card_id": "c1"}],
            )


# =========================================================================
# PART 3: New folder management methods
# =========================================================================


class TestCreateFolder(unittest.TestCase):
    """Tests for the create_folder method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_create_folder_success(self, mock_handle_response, mock_http_client):
        """Tests that create_folder sends the correct payload."""
        mock_handle_response.return_value = {
            "id": 1755116,
            "name": "folder123",
            "parentFolder": 1735877,
            "private": False,
        }

        archidekt = Archidekt()
        result = archidekt.create_folder(name="folder123", parent_folder_id="1735877")

        self.assertEqual(result["id"], 1755116)
        mock_http_client.post.assert_called_once_with(
            "decks/folders/",
            json={
                "name": "folder123",
                "private": False,
                "parentFolder": "1735877",
            },
        )

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_create_folder_private(self, mock_handle_response, mock_http_client):
        """Tests that the private flag is forwarded in the payload."""
        mock_handle_response.return_value = {"id": 1, "private": True}

        archidekt = Archidekt()
        archidekt.create_folder(name="secret", parent_folder_id="1735877", private=True)

        payload = _get_call_json(mock_http_client.post)
        self.assertTrue(payload["private"])

    @mock_authenticated_and_http_client
    def test_create_folder_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.post.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.create_folder(name="f", parent_folder_id="1735877")

    @patch.object(Archidekt, "http_client")
    def test_create_folder_no_auth(self, mock_http_client):
        """Tests that create_folder raises when not authenticated."""
        archidekt = Archidekt()
        with self.assertRaises(ArchidektAuthenticationError):
            archidekt.create_folder(name="f", parent_folder_id="1735877")


class TestGetFolderTree(unittest.TestCase):
    """Tests for the get_folder_tree method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_folder_tree_success(self, mock_handle_response, mock_http_client):
        """Tests that get_folder_tree returns the folder tree."""
        mock_handle_response.return_value = {
            "id": 1735877,
            "name": "Home",
            "children": None,
            "private": False,
        }

        archidekt = Archidekt()
        result = archidekt.get_folder_tree()

        self.assertEqual(result["id"], 1735877)
        mock_http_client.get.assert_called_once_with("decks/folderTree/")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_folder_tree_with_children(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that nested children are returned in the tree."""
        mock_handle_response.return_value = {
            "id": 1735877,
            "name": "Home",
            "children": [
                {
                    "id": 1755116,
                    "name": "folder123",
                    "children": None,
                    "private": True,
                }
            ],
            "private": False,
        }

        archidekt = Archidekt()
        result = archidekt.get_folder_tree()

        self.assertEqual(len(result["children"]), 1)
        self.assertEqual(result["children"][0]["name"], "folder123")

    @mock_authenticated_and_http_client
    def test_get_folder_tree_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.get.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.get_folder_tree()


class TestMassUpdate(unittest.TestCase):
    """Tests for the mass_update method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_mass_update_move_deck(self, mock_handle_response, mock_http_client):
        """Tests that moving a deck sends the correct patch."""
        mock_handle_response.return_value = [
            {"id": 24588160, "type": "deck", "patch": {}}
        ]

        archidekt = Archidekt()
        archidekt.mass_update(
            items=[
                {
                    "id": 24588160,
                    "type": "deck",
                    "patch": {"parentFolder": 1755116},
                }
            ]
        )

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(
            payload,
            {
                "items": [
                    {
                        "id": 24588160,
                        "type": "deck",
                        "patch": {"parentFolder": 1755116},
                    }
                ]
            },
        )
        mock_http_client.patch.assert_called_once_with("massUpdate/", json=payload)

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_mass_update_rename_folder(self, mock_handle_response, mock_http_client):
        """Tests that renaming a folder sends a name patch."""
        mock_handle_response.return_value = [
            {"id": 1755116, "type": "folder", "patch": {}}
        ]

        archidekt = Archidekt()
        archidekt.mass_update(
            items=[
                {
                    "id": 1755116,
                    "type": "folder",
                    "patch": {"name": "new name"},
                }
            ]
        )

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload["items"][0]["patch"], {"name": "new name"})

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_mass_update_multiple_items(self, mock_handle_response, mock_http_client):
        """Tests that multiple items are batched into one request."""
        mock_handle_response.return_value = [
            {"id": 1, "type": "deck", "patch": {}},
            {"id": 2, "type": "folder", "patch": {}},
        ]

        archidekt = Archidekt()
        archidekt.mass_update(
            items=[
                {"id": 1, "type": "deck", "patch": {"name": "a"}},
                {"id": 2, "type": "folder", "patch": {"name": "b"}},
            ]
        )

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(len(payload["items"]), 2)

    @mock_authenticated_and_http_client
    def test_mass_update_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.patch.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.mass_update(items=[{"id": 1, "type": "deck", "patch": {}}])


class TestSynchronizeCategories(unittest.TestCase):
    """Tests for the synchronize_categories method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_synchronize_categories_success(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that categories are sent and the response returned."""
        categories = [
            {
                "id": 309550737,
                "name": "Maybeboard",
                "isPremier": False,
                "includedInDeck": True,
                "includedInPrice": False,
            }
        ]
        mock_handle_response.return_value = {"categories": categories}

        archidekt = Archidekt()
        result = archidekt.synchronize_categories(deck_id="d1", categories=categories)

        payload = _get_call_json(mock_http_client.patch)
        self.assertEqual(payload, {"categories": categories})
        mock_http_client.patch.assert_called_once_with(
            "decks/d1/synchronizeCategories/", json=payload
        )
        self.assertEqual(result["categories"], categories)

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_synchronize_categories_with_new_category(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that a new category (id=None) is accepted."""
        categories = [
            {
                "id": None,
                "name": "New Cat",
                "isPremier": False,
                "includedInDeck": True,
                "includedInPrice": True,
            }
        ]
        mock_handle_response.return_value = {
            "categories": [
                {
                    "id": 309550738,
                    "name": "New Cat",
                    "isPremier": False,
                    "includedInDeck": True,
                    "includedInPrice": True,
                }
            ]
        }

        archidekt = Archidekt()
        result = archidekt.synchronize_categories(deck_id="d1", categories=categories)

        payload = _get_call_json(mock_http_client.patch)
        self.assertIsNone(payload["categories"][0]["id"])
        self.assertEqual(result["categories"][0]["id"], 309550738)

    @mock_authenticated_and_http_client
    def test_synchronize_categories_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.patch.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.synchronize_categories(deck_id="d1", categories=[])


class TestMassDeckEdit(unittest.TestCase):
    """Tests for the mass_deck_edit method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_mass_deck_edit_success(self, mock_handle_response, mock_http_client):
        """Tests that a successful edit returns the diff operations."""
        mock_handle_response.return_value = {
            "toAdd": [{"card": "Sol Ring"}],
            "toRemove": [],
            "cardErrors": [],
            "syntaxErrors": [],
            "categories": {},
        }

        archidekt = Archidekt()
        result = archidekt.mass_deck_edit(current="1 Sol Ring", edit="2 Sol Ring")

        payload = _get_call_json(mock_http_client.post)
        self.assertEqual(
            payload,
            {
                "parser": "archidekt",
                "current": "1 Sol Ring",
                "edit": "2 Sol Ring",
            },
        )
        mock_http_client.post.assert_called_once_with(
            "cards/massDeckEdit/", json=payload
        )
        self.assertEqual(len(result["toAdd"]), 1)

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_mass_deck_edit_with_card_errors(
        self, mock_handle_response, mock_http_client
    ):
        """Tests that card resolution errors are surfaced in the response."""
        mock_handle_response.return_value = {
            "toAdd": [],
            "toRemove": [],
            "cardErrors": [{"card": "Unknown Card"}],
            "syntaxErrors": [],
            "categories": {},
        }

        archidekt = Archidekt()
        result = archidekt.mass_deck_edit(
            current="1 Unknown Card", edit="2 Unknown Card"
        )

        self.assertEqual(len(result["cardErrors"]), 1)

    @mock_authenticated_and_http_client
    def test_mass_deck_edit_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.post.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.mass_deck_edit(current="a", edit="b")


# =========================================================================
# PART 4: New social features
# =========================================================================


class TestCreateComment(unittest.TestCase):
    """Tests for the create_comment method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_create_comment_plain_text(self, mock_handle_response, mock_http_client):
        """Tests that plain text is converted to Quill Delta JSON format."""
        mock_handle_response.return_value = {"id": 24644125}

        archidekt = Archidekt()
        archidekt.create_comment(parent_id="24644008", text="test comment")

        payload = _get_call_json(mock_http_client.post)
        self.assertEqual(payload["parent"], 24644008)
        expected_delta = json.dumps({"ops": [{"insert": "test comment\n"}]})
        self.assertEqual(payload["text"], expected_delta)
        mock_http_client.post.assert_called_once_with(
            "comments/createComment/", json=payload
        )

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_create_comment_response(self, mock_handle_response, mock_http_client):
        """Tests that the created comment object is returned."""
        mock_handle_response.return_value = {
            "id": 24644125,
            "text": '{"ops":[{"insert":"hi\\n"}]}',
            "parent": 24644008,
            "owner": {"id": 1071357, "username": "test_user"},
            "createdAt": "2026-07-22T14:10:53.999531Z",
            "archived": False,
            "children": [],
            "childrenCount": 0,
            "points": 0,
        }

        archidekt = Archidekt()
        result = archidekt.create_comment(parent_id="24644008", text="hi")

        self.assertEqual(result["id"], 24644125)
        self.assertEqual(result["parent"], 24644008)

    @mock_authenticated_and_http_client
    def test_create_comment_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.post.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.create_comment(parent_id="24644008", text="hi")


class TestGetNotifications(unittest.TestCase):
    """Tests for the get_notifications method."""

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    def test_get_notifications_success(self, mock_http_client, mock_handle_response):
        """Tests that notifications are returned for a given user_id."""
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response
        mock_handle_response.return_value = {
            "notifications": [{"id": 1, "type": "vote"}]
        }

        archidekt = Archidekt()
        result = archidekt.get_notifications(user_id="1071357")

        self.assertEqual(len(result["notifications"]), 1)
        mock_http_client.get.assert_called_once_with("users/1071357/notifications/")

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    def test_get_notifications_empty(self, mock_http_client, mock_handle_response):
        """Tests that an empty notification list is returned as-is."""
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response
        mock_handle_response.return_value = {"notifications": []}

        archidekt = Archidekt()
        result = archidekt.get_notifications(user_id="1071357")

        self.assertEqual(result["notifications"], [])

    @patch.object(Archidekt, "_handle_response")
    @patch.object(Archidekt, "http_client")
    def test_get_notifications_uses_auth_user_id(
        self, mock_http_client, mock_handle_response
    ):
        """Tests that the authenticated user's ID is used when no user_id."""
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response
        mock_handle_response.return_value = {"notifications": []}

        archidekt = Archidekt()
        archidekt.auth_handler._user_id = "1071357"

        archidekt.get_notifications()

        mock_http_client.get.assert_called_once_with("users/1071357/notifications/")

    @patch.object(Archidekt, "http_client")
    def test_get_notifications_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.get.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.get_notifications(user_id="1071357")


class TestGetFollowers(unittest.TestCase):
    """Tests for the get_followers method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_followers_success(self, mock_handle_response, mock_http_client):
        """Tests that followers are returned for a given user."""
        mock_handle_response.return_value = {
            "count": 1,
            "next": None,
            "previous": None,
            "results": [{"id": 1, "username": "follower1"}],
        }

        archidekt = Archidekt()
        result = archidekt.get_followers(user_id="1071357")

        self.assertEqual(result["count"], 1)
        self.assertEqual(len(result["results"]), 1)
        mock_http_client.get.assert_called_once_with("users/1071357/followers/")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_followers_empty(self, mock_handle_response, mock_http_client):
        """Tests that an empty followers list is returned as-is."""
        mock_handle_response.return_value = {
            "count": 0,
            "next": None,
            "previous": None,
            "results": [],
        }

        archidekt = Archidekt()
        result = archidekt.get_followers(user_id="1071357")

        self.assertEqual(result["count"], 0)
        self.assertEqual(result["results"], [])

    @mock_authenticated_and_http_client
    def test_get_followers_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.get.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.get_followers(user_id="1071357")


class TestGetFollowing(unittest.TestCase):
    """Tests for the get_following method."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_following_success(self, mock_handle_response, mock_http_client):
        """Tests that the following list is returned for a given user."""
        mock_handle_response.return_value = {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [
                {"id": 1, "username": "a"},
                {"id": 2, "username": "b"},
            ],
        }

        archidekt = Archidekt()
        result = archidekt.get_following(user_id="1071357")

        self.assertEqual(result["count"], 2)
        self.assertEqual(len(result["results"]), 2)
        mock_http_client.get.assert_called_once_with("users/1071357/following/")

    @mock_authenticated_and_http_client
    def test_get_following_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.get.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.get_following(user_id="1071357")


# =========================================================================
# PART 5: New deck discovery methods
# =========================================================================


class TestCuratedDecks(unittest.TestCase):
    """Tests for the curated deck discovery methods."""

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_curated_decks_success(self, mock_handle_response, mock_http_client):
        """Tests that curated decks are returned."""
        mock_handle_response.return_value = {"results": [{"id": 1, "name": "Deck 1"}]}

        archidekt = Archidekt()
        result = archidekt.get_curated_decks()

        self.assertEqual(len(result["results"]), 1)
        mock_http_client.get.assert_called_once_with("decks/curated/self/")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_curated_decks_empty(self, mock_handle_response, mock_http_client):
        """Tests that an empty curated deck list is returned as-is."""
        mock_handle_response.return_value = {"results": []}

        archidekt = Archidekt()
        result = archidekt.get_curated_decks()

        self.assertEqual(result["results"], [])

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_recent_decks_success(self, mock_handle_response, mock_http_client):
        """Tests that recent decks are returned from the correct endpoint."""
        mock_handle_response.return_value = {"results": [{"id": 2, "name": "Recent"}]}

        archidekt = Archidekt()
        result = archidekt.get_recent_decks()

        self.assertEqual(len(result["results"]), 1)
        mock_http_client.get.assert_called_once_with("decks/curated/self-recent/")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_followed_decks_success(self, mock_handle_response, mock_http_client):
        """Tests that followed decks are returned from the correct endpoint."""
        mock_handle_response.return_value = {"results": [{"id": 3, "name": "Followed"}]}

        archidekt = Archidekt()
        result = archidekt.get_followed_decks()

        self.assertEqual(len(result["results"]), 1)
        mock_http_client.get.assert_called_once_with("decks/curated/followed/")

    @patch.object(Archidekt, "_handle_response")
    @mock_authenticated_and_http_client
    def test_get_packages_success(self, mock_handle_response, mock_http_client):
        """Tests that packages are returned from the correct endpoint."""
        mock_handle_response.return_value = {"results": [{"id": 4, "name": "Package"}]}

        archidekt = Archidekt()
        result = archidekt.get_packages()

        self.assertEqual(len(result["results"]), 1)
        mock_http_client.get.assert_called_once_with("decks/curated/self-packages/")

    @mock_authenticated_and_http_client
    def test_get_curated_decks_network_error(self, mock_http_client):
        """Tests that network errors raise NetworkError."""
        mock_http_client.get.side_effect = requests.exceptions.RequestException("err")

        archidekt = Archidekt()
        with self.assertRaises(NetworkError):
            archidekt.get_curated_decks()


if __name__ == "__main__":
    unittest.main()
