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
from pymtg.providers.archidekt.exceptions import ArchidektValidationError
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

        mock_auth.assert_called_once()

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

        # Mock empty response data
        mock_handle_response.return_value = []

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
        assert card.card_faces is not None
        self.assertEqual(card.card_faces[0].flavor_text, "A string flavor")

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
        assert card.card_faces is not None
        self.assertEqual(
            card.card_faces[0].flavor_text,
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
        assert card.card_faces is not None
        self.assertIsNone(card.card_faces[0].flavor_text)

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
        assert card.card_faces is not None
        self.assertIsNone(card.card_faces[0].flavor_text)

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
        assert card.card_faces is not None
        self.assertIsNone(card.card_faces[0].flavor_text)

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
        assert card.card_faces is not None
        flavor = card.card_faces[0].flavor_text
        self.assertIn(type(flavor), (str, type(None)))


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
        mock_http_client.get.assert_called_once_with("decks/folders/1735877/")

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
