"""Integration tests for Archidekt provider.

This module contains integration tests that make real API calls to Archidekt.
These tests require network access and Archidekt credentials.

Tests will be skipped if:
- PYMTG_INTEGRATION_TEST_ARCHIDEKT_ENABLED environment variable is not set to 'true'
- Network access is not available
- Required credentials (PYMTG_INTEGRATION_TEST_ARCHIDEKT_USERNAME and
  PYMTG_INTEGRATION_TEST_ARCHIDEKT_PASSWORD) are not configured
"""

import logging
import os
import random
import string
import unittest

import requests

logger = logging.getLogger(__name__)

from pymtg.models.card import Card
from pymtg.models.deck import Deck
from pymtg.models.enums import Color
from pymtg.providers.archidekt import Archidekt


class TestArchidektIntegration(unittest.TestCase):
    """Integration tests for Archidekt provider."""

    @classmethod
    def setUpClass(cls):
        """Check if integration tests should be run.

        The environment-variable check short-circuits before the network
        probe so that disabled test sessions do not incur the 5-second
        timeout latency of ``_check_network_available``.
        """
        enabled = (
            os.getenv("PYMTG_INTEGRATION_TEST_ARCHIDEKT_ENABLED", "").lower() == "true"
        )
        cls.skip_tests = (
            not enabled
            or not cls._check_credentials_available()
            or not cls._check_network_available()
        )
        cls.username = os.getenv("PYMTG_INTEGRATION_TEST_ARCHIDEKT_USERNAME")
        cls.password = os.getenv("PYMTG_INTEGRATION_TEST_ARCHIDEKT_PASSWORD")

    @staticmethod
    def _check_network_available() -> bool:
        """Check if network access is available.

        Returns:
            True if network is available, False otherwise.
        """
        try:
            requests.get("https://archidekt.com", timeout=5)
            return True
        except (requests.exceptions.RequestException, requests.exceptions.Timeout):
            return False

    @staticmethod
    def _check_credentials_available() -> bool:
        """Check if required credentials are available.

        Returns:
            True if credentials are available, False otherwise.
        """
        username = os.getenv("PYMTG_INTEGRATION_TEST_ARCHIDEKT_USERNAME")
        password = os.getenv("PYMTG_INTEGRATION_TEST_ARCHIDEKT_PASSWORD")
        return bool(username and password)

    def setUp(self):
        """Set up test fixtures."""
        if self.skip_tests:
            self.skipTest(
                "Integration tests skipped "
                "(network or env or credentials not configured)"
            )
        # Create authenticated provider
        self.archidekt = Archidekt(username=self.username, password=self.password)
        # Track created decks for cleanup
        self.created_decks = []

    def tearDown(self):
        """Clean up test fixtures."""
        # Delete all created decks
        for deck_id in self.created_decks:
            try:
                self.archidekt.delete_folder_items(
                    items=[{"id": int(deck_id), "type": "deck"}]
                )
                logger.info("Deleted test deck %s", deck_id)
            except Exception as e:
                logger.warning("Failed to delete test deck %s: %s", deck_id, e)
        # Clear the list
        self.created_decks = []

    def test_authentication_successful(self):
        """Tests that authentication succeeds with valid credentials."""
        self.assertTrue(self.archidekt.is_authenticated())

    def test_get_user_decks_returns_list(self):
        """Tests that get_user_decks returns a list of decks."""
        decks = self.archidekt.get_user_decks()

        self.assertIsInstance(decks, list)
        # User may have 0 or more decks
        for deck in decks:
            self.assertIsInstance(deck, Deck)
            self.assertIsNotNone(deck.id)
            self.assertIsNotNone(deck.name)

    def test_search_returns_cards(self):
        """Tests that search returns cards for a query."""
        # Search for a common card
        cards = self.archidekt.search(name="Black Lotus", limit=5)

        self.assertIsInstance(cards, list)
        self.assertGreater(len(cards), 0)
        # At least one card should match
        for card in cards:
            self.assertIsInstance(card, Card)
            self.assertIsNotNone(card.id)
            self.assertIsNotNone(card.name)
            self.assertEqual(card.source, "archidekt")

    def test_search_with_color_filter(self):
        """Tests that search works with color filters."""

        # Search for blue cards
        cards = self.archidekt.search(colors=[Color.BLUE], limit=10)

        self.assertIsInstance(cards, list)
        self.assertGreater(len(cards), 0)

    def test_get_card_by_id(self):
        """Tests that get_card returns a card by Archidekt ID."""
        # First, search for a card to get a valid ID
        search_results = self.archidekt.search(name="Sol Ring", limit=1)
        self.assertGreater(len(search_results), 0)

        # Use oracle_id since Archidekt API uses oracleCardIds for filtering
        card_id = search_results[0].oracle_id
        self.assertIsNotNone(card_id)
        # Narrow type for static analysis (assertIsNotNone does not narrow).
        assert card_id is not None

        card = self.archidekt.get_card(card_id)

        self.assertIsNotNone(card)
        self.assertIsInstance(card, Card)
        self.assertEqual(card.oracle_id, card_id)
        self.assertEqual(card.source, "archidekt")

    def test_create_deck(self):
        """Tests that create_deck works correctly."""
        # Create a test deck
        deck_name = f"pymtg-integration-test-{self._generate_random_string(8)}"
        new_deck = self.archidekt.create_deck(name=deck_name)

        self.assertIsNotNone(new_deck)
        self.assertIsInstance(new_deck, Deck)
        self.assertEqual(new_deck.name, deck_name)
        self.assertIsNotNone(new_deck.id)

        # Track deck for cleanup
        self.created_decks.append(new_deck.id)

    def test_rate_limit_status(self):
        """Tests that rate limit status is returned correctly."""
        status = self.archidekt.get_rate_limit_status()

        self.assertIn("requests_per_minute", status)
        self.assertIsInstance(status["requests_per_minute"], int)

    def test_get_editions(self):
        """Tests that get_editions returns a list of editions."""
        editions = self.archidekt.get_editions()

        self.assertIsInstance(editions, list)
        self.assertGreater(len(editions), 0)
        # Check that each edition has expected fields
        for edition in editions:
            self.assertIsInstance(edition, dict)
            self.assertIn("editioncode", edition)
            self.assertIn("editionname", edition)
            self.assertIn("editiondate", edition)
            self.assertIn("editiontype", edition)

    def test_get_subtypes(self):
        """Tests that get_subtypes returns a list of subtypes."""
        subtypes = self.archidekt.get_subtypes()

        self.assertIsInstance(subtypes, list)
        self.assertGreater(len(subtypes), 0)
        # Check that each subtype has expected fields
        for subtype in subtypes:
            self.assertIsInstance(subtype, dict)
            self.assertIn("subtypename", subtype)

    def test_get_folder(self):
        """Tests that get_folder returns folder data."""
        # Get the authenticated user's decks to find a folder
        decks = self.archidekt.get_user_decks()

        # Find a folder ID from one of the user's decks
        folder_id = None
        for deck in decks:
            # The Deck model should have parent_folder_id attribute
            if hasattr(deck, "parent_folder_id") and deck.parent_folder_id:
                folder_id = str(deck.parent_folder_id)
                break

        # If no decks exist or no folders found, skip the test
        if folder_id is None:
            self.skipTest(
                "No folders available for test - user has no decks with folders"
            )

        # Now use the discovered folder ID to get folder data
        folder = self.archidekt.get_folder(folder_id)

        self.assertIsInstance(folder, dict)
        self.assertIn("id", folder)
        self.assertIn("name", folder)
        self.assertEqual(str(folder["id"]), folder_id)

    def test_get_tags(self):
        """Tests that get_tags returns a list of deck tags."""
        tags = self.archidekt.get_tags()

        self.assertIsInstance(tags, list)
        # May be empty if no tags exist, but should return a list
        for tag in tags:
            self.assertIsInstance(tag, dict)
            self.assertIn("id", tag)
            self.assertIn("name", tag)

    def test_get_notification_count(self):
        """Tests that get_notification_count returns notification data."""
        user_id = self.archidekt.auth_handler.user_id
        self.assertIsNotNone(user_id)

        result = self.archidekt.get_notification_count()

        self.assertIsInstance(result, dict)
        self.assertIn("notificationCount", result)
        self.assertIsInstance(result["notificationCount"], int)
        self.assertGreaterEqual(result["notificationCount"], 0)

    def test_delete_folder_items(self):
        """Tests that delete_folder_items removes decks from a folder."""
        # Get the authenticated user's root folder
        # For now, use None to let Archidekt use the default folder
        # The provider.create_deck will use None as the default folder_id
        deck_name = f"pymtg-integration-test-delete-{self._generate_random_string(8)}"
        new_deck = self.archidekt.create_deck(name=deck_name)

        # Verify the deck was created
        self.assertIsNotNone(new_deck)
        self.assertIsNotNone(new_deck.id)
        deck_id = new_deck.id

        # Delete the deck from the folder
        result = self.archidekt.delete_folder_items(
            items=[{"id": int(deck_id), "type": "deck"}]
        )

        # Verify the deletion was successful
        self.assertIsInstance(result, dict)
        # The deck was already deleted by delete_folder_items above, so it is
        # intentionally not tracked in self.created_decks; otherwise tearDown
        # would attempt a spurious double-delete.

    def test_get_comment(self):
        """Tests that get_comment returns comment data.

        This test requires a way to list comments for a deck, but the
        Archidekt provider does not currently implement a
        ``get_deck_comments`` method. Without it there is no reliable way
        to discover a comment ID at runtime, so the test is skipped rather
        than calling a non-existent method. Implementing
        ``get_deck_comments`` on the provider would un-skip this test.
        """
        self.skipTest("get_deck_comments is not implemented on the Archidekt provider")

    @staticmethod
    def _generate_random_string(length: int = 8) -> str:
        """Generate a random string for test names.

        Args:
            length: Length of the random string.

        Returns:
            A random string.
        """
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


if __name__ == "__main__":
    unittest.main()
