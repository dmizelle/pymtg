"""Tests for the Scryfall provider.

This module contains unit tests for the Scryfall provider implementation,
covering all major functionality including card retrieval, search, and error handling.
"""

import unittest
from unittest.mock import MagicMock, patch

import requests

from pymtg.exceptions import (
    APIError,
    InvalidQueryError,
    NetworkError,
    NotFoundError,
    RateLimitError,
)
from pymtg.models.card import Card
from pymtg.models.enums import Color, Rarity
from pymtg.providers.scryfall import Scryfall


class TestScryfallInitialization(unittest.TestCase):
    """Test Scryfall provider initialization."""

    def test_default_initialization(self):
        """Test that Scryfall provider initializes correctly with default parameters."""
        scryfall = Scryfall()
        self.assertEqual(scryfall.name, "scryfall")
        self.assertEqual(scryfall.base_url, "https://api.scryfall.com")
        self.assertIsNotNone(scryfall.http_client)
        self.assertIsNotNone(scryfall.config)

    def test_is_authenticated_always_true(self):
        """Test that Scryfall.is_authenticated() always returns True."""
        scryfall = Scryfall()
        self.assertTrue(scryfall.is_authenticated())

    def test_rate_limit_status(self):
        """Test that rate limit status returns correct information."""
        scryfall = Scryfall()
        status = scryfall.get_rate_limit_status()

        self.assertIn("rate_limit", status)
        self.assertIn("search_limit", status)
        self.assertIn("other_limit", status)
        self.assertEqual(status["search_limit"]["requests_per_second"], 2)
        self.assertEqual(status["other_limit"]["requests_per_second"], 10)


class TestScryfallGetCard(unittest.TestCase):
    """Test Scryfall.get_card() method."""

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    def test_get_card_success(self, mock_http_client, mock_handle_response):
        """Test successful card retrieval by ID."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock the response data (Black Lotus)
        mock_data = {
            "id": "38625902-0567-4f24-85b0-a00843553997",
            "name": "Black Lotus",
            "mana_cost": "{0}",
            "type_line": "Artifact",
            "oracle_text": "{T}, Sacrifice this artifact: Add {B}{B}{B}{B}{B}{B}{B}.",
            "rarity": "mythic",
            "set": {"code": "LEA", "name": "Limited Edition Alpha"},
            "color_identity": [],
            "colors": [],
            "cmc": 0.0,
        }
        mock_handle_response.return_value = mock_data

        # Mock the parse method
        with patch.object(
            Scryfall,
            "_parse_card",
            return_value=Card(
                id="38625902-0567-4f24-85b0-a00843553997",
                scryfall_id="38625902-0567-4f24-85b0-a00843553997",
                name="Black Lotus",
                source="scryfall",
            ),
        ):
            scryfall = Scryfall()
            card = scryfall.get_card("38625902-0567-4f24-85b0-a00843553997")

            self.assertIsInstance(card, Card)
            self.assertEqual(card.name, "Black Lotus")
            self.assertEqual(card.scryfall_id, "38625902-0567-4f24-85b0-a00843553997")
            self.assertEqual(card.source, "scryfall")

            # Verify HTTP client was called correctly
            mock_http_client.get.assert_called_once_with(
                "/cards/38625902-0567-4f24-85b0-a00843553997"
            )

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    def test_get_card_not_found(self, mock_http_client, mock_handle_response):
        """Test that NotFoundError is raised when card doesn't exist."""
        # Mock the HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock empty response data
        mock_handle_response.return_value = None

        scryfall = Scryfall()

        with self.assertRaises(NotFoundError) as context:
            scryfall.get_card("non-existent-id")

        self.assertEqual(context.exception.provider, "scryfall")
        self.assertEqual(context.exception.resource_type, "card")

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    def test_get_card_network_error(self, mock_http_client, mock_handle_response):
        """Test that NetworkError is raised on network failure."""
        # Mock the HTTP client to raise a request exception
        mock_http_client.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )

        scryfall = Scryfall()

        with self.assertRaises(NetworkError) as context:
            scryfall.get_card("test-id")

        self.assertIn("Network error getting card", str(context.exception))


class TestScryfallSearch(unittest.TestCase):
    """Test Scryfall.search() method."""

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    @patch.object(Scryfall, "_parse_card")
    @patch.object(Scryfall, "_build_search_query")
    def test_search_success(
        self, mock_build_query, mock_parse_card, mock_http_client, mock_handle_response
    ):
        """Test successful search with generic parameters."""
        # Mock query building
        mock_build_query.return_value = 'name:"Black Lotus"'

        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response data
        mock_data = {"data": [{"id": "test1"}, {"id": "test2"}]}
        mock_handle_response.return_value = mock_data

        # Mock card parsing
        mock_card1 = Card(id="test1", name="Black Lotus", source="scryfall")
        mock_card2 = Card(id="test2", name="Lightning Bolt", source="scryfall")
        mock_parse_card.side_effect = [mock_card1, mock_card2]

        scryfall = Scryfall()
        cards = scryfall.search(name="Black Lotus", limit=2)

        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0].name, "Black Lotus")
        self.assertEqual(cards[1].name, "Lightning Bolt")

        # Verify query building
        mock_build_query.assert_called_once()

        # Verify HTTP client was called with correct parameters
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        self.assertEqual(call_args[0][0], "/cards/search")
        self.assertIn("q", call_args[1]["params"])
        self.assertIn("page", call_args[1]["params"])
        self.assertIn("limit", call_args[1]["params"])

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    def test_search_with_colors(self, mock_http_client, mock_handle_response):
        """Test search with color parameters."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response data
        mock_data = {"data": []}
        mock_handle_response.return_value = mock_data

        scryfall = Scryfall()
        mock_card = Card(id="test-id", name="Test Card")
        with patch.object(Scryfall, "_parse_card", return_value=mock_card):
            scryfall.search(colors=[Color.BLUE, Color.BLACK], limit=10)

        # Verify the search was called
        mock_http_client.get.assert_called_once()

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    def test_search_network_error(self, mock_http_client, mock_handle_response):
        """Test that NetworkError is raised on search network failure."""
        # Mock the HTTP client to raise a request exception
        mock_http_client.get.side_effect = requests.exceptions.RequestException(
            "Network error"
        )

        scryfall = Scryfall()

        with self.assertRaises(NetworkError):
            scryfall.search(name="test")


class TestScryfallSearchSyntax(unittest.TestCase):
    """Test Scryfall.search_syntax() method."""

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    @patch.object(Scryfall, "_parse_card")
    def test_search_syntax_success(
        self, mock_parse_card, mock_http_client, mock_handle_response
    ):
        """Test successful syntax search."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response data
        mock_data = {"data": [{"id": "test1"}]}
        mock_handle_response.return_value = mock_data

        # Mock card parsing
        mock_card = Card(id="test1", name="Test Card", source="scryfall")
        mock_parse_card.return_value = mock_card

        scryfall = Scryfall()
        cards = scryfall.search_syntax("c:U type:creature", limit=5)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].name, "Test Card")

        # Verify HTTP client was called with query
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        self.assertEqual(call_args[1]["params"]["q"], "c:U type:creature")

    def test_search_syntax_invalid_query(self):
        """Test that InvalidQueryError is raised for invalid query."""
        scryfall = Scryfall()

        with self.assertRaises(InvalidQueryError) as context:
            scryfall.search_syntax("")

        self.assertIn("Query must be a non-empty string", str(context.exception))

        with self.assertRaises(InvalidQueryError):
            scryfall.search_syntax(None)  # type: ignore  # Intentional None argument

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    def test_search_syntax_with_options(self, mock_http_client, mock_handle_response):
        """Test syntax search with additional options."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response data
        mock_data = {"data": []}
        mock_handle_response.return_value = mock_data

        scryfall = Scryfall()
        mock_card = Card(id="test-id", name="Test Card")
        with patch.object(Scryfall, "_parse_card", return_value=mock_card):
            scryfall.search_syntax(
                "type:creature", limit=10, page=2, order="name", unique="prints"
            )

        # Verify all parameters were passed
        call_args = mock_http_client.get.call_args
        params = call_args[1]["params"]
        self.assertEqual(params["q"], "type:creature")
        self.assertEqual(params["limit"], 10)
        self.assertEqual(params["page"], 2)
        self.assertEqual(params["order"], "name")
        self.assertEqual(params["unique"], "prints")


class TestScryfallAutocomplete(unittest.TestCase):
    """Test Scryfall.autocomplete() method."""

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    def test_autocomplete_success(self, mock_http_client, mock_handle_response):
        """Test successful autocomplete."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response data
        mock_data = {"data": ["Lightning Bolt", "Lightning Greaves", "Lightning Helix"]}
        mock_handle_response.return_value = mock_data

        scryfall = Scryfall()
        suggestions = scryfall.autocomplete("Ligh", limit=5)

        self.assertEqual(len(suggestions), 3)
        self.assertEqual(suggestions[0], "Lightning Bolt")
        self.assertEqual(suggestions[1], "Lightning Greaves")
        self.assertEqual(suggestions[2], "Lightning Helix")

        # Verify HTTP client was called
        mock_http_client.get.assert_called_once_with(
            "/cards/autocomplete", params={"q": "Ligh", "limit": 5}
        )

    def test_autocomplete_invalid_query(self):
        """Test that InvalidQueryError is raised for invalid autocomplete query."""
        scryfall = Scryfall()

        with self.assertRaises(InvalidQueryError):
            scryfall.autocomplete("")

        with self.assertRaises(InvalidQueryError):
            scryfall.autocomplete(None)  # type: ignore  # Intentional None argument

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    def test_autocomplete_empty_results(self, mock_http_client, mock_handle_response):
        """Test autocomplete with no results."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock empty response data
        mock_handle_response.return_value = None

        scryfall = Scryfall()
        suggestions = scryfall.autocomplete("xyzabc123", limit=5)

        self.assertEqual(suggestions, [])

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    def test_autocomplete_empty_data(self, mock_http_client, mock_handle_response):
        """Test autocomplete with empty data list."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response with empty data
        mock_handle_response.return_value = {"data": []}

        scryfall = Scryfall()
        suggestions = scryfall.autocomplete("test", limit=5)

        self.assertEqual(suggestions, [])


class TestScryfallGetCardsByName(unittest.TestCase):
    """Test Scryfall.get_cards_by_name() method."""

    @patch.object(Scryfall, "_handle_response")
    @patch.object(Scryfall, "http_client")
    @patch.object(Scryfall, "_parse_card")
    def test_get_cards_by_name_success(
        self, mock_parse_card, mock_http_client, mock_handle_response
    ):
        """Test successful card retrieval by name."""
        # Mock HTTP client
        mock_response = MagicMock()
        mock_http_client.get.return_value = mock_response

        # Mock response data (redirect to actual card)
        mock_data = {
            "id": "38625902-0567-4f24-85b0-a00843553997",
            "name": "Black Lotus",
        }
        mock_handle_response.return_value = mock_data

        # Mock card parsing
        mock_card = Card(
            id="38625902-0567-4f24-85b0-a00843553997",
            name="Black Lotus",
            source="scryfall",
        )
        mock_parse_card.return_value = mock_card

        scryfall = Scryfall()
        cards = scryfall.get_cards_by_name("Black Lotus")

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].name, "Black Lotus")

        # Verify HTTP client was called
        mock_http_client.get.assert_called_once()

    def test_get_cards_by_name_invalid_name(self):
        """Test that InvalidQueryError is raised for invalid card name."""
        scryfall = Scryfall()

        with self.assertRaises(InvalidQueryError):
            scryfall.get_cards_by_name("")

        with self.assertRaises(InvalidQueryError):
            scryfall.get_cards_by_name(None)  # type: ignore  # Intentional None argument


class TestScryfallResponseParsing(unittest.TestCase):
    """Test Scryfall response parsing."""

    def test_parse_card_basic(self):
        """Test parsing a basic card from Scryfall data."""
        scryfall = Scryfall()

        # Basic card data
        scryfall_data = {
            "id": "38625902-0567-4f24-85b0-a00843553997",
            "name": "Black Lotus",
            "mana_cost": "{0}",
            "type_line": "Artifact",
            "oracle_text": "{T}, Sacrifice this artifact: Add {B}{B}{B}{B}{B}{B}{B}.",
            "rarity": "mythic",
            "set": {"code": "LEA", "name": "Limited Edition Alpha", "set_type": "core"},
            "color_identity": [],
            "colors": [],
            "cmc": 0.0,
            "collector_number": "332",
        }

        card = scryfall._parse_card(scryfall_data)

        self.assertIsInstance(card, Card)
        self.assertEqual(card.id, "38625902-0567-4f24-85b0-a00843553997")
        self.assertEqual(card.scryfall_id, "38625902-0567-4f24-85b0-a00843553997")
        self.assertEqual(card.name, "Black Lotus")
        self.assertEqual(card.mana_cost, "{0}")
        self.assertEqual(card.type_line, "Artifact")
        self.assertEqual(
            card.oracle_text, "{T}, Sacrifice this artifact: Add {B}{B}{B}{B}{B}{B}{B}."
        )
        self.assertEqual(card.set_code, "LEA")
        self.assertEqual(card.set_name, "Limited Edition Alpha")
        self.assertEqual(card.rarity, Rarity.MYTHIC)
        self.assertEqual(card.collector_number, "332")
        self.assertEqual(card.cmc, 0.0)
        self.assertEqual(card.source, "scryfall")

    def test_parse_card_with_colors(self):
        """Test parsing a card with colors from Scryfall data."""
        scryfall = Scryfall()

        # Card with colors
        scryfall_data = {
            "id": "test-id",
            "name": "Counterspell",
            "type_line": "Instant",
            "colors": ["U"],
            "color_identity": ["U"],
            "rarity": "common",
            "set": {"code": "LEA", "name": "Limited Edition Alpha", "set_type": "core"},
        }

        card = scryfall._parse_card(scryfall_data)

        self.assertEqual(card.name, "Counterspell")
        self.assertEqual(card.colors, [Color.BLUE])
        self.assertEqual(card.color_identity, [Color.BLUE])

    def test_parse_card_with_pricing(self):
        """Test parsing a card with pricing information."""
        scryfall = Scryfall()

        # Card with pricing
        scryfall_data = {
            "id": "test-id",
            "name": "Black Lotus",
            "type_line": "Artifact",
            "rarity": "mythic",
            "set": {"code": "LEA", "name": "Limited Edition Alpha", "set_type": "core"},
            "prices": {
                "usd": {"normal": 50000.0, "foil": 100000.0, "etched": None},
                "eur": {"normal": 45000.0, "foil": 90000.0},
                "tix": {"normal": None},
            },
        }

        card = scryfall._parse_card(scryfall_data)

        self.assertIsNotNone(card.pricing)
        pricing = card.pricing
        assert pricing is not None
        self.assertIsNotNone(pricing.scryfall)
        scryfall_pricing = pricing.scryfall
        assert scryfall_pricing is not None
        self.assertEqual(scryfall_pricing.usd, 50000.0)
        self.assertEqual(scryfall_pricing.usd_foil, 100000.0)
        self.assertIsNone(scryfall_pricing.usd_etched)
        self.assertEqual(scryfall_pricing.eur, 45000.0)
        self.assertEqual(scryfall_pricing.eur_foil, 90000.0)
        self.assertIsNone(scryfall_pricing.tix)

    def test_parse_card_multifaced(self):
        """Test parsing a multifaced card."""
        scryfall = Scryfall()

        # Multifaced card data
        scryfall_data = {
            "id": "test-id",
            "name": "Delver of Secrets // Insectile Aberration",
            "type_line": "Creature — Human Wizard",
            "colors": ["U"],
            "color_identity": ["U"],
            "rarity": "common",
            "set": {"code": "ISD", "name": "Innistrad", "set_type": "expansion"},
            "card_faces": [
                {
                    "name": "Delver of Secrets",
                    "mana_cost": "{U}",
                    "type_line": "Creature — Human Wizard",
                    "oracle_text": "At the beginning of your upkeep, look at the top card of your library. If it's an instant or sorcery card, you may reveal that card and transform Delver of Secrets.",
                    "power": "1",
                    "toughness": "1",
                    "colors": ["U"],
                },
                {
                    "name": "Insectile Aberration",
                    "type_line": "Creature — Insect Horror",
                    "oracle_text": "Flying",
                    "power": "3",
                    "toughness": "2",
                    "colors": ["U"],
                },
            ],
        }

        card = scryfall._parse_card(scryfall_data)

        self.assertEqual(card.name, "Delver of Secrets")
        self.assertIsNotNone(card.card_faces)
        card_faces = card.card_faces
        assert card_faces is not None
        self.assertEqual(len(card_faces), 2)
        self.assertEqual(card_faces[0].name, "Delver of Secrets")
        self.assertEqual(card_faces[1].name, "Insectile Aberration")

    def test_parse_colors(self):
        """Test color parsing."""
        scryfall = Scryfall()

        # Test all colors
        colors = ["W", "U", "B", "R", "G"]
        parsed = scryfall._parse_colors(colors)
        expected = [Color.WHITE, Color.BLUE, Color.BLACK, Color.RED, Color.GREEN]
        self.assertEqual(parsed, expected)

        # Test None input
        self.assertIsNone(scryfall._parse_colors(None))

        # Test empty list
        self.assertIsNone(scryfall._parse_colors([]))


class TestScryfallErrorHandling(unittest.TestCase):
    """Test Scryfall error handling."""

    def test_handle_response_404(self):
        """Test that _handle_response raises NotFoundError for 404."""
        scryfall = Scryfall()

        # Create a mock response with 404 status
        mock_response = MagicMock()
        mock_response.status_code = 404

        with self.assertRaises(NotFoundError) as context:
            scryfall._handle_response(mock_response, "card")

        self.assertEqual(context.exception.provider, "scryfall")
        self.assertEqual(context.exception.resource_type, "card")

    def test_handle_response_429(self):
        """Test that _handle_response raises RateLimitError for 429."""
        scryfall = Scryfall()

        # Create a mock response with 429 status
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers.get.return_value = "10"

        with self.assertRaises(RateLimitError) as context:
            scryfall._handle_response(mock_response, "search")

        self.assertEqual(context.exception.provider, "scryfall")
        self.assertEqual(context.exception.retry_after, 10)

    def test_handle_response_401(self):
        """Test that _handle_response raises AuthenticationError for 401."""
        from pymtg.exceptions import AuthenticationError

        scryfall = Scryfall()

        # Create a mock response with 401 status
        mock_response = MagicMock()
        mock_response.status_code = 401

        with self.assertRaises(AuthenticationError) as context:
            scryfall._handle_response(mock_response, "search")

        self.assertEqual(context.exception.provider, "scryfall")

    def test_handle_response_400(self):
        """Test that _handle_response raises APIError for 400."""
        scryfall = Scryfall()

        # Create a mock response with 400 status
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        with self.assertRaises(APIError) as context:
            scryfall._handle_response(mock_response, "search")

        self.assertEqual(context.exception.provider, "scryfall")
        self.assertEqual(context.exception.status_code, 400)


class TestScryfallQueryBuilding(unittest.TestCase):
    """Test Scryfall query building."""

    def test_build_search_query_name_only(self):
        """Test query building with name only."""
        scryfall = Scryfall()
        query = scryfall._build_search_query(name="Black Lotus")
        self.assertEqual(query, '"Black Lotus"')

    def test_build_search_query_with_colors(self):
        """Test query building with colors."""
        scryfall = Scryfall()
        query = scryfall._build_search_query(colors=[Color.BLUE])
        self.assertEqual(query, "c:U")

    def test_build_search_query_with_multiple_colors(self):
        """Test query building with multiple colors."""
        scryfall = Scryfall()
        query = scryfall._build_search_query(colors=[Color.BLUE, Color.BLACK])
        self.assertEqual(query, "ci:UB")

    def test_build_search_query_with_identity(self):
        """Test query building with color identity."""
        scryfall = Scryfall()
        query = scryfall._build_search_query(identity=[Color.RED, Color.GREEN])
        self.assertEqual(query, "id:RG")

    def test_build_search_query_with_type_line(self):
        """Test query building with type line."""
        scryfall = Scryfall()
        query = scryfall._build_search_query(type_line="Creature")
        self.assertEqual(query, '"Creature"')

    def test_build_search_query_complex(self):
        """Test complex query building."""
        scryfall = Scryfall()
        query = scryfall._build_search_query(
            name="Bolt", colors=[Color.RED], type_line="Instant"
        )
        self.assertIn('"Bolt"', query)
        self.assertIn("c:R", query)
        self.assertIn('"Instant"', query)

    def test_build_search_query_with_set_code(self):
        """Test query building with set code."""
        scryfall = Scryfall()
        query = scryfall._build_search_query(name="Lotus", set_code="LEA")
        self.assertIn('"Lotus"', query)
        self.assertIn("set:LEA", query)


class TestScryfallRepr(unittest.TestCase):
    """Test Scryfall string representation."""

    def test_repr(self):
        """Test the __repr__ method."""
        scryfall = Scryfall()
        repr_str = repr(scryfall)

        self.assertIn("Scryfall", repr_str)
        self.assertIn("name='scryfall'", repr_str)
        self.assertIn("https://api.scryfall.com", repr_str)


if __name__ == "__main__":
    unittest.main()
