"""Unit tests for new Archidekt provider methods.

This module tests the fixed and new Archidekt methods including deck
management, folder operations, social features, and deck discovery.
"""

import functools
import json
import unittest
from unittest.mock import MagicMock, patch

import requests

from pymtg.auth.jwt import JWTAuthHandler
from pymtg.exceptions import NetworkError, NotFoundError
from pymtg.models.deck import Deck
from pymtg.models.enums import Format
from pymtg.providers.archidekt import Archidekt
from pymtg.providers.archidekt.exceptions import (
    ArchidektAuthenticationError,
    ArchidektValidationError,
)


def mock_authenticated_and_http_client(func):
    """Decorator mocking JWTAuthHandler.is_authenticated and http_client.

    Reduces duplication for tests needing both mocks. The decorated test
    receives ``mock_http_client`` as a keyword argument; because it is
    passed by keyword, ``mock_http_client`` must be the LAST parameter in
    the wrapped test's signature (after any mocks injected by outer
    ``@patch.object`` decorators, which arrive positionally).

    Returns:
        The wrapped test function with both mocks applied.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        patcher1 = patch.object(JWTAuthHandler, "is_authenticated", return_value=True)
        patcher2 = patch.object(Archidekt, "http_client")
        with patcher1, patcher2 as mock_http_client:
            return func(*args, mock_http_client=mock_http_client, **kwargs)

    return wrapper


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
