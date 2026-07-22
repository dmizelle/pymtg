"""Tests for the Moxfield provider.

This module contains unit tests for the Moxfield provider implementation,
covering all major functionality including authentication, deck retrieval,
card search, and error handling.

Note:
    The Moxfield API is accessed via the Parse.bot wrapper service, which requires
    an API key. These tests use mocked responses to verify the provider's
    behavior without requiring actual API credentials or network access.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from pymtg.auth.api_key import APIKeyAuthHandler
from pymtg.exceptions import (
    APIError,
    AuthenticationError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from pymtg.models.card import Card
from pymtg.models.enums import Board, Color, Format, Rarity
from pymtg.providers.base import BaseProvider
from pymtg.providers.moxfield import Moxfield


class TestMoxfieldInitialization(unittest.TestCase):
    """Test Moxfield provider initialization."""

    def test_default_initialization(self):
        """Test that Moxfield provider initializes correctly with default parameters."""
        moxfield = Moxfield()
        self.assertEqual(moxfield.name, "moxfield")
        self.assertEqual(
            moxfield.base_url,
            "https://api.parse.bot/scraper/55189296-4a3a-4cd2-a006-802b22cd2b73/",
        )
        self.assertIsNotNone(moxfield.http_client)
        self.assertIsNotNone(moxfield.config)
        self.assertIsNotNone(moxfield.auth_handler)
        self.assertIsInstance(moxfield.auth_handler, APIKeyAuthHandler)

    def test_initialization_with_api_key(self):
        """Test that Moxfield provider initializes with API key."""
        moxfield = Moxfield(api_key="test-api-key")
        self.assertEqual(moxfield.name, "moxfield")
        self.assertTrue(moxfield.is_authenticated())

    def test_init_api_key_set_after_successful_init(self):
        """Test that _api_key is set after successful initialization.

        Verifies that api_key is stored following super().__init__() so the
        attribute is present once the object is fully constructed.
        """
        moxfield = Moxfield(api_key="test-api-key")
        self.assertEqual(moxfield._api_key, "test-api-key")

    def test_init_api_key_not_set_if_super_init_fails(self):
        """Test that _api_key is not set if super().__init__() raises.

        Verifies the fix for issue #189: api_key is stored after
        super().__init__() so that if parent initialization fails, the object
        is not left in an inconsistent state with _api_key set but base
        attributes missing.
        """
        with patch.object(
            BaseProvider, "__init__", side_effect=RuntimeError("init failed")
        ):
            instance = Moxfield.__new__(Moxfield)
            with self.assertRaises(RuntimeError):
                Moxfield.__init__(instance, api_key="test-api-key")
            self.assertFalse(hasattr(instance, "_api_key"))

    def test_init_api_key_none_set_after_successful_init(self):
        """Test that _api_key is None after successful init without api_key.

        Verifies that _api_key is set to None (not missing) when no api_key
        is provided, since the attribute is stored after super().__init__().
        """
        moxfield = Moxfield()
        self.assertIsNone(moxfield._api_key)

    def test_is_authenticated_without_api_key(self):
        """Test that is_authenticated returns False without API key."""
        moxfield = Moxfield()
        self.assertFalse(moxfield.is_authenticated())

    def test_is_authenticated_with_api_key(self):
        """Test that is_authenticated returns True with API key."""
        moxfield = Moxfield(api_key="test-api-key")
        self.assertTrue(moxfield.is_authenticated())

    def test_rate_limit_status(self):
        """Test that rate limit status returns correct information."""
        moxfield = Moxfield()
        status = moxfield.get_rate_limit_status()
        self.assertIn("requests_per_minute", status)
        self.assertEqual(status["requests_per_minute"], 100)

    def test_repr(self):
        """Test string representation of Moxfield provider."""
        moxfield = Moxfield()
        repr_str = repr(moxfield)
        self.assertIn("Moxfield", repr_str)
        self.assertIn("moxfield", repr_str)
        self.assertIn("not authenticated", repr_str)

        moxfield_auth = Moxfield(api_key="test-key")
        repr_str_auth = repr(moxfield_auth)
        self.assertIn("authenticated", repr_str_auth)


class TestMoxfieldAuthentication(unittest.TestCase):
    """Test Moxfield authentication methods."""

    def test_authenticate_with_valid_api_key(self):
        """Tests authentication with a valid API key."""
        moxfield = Moxfield()
        moxfield.authenticate("test-api-key")
        self.assertTrue(moxfield.is_authenticated())

    def test_authenticate_sets_api_key(self):
        """Tests that authenticate stores the API key on both provider and handler.

        Verifies that the API key passed to authenticate() is stored on both
        the Moxfield provider instance (_api_key) and the auth_handler
        (api_key property), ensuring authentication is backed by a real key.
        """
        moxfield = Moxfield()
        self.assertFalse(moxfield.is_authenticated())
        moxfield.authenticate("new-api-key")
        self.assertTrue(moxfield.is_authenticated())
        self.assertEqual(moxfield._api_key, "new-api-key")
        self.assertEqual(moxfield.auth_handler.api_key, "new-api-key")

    def test_refresh_auth_with_valid_api_key(self):
        """Tests authentication refresh with a valid API key."""
        moxfield = Moxfield(api_key="test-api-key")
        moxfield.refresh_auth()
        self.assertTrue(moxfield.is_authenticated())

    def test_refresh_auth_without_api_key(self):
        """Test that refresh_auth raises error without API key."""
        moxfield = Moxfield()
        with self.assertRaises(AuthenticationError):
            moxfield.refresh_auth()


class TestMoxfieldGetCard(unittest.TestCase):
    """Test Moxfield.get_card() method."""

    def test_get_card_returns_card(self):
        """Tests that get_card returns a card by ID."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "moxfield-card-123",
            "name": "Black Lotus",
            "scryfall_id": "38625902-0567-4f24-85b0-a00843553997",
            "mana_cost": "{0}",
            "type_line": "Artifact",
            "oracle_text": "{T}, Sacrifice this artifact: Add seven mana.",
            "rarity": "mythic",
            "color_identity": [],
            "colors": [],
            "cmc": 0.0,
        }
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            result = moxfield.get_card("moxfield-card-123")
        self.assertEqual(result.name, "Black Lotus")
        self.assertEqual(result.source, "moxfield")

    def test_get_card_not_found(self):
        """Test that get_card raises NotFoundError when card not found."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            with self.assertRaises(NotFoundError):
                moxfield.get_card("non-existent-card")

    def test_get_card_network_error(self):
        """Test that get_card raises NetworkError on network failure."""
        moxfield = Moxfield(api_key="test-key")
        with patch.object(
            moxfield.http_client,
            "get",
            side_effect=requests.exceptions.RequestException("Network error"),
        ):
            with self.assertRaises(NetworkError):
                moxfield.get_card("test-card-id")

    def test_get_card_requires_auth(self):
        """Test that get_card raises AuthenticationError without API key."""
        moxfield = Moxfield()
        with self.assertRaises(AuthenticationError):
            moxfield.get_card("test-card-id")

    def test_get_card_rate_limit_error(self):
        """Test that get_card raises RateLimitError on 429 status.

        Verifies that get_card handles HTTP 429 rate limit responses
        consistently with search, matching the coverage of
        TestMoxfieldErrorHandling.test_handle_rate_limit_error.
        """
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            with self.assertRaises(RateLimitError):
                moxfield.get_card("test-card-id")

    def test_get_card_server_error(self):
        """Test that get_card raises APIError on 5xx server error."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            with self.assertRaises(APIError):
                moxfield.get_card("test-card-id")


class TestMoxfieldSearch(unittest.TestCase):
    """Test Moxfield.search() method."""

    def test_search_returns_results(self):
        """Tests that search returns card results.

        This test verifies that the correct endpoint and query parameters are
        passed to the HTTP client, including the built query string and limit.
        """
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "card-1",
                "name": "Black Lotus",
                "mana_cost": "{0}",
                "type_line": "Artifact",
                "rarity": "mythic",
            }
        ]
        with patch.object(
            moxfield.http_client, "get", return_value=mock_response
        ) as mock_get:
            result = moxfield.search(name="Black Lotus", limit=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Black Lotus")
        # Verify HTTP client was called with correct URL and params
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "/cards/search")
        self.assertEqual(
            call_args[1]["params"],
            {"query": '"Black Lotus"', "limit": 5},
        )

    def test_search_empty_results(self):
        """Tests that search returns empty list when no results.

        This test verifies that the correct endpoint and query parameters are
        passed to the HTTP client even when no results are returned.
        """
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        with patch.object(
            moxfield.http_client, "get", return_value=mock_response
        ) as mock_get:
            result = moxfield.search(name="Non-existent Card")
        self.assertEqual(result, [])
        # Verify HTTP client was called with correct URL and params
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "/cards/search")
        self.assertEqual(
            call_args[1]["params"],
            {"query": '"Non-existent Card"', "limit": 20},
        )

    def test_search_network_error(self):
        """Test that search raises NetworkError on network failure."""
        moxfield = Moxfield(api_key="test-key")
        with patch.object(
            moxfield.http_client,
            "get",
            side_effect=requests.exceptions.RequestException("Network error"),
        ):
            with self.assertRaises(NetworkError):
                moxfield.search(name="Test")

    def test_search_requires_auth(self):
        """Test that search raises AuthenticationError without API key."""
        moxfield = Moxfield()
        with self.assertRaises(AuthenticationError):
            moxfield.search(name="Test")

    def test_build_search_query_name_only(self):
        """Test query building with name only."""
        moxfield = Moxfield(api_key="test-key")
        result = moxfield._build_search_query(name="Black Lotus")
        self.assertEqual(result, '"Black Lotus"')

    def test_build_search_query_with_colors(self):
        """Test query building with a single color (include)."""
        moxfield = Moxfield(api_key="test-key")
        result = moxfield._build_search_query(name="Lotus", colors=[Color.BLUE])
        self.assertEqual(result, '"Lotus" c:U')

    def test_build_search_query_with_multiple_colors(self):
        """Test query building with multiple colors (include)."""
        moxfield = Moxfield(api_key="test-key")
        result = moxfield._build_search_query(
            name="Lotus", colors=[Color.BLUE, Color.BLACK]
        )
        self.assertEqual(result, '"Lotus" ci:UB')

    def test_build_search_query_with_identity(self):
        """Test query building with exact color identity match."""
        moxfield = Moxfield(api_key="test-key")
        result = moxfield._build_search_query(
            name="Lotus", identity=[Color.RED, Color.GREEN]
        )
        self.assertEqual(result, '"Lotus" id:RG')

    def test_build_search_query_colors_and_identity_distinct(self):
        """Test that colors and identity produce distinct operators."""
        moxfield = Moxfield(api_key="test-key")
        colors_result = moxfield._build_search_query(colors=[Color.BLUE])
        identity_result = moxfield._build_search_query(identity=[Color.BLUE])
        self.assertNotEqual(colors_result, identity_result)
        self.assertEqual(colors_result, "c:U")
        self.assertEqual(identity_result, "id:U")


class TestMoxfieldSearchSyntax(unittest.TestCase):
    """Test Moxfield.search_syntax() method."""

    def test_search_syntax_returns_results(self):
        """Tests that search_syntax returns results for a syntax query.

        This test verifies that the correct endpoint and query parameters are
        passed to the HTTP client, including the raw query string and limit.
        """
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "card-1",
                "name": "Island",
                "mana_cost": "{0}",
                "type_line": "Land",
                "rarity": "common",
            }
        ]
        with patch.object(
            moxfield.http_client, "get", return_value=mock_response
        ) as mock_get:
            result = moxfield.search_syntax("t:Land", limit=10)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "Island")
        # Verify HTTP client was called with correct URL and params
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "/cards/search")
        self.assertEqual(
            call_args[1]["params"],
            {"query": "t:Land", "limit": 10},
        )

    def test_search_syntax_requires_auth(self):
        """Test that search_syntax raises AuthenticationError without API key."""
        moxfield = Moxfield()
        with self.assertRaises(AuthenticationError):
            moxfield.search_syntax("t:Land")

    def test_search_syntax_network_error(self):
        """Test that search_syntax raises NetworkError on network failure."""
        moxfield = Moxfield(api_key="test-key")
        with patch.object(
            moxfield.http_client,
            "get",
            side_effect=requests.exceptions.RequestException("Network error"),
        ):
            with self.assertRaises(NetworkError):
                moxfield.search_syntax("t:Land")


class TestMoxfieldGetDeck(unittest.TestCase):
    """Test Moxfield.get_deck() method."""

    def test_get_deck_returns_deck(self):
        """Tests that get_deck returns a deck by ID."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "deck-123",
            "name": "Test Deck",
            "format": "commander",
            "cards": [],
        }
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            result = moxfield.get_deck("deck-123")
        self.assertEqual(result.id, "deck-123")
        self.assertEqual(result.name, "Test Deck")
        self.assertEqual(result.format, Format.COMMANDER)

    def test_get_deck_requires_auth(self):
        """Test that get_deck raises AuthenticationError without API key."""
        moxfield = Moxfield()
        with self.assertRaises(AuthenticationError):
            moxfield.get_deck("deck-123")

    def test_get_deck_not_found(self):
        """Test that get_deck raises NotFoundError when deck not found."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            with self.assertRaises(NotFoundError):
                moxfield.get_deck("non-existent-deck")


class TestMoxfieldGetDeckFull(unittest.TestCase):
    """Test Moxfield.get_deck_full() method."""

    def test_get_deck_full_returns_deck(self):
        """Tests that get_deck_full returns a full deck."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "deck-123",
            "name": "Full Test Deck",
            "format": "commander",
            "cards": [],
        }
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            result = moxfield.get_deck_full("deck-123")
        self.assertEqual(result.id, "deck-123")
        self.assertEqual(result.name, "Full Test Deck")


class TestMoxfieldGetUserDecks(unittest.TestCase):
    """Test Moxfield.get_user_decks() method."""

    def test_get_user_decks_returns_decks(self):
        """Tests that get_user_decks returns user decks."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "deck-1",
                "name": "Deck 1",
                "format": "commander",
                "cards": [],
            },
            {
                "id": "deck-2",
                "name": "Deck 2",
                "format": "modern",
                "cards": [],
            },
        ]
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            result = moxfield.get_user_decks("test-user")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, "deck-1")
        self.assertEqual(result[1].id, "deck-2")

    def test_get_user_decks_requires_auth(self):
        """Test that get_user_decks raises AuthenticationError without API key."""
        moxfield = Moxfield()
        with self.assertRaises(AuthenticationError):
            moxfield.get_user_decks("test-user")


class TestMoxfieldAutocomplete(unittest.TestCase):
    """Test Moxfield.autocomplete() method."""

    def test_autocomplete_returns_list(self):
        """Tests that autocomplete returns results from a list response."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = ["Black Lotus", "Island", "Mountain"]
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            result = moxfield.autocomplete("Bl")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "Black Lotus")

    def test_autocomplete_returns_dict(self):
        """Tests that autocomplete returns results from a dict response."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "suggestions": ["Counterspell", "Cyclonic Rift"]
        }
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            result = moxfield.autocomplete("Coun")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "Counterspell")

    def test_autocomplete_requires_auth(self):
        """Test that autocomplete raises AuthenticationError without API key."""
        moxfield = Moxfield()
        with self.assertRaises(AuthenticationError):
            moxfield.autocomplete("test")


class TestMoxfieldCardParsing(unittest.TestCase):
    """Test Moxfield card parsing functionality."""

    def test_parse_card_basic(self):
        """Test parsing a basic card."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "card-123",
            "scryfall_id": "scryfall-uuid-123",
            "name": "Black Lotus",
            "mana_cost": "{0}",
            "type_line": "Artifact",
            "oracle_text": "{T}, Sacrifice this artifact: Add seven mana.",
            "rarity": "mythic",
            "colors": [],
            "color_identity": [],
            "cmc": 0.0,
            "set": {"code": "LEA", "name": "Limited Edition Alpha"},
            "set_type": "core",
        }
        card = moxfield._parse_card(data)
        assert card is not None
        # When scryfall_id is present, it's used as the id
        self.assertEqual(card.id, "scryfall-uuid-123")
        self.assertEqual(card.scryfall_id, "scryfall-uuid-123")
        self.assertEqual(card.name, "Black Lotus")
        self.assertEqual(card.mana_cost, "{0}")
        self.assertEqual(card.type_line, "Artifact")
        self.assertEqual(card.rarity, Rarity.MYTHIC)
        self.assertEqual(card.set_code, "LEA")
        self.assertEqual(card.set_name, "Limited Edition Alpha")
        self.assertEqual(card.source, "moxfield")

    def test_parse_card_with_colors(self):
        """Test parsing a card with colors."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "card-456",
            "name": "Counterspell",
            "mana_cost": "{U}{U}",
            "type_line": "Instant",
            "colors": ["U"],
            "color_identity": ["U"],
            "cmc": 2.0,
            "rarity": "common",
        }
        card = moxfield._parse_card(data)
        assert card is not None
        self.assertEqual(card.name, "Counterspell")
        self.assertEqual(card.colors, [Color.BLUE])
        self.assertEqual(card.color_identity, [Color.BLUE])

    def test_parse_card_with_card_faces(self):
        """Test parsing a card with multiple faces."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "card-789",
            "name": "Delver of Secrets",
            "scryfall_id": "delver-uuid",
            "card_faces": [
                {
                    "name": "Delver of Secrets",
                    "mana_cost": "{U}",
                    "type_line": "Creature Human Wizard",
                    "oracle_text": "At the beginning of your upkeep",
                    "power": "1",
                    "toughness": "1",
                    "colors": ["U"],
                },
                {
                    "name": "Insectile Aberration",
                    "mana_cost": "",
                    "type_line": "Creature Insect Horror",
                    "oracle_text": "Flying",
                    "power": "3",
                    "toughness": "2",
                    "colors": ["U"],
                },
            ],
            "cmc": 1.0,
            "type_line": "Creature Human Wizard",
            "rarity": "common",
        }
        card = moxfield._parse_card(data)
        assert card is not None
        self.assertEqual(card.name, "Delver of Secrets")
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        self.assertEqual(len(card_faces), 2)
        # Verify face field mappings
        self.assertEqual(card_faces[0].name, "Delver of Secrets")
        self.assertEqual(card_faces[0].mana_cost, "{U}")
        self.assertEqual(card_faces[0].type_line, "Creature Human Wizard")
        self.assertEqual(card_faces[0].power, "1")
        self.assertEqual(card_faces[0].toughness, "1")
        self.assertEqual(card_faces[1].name, "Insectile Aberration")
        self.assertEqual(card_faces[1].type_line, "Creature Insect Horror")
        self.assertEqual(card_faces[1].power, "3")
        self.assertEqual(card_faces[1].toughness, "2")

    def test_parse_card_flavor_text_list_filters_none(self):
        """Test that None values are filtered from flavor_text list."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "card-123",
            "name": "Black Lotus",
            "flavor_text": ["A flavorful card", None, "Another flavor"],
        }
        card = moxfield._parse_card(data)
        assert card is not None
        assert card.flavors is not None
        self.assertEqual(len(card.flavors), 2)
        self.assertEqual(card.flavors[0], "A flavorful card")
        self.assertEqual(card.flavors[1], "Another flavor")

    def test_parse_card_flavor_text_all_none_returns_none(self):
        """Test that flavor_text list with all None values returns None."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "card-123",
            "name": "Black Lotus",
            "flavor_text": [None, None],
        }
        card = moxfield._parse_card(data)
        assert card is not None
        self.assertIsNone(card.flavors)

    def test_parse_card_image_uris_filters_empty_strings(self):
        """Test that empty string values are filtered from image_uris."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "card-123",
            "name": "Black Lotus",
            "image_uris": {
                "normal": "https://example.com/normal.jpg",
                "small": "",
                "large": "https://example.com/large.jpg",
            },
        }
        card = moxfield._parse_card(data)
        assert card is not None
        assert card.image_uris is not None
        self.assertEqual(len(card.image_uris), 2)
        self.assertIn("normal", card.image_uris)
        self.assertIn("large", card.image_uris)
        self.assertNotIn("small", card.image_uris)

    def test_parse_card_image_uris_filters_non_string_values(self):
        """Test that non-string values are filtered from image_uris."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "card-123",
            "name": "Black Lotus",
            "image_uris": {
                "normal": "https://example.com/normal.jpg",
                "png": 12345,
                "border_crop": None,
                "large": "https://example.com/large.jpg",
            },
        }
        card = moxfield._parse_card(data)
        assert card is not None
        assert card.image_uris is not None
        self.assertEqual(len(card.image_uris), 2)
        self.assertIn("normal", card.image_uris)
        self.assertIn("large", card.image_uris)
        self.assertNotIn("png", card.image_uris)
        self.assertNotIn("border_crop", card.image_uris)

    def test_parse_card_image_uris_all_empty_returns_none(self):
        """Test that image_uris with all empty values returns None."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "card-123",
            "name": "Black Lotus",
            "image_uris": {
                "normal": "",
                "small": "",
            },
        }
        card = moxfield._parse_card(data)
        assert card is not None
        self.assertIsNone(card.image_uris)

    def test_parse_colors(self):
        """Test color parsing helper method."""
        moxfield = Moxfield(api_key="test-key")
        result = moxfield._parse_colors(["W", "U", "B"])
        self.assertEqual(result, [Color.WHITE, Color.BLUE, Color.BLACK])
        result = moxfield._parse_colors(None)
        self.assertIsNone(result)
        result = moxfield._parse_colors([])
        self.assertIsNone(result)
        result = moxfield._parse_colors(["w", "U", "b"])
        self.assertEqual(result, [Color.WHITE, Color.BLUE, Color.BLACK])


class TestMoxfieldDeckParsing(unittest.TestCase):
    """Test Moxfield deck parsing functionality."""

    def test_parse_deck_basic(self):
        """Test parsing a basic deck."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "deck-123",
            "name": "Test Commander Deck",
            "description": "A test deck",
            "format": "commander",
            "cards": [],
            "owner": "testuser",
            "owner_id": "user-123",
            "is_public": True,
        }
        deck = moxfield._parse_deck(data)
        self.assertEqual(deck.id, "deck-123")
        self.assertEqual(deck.name, "Test Commander Deck")
        self.assertEqual(deck.description, "A test deck")
        self.assertEqual(deck.format, Format.COMMANDER)
        self.assertEqual(deck.privacy, "public")
        self.assertEqual(deck.source, "moxfield")

    def test_parse_deck_with_cards(self):
        """Test parsing a deck with cards."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "deck-456",
            "name": "Test Deck with Cards",
            "format": "modern",
            "cards": [
                {
                    "card": {
                        "id": "card-1",
                        "name": "Island",
                        "mana_cost": "{0}",
                        "type_line": "Land",
                        "rarity": "common",
                        "colors": [],
                        "color_identity": [],
                    },
                    "quantity": 4,
                    "board": "main",
                }
            ],
        }
        deck = moxfield._parse_deck(data)
        self.assertEqual(deck.id, "deck-456")
        self.assertIsNotNone(deck.cards)
        cards = deck.cards
        assert cards is not None
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].count, 4)
        self.assertEqual(cards[0].board, Board.MAIN)

    def test_parse_deck_with_sideboard(self):
        """Test parsing a deck with sideboard."""
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "deck-789",
            "name": "Test Deck with Sideboard",
            "format": "standard",
            "cards": [
                {
                    "card": {
                        "id": "card-1",
                        "name": "Plains",
                        "mana_cost": "{0}",
                        "type_line": "Land",
                        "rarity": "common",
                    },
                    "quantity": 4,
                    "board": "main",
                }
            ],
            "sideboard": [
                {
                    "card": {
                        "id": "card-2",
                        "name": "Disallow",
                        "mana_cost": "{U}{U}",
                        "type_line": "Instant",
                        "rarity": "uncommon",
                    },
                    "quantity": 2,
                    "board": "sideboard",
                }
            ],
        }
        deck = moxfield._parse_deck(data)
        self.assertEqual(deck.id, "deck-789")
        cards = deck.cards or []
        self.assertEqual(len(cards), 2)
        # Verify board assignments are correct after merging
        main_cards = [c for c in cards if c.board == Board.MAIN]
        side_cards = [c for c in cards if c.board == Board.SIDEBOARD]
        self.assertEqual(len(main_cards), 1)
        self.assertEqual(len(side_cards), 1)
        self.assertEqual(main_cards[0].card.name, "Plains")
        self.assertEqual(side_cards[0].card.name, "Disallow")

    def test_parse_deck_invalid_board_defaults_to_main_with_warning(self):
        """Test that invalid board strings default to MAIN with a warning.

        Verifies that when a board string cannot be matched to a Board enum
        value (via either upper or lowercase lookup), the card is assigned to
        Board.MAIN and a warning is logged.
        """
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "deck-invalid-board",
            "name": "Test Deck Invalid Board",
            "format": "standard",
            "cards": [
                {
                    "card": {
                        "id": "card-1",
                        "name": "Island",
                        "mana_cost": "{0}",
                        "type_line": "Land",
                        "rarity": "common",
                    },
                    "quantity": 4,
                    "board": "invalid_board_name",
                }
            ],
        }
        with self.assertLogs(
            "pymtg.providers.moxfield", level="WARNING"
        ) as log_context:
            deck = moxfield._parse_deck(data)
        cards = deck.cards or []
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].board, Board.MAIN)
        self.assertTrue(
            any("Unknown board" in msg for msg in log_context.output),
            f"Expected 'Unknown board' warning in logs: {log_context.output}",
        )

    def test_parse_deck_quantity_zero_preserved(self):
        """Test that explicit quantity 0 is preserved, not defaulted to 1.

        Verifies the fix for issue #120: the `or` chaining treated 0 as
        falsy and fell through to the default of 1. The _extract_quantity
        helper uses explicit None checks so 0 is preserved.
        """
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "deck-zero-qty",
            "name": "Test Deck Zero Quantity",
            "format": "standard",
            "cards": [
                {
                    "card": {
                        "id": "card-1",
                        "name": "Island",
                        "mana_cost": "{0}",
                        "type_line": "Land",
                        "rarity": "common",
                    },
                    "quantity": 0,
                    "board": "main",
                }
            ],
        }
        deck = moxfield._parse_deck(data)
        cards = deck.cards or []
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].count, 0)

    def test_parse_deck_quantity_falls_back_to_count(self):
        """Test that quantity falls back to 'count' field when missing.

        Verifies the fallback chain still works: quantity -> count -> qty
        -> 1, but only when fields are absent (None), not when they are 0.
        """
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "deck-fallback",
            "name": "Test Deck Fallback",
            "format": "standard",
            "cards": [
                {
                    "card": {
                        "id": "card-1",
                        "name": "Island",
                        "mana_cost": "{0}",
                        "type_line": "Land",
                        "rarity": "common",
                    },
                    "count": 3,
                    "board": "main",
                }
            ],
        }
        deck = moxfield._parse_deck(data)
        cards = deck.cards or []
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].count, 3)

    def test_parse_deck_quantity_defaults_to_1_when_absent(self):
        """Test that quantity defaults to 1 when no quantity field exists.

        Verifies the default behavior when quantity, count, and qty are
        all absent from the card data.
        """
        moxfield = Moxfield(api_key="test-key")
        data = {
            "id": "deck-default",
            "name": "Test Deck Default",
            "format": "standard",
            "cards": [
                {
                    "card": {
                        "id": "card-1",
                        "name": "Island",
                        "mana_cost": "{0}",
                        "type_line": "Land",
                        "rarity": "common",
                    },
                    "board": "main",
                }
            ],
        }
        deck = moxfield._parse_deck(data)
        cards = deck.cards or []
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].count, 1)

    def test_extract_quantity_zero_not_treated_as_missing(self):
        """Test _extract_quantity preserves 0 across all field names.

        Verifies that 0 is returned for quantity, count, and qty fields
        rather than falling through to the default of 1.
        """
        moxfield = Moxfield(api_key="test-key")
        self.assertEqual(moxfield._extract_quantity({"quantity": 0}), 0)
        self.assertEqual(moxfield._extract_quantity({"count": 0}), 0)
        self.assertEqual(moxfield._extract_quantity({"qty": 0}), 0)

    def test_extract_quantity_none_falls_through(self):
        """Test _extract_quantity falls through when fields are None.

        Verifies that explicit None values are treated as missing and the
        next field in the chain is checked.
        """
        moxfield = Moxfield(api_key="test-key")
        self.assertEqual(
            moxfield._extract_quantity({"quantity": None, "count": None, "qty": 5}),
            5,
        )
        self.assertEqual(
            moxfield._extract_quantity({"quantity": None, "count": None, "qty": None}),
            1,
        )


class TestMoxfieldIterSearch(unittest.TestCase):
    """Test Moxfield.iter_search() method (inherited from BaseProvider)."""

    def test_iter_search_basic(self):
        """Test basic iter_search functionality and pagination.

        Verifies that iter_search fetches pages until the limit is reached
        or a page is empty/partial, and that the ``page`` argument
        increments across calls.
        """
        moxfield = Moxfield(api_key="test-key")
        # A full first page (page_size cards) so iter_search fetches a
        # second page; the second page is empty, terminating iteration.
        first_page = [
            Card(id=str(i), name=f"Card {i}", source="moxfield") for i in range(5)
        ]
        # Use side_effect to return results first, then empty list (simulating pagination)
        with patch.object(
            moxfield,
            "search",
            side_effect=[
                first_page,
                [],
            ],
        ) as mock_search:
            results = list(moxfield.iter_search(name="Test", limit=10, page_size=5))
        self.assertEqual(len(results), 5)
        # Verify pagination incremented correctly across calls
        self.assertEqual(mock_search.call_count, 2)
        first_call = mock_search.call_args_list[0]
        second_call = mock_search.call_args_list[1]
        self.assertEqual(first_call.kwargs["page"], 1)
        self.assertEqual(first_call.kwargs["limit"], 5)
        self.assertEqual(second_call.kwargs["page"], 2)
        self.assertEqual(second_call.kwargs["limit"], 5)


class TestMoxfieldErrorHandling(unittest.TestCase):
    """Test Moxfield error handling."""

    def test_handle_rate_limit_error(self):
        """Test that rate limit errors are raised correctly."""
        moxfield = Moxfield(api_key="test-key")
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        with patch.object(moxfield.http_client, "get", return_value=mock_response):
            with self.assertRaises(RateLimitError):
                moxfield.search(name="Test")


class TestMoxfieldContextManager(unittest.TestCase):
    """Test Moxfield context manager support."""

    def test_context_manager(self):
        """Test that Moxfield can be used as a context manager."""
        with Moxfield(api_key="test-key") as moxfield:
            self.assertIsNotNone(moxfield)
            self.assertTrue(moxfield.is_authenticated())

    @patch.object(Moxfield, "close")
    def test_context_manager_calls_close(self, mock_close):
        """Test that context manager calls close on exit."""
        with Moxfield(api_key="test-key"):
            pass
        mock_close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
