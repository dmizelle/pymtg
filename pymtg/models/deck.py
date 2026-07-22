"""Deck model for Magic: The Gathering decks.

This module provides the Deck model for representing Magic: The Gathering
decks in a normalized format across all providers.
"""

from pymtg.models.base import PyMTGBaseModel
from pymtg.models.card import DeckCard
from pymtg.models.enums import Board, Format


class Deck(PyMTGBaseModel):
    """Normalized Magic: The Gathering deck model.

    This model represents a Magic: The Gathering deck in a normalized format
    that is consistent across all supported providers. It includes all the
    essential fields for representing decks from Archidekt, Moxfield, and
    potentially other deckbuilding providers.

    Attributes:
        id: Provider-specific deck ID.
        name: Deck name.
        description: Deck description.
        format: Deck format.
        commander: List of commander card IDs.
        cards: List of DeckCard objects representing all cards in the deck,
            including main, sideboard, commander, and maybe board cards. Each
            card's board attribute indicates which board it belongs to.
        sideboard: Legacy field for sideboard cards. The get_sideboard_cards()
            method filters from cards by board attribute instead.
        maybe_board: Legacy field for maybe board cards. The
            get_maybeboard_cards() method filters from cards by board
            attribute instead.
        source: Provider name that provided this deck data.
        source_id: Provider-specific ID.
        url: URL to the deck on the provider's site.
        created_at: When the deck was created.
        updated_at: When the deck was last updated.
        views: Number of times the deck has been viewed.
        upvotes: Number of upvotes.
        downvotes: Number of downvotes.
        tags: List of tags for the deck.
        categories: List of categories for the deck.
        privacy: Privacy setting (public, private, unlisted).
        owner: Owner username or ID.
        owner_id: Owner's provider-specific ID.
        collapsed: Whether the deck is collapsed/folded.
        parent_folder_id: The ID of the parent folder containing this deck.
    """

    id: str
    name: str
    description: str | None = None
    format: Format | None = None
    commander: list[str] | None = None
    cards: list[DeckCard] | None = None
    sideboard: list[DeckCard] | None = None
    maybe_board: list[DeckCard] | None = None
    source: str | None = None
    source_id: str | None = None
    url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    views: int | None = None
    upvotes: int | None = None
    downvotes: int | None = None
    tags: list[str] | None = None
    categories: list[str] | None = None
    privacy: str | None = None
    owner: str | None = None
    owner_id: str | None = None
    collapsed: bool | None = None
    parent_folder_id: str | None = None

    def get_main_deck_cards(self) -> list[DeckCard]:
        """Get all cards in the main deck.

        Positively selects cards whose board is ``None`` (legacy/default
        placement) or ``Board.MAIN`` so that sideboard, commander-zone,
        and maybeboard cards are excluded. This keeps the main-deck
        accessor consistent with the dedicated ``get_sideboard_cards()``,
        ``get_commander_cards()``, and ``get_maybeboard_cards()``
        accessors.

        Returns:
            List of DeckCard objects in the main deck.
        """
        if self.cards is None:
            return []
        return [
            card
            for card in self.cards
            if card.board is None or card.board == Board.MAIN.value
        ]

    def get_sideboard_cards(self) -> list[DeckCard]:
        """Get all cards in the sideboard.

        Returns:
            List of DeckCard objects in the sideboard.
        """
        if self.cards is None:
            return []
        return [card for card in self.cards if card.board == Board.SIDEBOARD.value]

    def get_maybeboard_cards(self) -> list[DeckCard]:
        """Get all cards in the maybe board.

        Returns:
            List of DeckCard objects in the maybe board.
        """
        if self.cards is None:
            return []
        return [card for card in self.cards if card.board == Board.MAYBEBOARD.value]

    def get_commander_cards(self) -> list[DeckCard]:
        """Get all cards in the commander zone.

        Returns:
            List of DeckCard objects in the commander zone.
        """
        if self.cards is None:
            return []
        return [card for card in self.cards if card.board == Board.COMMANDER.value]

    def get_total_cards(self) -> int:
        """Get the total number of cards in the main deck.

        Only main-deck cards are counted; sideboard, commander-zone,
        and maybeboard cards are excluded (use the dedicated accessors
        to total those zones separately).

        Returns:
            Total count of cards in the main deck.
        """
        if self.cards is None:
            return 0
        return sum(card.count for card in self.get_main_deck_cards())

    def get_card_count(self, card_name: str) -> int:
        """Get the number of copies of a specific card in the deck.

        Args:
            card_name: The name of the card to count.

        Returns:
            The total number of copies of the card in the deck.
        """
        count = 0
        for card in self.get_main_deck_cards():
            if card.card.name.lower() == card_name.lower():
                count += card.count
        for card in self.get_sideboard_cards():
            if card.card.name.lower() == card_name.lower():
                count += card.count
        for card in self.get_maybeboard_cards():
            if card.card.name.lower() == card_name.lower():
                count += card.count
        return count

    def get_unique_cards(self) -> list[DeckCard]:
        """Get the list of unique cards in the deck.

        Uses case-insensitive matching for consistency with get_card_count.

        Returns:
            List of DeckCard objects with unique card names.
        """
        seen: dict[str, DeckCard] = {}
        for card in self.get_main_deck_cards():
            key = card.card.name.lower()
            if key not in seen:
                seen[key] = card
        for card in self.get_sideboard_cards():
            key = card.card.name.lower()
            if key not in seen:
                seen[key] = card
        for card in self.get_maybeboard_cards():
            key = card.card.name.lower()
            if key not in seen:
                seen[key] = card
        return list(seen.values())

    def is_valid_for_format(self) -> bool:
        """Check if the deck is valid for its declared format.

        Performs basic validation: checks that the deck has cards and the
        format is a valid Format enum value. Full format-specific validation
        (e.g., card legality, deck size limits) would require additional
        format-specific rules and is not yet implemented.

        With ``use_enum_values=True`` in the model config, ``self.format``
        is already a validated ``Format`` value after normal Pydantic
        construction, so no runtime re-check of the enum membership is
        performed here. Decks built via ``model_construct()`` or another
        validation-bypassing path may carry an unvalidated format string.

        Returns:
            True if the deck has cards and format is valid, False otherwise.
        """
        # Basic validation: deck must have at least one card.
        if self.cards is None or len(self.cards) == 0:
            return False

        return True
