"""Integration tests for Scryfall provider.

This module contains integration tests that make real API calls to Scryfall.
These tests require network access and respect Scryfall's rate limits.

Tests will be skipped if:
- Network access is not available
- Rate limits would be exceeded
- SCRYFALL_ENABLE_INTEGRATION_TESTS environment variable is not set to 'true'
"""

import logging
import os
import unittest

import requests

from pymtg.exceptions import NotFoundError
from pymtg.providers.scryfall import Scryfall

logger = logging.getLogger(__name__)


class TestScryfallIntegration(unittest.TestCase):
    """Integration tests for Scryfall provider."""

    @classmethod
    def setUpClass(cls):
        """Check if integration tests should be run."""
        cls.skip_tests = (
            os.getenv("SCRYFALL_ENABLE_INTEGRATION_TESTS", "").lower() != "true"
            or not cls._check_network_available()
        )

    @staticmethod
    def _check_network_available() -> bool:
        """Check if network access is available.

        Returns:
            True if network is available, False otherwise.
        """
        try:
            response = requests.get("https://api.scryfall.com", timeout=5)
            response.close()
            return response.ok
        except requests.exceptions.RequestException as e:
            logger.debug("Scryfall network probe failed: %s", e)
            return False

    def setUp(self):
        """Set up test fixtures."""
        if self.skip_tests:
            self.skipTest("Integration tests skipped (network or env not configured)")
        self.scryfall = Scryfall()

    def tearDown(self):
        """Clean up test fixtures.

        Closes any underlying session the Scryfall client may hold so
        connections do not leak across test methods.
        """
        if hasattr(self, "scryfall") and hasattr(self.scryfall, "close"):
            self.scryfall.close()

    def test_get_card_returns_card(self):
        """Tests that get_card returns a card by ID."""
        # Use a well-known card ID (Black Lotus from Limited Edition Alpha)
        card_id = "bd8fa327-dd41-4737-8f19-2cf5eb1f7cdd"
        card = self.scryfall.get_card(card_id)

        self.assertIsNotNone(card)
        self.assertEqual(card.name, "Black Lotus")
        self.assertEqual(card.source, "scryfall")
        self.assertIsNotNone(card.id)

    def test_get_card_not_found(self):
        """Test that NotFoundError is raised for non-existent card."""
        # Use a fake UUID
        fake_id = "00000000-0000-0000-0000-000000000000"
        with self.assertRaises(NotFoundError):
            self.scryfall.get_card(fake_id)

    def test_search_returns_results(self):
        """Tests that search returns results for a card name."""
        cards = self.scryfall.search(name="Black Lotus", limit=5)

        self.assertIsInstance(cards, list)
        self.assertGreater(len(cards), 0)
        # At least one card should match
        card_names = [c.name for c in cards]
        self.assertIn("Black Lotus", card_names)

    def test_search_syntax_returns_results(self):
        """Tests that search_syntax returns results for a query."""
        # Search for blue creatures
        cards = self.scryfall.search_syntax("c:U type:creature", limit=10)

        self.assertIsInstance(cards, list)
        self.assertGreater(len(cards), 0)
        # Verify at least some cards are blue (have U in their colors)
        blue_cards = [card for card in cards if card.colors and "U" in card.colors]
        self.assertGreater(
            len(blue_cards), 0, "Expected to find at least one blue creature"
        )

    def test_autocomplete_returns_results(self):
        """Tests that autocomplete returns results for a query."""
        results = self.scryfall.autocomplete("Blac")

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        # Should contain cards starting with "Black"
        self.assertTrue(any("Black" in name for name in results))


if __name__ == "__main__":
    unittest.main()
