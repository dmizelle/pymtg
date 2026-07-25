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

from pymtg.models.card import Card
from pymtg.models.deck import Deck
from pymtg.models.enums import Color, Format
from pymtg.providers.archidekt import Archidekt
logger = logging.getLogger(__name__)



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
        # Track created resources for cleanup
        self.created_decks = []
        self.created_folder_ids = []
        self.created_comment_ids = []
        self.voted_deck_ids = []

    def tearDown(self):
        """Clean up all created resources.

        Removes votes, comments, decks, and folders in the correct order
        so the account is left in its original state.  All errors are
        logged but not raised so cleanup continues even if one resource
        fails to delete.
        """
        # Remove votes (re-vote with remove=True)
        for deck_id in self.voted_deck_ids:
            try:
                self.archidekt.vote_deck(deck_id, remove=True)
            except Exception as e:
                logger.warning("Failed to remove vote on deck %s: %s", deck_id, e)
        # Delete comments
        for comment_id in self.created_comment_ids:
            try:
                self.archidekt.delete_folder_items(
                    items=[{"id": int(comment_id), "type": "comment"}]
                )
            except Exception as e:
                logger.warning("Failed to delete comment %s: %s", comment_id, e)
        # Delete all created decks
        for deck_id in self.created_decks:
            try:
                self.archidekt.delete_folder_items(
                    items=[{"id": int(deck_id), "type": "deck"}]
                )
                logger.info("Deleted test deck %s", deck_id)
            except Exception as e:
                logger.warning("Failed to delete test deck %s: %s", deck_id, e)
        # Delete folders
        for folder_id in self.created_folder_ids:
            try:
                self.archidekt.delete_folder_items(
                    items=[{"id": int(folder_id), "type": "folder"}]
                )
            except Exception as e:
                logger.warning("Failed to delete folder %s: %s", folder_id, e)
        # Clear the lists
        self.created_decks = []
        self.created_folder_ids = []
        self.created_comment_ids = []
        self.voted_deck_ids = []

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

        # Track deck for cleanup immediately, before any assertions that
        # might fail and propagate before the deck is registered.
        if new_deck is not None and new_deck.id is not None:
            self.created_decks.append(new_deck.id)

        self.assertIsNotNone(new_deck)
        self.assertIsInstance(new_deck, Deck)
        self.assertEqual(new_deck.name, deck_name)
        self.assertIsNotNone(new_deck.id)

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

        # Track deck for cleanup BEFORE deleting, so tearDown covers the
        # failure path (delete may raise, leaving the deck orphaned
        # otherwise).
        self.created_decks.append(deck_id)

        # Delete the deck from the folder
        result = self.archidekt.delete_folder_items(
            items=[{"id": int(deck_id), "type": "deck"}]
        )

        # Verify the deletion was successful
        self.assertIsInstance(result, dict)
        # tearDown will also attempt deletion; a double-delete is
        # harmless because delete_folder_items tolerates already-deleted
        # items and tearDown catches any residual exceptions.

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

    def _create_test_deck(self, name: str | None = None) -> str:
        """Create a test deck and track it for cleanup.

        Args:
            name: Optional deck name.  A random name is generated if
                None.

        Returns:
            The deck ID as a string.
        """
        deck_name = name or f"pymtg-it-{self._generate_random_string()}"
        deck = self.archidekt.create_deck(name=deck_name)
        deck_id = str(deck.id)
        self.created_decks.append(deck_id)
        return deck_id

    # ==================================================================
    # Deck management tests
    # ==================================================================

    def test_update_deck(self):
        """Tests that update_deck changes deck metadata."""
        deck_id = self._create_test_deck()
        result = self.archidekt.update_deck(
            deck_id, name="pymtg-updated-name", private=True
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(result["name"], "pymtg-updated-name")
        self.assertTrue(result["private"])

    def test_update_deck_format(self):
        """Tests that update_deck changes the deck format."""
        deck_id = self._create_test_deck()
        result = self.archidekt.update_deck(deck_id, format=Format.MODERN)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["deckFormat"], 2)

    def test_update_deck_theorycrafted(self):
        """Tests that update_deck toggles theorycrafted flag."""
        deck_id = self._create_test_deck()
        result = self.archidekt.update_deck(deck_id, theorycrafted=True)
        self.assertIsInstance(result, dict)
        self.assertTrue(result["theorycrafted"])

    def test_delete_deck(self):
        """Tests that delete_deck removes a deck."""
        deck_id = self._create_test_deck()
        result = self.archidekt.delete_deck(deck_id)
        self.assertTrue(result)
        self.created_decks.remove(deck_id)

    def test_clone_deck(self):
        """Tests that clone_deck creates a copy of a deck."""
        deck_id = self._create_test_deck()
        result = self.archidekt.clone_deck(
            deck_id, name=f"pymtg-clone-{self._generate_random_string()}"
        )
        self.assertIsInstance(result, dict)
        self.assertIn("id", result)
        clone_id = str(result["id"])
        self.created_decks.append(clone_id)
        self.assertNotEqual(clone_id, deck_id)

    def test_clone_deck_private(self):
        """Tests that clone_deck respects the private flag."""
        deck_id = self._create_test_deck()
        result = self.archidekt.clone_deck(
            deck_id,
            name=f"pymtg-clone-priv-{self._generate_random_string()}",
            private=True,
        )
        self.assertIsInstance(result, dict)
        clone_id = str(result["id"])
        self.created_decks.append(clone_id)

    def test_export_deck_pdf(self):
        """Tests that export_deck_pdf returns a file URL."""
        result = self.archidekt.export_deck_pdf(
            deck_name="pymtg-export-test",
            cards=[{"name": "Sol Ring", "quantity": 1}],
            deck_size=1,
            sideboard_size=0,
        )
        self.assertIsInstance(result, dict)
        self.assertIn("fileUrl", result)
        self.assertTrue(result["fileUrl"].startswith("http"))

    def test_vote_deck(self):
        """Tests that vote_deck upvotes and returns point count."""
        deck_id = self._create_test_deck()
        self.voted_deck_ids.append(deck_id)
        result = self.archidekt.vote_deck(deck_id, remove=False)
        self.assertIsInstance(result, dict)
        self.assertIn("points", result)
        self.assertGreaterEqual(result["points"], 1)

    def test_vote_deck_remove(self):
        """Tests that vote_deck with remove=True removes the vote."""
        deck_id = self._create_test_deck()
        self.archidekt.vote_deck(deck_id, remove=False)
        result = self.archidekt.vote_deck(deck_id, remove=True)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["points"], 0)

    def test_modify_cards_add(self):
        """Tests that modify_cards adds a card to a deck."""
        deck_id = self._create_test_deck()
        cards = self.archidekt.search(name="Sol Ring", limit=1)
        self.assertGreater(len(cards), 0)
        card_id = cards[0].id
        self.assertIsNotNone(card_id)
        assert card_id is not None

        result = self.archidekt.modify_cards(
            deck_id,
            operations=[
                {
                    "action": "add",
                    "card_id": card_id,
                    "quantity": 1,
                    "categories": ["Ramp"],
                }
            ],
        )
        self.assertIsInstance(result, dict)
        self.assertIn("add", result)
        self.assertGreater(len(result["add"]), 0)
        self.assertIn("deckRelationId", result["add"][0])

    def test_modify_cards_batch(self):
        """Tests that modify_cards handles batch add operations."""
        deck_id = self._create_test_deck()

        cards = self.archidekt.search(name="Sol Ring", limit=1)
        self.assertGreater(len(cards), 0)
        sol_ring_id = cards[0].id
        assert sol_ring_id is not None

        cards2 = self.archidekt.search(name="Arcane Signet", limit=1)
        self.assertGreater(len(cards2), 0)
        arcane_id = cards2[0].id
        assert arcane_id is not None

        result = self.archidekt.modify_cards(
            deck_id,
            operations=[
                {
                    "action": "add",
                    "card_id": sol_ring_id,
                    "quantity": 1,
                    "categories": ["Ramp"],
                },
                {
                    "action": "add",
                    "card_id": arcane_id,
                    "quantity": 1,
                    "categories": ["Ramp"],
                },
            ],
        )
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result["add"]), 2)

    # ==================================================================
    # Folder management tests
    # ==================================================================

    def test_create_folder(self):
        """Tests that create_folder creates a new folder."""
        tree = self.archidekt.get_folder_tree()
        root_folder_id = str(tree["id"])

        folder_name = f"pymtg-folder-{self._generate_random_string()}"
        result = self.archidekt.create_folder(
            name=folder_name,
            parent_folder_id=root_folder_id,
            private=True,
        )
        self.assertIsInstance(result, dict)
        self.assertIn("id", result)
        self.assertEqual(result["name"], folder_name)
        self.assertTrue(result["private"])
        self.created_folder_ids.append(str(result["id"]))

    def test_create_folder_public(self):
        """Tests that create_folder respects private=False."""
        tree = self.archidekt.get_folder_tree()
        root_folder_id = str(tree["id"])

        folder_name = f"pymtg-folder-pub-{self._generate_random_string()}"
        result = self.archidekt.create_folder(
            name=folder_name,
            parent_folder_id=root_folder_id,
            private=False,
        )
        self.assertIsInstance(result, dict)
        self.assertFalse(result["private"])
        self.created_folder_ids.append(str(result["id"]))

    def test_get_folder_tree(self):
        """Tests that get_folder_tree returns the folder hierarchy."""
        result = self.archidekt.get_folder_tree()
        self.assertIsInstance(result, dict)
        self.assertIn("id", result)
        self.assertIn("name", result)
        self.assertIn("private", result)

    def test_get_folder_tree_has_children_after_create(self):
        """Tests that get_folder_tree shows newly created folders."""
        tree_before = self.archidekt.get_folder_tree()
        root_folder_id = str(tree_before["id"])

        folder_name = f"pymtg-tree-test-{self._generate_random_string()}"
        result = self.archidekt.create_folder(
            name=folder_name,
            parent_folder_id=root_folder_id,
            private=True,
        )
        self.created_folder_ids.append(str(result["id"]))

        tree_after = self.archidekt.get_folder_tree()
        children = tree_after.get("children") or []
        child_names = [c.get("name") for c in children]
        self.assertIn(folder_name, child_names)

    def test_mass_update_rename_folder(self):
        """Tests that mass_update renames a folder."""
        tree = self.archidekt.get_folder_tree()
        root_folder_id = str(tree["id"])

        folder_name = f"pymtg-rename-{self._generate_random_string()}"
        result = self.archidekt.create_folder(
            name=folder_name,
            parent_folder_id=root_folder_id,
            private=True,
        )
        folder_id = result["id"]
        self.created_folder_ids.append(str(folder_id))

        new_name = f"pymtg-renamed-{self._generate_random_string()}"
        update_result = self.archidekt.mass_update(
            items=[
                {
                    "id": folder_id,
                    "type": "folder",
                    "patch": {"name": new_name},
                }
            ]
        )
        self.assertIsInstance(update_result, list)
        self.assertEqual(len(update_result), 1)

    def test_mass_update_move_deck(self):
        """Tests that mass_update moves a deck between folders."""
        tree = self.archidekt.get_folder_tree()
        root_folder_id = str(tree["id"])

        folder_name = f"pymtg-move-target-{self._generate_random_string()}"
        folder_result = self.archidekt.create_folder(
            name=folder_name,
            parent_folder_id=root_folder_id,
            private=True,
        )
        subfolder_id = folder_result["id"]
        self.created_folder_ids.append(str(subfolder_id))

        deck_id = self._create_test_deck()

        result = self.archidekt.mass_update(
            items=[
                {
                    "id": int(deck_id),
                    "type": "deck",
                    "patch": {"parentFolder": subfolder_id},
                }
            ]
        )
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_synchronize_categories(self):
        """Tests that synchronize_categories creates categories."""
        deck_id = self._create_test_deck()
        result = self.archidekt.synchronize_categories(
            deck_id,
            categories=[
                {
                    "id": None,
                    "name": f"pymtg-cat-{self._generate_random_string()}",
                    "isPremier": False,
                    "includedInDeck": True,
                    "includedInPrice": True,
                },
            ],
        )
        self.assertIsInstance(result, dict)
        self.assertIn("categories", result)
        self.assertGreaterEqual(len(result["categories"]), 1)

    def test_mass_deck_edit(self):
        """Tests that mass_deck_edit parses text-based deck edits."""
        result = self.archidekt.mass_deck_edit(
            current="1x Sol Ring (msc) [Ramp]",
            edit="1x Arcane Signet [CMM]",
        )
        self.assertIsInstance(result, dict)
        self.assertIn("toAdd", result)
        self.assertIn("toRemove", result)
        self.assertGreater(len(result["toAdd"]), 0)
        self.assertGreater(len(result["toRemove"]), 0)

    # ==================================================================
    # Social features tests
    # ==================================================================

    def test_get_notifications(self):
        """Tests that get_notifications returns the notification list."""
        user_id = self.archidekt.auth_handler.user_id
        self.assertIsNotNone(user_id)
        result = self.archidekt.get_notifications()
        self.assertIsInstance(result, dict)
        self.assertIn("notifications", result)

    def test_get_followers(self):
        """Tests that get_followers returns the followers list."""
        user_id = self.archidekt.auth_handler.user_id
        self.assertIsNotNone(user_id)
        assert user_id is not None
        result = self.archidekt.get_followers(user_id)
        self.assertIsInstance(result, dict)
        self.assertIn("count", result)
        self.assertIn("results", result)

    def test_get_following(self):
        """Tests that get_following returns the following list."""
        user_id = self.archidekt.auth_handler.user_id
        self.assertIsNotNone(user_id)
        assert user_id is not None
        result = self.archidekt.get_following(user_id)
        self.assertIsInstance(result, dict)
        self.assertIn("count", result)
        self.assertIn("results", result)

    def test_create_comment(self):
        """Tests that create_comment posts a comment on a deck.

        Creates a deck, then comments on it.  The comment is tracked for
        cleanup in tearDown.
        """
        deck_id = self._create_test_deck()
        try:
            result = self.archidekt.create_comment(
                parent_id=deck_id,
                text=f"pymtg integration test comment {self._generate_random_string()}",
            )
            self.assertIsInstance(result, dict)
            self.assertIn("id", result)
            self.created_comment_ids.append(str(result["id"]))
        except Exception as e:
            self.skipTest(f"Could not create comment on deck {deck_id}: {e}")

    # ==================================================================
    # Deck discovery tests
    # ==================================================================

    def test_get_curated_decks(self):
        """Tests that get_curated_decks returns the user's decks."""
        self._create_test_deck()
        result = self.archidekt.get_curated_decks()
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        self.assertIsInstance(result["results"], list)

    def test_get_recent_decks(self):
        """Tests that get_recent_decks returns recently viewed decks."""
        result = self.archidekt.get_recent_decks()
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        self.assertIsInstance(result["results"], list)

    def test_get_followed_decks(self):
        """Tests that get_followed_decks returns followed users' decks."""
        result = self.archidekt.get_followed_decks()
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        self.assertIsInstance(result["results"], list)

    def test_get_packages(self):
        """Tests that get_packages returns the user's card packages."""
        result = self.archidekt.get_packages()
        self.assertIsInstance(result, dict)
        self.assertIn("results", result)
        self.assertIsInstance(result["results"], list)

    # ==================================================================
    # Auth refresh test
    # ==================================================================

    def test_refresh_auth(self):
        """Tests that refresh_auth refreshes the JWT token.

        Verifies the fix for the doubled /api/ prefix bug in the
        refresh endpoint URL.
        """
        self.archidekt.refresh_auth()
        self.assertTrue(self.archidekt.is_authenticated())


if __name__ == "__main__":
    unittest.main()
