"""Card and card-related models for Magic: The Gathering.

This module provides the main Card model and related models (CardFace, DeckCard)
for representing Magic: The Gathering cards in a normalized format across all
providers.
"""

from typing import Any, ClassVar

from pymtg.models.base import PyMTGBaseModel
from pymtg.models.enums import Color, Format, Rarity
from pymtg.models.pricing import Pricing


class CardFace(PyMTGBaseModel):
    """Represents a single face of a Magic: The Gathering card.

    Some cards (like transform, modal dual-faced, or flip cards) have multiple
    faces. Each face is represented by a CardFace object.

    Attributes:
        name: Name of the face.
        mana_cost: Mana cost of the face.
        type_line: Type line of the face.
        oracle_text: Oracle rules text of the face.
        power: Power of the face (as string to handle non-numeric values).
        toughness: Toughness of the face (as string to handle non-numeric values).
        colors: Colors in the mana cost of this face.
        color_indicator: Colors in the color indicator of this face.
        loyalty: Loyalty value (for planeswalkers).
        defense: Defense value (for battles).
        flavor_text: Flavor text of the face.
        artist: Artist name.
        artist_id: Scryfall artist ID.
        illustration_id: Scryfall illustration ID.
        image_uris: Dictionary of image URIs for this face.
    """

    name: str
    mana_cost: str | None = None
    type_line: str | None = None
    oracle_text: str | None = None
    power: str | None = None
    toughness: str | None = None
    colors: list[Color] | None = None
    color_indicator: list[Color] | None = None
    loyalty: str | None = None
    defense: str | None = None
    flavor_text: str | None = None
    artist: str | None = None
    artist_id: str | None = None
    illustration_id: str | None = None
    image_uris: dict[str, str] | None = None


class Legality(PyMTGBaseModel):
    """Represents the legality of a card in a format.

    Attributes:
        format: The format name.
        status: The legality status (legal, not_legal, restricted, banned).
    """

    format: Format
    status: str


class Card(PyMTGBaseModel):
    """Normalized Magic: The Gathering card model.

    This model represents a Magic: The Gathering card in a normalized format
    that is consistent across all supported providers. It includes all the
    essential fields needed for Card Lookup, Deck Aggregator, and Universal
    Search functionality.

    Attributes:
        id: Provider-specific card ID.
        scryfall_id: Canonical Scryfall UUID (None if not available from provider).
        oracle_id: Oracle ID for the card text (same across printings).
        name: Card name.
        printed_name: The name as printed on the card.
        mana_cost: Raw mana cost string.
        cmc: Converted mana cost (float to handle fractional costs).
        type_line: Full type line string.
        printed_type_line: The type line as printed on the card.
        oracle_text: Oracle rules text.
        printed_text: The rules text as printed on the card.
        flavors: List of flavor text strings.
        colors: List of colors in mana cost.
        color_identity: List of colors in color identity.
        color_indicator: List of colors in color indicator.
        keywords: List of keyword abilities.
        all_parts: List of IDs for cards in the same cycle/part.
        card_faces: List of CardFace objects for multi-faced cards.
        set_code: Set code (e.g., "LEA", "M20").
        set_name: Full set name.
        set_type: Set type (e.g., "core", "expansion").
        rarity: Card rarity.
        collector_number: Collector number.
        power: Power (string to handle non-numeric values like "*").
        toughness: Toughness (string).
        loyalty: Loyalty (string for planeswalkers).
        defense: Defense (string for battles).
        layout: Card layout (normal, split, transform, etc.).
        image_uris: Dictionary of image URIs.
        image_status: Status of image availability.
        pricing: Pricing information (nullable, eager-loaded).
        legalities: Dictionary of format legalities.
        released_at: Date the card was released.
        reserved: Whether the card is on the Reserved List.
        foil: Whether the card is foil.
        nonfoil: Whether the card is non-foil.
        oversized: Whether the card is oversized.
        promo: Whether the card is a promo.
        reprint: Whether the card is a reprint.
        variation: Whether the card is a variation.
        multiverse_ids: List of Multiverse IDs for the card.
        tcgplayer_id: TCGPlayer product ID.
        cardmarket_id: Cardmarket ID.
        prints_search_uri: URI to search for all prints of this card.
        rulings_uri: URI to the card's rulings on Scryfall.
        scryfall_uri: URI to the card on Scryfall.
        uri: URI to the card on the provider's site.
        source: Provider name that provided this card data.
    """

    _SHARED_FACE_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "mana_cost",
        "type_line",
        "oracle_text",
        "power",
        "toughness",
        "colors",
        "color_indicator",
        "loyalty",
        "defense",
        "artist",
        "artist_id",
        "illustration_id",
        "image_uris",
    )

    id: str
    scryfall_id: str | None = None
    oracle_id: str | None = None
    name: str
    printed_name: str | None = None
    mana_cost: str | None = None
    cmc: float | None = None
    type_line: str | None = None
    printed_type_line: str | None = None
    oracle_text: str | None = None
    printed_text: str | None = None
    flavors: list[str] | None = None
    colors: list[Color] | None = None
    color_identity: list[Color] | None = None
    color_indicator: list[Color] | None = None
    keywords: list[str] | None = None
    all_parts: list[str] | None = None
    card_faces: list[CardFace] | None = None
    set_code: str | None = None
    set_name: str | None = None
    set_type: str | None = None
    rarity: Rarity | None = None
    collector_number: str | None = None
    power: str | None = None
    toughness: str | None = None
    loyalty: str | None = None
    defense: str | None = None
    layout: str | None = None
    image_uris: dict[str, str] | None = None
    image_status: str | None = None
    artist: str | None = None
    artist_id: str | None = None
    illustration_id: str | None = None
    pricing: Pricing | None = None
    legalities: dict[str, str] | None = None
    released_at: str | None = None
    reserved: bool | None = None
    foil: bool | None = None
    nonfoil: bool | None = None
    oversized: bool | None = None
    promo: bool | None = None
    reprint: bool | None = None
    variation: bool | None = None
    multiverse_ids: list[int] | None = None
    tcgplayer_id: int | None = None
    cardmarket_id: int | None = None
    prints_search_uri: str | None = None
    rulings_uri: str | None = None
    scryfall_uri: str | None = None
    uri: str | None = None
    source: str | None = None

    def is_white(self) -> bool:
        """Check if this card is white.

        Returns:
            True if the card's color identity contains white.
        """
        return Color.WHITE in (self.color_identity or [])

    def is_blue(self) -> bool:
        """Check if this card is blue.

        Returns:
            True if the card's color identity contains blue.
        """
        return Color.BLUE in (self.color_identity or [])

    def is_black(self) -> bool:
        """Check if this card is black.

        Returns:
            True if the card's color identity contains black.
        """
        return Color.BLACK in (self.color_identity or [])

    def is_red(self) -> bool:
        """Check if this card is red.

        Returns:
            True if the card's color identity contains red.
        """
        return Color.RED in (self.color_identity or [])

    def is_green(self) -> bool:
        """Check if this card is green.

        Returns:
            True if the card's color identity contains green.
        """
        return Color.GREEN in (self.color_identity or [])

    def is_colorless(self) -> bool:
        """Check if this card is colorless.

        Returns:
            True if the card has no color identity.
        """
        return self.color_identity is None or len(self.color_identity) == 0

    def is_multicolor(self) -> bool:
        """Check if this card is multicolor.

        Returns:
            True if the card has multiple colors in its identity.
        """
        return self.color_identity is not None and len(self.color_identity) > 1

    def get_color_identity_string(self) -> str:
        """Get the color identity as a string.

        Colors are sorted in WUBRG order (White, Blue, Black, Red, Green) to match
        Magic: The Gathering conventions for mana costs and color identities.

        Returns:
            A string representation of the color identity (e.g., "WUBRG").
        """
        if self.color_identity is None:
            return ""
        # WUBRG order for sorting
        color_order = {"W": 0, "U": 1, "B": 2, "R": 3, "G": 4}
        # Handle both Color enums and strings (due to use_enum_values=True)
        values = [c.value if isinstance(c, Color) else c for c in self.color_identity]
        return "".join(sorted(values, key=lambda x: color_order.get(x, 5)))

    def get_mana_value(self) -> float:
        """Get the mana value (converted mana cost) of the card.

        Returns:
            The converted mana cost as a float, or 0.0 if not available.
        """
        return self.cmc or 0.0

    def is_creature(self) -> bool:
        """Check if this card is a creature.

        Returns:
            True if the card's type line contains "Creature".
        """
        return self.type_line is not None and "Creature" in self.type_line

    def is_instant(self) -> bool:
        """Check if this card is an instant.

        Returns:
            True if the card's type line contains "Instant".
        """
        return self.type_line is not None and "Instant" in self.type_line

    def is_sorcery(self) -> bool:
        """Check if this card is a sorcery.

        Returns:
            True if the card's type line contains "Sorcery".
        """
        return self.type_line is not None and "Sorcery" in self.type_line

    def is_artifact(self) -> bool:
        """Check if this card is an artifact.

        Returns:
            True if the card's type line contains "Artifact".
        """
        return self.type_line is not None and "Artifact" in self.type_line

    def is_enchantment(self) -> bool:
        """Check if this card is an enchantment.

        Returns:
            True if the card's type line contains "Enchantment".
        """
        return self.type_line is not None and "Enchantment" in self.type_line

    def is_land(self) -> bool:
        """Check if this card is a land.

        Returns:
            True if the card's type line contains "Land".
        """
        return self.type_line is not None and "Land" in self.type_line

    def is_planeswalker(self) -> bool:
        """Check if this card is a planeswalker.

        Returns:
            True if the card's type line contains "Planeswalker".
        """
        return self.type_line is not None and "Planeswalker" in self.type_line

    def is_battle(self) -> bool:
        """Check if this card is a battle.

        Returns:
            True if the card's type line contains "Battle".
        """
        return self.type_line is not None and "Battle" in self.type_line

    def get_main_face(self) -> CardFace | None:
        """Get the main face of the card.

        Returns:
            The first CardFace if card_faces is not None and not empty, else None.
        """
        if self.card_faces and len(self.card_faces) > 0:
            return self.card_faces[0]
        return None

    def validate_main_face_consistency(self) -> dict[str, tuple[Any, Any]]:
        """Validates that top-level Card fields match the main face's fields.

        For multi-faced cards (transform, modal dual-faced, etc.), the
        top-level Card fields should match the corresponding fields on the
        main face (card_faces[0]). This method checks all fields shared
        between Card and CardFace for consistency.

        Returns:
            A dict mapping mismatched field names to tuples of
            (card_value, face_value). Returns an empty dict if all shared
            fields are consistent or if the card has no faces.
        """
        main_face = self.get_main_face()
        if main_face is None:
            return {}

        mismatches: dict[str, tuple[Any, Any]] = {}
        for field in self._SHARED_FACE_FIELDS:
            card_value = getattr(self, field, None)
            face_value = getattr(main_face, field, None)
            if card_value != face_value:
                mismatches[field] = (card_value, face_value)
        return mismatches


class DeckCard(PyMTGBaseModel):
    """Represents a card in a deck with count and board information.

    This model represents a card within a deck, including how many copies
    are in the deck and which board (main, sideboard, commander, etc.) it belongs to.

    Attributes:
        card: The Card object.
        count: Number of copies of this card in the deck.
        board: The board this card belongs to.
    """

    card: Card
    count: int
    board: str | None = None
